"""Historical metrics, event log and monthly data-usage tracking."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from auth import require_user
from deps import get_aggregator, get_store
from schemas import Event, LinkUsage, MetricsResponse, QuotaUpdate, UsageResponse
from services.metrics_store import current_month, month_progress

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


def _link_usage(link_id: str, label: str, rx: float, tx: float, quota: dict,
                progress: float = 1.0) -> LinkUsage:
    total = rx + tx
    cap_gb = quota.get("cap_gb")
    warn_pct = quota.get("warn_pct") or 80
    cap_bytes = cap_gb * 1e9 if cap_gb else None
    projected = total / progress if progress > 0 else total
    return LinkUsage(
        link_id=link_id, label=label, rx_bytes=rx, tx_bytes=tx, total_bytes=total,
        cap_gb=cap_gb, warn_pct=warn_pct,
        used_pct=(total / cap_bytes * 100.0) if cap_bytes else None,
        over_warn=bool(cap_bytes and total >= cap_bytes * warn_pct / 100.0),
        over_cap=bool(cap_bytes and total >= cap_bytes),
        projected_bytes=projected,
        projected_pct=(projected / cap_bytes * 100.0) if cap_bytes else None,
        projected_over_cap=bool(cap_bytes and projected > cap_bytes),
    )


@router.get("/usage", response_model=UsageResponse)
async def usage(_: str = Depends(require_user)) -> UsageResponse:
    store = get_store()
    month = current_month()
    raw = await store.usage(month)
    quotas = await store.quotas()
    labels = {l.id: l.label for l in (await get_aggregator().status()).links}
    progress, day, days = month_progress()
    ids = set(raw) | set(quotas) | set(labels)
    links: list[LinkUsage] = []
    total = 0.0
    for link_id in sorted(ids):
        rx, tx = raw.get(link_id, (0.0, 0.0))
        total += rx + tx
        links.append(_link_usage(link_id, labels.get(link_id, link_id), rx, tx,
                                 quotas.get(link_id, {}), progress))
    return UsageResponse(month=month, total_bytes=total, links=links,
                         day_of_month=day, days_in_month=days)


@router.get("/usage.csv")
async def usage_csv(_: str = Depends(require_user)) -> Response:
    """Current month's per-link volume as CSV, for billing or a spreadsheet."""
    report = await usage()
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["month", "link_id", "label", "rx_bytes", "tx_bytes",
                     "total_bytes", "total_gb", "cap_gb", "used_pct",
                     "projected_gb"])
    for link in report.links:
        writer.writerow([
            report.month, link.link_id, link.label,
            int(link.rx_bytes), int(link.tx_bytes), int(link.total_bytes),
            f"{link.total_bytes / 1e9:.3f}",
            f"{link.cap_gb:g}" if link.cap_gb else "",
            f"{link.used_pct:.1f}" if link.used_pct is not None else "",
            f"{link.projected_bytes / 1e9:.3f}",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="omr-usage-{report.month}.csv"'},
    )


@router.put("/usage/{link_id}/quota", response_model=LinkUsage)
async def set_quota(link_id: str, payload: QuotaUpdate, _: str = Depends(require_user)) -> LinkUsage:
    store = get_store()
    cap_gb = payload.cap_gb if (payload.cap_gb and payload.cap_gb > 0) else None
    warn_pct = payload.warn_pct or 80
    await store.set_quota(link_id, cap_gb, warn_pct)
    rx, tx = (await store.usage(current_month())).get(link_id, (0.0, 0.0))
    labels = {l.id: l.label for l in (await get_aggregator().status()).links}
    progress, _day, _days = month_progress()
    return _link_usage(link_id, labels.get(link_id, link_id), rx, tx,
                       {"cap_gb": cap_gb, "warn_pct": warn_pct}, progress)
