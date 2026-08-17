import json
import logging
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_CORS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://crawlio:crawlio@localhost:5432/crawlio"

    cors_origins: str = ""

    def model_post_init(self, __context) -> None:
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        raw = self.cors_origins.strip() if self.cors_origins else ""
        if not raw:
            self.cors_origins = list(_DEFAULT_CORS)
        else:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    self.cors_origins = [str(x) for x in parsed]
                elif isinstance(parsed, str):
                    self.cors_origins = [parsed]
                else:
                    self.cors_origins = list(_DEFAULT_CORS)
            except (json.JSONDecodeError, ValueError):
                self.cors_origins = [u.strip() for u in raw.split(",") if u.strip()]
        logger.info("CORS origins: %s", self.cors_origins)

        raw_emails = self.super_admin_emails.strip() if self.super_admin_emails else ""
        if raw_emails:
            try:
                parsed_emails = json.loads(raw_emails)
                if isinstance(parsed_emails, list):
                    self.super_admin_emails = [str(e) for e in parsed_emails]
                else:
                    self.super_admin_emails = [raw_emails]
            except (json.JSONDecodeError, ValueError):
                self.super_admin_emails = [e.strip() for e in raw_emails.split(",") if e.strip()]
        else:
            self.super_admin_emails = []

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    super_admin_emails: str = ""
    brevo_api_key: str = ""
    brevo_sender_email: str = "onboarding@crawlio.io"
    brevo_sender_name: str = "Crawlio"
    mistral_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    google_maps_max_results: int = 50
    google_maps_headless: bool = True
    google_maps_delay_seconds: float = 1.5
    google_maps_search_limit: int = 50
    proxy_url: str = ""
    directory_enabled: bool = True
    geoapify_api_key: str = ""
    geoapify_enabled: bool = True
    validate_emails: bool = False

    tavily_api_key: str = ""
    tavily_enabled: bool = True
    tavily_max_results: int = 40

    discovery_cache_ttl_hours: int = 24
    discovery_prewarm_enabled: bool = False
    discovery_prewarm_interval_minutes: int = 10
    discovery_prewarm_batch_size: int = 2

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/email-accounts/oauth/google/callback"

    email_token_encryption_key: str = ""
    pro_daily_email_limit: int = 100
    enterprise_daily_email_limit: int = 500

    meta_app_id: str = ""
    meta_app_secret: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_graph_version: str = "v21.0"
    whatsapp_webhook_url: str = ""
    whatsapp_test_phone_number_id: str = ""
    whatsapp_test_access_token: str = ""
    pro_daily_whatsapp_limit: int = 200
    enterprise_daily_whatsapp_limit: int = 1000


settings = Settings()
