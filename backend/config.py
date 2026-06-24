"""Application configuration via pydantic-settings."""
from __future__ import annotations

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://hcb_user:hcb_secure_password@localhost:5432/hcb_monitor"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Polymarket API endpoints
    POLYMARKET_CLOB_URL: str = "https://clob.polymarket.com"
    POLYMARKET_GAMMA_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_WS_URL: str = (
        "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    )

    # Polling intervals (seconds)
    POLL_INTERVAL_TRADES: int = 30
    POLL_INTERVAL_MARKETS: int = 300

    # Anomaly detection schedule
    ANOMALY_DETECT_INTERVAL_HOURS: int = 6

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_FROM_EMAIL: str = "hcb-monitor@example.com"
    ALERT_TO_EMAILS: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Application
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Alert rate limiting
    ALERT_RATE_LIMIT_MINUTES: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def alert_to_emails_list(self) -> List[str]:
        return [e.strip() for e in self.ALERT_TO_EMAILS.split(",") if e.strip()]


settings = Settings()
