"""Authentication routes: password login and identity lookup."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import Principal, get_current_principal
from app.core.config import get_settings
from app.core.security import create_access_token, user_store
from app.models.schemas import TokenResponse, UserInfo

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Exchange username/password for a bearer token."""
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is disabled on this server.",
        )
    user = user_store.authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=UserInfo)
def me(principal: Principal = Depends(get_current_principal)) -> UserInfo:
    """Return the identity behind the current request."""
    return UserInfo(
        username=principal.username,
        role=principal.role,
        authenticated=principal.authenticated,
    )
