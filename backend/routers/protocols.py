"""Protocol listing, switching and MPTCP scheduler / tuning."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from deps import get_aggregator, get_store
from schemas import (
    Event,
    ProtocolInfo,
    ProtocolSwitch,
    ProtocolTuning,
    SchedulerUpdate,
)
from services.omr_proxy import OmrProxy
from services.router_proxy import RouterProxy

router = APIRouter(prefix="/protocols", tags=["protocols"])

SCHEDULERS = {
    "default": "Pakete über alle Links, schnellster Pfad gewinnt. Guter Allrounder.",
    "roundrobin": "Reihum gleichmäßig über alle Links. Einfache Lastverteilung.",
    "redundant": "Alle Pakete über ALLE Links gleichzeitig. Höchste Ausfallsicherheit, höchster Overhead.",
    "blest": "Bevorzugt schnelle Subflows, bremst langsame aus. Gut bei stark unterschiedlichen Leitungen.",
    "fullmesh": "Vollständige Vermaschung aller Interfaces. Empfohlen bei vielen Links.",
}


@router.get("", response_model=list[ProtocolInfo])
async def list_protocols(_: str = Depends(require_user)) -> list[ProtocolInfo]:
    protocols = await OmrProxy().protocols()
    # Recommendation: pick based on number of active links.
    status = await get_aggregator().status()
    n = status.total_links or len(status.links)
    rec = "glorytun_tcp" if n <= 1 else "shadowsocks"
    for p in protocols:
        p.recommended = (p.id == rec)
    return protocols


@router.get("/schedulers")
async def list_schedulers(_: str = Depends(require_user)) -> dict:
    return {"schedulers": [{"id": k, "description": v} for k, v in SCHEDULERS.items()]}


@router.post("/switch")
async def switch_protocol(payload: ProtocolSwitch, _: str = Depends(require_user)) -> dict:
    ok = await OmrProxy().switch_protocol(payload.protocol)
    if not ok:
        raise HTTPException(status_code=502, detail="Protokoll-Wechsel fehlgeschlagen")
    await get_store().add_event(Event(
        ts=int(time.time()), type="protocol_switch",
        detail=f"Protokoll gewechselt zu {payload.protocol}", severity="info"))
    return {"success": True, "protocol": payload.protocol}


@router.put("/scheduler")
async def set_scheduler(payload: SchedulerUpdate, _: str = Depends(require_user)) -> dict:
    if payload.scheduler not in SCHEDULERS:
        raise HTTPException(status_code=400, detail="Unbekannter Scheduler")
    router_proxy = RouterProxy()
    await router_proxy.uci_set("network", "globals", {"mptcp_scheduler": payload.scheduler})
    await router_proxy.uci_commit("network")
    return {"success": True, "scheduler": payload.scheduler}


@router.put("/tune")
async def tune(payload: ProtocolTuning, _: str = Depends(require_user)) -> dict:
    router_proxy = RouterProxy()
    values: dict = {}
    if payload.mtu is not None:
        values["mtu"] = str(payload.mtu)
    if payload.congestion is not None:
        values["congestion"] = payload.congestion
    if payload.tcp_fast_open is not None:
        values["tcp_fast_open"] = "1" if payload.tcp_fast_open else "0"
    if values:
        await router_proxy.uci_set("openmptcprouter", "settings", values)
        await router_proxy.uci_commit("openmptcprouter")
    return {"success": True, "applied": values}
