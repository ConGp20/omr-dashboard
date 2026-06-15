"""System: component versions, updates, backup & restore."""
from __future__ import annotations

import json
import os

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response

from auth import require_user
from config import get_settings
from schemas import ComponentVersion, PortForward, VersionsResponse
from services import backup_service
from services.omr_proxy import OmrProxy
from services.router_proxy import RouterProxy
from services.shorewall_service import ShorewallService
from services.wireguard_service import WireguardService

router = APIRouter(prefix="/system", tags=["system"])

DASHBOARD_VERSION = "1.0.0"


async def _github_latest(repo: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"https://api.github.com/repos/{repo}/releases/latest")
            if r.status_code == 200:
                return r.json().get("tag_name")
    except Exception:
        return None
    return None


@router.get("/versions", response_model=VersionsResponse)
async def versions(_: str = Depends(require_user)) -> VersionsResponse:
    settings = get_settings()
    if settings.demo:
        return VersionsResponse(components=[
            ComponentVersion(component="OMR Router", installed="0.1060", available="0.1061",
                             update_available=True,
                             changelog_url="https://github.com/Ysurac/openmptcprouter/releases"),
            ComponentVersion(component="OMR VPS Admin", installed="0.1060", available="0.1060"),
            ComponentVersion(component="OMR Dashboard", installed=DASHBOARD_VERSION,
                             available=DASHBOARD_VERSION),
            ComponentVersion(component="OpenWRT", installed="23.05.3", available="23.05.5",
                             update_available=True),
            ComponentVersion(component="Kernel (VPS)", installed="6.1.90", available="6.1.95",
                             update_available=True),
        ])

    components: list[ComponentVersion] = []
    board = await RouterProxy().board()
    release = board.get("release", {}).get("version") if isinstance(board.get("release"), dict) else None
    components.append(ComponentVersion(component="OpenWRT", installed=release or "unbekannt"))
    components.append(ComponentVersion(component="OMR Dashboard", installed=DASHBOARD_VERSION,
                                       available=DASHBOARD_VERSION))
    components.append(ComponentVersion(component="Kernel (VPS)", installed=os.uname().release))
    return VersionsResponse(components=components)


@router.post("/update")
async def update(_: str = Depends(require_user)) -> dict:
    settings = get_settings()
    if settings.demo:
        return {"success": True, "detail": "Demo-Modus: kein echtes Update ausgeführt"}
    return {"success": False, "detail": "Update über VPS-Konsole ausführen: omr-update"}


# --- backup / restore ----------------------------------------------------- #
def _collect_config() -> tuple[dict, dict, dict]:
    """Gather VPS config, router config and secrets for a backup."""
    omr = OmrProxy()
    vps_config = {
        "active_protocol": omr.current_vpn(),
        "port_forwardings": [pf.model_dump() for pf in ShorewallService().list_forwards()],
        "exit_vpn": WireguardService().get_exit_vpn().model_dump(),
    }
    router_config: dict = {}
    secrets = {"omr_admin_config": omr.read_admin_config()}
    return vps_config, router_config, secrets


@router.post("/backup")
async def create_backup(password: str = Form(...), _: str = Depends(require_user)) -> Response:
    if not password:
        raise HTTPException(status_code=400, detail="Passwort erforderlich")
    vps_config, router_config, secrets = _collect_config()
    blob = backup_service.create_backup(
        password=password, vps_config=vps_config,
        router_config=router_config, secrets=secrets)
    return Response(
        content=blob,
        media_type="application/gzip",
        headers={"Content-Disposition": "attachment; filename=config.omr-backup.json.gz"},
    )


@router.post("/restore/preview")
async def restore_preview(file: UploadFile, _: str = Depends(require_user)) -> dict:
    blob = await file.read()
    try:
        return backup_service.preview_backup(blob=blob)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/restore")
async def restore(file: UploadFile, password: str = Form(...), _: str = Depends(require_user)) -> dict:
    blob = await file.read()
    try:
        data = backup_service.read_backup(password=password, blob=blob)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Re-apply port forwardings and exit-vpn from the backup.
    applied: list[str] = []
    sw = ShorewallService()
    for pf in data["vps"].get("port_forwardings", []):
        sw.add_forward(PortForward(**pf))
        applied.append(f"Port-Weiterleitung {pf.get('src_port')}")
    return {"success": True, "created": data.get("created"), "applied": applied}
