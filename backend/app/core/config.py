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
    google_maps_search_limit: int = 20
    # Optional proxy for the crawlers (anti-bot), e.g. "http://user:pass@host:port".
    proxy_url: str = ""
    # Rotating residential proxy pool (anti-bot for Google Maps). Comma-separated
    # proxy URLs — used only by sources that need residential IPs (Google Maps).
    # Leave empty to run fully free on direct connections.
    residential_proxy_list: list[str] = []
    # Optional secondary proxy list for non-Maps HTTP crawlers (directories,
    # Bing). Empty = direct connection.
    http_proxy_list: list[str] = []
    # Per-source proxy cooldown (seconds) after a block/429 before a proxy is
    # tried again.
    proxy_cooldown_seconds: int = 300
    directory_enabled: bool = True
    # Bing Maps (worldwide) and BizData (OSM) crawlers — on by default; both are
    # free and degrade to [] on failure/block so they can't break a search.
    bing_maps_enabled: bool = True
    bizdata_enabled: bool = True
    # Email validation (MX lookup) — on, but can be disabled for offline test runs.
    validate_emails: bool = True

    # Optional, opt-in last-resort top-up when Google Maps + OSM + directories
    # come up short (e.g. thinner markets outside major cities). Off by default:
    # contributes name + website candidates only, never guessed contact info —
    # see web_search_service.py for why that's safe.
    tavily_api_key: str = ""
    tavily_enabled: bool = False
    tavily_max_results: int = 10

    # Shared, global cache of validated discovery results per niche+city+country
    # (not workspace-scoped) — repeat searches across every workspace reuse the
    # same scrape instead of re-hitting Google Maps/OSM/directories each time.
    discovery_cache_ttl_hours: int = 2
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
