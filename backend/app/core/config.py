"""Application settings.

All configuration comes from environment variables (optionally a ``.env`` file).
Secrets are never hard-coded; see ``.env.example`` at the repository root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", BACKEND_DIR / ".env"),
        env_prefix="IIOS_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    # Database. SQLite is accepted for local demos and tests; PostgreSQL is the
    # production target (row-level security is only enforced on PostgreSQL).
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'iios.db'}"
    database_echo: bool = False

    # Files uploaded by users and generated reports.
    storage_dir: Path = BACKEND_DIR / "data" / "storage"
    max_upload_mb: int = 20
    max_xlsx_uncompressed_mb: int = 200

    # Sessions
    session_cookie_name: str = "iios_session"
    csrf_cookie_name: str = "iios_csrf"
    session_idle_timeout_minutes: int = 120
    session_absolute_timeout_hours: int = 24
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict"] = "lax"

    # Login protection
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    login_rate_limit_per_minute: int = 10
    api_rate_limit_per_minute: int = 300
    password_min_length: int = 10

    password_reset_ttl_minutes: int = 60
    public_app_url: str = "http://localhost:3000"

    # Outbound e-mail (used for password recovery). When not configured, the
    # development environment prints the reset link to the server log; any
    # other environment refuses to pretend the e-mail was sent.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True

    allow_self_signup: bool = False

    cors_origins: list[str] = Field(default_factory=list)

    # Branding (white-label). The UI reads these from /api/v1/system/branding.
    brand_name: str = "Industrial Intelligence OS"
    brand_short_name: str = "IIOS"
    brand_primary_color: str = "#0f766e"
    brand_support_email: str | None = None

    # Analysis limits
    max_rows_per_import_hard_limit: int = 200_000

    log_level: str = "INFO"
    log_json: bool = True

    @field_validator("storage_dir")
    @classmethod
    def _absolute_storage(cls, v: Path) -> Path:
        return v if v.is_absolute() else (BACKEND_DIR / v).resolve()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
