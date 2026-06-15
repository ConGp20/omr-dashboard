"""QoS profiles and domain-based routing rules."""
from __future__ import annotations

import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from config import get_settings
from schemas import DomainRule, QosProfile
from services.router_proxy import RouterProxy

router = APIRouter(prefix="/qos", tags=["qos"])

PROFILES = {
    "gaming": {"name": "Gaming", "prioritizes": "UDP-Spielverkehr (DSCP EF), niedrige Latenz"},
    "streaming": {"name": "Streaming", "prioritizes": "Hoher Durchsatz, große TCP-Puffer"},
    "work": {"name": "Arbeit / VoIP", "prioritizes": "Videokonferenzen (RTP/RTCP), dann HTTP"},
    "download": {"name": "Download", "prioritizes": "Maximaler Durchsatz, Latenz unwichtig"},
    "default": {"name": "Standard", "prioritizes": "Best-Effort, keine Priorisierung"},
}

DOMAIN_PRESETS = {
    "google": ["google.com", "googleapis.com", "gstatic.com", "youtube.com"],
    "microsoft": ["microsoft.com", "office.com", "office365.com", "live.com"],
    "netflix": ["netflix.com", "nflxvideo.net"],
    "gaming": ["steampowered.com", "epicgames.com", "battle.net"],
}


def _state_path() -> str:
    return os.path.join(get_settings().data_dir, "qos.json")


def _load() -> dict:
    try:
        with open(_state_path()) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"active": "default", "domains": []}


def _save(data: dict) -> None:
    os.makedirs(get_settings().data_dir, exist_ok=True)
    with open(_state_path(), "w") as fh:
        json.dump(data, fh)


@router.get("/profile", response_model=QosProfile)
async def get_profile(_: str = Depends(require_user)) -> QosProfile:
    return QosProfile(active=_load().get("active", "default"), available=list(PROFILES.keys()))


@router.get("/profiles")
async def list_profiles(_: str = Depends(require_user)) -> dict:
    return {"profiles": [{"id": k, **v} for k, v in PROFILES.items()]}


@router.put("/profile")
async def set_profile(payload: QosProfile, _: str = Depends(require_user)) -> dict:
    if payload.active not in PROFILES:
        raise HTTPException(status_code=400, detail="Unbekanntes Profil")
    data = _load()
    data["active"] = payload.active
    _save(data)
    # Apply via router (omr-dscp UCI) in real mode.
    if not get_settings().demo:
        rp = RouterProxy()
        await rp.uci_set("omr-dscp", "settings", {"profile": payload.active})
        await rp.uci_commit("omr-dscp")
    return {"success": True, "active": payload.active}


@router.get("/domains", response_model=list[DomainRule])
async def list_domains(_: str = Depends(require_user)) -> list[DomainRule]:
    return [DomainRule(**d) for d in _load().get("domains", [])]


@router.post("/domains", response_model=DomainRule)
async def add_domain(rule: DomainRule, _: str = Depends(require_user)) -> DomainRule:
    rule.id = rule.id or uuid.uuid4().hex[:8]
    data = _load()
    data.setdefault("domains", []).append(rule.model_dump())
    _save(data)
    return rule


@router.delete("/domains/{rule_id}")
async def delete_domain(rule_id: str, _: str = Depends(require_user)) -> dict:
    data = _load()
    before = len(data.get("domains", []))
    data["domains"] = [d for d in data.get("domains", []) if d.get("id") != rule_id]
    _save(data)
    if len(data["domains"]) == before:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    return {"success": True}


@router.get("/domain-presets")
async def domain_presets(_: str = Depends(require_user)) -> dict:
    return {"presets": DOMAIN_PRESETS}
