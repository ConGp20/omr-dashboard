"""Minimal JWT auth for the dashboard.

A single dashboard user authenticates with a password (defaults to the OMR
admin key when ``OMR_DASHBOARD_PASS`` is unset). Tokens are HS256 JWTs. The
dependency is permissive in demo mode so the UI is immediately usable.
"""
from __future__ import annotations

import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import get_settings

_bearer = HTTPBearer(auto_error=False)


def _expected_password() -> str:
    s = get_settings()
    return s.dashboard_pass or s.omr_admin_key


def auth_required() -> bool:
    """Whether clients must present a token.

    False in demo mode and on a fresh install with no password configured —
    the UI uses this to skip the login screen instead of showing a form that
    would accept anything.
    """
    s = get_settings()
    return not s.demo and bool(_expected_password())


# --- brute-force protection ------------------------------------------------
# The dashboard is meant to sit behind the management tunnel, but it only takes
# one misconfigured BIND_ADDR for the login to face the internet. Throttling
# costs nothing and removes online password guessing as an option.
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

_failures: dict[str, list[float]] = {}


def lockout_remaining(client: str, now: float | None = None) -> float:
    """Seconds until ``client`` may try again; 0 when it is not locked out."""
    now = time.time() if now is None else now
    recent = [t for t in _failures.get(client, []) if now - t < LOCKOUT_SECONDS]
    _failures[client] = recent
    if len(recent) < MAX_ATTEMPTS:
        return 0.0
    return LOCKOUT_SECONDS - (now - recent[-MAX_ATTEMPTS])


def record_failure(client: str, now: float | None = None) -> None:
    now = time.time() if now is None else now
    _failures.setdefault(client, []).append(now)


def reset_failures(client: str | None = None) -> None:
    """Clear throttling state — on success for one client, or all of it."""
    if client is None:
        _failures.clear()
    else:
        _failures.pop(client, None)


def verify_credentials(username: str, password: str) -> bool:
    s = get_settings()
    if s.demo:
        return True
    expected = _expected_password()
    if not expected:
        # No password configured yet (fresh install) — allow first use.
        return True
    # Compare in constant time so a wrong password cannot be found by timing.
    return username == s.dashboard_user and secrets.compare_digest(password, expected)


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
