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

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.middleware import PrivateNetworkAccessMiddleware

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
    return {"status": "ok"}
