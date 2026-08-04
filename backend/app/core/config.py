from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://crawlio:crawlio@localhost:5432/crawlio"
    cors_origins: list[str] = ["http://localhost:5173"]

    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    resend_api_key: str = ""
    mistral_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
