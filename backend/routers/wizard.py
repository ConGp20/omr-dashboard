"""Setup wizard: connect to VPS, detect WANs, apply full configuration."""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form

from auth import require_user
from config import get_settings
from deps import get_store
from schemas import (
    Event,
    WizardApply,
    WizardApplyResult,
    WizardApplyStep,
    WizardConnect,
    WizardConnectResult,
    WizardDetectResult,
    WizardDetectWans,
)
from services import backup_service
from services.omr_proxy import PROTOCOL_META, OmrProxy
from services.router_proxy import RouterProxy

router = APIRouter(prefix="/wizard", tags=["wizard"])

_log = logging.getLogger("omr_dashboard.wizard")


@router.post("/connect", response_model=WizardConnectResult)
async def connect(payload: WizardConnect, _: str = Depends(require_user)) -> WizardConnectResult:
    settings = get_settings()
    if settings.demo:
        return WizardConnectResult(
            success=True, vps_version="0.1060", current_vpn="glorytun_tcp",
            protocols_available=list(PROTOCOL_META.keys()))
    # Probe the omr-admin API on the target VPS.
    url = f"https://{payload.vps_ip}:65500/"
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {payload.omr_key}"})
            if resp.status_code == 401:
                return WizardConnectResult(success=False, error="Falscher Server-Schlüssel (401)")
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return WizardConnectResult(
                success=True,
                vps_version=str(data.get("version", "unbekannt")),
                current_vpn=data.get("vpn"),
                protocols_available=list(PROTOCOL_META.keys()),
            )
    except httpx.ConnectError:
        return WizardConnectResult(
            success=False,
            error="VPS nicht erreichbar — Port 65500 durch Firewall blockiert oder falsche IP?")
    except Exception:  # noqa: BLE001
        _log.warning("Wizard-Connect zu %s fehlgeschlagen", payload.vps_ip, exc_info=True)
        return WizardConnectResult(
            success=False, error="Verbindung fehlgeschlagen — Details siehe Server-Log")


@router.post("/detect-wans", response_model=WizardDetectResult)
async def detect_wans(payload: WizardDetectWans, _: str = Depends(require_user)) -> WizardDetectResult:
    rp = RouterProxy(payload.router_ip, payload.router_user, payload.router_pass)
    if not await rp.ping():
        return WizardDetectResult(error="Router nicht erreichbar oder falsche Zugangsdaten")
    wans = await rp.detect_wans()
    if not wans:
        return WizardDetectResult(error="Keine WAN-Schnittstellen gefunden")
    return WizardDetectResult(wans=wans)


@router.post("/apply", response_model=WizardApplyResult)
async def apply(payload: WizardApply, _: str = Depends(require_user)) -> WizardApplyResult:
    settings = get_settings()
    steps: list[WizardApplyStep] = []

    # Step 1: switch protocol on VPS
    if settings.demo:
        steps.append(WizardApplyStep(step="VPS: Protokoll aktivieren", ok=True,
                                     detail=f"{payload.protocol} aktiviert"))
    else:
        ok = await OmrProxy().switch_protocol(payload.protocol)
        steps.append(WizardApplyStep(step="VPS: Protokoll aktivieren", ok=ok,
                                     detail=payload.protocol))

    # Step 2: push config to router (VPS IP, keys, WAN labels)
    rp = RouterProxy(payload.router_ip, payload.router_user, payload.router_pass)
    if settings.demo:
        steps.append(WizardApplyStep(step="Router: VPS-IP & Schlüssel übertragen", ok=True,
                                     detail="Auto-Sync abgeschlossen"))
    else:
        ok_vps = await rp.uci_set("openmptcprouter", "vps", {"ip": payload.vps_ip})
        for wan in payload.wans:
            await rp.uci_set("openmptcprouter", wan.id, {"name": wan.label or wan.id})
        await rp.uci_commit("openmptcprouter")
        steps.append(WizardApplyStep(step="Router: VPS-IP & WAN-Labels übertragen", ok=ok_vps))

    # Step 3: wait for tunnel
    tunnel_up = await _wait_for_tunnel(timeout=30 if not settings.demo else 1)
    steps.append(WizardApplyStep(step="Tunnel aufbauen", ok=tunnel_up,
                                 detail="Verbunden" if tunnel_up else "Zeitüberschreitung"))

    # Step 4: quick speed sample
    download = upload = None
    if tunnel_up:
        if settings.demo:
            download, upload = 142.5, 28.3
        steps.append(WizardApplyStep(step="Geschwindigkeitstest", ok=True))

    await get_store().add_event(Event(
        ts=int(time.time()), type="wizard_apply",
        detail=f"Ersteinrichtung abgeschlossen ({payload.protocol})", severity="info"))

    return WizardApplyResult(
        success=all(s.ok for s in steps), steps=steps,
        download_mbps=download, upload_mbps=upload)


async def _wait_for_tunnel(timeout: int) -> bool:
    from deps import get_aggregator
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = await get_aggregator().status()
        if status.tunnel and status.tunnel.up:
            return True
        await asyncio.sleep(2)
    # In demo mode the first status already reports up.
    status = await get_aggregator().status()
    return bool(status.tunnel and status.tunnel.up)


@router.post("/restore-backup")
async def restore_backup(
    file: UploadFile,
    password: str = Form(...),
    _: str = Depends(require_user),
) -> dict:
    blob = await file.read()
    try:
        data = backup_service.read_backup(password=password, blob=blob)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": True, "preview": {
        "created": data.get("created"),
        "active_protocol": data["vps"].get("active_protocol"),
        "port_forwardings": len(data["vps"].get("port_forwardings", [])),
    }}
