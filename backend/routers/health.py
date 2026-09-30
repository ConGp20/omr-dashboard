"""Configuration advisor endpoint — non-blocking hints and recommendations."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import require_user
from config import get_settings
from deps import get_aggregator, get_store
from schemas import HealthReport
from services import advisor, alerts_service
from services.metrics_store import current_month, month_progress

router = APIRouter(prefix="/health-check", tags=["health"])


@router.get("", response_model=HealthReport)
async def health_check(_: str = Depends(require_user)) -> HealthReport:
    settings = get_settings()
    store = get_store()
    ctx = advisor.AdvisorContext(
        settings=settings,
        status=await get_aggregator().status(),
        quotas=await store.quotas(),
        usage=await store.usage(current_month()),
        alerts=alerts_service.load_config(settings.data_dir),
        bind_addr=advisor.bind_addr_from_env(),
        month_progress=month_progress()[0],
    )
    findings = advisor.evaluate(ctx)
    return HealthReport(
        findings=findings,
        errors=sum(1 for f in findings if f.severity == "error"),
        warnings=sum(1 for f in findings if f.severity == "warn"),
        infos=sum(1 for f in findings if f.severity == "info"),
        checked=len(advisor.CHECKS),
    )
