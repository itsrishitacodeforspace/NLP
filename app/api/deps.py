"""FastAPI dependencies for authentication and authorisation."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import ROLE_RANK, decode_access_token, role_allows, user_store

logger = get_logger()

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
    username = str(claims.get("sub", "unknown"))
    role = str(claims.get("role", "viewer"))
    # Re-validate against the live user store: a token is only as good as the
    # user behind it. A user deleted or demoted after the token was minted
    # keeps a valid JWT until expiry otherwise (audit P2).
    #
    # Degradation semantics (graceful-degradation requirement): the token is
    # the primary credential, so a user the store has *never seen* (store not
    # yet initialised in this process) or a store error are treated as
    # "unknown" and the claims are trusted. A user the store *has seen* and
    # that is now gone is a deletion, and is rejected.
    try:
        known = user_store.has_ever_seen(username)
        user = user_store.get(username, seed=False)
    except Exception as exc:  # pragma: no cover - store must not break requests
        logger.warning("User-store lookup for {!r} failed ({}); trusting token claims", username, exc)
        known, user = False, None
    if user is None and known:
        logger.warning("User {!r} was removed after its token was issued; rejecting", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user is not None:
        if ROLE_RANK.get(role, 0) > ROLE_RANK.get(user.role, 0):
            logger.warning(
                "Token role {!r} exceeds stored role {!r} for {!r}; rejecting",
                role, user.role, username,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is no longer valid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # A lower or equal stored role is honoured: a user promoted since the
        # token was minted immediately gets the higher stored role.
        role = user.role
    return Principal(username=username, role=role, authenticated=True)


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
