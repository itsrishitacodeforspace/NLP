"""FastAPI dependencies for authentication and authorisation."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.security import decode_access_token, role_allows

# auto_error=False so an unauthenticated request reaches our own logic, which
# decides whether auth is actually required (it is off by default).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


class Principal:
    """The identity behind a request."""

    def __init__(self, username: str, role: str, authenticated: bool) -> None:
        self.username = username
        self.role = role
        self.authenticated = authenticated

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Principal(username={self.username!r}, role={self.role!r}, authenticated={self.authenticated})"


def get_current_principal(token: Optional[str] = Depends(oauth2_scheme)) -> Principal:
    """Resolve the caller. When auth is disabled this is an anonymous admin."""
    settings = get_settings()
    if not settings.auth_enabled:
        return Principal(username="anonymous", role="admin", authenticated=False)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Principal(
        username=str(claims.get("sub", "unknown")),
        role=str(claims.get("role", "viewer")),
        authenticated=True,
    )


def require_role(*allowed: str) -> Callable[..., Principal]:
    """Dependency factory requiring the caller to hold one of ``allowed`` roles.

    A no-op when authentication is disabled, so the demo and tests keep working
    without tokens.
    """

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.authenticated:
            return principal
        if not role_allows(principal.role, list(allowed)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges for this operation",
            )
        return principal

    return _dependency
