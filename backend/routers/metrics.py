"""Historical metrics and event log."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from deps import get_store
from schemas import Event, MetricsResponse

router = APIRouter(prefix="/dashboard", tags=["metrics"])

_VALID_PERIODS = {"1h", "6h", "24h", "7d"}


@router.get("/metrics/{period}", response_model=MetricsResponse)
async def metrics(period: str, _: str = Depends(require_user)) -> MetricsResponse:
    if period not in _VALID_PERIODS:
        raise HTTPException(status_code=400, detail="Ungültiger Zeitraum")
    points = await get_store().metrics(period)
    return MetricsResponse(period=period, points=points)


@router.get("/events", response_model=list[Event])
async def events(limit: int = 50, _: str = Depends(require_user)) -> list[Event]:
    return await get_store().events(limit=limit)
