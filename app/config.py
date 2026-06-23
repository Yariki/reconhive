"""Application settings (env-driven)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECONHIVE_", env_file=".env", extra="ignore"
    )

    # asyncpg DSN, e.g. postgresql+asyncpg://user:pass@localhost:5432/reconhive
    database_url: str = Field(
        default="postgresql+asyncpg://reconhive:reconhive@localhost:5432/reconhive"
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Safety rails for the scan planner.
    # Refuse to expand/queue a job whose authorized host count exceeds this,
    # to guard against fat-fingering a /8 even when it is technically in scope.
    max_authorized_hosts_per_job: int = 65_536

    # Optional MaxMind GeoLite2/GeoIP2 binary database paths.
    geoip_city_db: str | None = None
    geoip_asn_db: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
