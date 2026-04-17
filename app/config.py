from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    bot_token: str = Field(..., alias="BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    scraper_interval_seconds: int = Field(180, alias="SCRAPER_INTERVAL_SECONDS")
    notifier_interval_seconds: int = Field(90, alias="NOTIFIER_INTERVAL_SECONDS")
    default_headlines_count: int = Field(5, alias="DEFAULT_HEADLINES_COUNT")
    http_timeout_seconds: int = Field(15, alias="HTTP_TIMEOUT_SECONDS")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    guardian_api_key: str = Field("test", alias="GUARDIAN_API_KEY")
    guardian_sections: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("business", "world"),
        alias="GUARDIAN_SECTIONS",
    )

    nytimes_api_key: str = Field("", alias="NYTIMES_API_KEY")
    nytimes_sections: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("business", "world"),
        alias="NYTIMES_SECTIONS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        """Validate that Telegram bot token is not empty."""
        token = value.strip()
        if not token:
            raise ValueError("BOT_TOKEN must not be empty.")
        return token

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Validate async SQLAlchemy database URL."""
        url = value.strip()
        if not url:
            raise ValueError("DATABASE_URL must not be empty.")
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with 'postgresql+asyncpg://'.")
        return url

    @field_validator("guardian_api_key", "nytimes_api_key", mode="before")
    @classmethod
    def normalize_optional_api_key(cls, value: Any) -> str:
        """Normalize optional API key values."""
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("guardian_sections", "nytimes_sections", mode="before")
    @classmethod
    def parse_sections(cls, value: Any) -> tuple[str, ...]:
        """Parse comma-separated sections from environment."""
        if value is None:
            raise ValueError("Sections configuration must not be empty.")

        if isinstance(value, str):
            items = [item.strip().lower() for item in value.split(",") if item.strip()]
            if not items:
                raise ValueError("At least one section must be provided.")
            return tuple(items)

        if isinstance(value, (list, tuple, set)):
            items = [str(item).strip().lower() for item in value if str(item).strip()]
            if not items:
                raise ValueError("At least one section must be provided.")
            return tuple(items)

        raise ValueError("Sections configuration must be a string or sequence of strings.")

    @field_validator(
        "scraper_interval_seconds",
        "notifier_interval_seconds",
        "http_timeout_seconds",
    )
    @classmethod
    def validate_positive_interval(cls, value: int) -> int:
        """Validate positive interval values."""
        if value <= 0:
            raise ValueError("Interval values must be positive integers.")
        return value

    @field_validator("default_headlines_count")
    @classmethod
    def validate_default_headlines_count(cls, value: int) -> int:
        """Validate number of headlines per response."""
        if not 1 <= value <= 20:
            raise ValueError("DEFAULT_HEADLINES_COUNT must be between 1 and 20.")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: Any) -> str:
        """Normalize log level."""
        if value is None:
            return "INFO"
        normalized = str(value).strip().upper()
        if not normalized:
            return "INFO"
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()