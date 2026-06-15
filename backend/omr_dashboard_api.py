#!/usr/bin/env python3
"""OMR Dashboard backend — FastAPI sidecar for OpenMPTCProuter.

Runs alongside the existing omr-admin service (port 65500) and exposes a clean,
aggregated API for the modern dashboard frontend. Enable ``OMR_DASHBOARD_DEMO``
to serve synthetic data for development without a live VPS/router.
"""
from __future__ import annotations

import contextlib

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import deps
from config import get_settings
from routers import (
    auth_router,
    configmap,
    diagnostics,
    dns,
    firewall,
    links,
    metrics,
    protocols,
    qos,
    status,
    system,
    vps,
    wizard,
)
from services.aggregator import Aggregator
from services.metrics_store import MetricsStore


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    store = MetricsStore()
    aggregator = Aggregator(store)
    deps.init(store, aggregator)
    await aggregator.start()
    try:
        yield
    finally:
        await aggregator.stop()
        store.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="OMR Dashboard API",
        version="1.0.0",
        description="Aggregated control plane for OpenMPTCProuter",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dashboard is reached over the management tunnel only
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router.router)
    app.include_router(status.router)
    app.include_router(metrics.router)
    app.include_router(links.router)
    app.include_router(protocols.router)
    app.include_router(vps.router)
    app.include_router(firewall.router)
    app.include_router(qos.router)
    app.include_router(dns.router)
    app.include_router(diagnostics.router)
    app.include_router(system.router)
    app.include_router(configmap.router)
    app.include_router(wizard.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "demo": settings.demo, "version": "1.0.0"}

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("omr_dashboard_api:app", host="0.0.0.0", port=8000, reload=False)
