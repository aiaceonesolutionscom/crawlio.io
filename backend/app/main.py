import asyncio
import sys

# Playwright needs asyncio.create_subprocess_exec to launch Chromium, which only
# works under Windows' ProactorEventLoop. Plain `python -m uvicorn` already
# defaults there, but uvicorn's --reload supervisor on Windows can leave the
# worker on SelectorEventLoop instead, silently breaking every browser-based
# scrape (discovery/enrichment) with NotImplementedError. Force it explicitly
# so this holds regardless of how the server is launched.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.middleware import PrivateNetworkAccessMiddleware
from app.db.session import engine
from app.services.crawlers.base import source_tracker

app = FastAPI(title="Crawlio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Must wrap CORSMiddleware (added after it) so it sees the preflight response
# CORSMiddleware already built, and just adds the one extra header Chrome's
# Private Network Access check needs on top of it.
app.add_middleware(PrivateNetworkAccessMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Liveness + deep health: DB reachable, per-source reliability stats, and
    which crawler circuit breakers are currently open (blocked sources)."""
    # DB reachability — a cheap round-trip; failure means the API is up but
    # every data path is broken, which /health should report, not paper over.
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    breakers = {
        "google_maps": maps_breaker_open(),
        "bing_maps": bing_breaker_open(),
        "bizdata": bizdata_breaker_open(),
        "directory": directory_breaker_open(),
    }

    sources = source_tracker.all_stats()
    unhealthy = source_tracker.unhealthy(min_rate=0.3, min_samples=5)

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "database": "ok" if db_ok else "unreachable",
        "circuit_breakers": breakers,
        "sources": sources,
        "unhealthy_sources": unhealthy,
    }


def maps_breaker_open() -> bool:
    from app.services.crawlers import maps_crawler

    return maps_crawler._breaker.open


def bing_breaker_open() -> bool:
    from app.services.crawlers import bing_maps_crawler

    return bing_maps_crawler._breaker.open


def bizdata_breaker_open() -> bool:
    from app.services.crawlers import bizdata_crawler

    return bizdata_crawler._breaker.open


def directory_breaker_open() -> bool:
    from app.services.crawlers import directory_scraper

    return directory_scraper._breaker.open
