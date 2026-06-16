"""Central configuration for the OMR Dashboard backend.

All values can be overridden via environment variables (see .env.example).
When ``OMR_DASHBOARD_DEMO`` is true the backend serves synthetic data so the
dashboard can be developed and demonstrated without a live VPS/router pair.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMR_DASHBOARD_", extra="ignore")

    # --- Demo / development -------------------------------------------------
    demo: bool = False

    # --- Existing OMR Admin API (FastAPI on the VPS, port 65500) -------------
    omr_admin_url: str = "https://127.0.0.1:65500"
    omr_admin_key: str = ""
    omr_admin_config: str = "/etc/omr-admin/omr-admin-config.json"

    # --- Router (LuCI / ubus) ----------------------------------------------
    router_ip: str = "192.168.100.1"
    router_user: str = "root"
    router_pass: str = ""

    # --- Shorewall (port forwarding / firewall) -----------------------------
    shorewall_rules: str = "/etc/shorewall/rules"

    # --- Persistence --------------------------------------------------------
    data_dir: str = "/var/opt/omr-dashboard"

    # --- Auth ---------------------------------------------------------------
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_minutes: int = 720
    dashboard_user: str = "admin"
    dashboard_pass: str = ""  # empty -> falls back to omr_admin_key

    # --- Polling ------------------------------------------------------------
    poll_interval_seconds: int = 10
    metrics_retention_days: int = 7

    @property
    def db_path(self) -> str:
        return f"{self.data_dir}/dashboard.db"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Apply persisted overrides (router/auth credentials edited later from the
    # dashboard, see services/settings_service.py) on top of the env defaults.
    from services.settings_service import load_overrides

    overrides = load_overrides(settings.data_dir)
    if overrides:
        settings = settings.model_copy(update=overrides)
    return settings


def clear_settings_cache() -> None:
    """Call after persisting new overrides so the next get_settings() picks
    them up. Every consumer (auth, RouterProxy, OmrProxy, ...) reads settings
    fresh via get_settings() on each use, so no further plumbing is needed."""
    get_settings.cache_clear()
