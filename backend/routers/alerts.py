"""Alert channel configuration and test delivery."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import require_user
from config import get_settings
from schemas import AlertConfigPublic, AlertConfigUpdate, AlertTestResult
from services import alerts_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/config", response_model=AlertConfigPublic)
async def get_config(_: str = Depends(require_user)) -> AlertConfigPublic:
    cfg = alerts_service.load_config(get_settings().data_dir)
    return alerts_service.public_config(cfg)


@router.put("/config", response_model=AlertConfigPublic)
async def update_config(
    payload: AlertConfigUpdate, _: str = Depends(require_user)
) -> AlertConfigPublic:
    cfg = alerts_service.save_config(
        get_settings().data_dir, payload.model_dump(exclude_none=True))
    return alerts_service.public_config(cfg)


@router.post("/test", response_model=AlertTestResult)
async def test(_: str = Depends(require_user)) -> AlertTestResult:
    results = await alerts_service.send_test(get_settings().data_dir)
    return AlertTestResult(results=results)
