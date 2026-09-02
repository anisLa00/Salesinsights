"""Application settings, loaded from environment variables / a `.env` file.

The module also exposes the lowercase names Celery expects
(`broker_url`, `result_backend`, ...) so that
`celery_app.config_from_object("src.config")` can read them directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sales:sales@localhost:5432/sales_insight"

    # JWT
    JWT_SECRET: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"

    # Redis (token blocklist + Celery broker/backend)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "no-reply@example.com"
    MAIL_FROM_NAME: str = "Sales Insight"
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    # Public domain, used to build links inside emails
    DOMAIN: str = "localhost:8000"

    # AI (Claude API)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def ai_enabled(self) -> bool:
        """True when an API key is set and live AI calls can be made."""
        return bool(self.ANTHROPIC_API_KEY.strip())


Config = Settings()

# --- Celery configuration (read via config_from_object) ---
broker_url = Config.REDIS_URL
result_backend = Config.REDIS_URL
broker_connection_retry_on_startup = True
