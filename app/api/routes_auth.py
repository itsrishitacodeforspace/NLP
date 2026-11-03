"""Authentication routes: password login and identity lookup.

The ``/token`` endpoint is protected by a process-local, per-username failure
throttle: after ``TOKEN_MAX_FAILURES`` consecutive bad logins for a username,
further attempts for that username are rejected with **429** (Retry-After
hinted) until ``TOKEN_LOCKOUT_SECONDS`` have elapsed. A successful login
resets the counter. Counters live in process memory (they do not survive a
restart and are not shared across replicas — a single-process demo is the
supported deployment shape for this feature).
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import Principal, get_current_principal
from app.core.config import get_settings
from app.core.security import create_access_token, user_store
from app.models.schemas import TokenResponse, UserInfo

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Throttle tuning (module constants so tests can observe/override cheaply).
TOKEN_MAX_FAILURES = 5
TOKEN_LOCKOUT_SECONDS = 60.0

# username -> [consecutive_failures, monotonic_time_of_last_failure]
_token_failures: dict[str, list] = {}
_token_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _lockout_state(username: str) -> tuple[bool, float]:
    """Return ``(locked, remaining_seconds)`` for a username."""
    with _token_lock:
        entry = _token_failures.get(username)
        if not entry or entry[0] < TOKEN_MAX_FAILURES:
            return False, 0.0
        remaining = TOKEN_LOCKOUT_SECONDS - (_now() - entry[1])
        if remaining <= 0:
            # Window elapsed: the counter resets.
            del _token_failures[username]
            return False, 0.0
        return True, remaining


def _record_failure(username: str) -> None:
    with _token_lock:
        failures, last = _token_failures.get(username, [0, _now()])
        _token_failures[username] = [failures + 1, _now()]


def _record_success(username: str) -> None:
    with _token_lock:
        _token_failures.pop(username, None)


def _reset_token_throttle() -> None:
    """Clear all throttle state (test helper)."""
    with _token_lock:
        _token_failures.clear()


def _throttle_snapshot() -> dict:
    """Read-only copy of the throttle state (test helper)."""
    with _token_lock:
        return {u: [f, t] for u, (f, t) in _token_failures.items()}


@router.post("/token", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Exchange username/password for a bearer token.

    Throttled per username: ``TOKEN_MAX_FAILURES`` consecutive failures lock
    the username out for ``TOKEN_LOCKOUT_SECONDS`` (HTTP 429 with a
    ``Retry-After`` hint). The 429 (rather than a 401) is intentional and
    documented: it tells a *legitimate* user that their attempts are being
    throttled without revealing anything about credentials.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is disabled on this server.",
        )

    locked, remaining = _lockout_state(form.username)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts; please try again later.",
            headers={"Retry-After": str(int(remaining) + 1)},
        )

    user = user_store.authenticate(form.username, form.password)
    if user is None:
        _record_failure(form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _record_success(form.username)
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
