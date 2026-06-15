"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from auth import create_token, require_user, verify_credentials
from schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Falscher Benutzername oder Passwort")
    return TokenResponse(access_token=create_token(payload.username))


@router.get("/me")
async def me(user: str = Depends(require_user)) -> dict:
    return {"user": user}
