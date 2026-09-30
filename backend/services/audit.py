"""Audit trail for configuration changes.

Implemented as middleware rather than calls sprinkled through the routers: it
cannot be forgotten when an endpoint is added, and it records every mutating
request uniformly.

Only the request line is stored — method, path, status, actor, client. Bodies
and query strings never are, because they carry passwords, tunnel keys and bot
tokens, and an audit table is meant to be safe to read.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from fastapi import Request, Response
import jwt
from jwt import InvalidTokenError

from config import get_settings

_log = logging.getLogger("omr_dashboard.audit")

# Reads change nothing, so they are not recorded — the trail stays about
# changes rather than drowning in dashboard polling.
_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Endpoints that mutate nothing despite their verb, or that would add noise.
_SKIP_PATHS = {"/diagnostics/ping", "/diagnostics/speedtest", "/diagnostics/mtu",
               "/alerts/test", "/settings/connection/test"}


def actor_from_request(request: Request) -> str:
    """Best-effort identity of the caller from the bearer token."""
    settings = get_settings()
    if settings.demo:
        return "demo"
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return "anonymous"
    try:
        payload = jwt.decode(header[7:], settings.jwt_secret, algorithms=["HS256"])
        return str(payload.get("sub") or "user")
    except InvalidTokenError:
        return "unknown"


def should_audit(method: str, path: str) -> bool:
    return method.upper() in _AUDITED_METHODS and path not in _SKIP_PATHS


async def middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    path = request.url.path
    if not should_audit(request.method, path):
        return response
    try:
        from deps import get_store

        await get_store().add_audit(
            actor=actor_from_request(request),
            method=request.method,
            path=path,
            status=response.status_code,
            client=request.client.host if request.client else "unknown",
        )
    except Exception:  # noqa: BLE001 — auditing must never fail a request
        _log.warning("audit write failed for %s %s", request.method, path, exc_info=True)
    return response
