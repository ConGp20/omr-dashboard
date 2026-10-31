"""Simplified firewall rule management and presets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from schemas import FirewallRule, FirewallRuleResult
from services.shorewall_service import FIREWALL_PRESETS, ShorewallService

router = APIRouter(prefix="/firewall", tags=["firewall"])


@router.get("/rules", response_model=list[FirewallRule])
async def list_rules(_: str = Depends(require_user)) -> list[FirewallRule]:
    return ShorewallService().list_rules()


@router.post("/rules", response_model=FirewallRuleResult)
async def add_rule(rule: FirewallRule, _: str = Depends(require_user)) -> FirewallRuleResult:
    svc = ShorewallService()
    saved = svc.add_rule(rule)
    return FirewallRuleResult(**saved.model_dump(), warning=svc.last_warning)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _: str = Depends(require_user)) -> dict:
    svc = ShorewallService()
    if not svc.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    return {"success": True, "warning": svc.last_warning}


@router.get("/presets")
async def presets(_: str = Depends(require_user)) -> dict:
    return {"presets": FIREWALL_PRESETS}
