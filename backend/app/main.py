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
