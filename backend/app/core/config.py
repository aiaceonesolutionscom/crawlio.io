from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://crawlio:crawlio@localhost:5432/crawlio"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    super_admin_emails: list[str] = []
    brevo_api_key: str = ""
    brevo_sender_email: str = "onboarding@crawlio.io"
    brevo_sender_name: str = "Crawlio"
    mistral_api_key: str = ""
    tavily_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/email-accounts/oauth/google/callback"

    email_token_encryption_key: str = ""
    pro_daily_email_limit: int = 100
    enterprise_daily_email_limit: int = 500


settings = Settings()
