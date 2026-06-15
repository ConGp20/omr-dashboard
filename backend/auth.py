"""Minimal JWT auth for the dashboard.

A single dashboard user authenticates with a password (defaults to the OMR
admin key when ``OMR_DASHBOARD_PASS`` is unset). Tokens are HS256 JWTs. The
dependency is permissive in demo mode so the UI is immediately usable.
"""
from __future__ import annotations

import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import get_settings

_bearer = HTTPBearer(auto_error=False)


def _expected_password() -> str:
    s = get_settings()
    return s.dashboard_pass or s.omr_admin_key


def verify_credentials(username: str, password: str) -> bool:
    s = get_settings()
    if s.demo:
        return True
    expected = _expected_password()
    if not expected:
        # No password configured yet (fresh install) — allow first use.
        return True
    return username == s.dashboard_user and password == expected


def create_token(username: str) -> str:
    s = get_settings()
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + s.jwt_ttl_minutes * 60,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


async def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    s = get_settings()
    if s.demo:
        return "demo"
    # If no password is configured, auth is effectively open (fresh install).
    if not _expected_password():
        return "anonymous"
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, s.jwt_secret, algorithms=["HS256"])
        return payload.get("sub", "user")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
