"""Simplified firewall rule management and presets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from schemas import FirewallRule
from services.shorewall_service import FIREWALL_PRESETS, ShorewallService

router = APIRouter(prefix="/firewall", tags=["firewall"])


@router.get("/rules", response_model=list[FirewallRule])
async def list_rules(_: str = Depends(require_user)) -> list[FirewallRule]:
    return ShorewallService().list_rules()


@router.post("/rules", response_model=FirewallRule)
async def add_rule(rule: FirewallRule, _: str = Depends(require_user)) -> FirewallRule:
    return ShorewallService().add_rule(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _: str = Depends(require_user)) -> dict:
    if not ShorewallService().delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    return {"success": True}


@router.get("/presets")
async def presets(_: str = Depends(require_user)) -> dict:
    return {"presets": FIREWALL_PRESETS}
