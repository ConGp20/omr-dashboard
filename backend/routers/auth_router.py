"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth import (
    auth_required,
    create_token,
    lockout_remaining,
    record_failure,
    require_user,
    reset_failures,
    verify_credentials,
)
from config import get_settings
from schemas import AuthStatus, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
async def auth_status() -> AuthStatus:
    """Whether a login is needed at all.

    Lets the UI skip the login screen in demo mode and on a fresh install with
    no password set, instead of showing a form that would accept anything.
    """
    settings = get_settings()
    return AuthStatus(
        auth_required=auth_required(),
        demo=settings.demo,
        username=settings.dashboard_user,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    client = request.client.host if request.client else "unknown"
    remaining = lockout_remaining(client)
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Zu viele Fehlversuche — bitte {int(remaining) + 1} Sekunden warten",
            headers={"Retry-After": str(int(remaining) + 1)},
        )
    if not verify_credentials(payload.username, payload.password):
        record_failure(client)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Falscher Benutzername oder Passwort")
    reset_failures(client)
    return TokenResponse(access_token=create_token(payload.username))


@router.get("/me")
async def me(user: str = Depends(require_user)) -> dict:
    return {"user": user}
