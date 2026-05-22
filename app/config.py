"""Application configuration.

Centralizes settings so the database URL, log level, and pagination
defaults can be overridden via environment variables without code changes.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEDGER_", env_file=".env")

    # Embedded SQLite by default; override with LEDGER_DATABASE_URL for tests/Docker.
    database_url: str = "sqlite:///./ledger.db"

    # Structured logging level.
    log_level: str = "INFO"

    # Default and maximum page sizes for the event listing endpoint.
    default_page_size: int = 50
    max_page_size: int = 200


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
