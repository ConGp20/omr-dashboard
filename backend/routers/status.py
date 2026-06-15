"""Live status, topology and Server-Sent-Events stream."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from auth import require_user
from deps import get_aggregator
from schemas import DashboardStatus, Topology

router = APIRouter(prefix="/dashboard", tags=["status"])


@router.get("/status", response_model=DashboardStatus)
async def get_status(_: str = Depends(require_user)) -> DashboardStatus:
    return await get_aggregator().status()


@router.get("/topology", response_model=Topology)
async def get_topology(_: str = Depends(require_user)) -> Topology:
    return await get_aggregator().topology()


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """SSE stream pushing the full status payload on every poll tick."""
    agg = get_aggregator()

    async def event_gen():
        q = agg.subscribe()
        try:
            # Send an immediate snapshot.
            snapshot = await agg.status()
            yield f"event: status\ndata: {snapshot.model_dump_json()}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    status: DashboardStatus = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"event: status\ndata: {status.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive comment
                    yield ": keepalive\n\n"
        finally:
            agg.unsubscribe(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
