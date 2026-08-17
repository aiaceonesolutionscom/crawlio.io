import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://crawlio:crawlio@localhost:5432/crawlio"

    def model_post_init(self, __context) -> None:
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            return [v]
        return ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    super_admin_emails: list[str] = []
    brevo_api_key: str = ""
    brevo_sender_email: str = "onboarding@crawlio.io"
    brevo_sender_name: str = "Crawlio"
    mistral_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # Lead crawler (Google Maps + directories) — free, open-source discovery sources.
    google_maps_max_results: int = 50
    google_maps_headless: bool = True
    google_maps_delay_seconds: float = 1.5
    # Max place-detail pages visited per search — a safety ceiling below
    # google_maps_max_results since each visit is a real navigation Google can
    # fingerprint. Higher = closer to the requested lead count, at the cost of
    # more requests per search; for volume beyond this, use proxy_url rather
    # than raising it unbounded.
    google_maps_search_limit: int = 50
    # Optional proxy for the crawlers (anti-bot), e.g. "http://user:pass@host:port".
    proxy_url: str = ""
    directory_enabled: bool = True
    # Geoapify Places — free OSM-based POI search (3k requests/day, no billing
    # card). Additive; skipped entirely when geoapify_api_key is empty.
    geoapify_api_key: str = ""
    geoapify_enabled: bool = True
    # Email validation (MX lookup) — OFF by default so out-of-the-box discovery
    # is fast and has no DNS dependency (lookups add latency on large batches and
    # can fail in restricted networks). Enable for stricter deliverability checks.
    validate_emails: bool = False

    # Optional, opt-in last-resort top-up when Google Maps + OSM + directories
    # come up short (e.g. thinner markets outside major cities). Off by default:
    # contributes name + website candidates only, never guessed contact info —
    # see web_search_service.py for why that's safe.
    tavily_api_key: str = ""
    tavily_enabled: bool = True
    tavily_max_results: int = 40

    # Shared, global cache of validated discovery results per niche+city+country
    # (not workspace-scoped) — repeat searches across every workspace reuse the
    # same scrape instead of re-hitting Google Maps/OSM/directories each time.
    discovery_cache_ttl_hours: int = 24
    # Demand-driven background pre-warm crawler (Celery beat) — refreshes cache
    # rows before they expire, spread gently across the day. Off by default:
    # it needs Redis + a running worker + beat process, which isn't guaranteed
    # in every environment; enable once that infra is actually up.
    discovery_prewarm_enabled: bool = False
    discovery_prewarm_interval_minutes: int = 10
    discovery_prewarm_batch_size: int = 2

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/email-accounts/oauth/google/callback"

    email_token_encryption_key: str = ""
    pro_daily_email_limit: int = 100
    enterprise_daily_email_limit: int = 500

    # WhatsApp Business Platform (Meta Cloud API). Platform-level shared config:
    # one Meta App backs every workspace; each workspace connects its own WABA +
    # phone number via Embedded Signup or manual System User credentials.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_graph_version: str = "v21.0"
    whatsapp_webhook_url: str = ""
    # Dev-only test number credentials (Meta API Setup tab; temporary 24h token).
    whatsapp_test_phone_number_id: str = ""
    whatsapp_test_access_token: str = ""
    pro_daily_whatsapp_limit: int = 200
    enterprise_daily_whatsapp_limit: int = 1000


settings = Settings()
