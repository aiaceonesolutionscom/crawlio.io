import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# Playwright needs asyncio.create_subprocess_exec to launch Chromium, which only
# works under Windows' ProactorEventLoop. Plain `python -m uvicorn` already
# defaults there, but uvicorn's --reload supervisor on Windows can leave the
# worker on SelectorEventLoop instead, silently breaking every browser-based
# scrape (discovery/enrichment) with NotImplementedError. Force it explicitly
# so this holds regardless of how the server is launched.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Surface INFO logs (source counts, lookups, skips) in the API process — the
# root logger's default WARNING hides the discovery diagnostics entirely.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.middleware import PrivateNetworkAccessMiddleware


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Load any admin-set API-key overrides (system_settings.integration.*) into
    # the in-process runtime cache so services pick them up at boot.
    from app.services.admin import integration_service

    await integration_service.hydrate_runtime_from_db()
    yield


app = FastAPI(title="Crawlio API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://triconrepublic.com",
        "http://triconrepublic.com",
    ],
    allow_origin_regex=r"https?://.*\.?triconrepublic\.com",
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
    return {"status": "ok"}
