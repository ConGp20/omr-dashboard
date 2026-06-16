"""Connection & security settings — credentials the wizard sets once but that
must stay editable afterwards (docs/routing-plan.de.md §8). Backed by
services/settings_service.py's encrypted override store; ``BIND_ADDR`` and
listen ports remain the one exception that still needs a container restart,
since they're baked into docker-compose.yml's port bindings, not read by the
running process."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from config import clear_settings_cache, get_settings
from schemas import (
    ConnectionSettings,
    ConnectionSettingsUpdate,
    ConnectionTestResult,
    SecuritySettings,
    SecuritySettingsUpdate,
)
from services.omr_proxy import OmrProxy
from services.router_proxy import RouterProxy
from services.settings_service import SettingsStoreError, overridden_fields, save_overrides

router = APIRouter(prefix="/settings", tags=["settings"])

_CONNECTION_FIELDS = {"router_ip", "router_user", "router_pass", "omr_admin_key"}
_SECURITY_FIELDS = {"dashboard_user", "dashboard_pass", "jwt_secret"}
_DEFAULT_JWT_SECRET = "change-me-in-production"


def _connection_view() -> ConnectionSettings:
    s = get_settings()
    overridden = overridden_fields(s.data_dir)
    return ConnectionSettings(
        router_ip=s.router_ip,
        router_user=s.router_user,
        router_pass_set=bool(s.router_pass),
        omr_admin_key_set=bool(s.omr_admin_key),
        overridden=sorted(overridden & _CONNECTION_FIELDS),
    )


def _security_view() -> SecuritySettings:
    s = get_settings()
    overridden = overridden_fields(s.data_dir)
    return SecuritySettings(
        dashboard_user=s.dashboard_user,
        dashboard_pass_set=bool(s.dashboard_pass),
        jwt_secret_set=s.jwt_secret != _DEFAULT_JWT_SECRET,
        overridden=sorted(overridden & _SECURITY_FIELDS),
    )


@router.get("/connection", response_model=ConnectionSettings)
async def get_connection(_: str = Depends(require_user)) -> ConnectionSettings:
    return _connection_view()


@router.put("/connection", response_model=ConnectionSettings)
async def set_connection(
    update: ConnectionSettingsUpdate, _: str = Depends(require_user)
) -> ConnectionSettings:
    s = get_settings()
    try:
        save_overrides(s.data_dir, update.model_dump(exclude_none=True))
    except SettingsStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    clear_settings_cache()
    return _connection_view()


@router.post("/connection/test", response_model=ConnectionTestResult)
async def test_connection(_: str = Depends(require_user)) -> ConnectionTestResult:
    s = get_settings()
    if s.demo:
        return ConnectionTestResult(
            router_reachable=True, router_detail="Demo-Modus",
            omr_admin_reachable=True, omr_admin_detail="Demo-Modus",
        )
    result = ConnectionTestResult()
    try:
        result.router_reachable = await RouterProxy().ping()
        result.router_detail = "Erreichbar" if result.router_reachable else "Keine Antwort / falsche Zugangsdaten"
    except Exception as exc:  # noqa: BLE001 - surface any transport error to the UI
        result.router_detail = str(exc)
    try:
        result.omr_admin_reachable = await OmrProxy().ping()
        result.omr_admin_detail = "Erreichbar" if result.omr_admin_reachable else "Keine Antwort"
    except Exception as exc:  # noqa: BLE001
        result.omr_admin_detail = str(exc)
    return result


@router.get("/security", response_model=SecuritySettings)
async def get_security(_: str = Depends(require_user)) -> SecuritySettings:
    return _security_view()


@router.put("/security", response_model=SecuritySettings)
async def set_security(
    update: SecuritySettingsUpdate, _: str = Depends(require_user)
) -> SecuritySettings:
    s = get_settings()
    try:
        save_overrides(s.data_dir, update.model_dump(exclude_none=True))
    except SettingsStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    clear_settings_cache()
    return _security_view()
