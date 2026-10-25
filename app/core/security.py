"""Authentication & authorisation primitives.

Passwords are hashed with ``bcrypt`` when the library is importable, falling
back to a stdlib PBKDF2-HMAC-SHA256 scheme so the module never hard-fails for a
missing/broken binary dependency. Access tokens are signed JWTs (python-jose).

Auth is **off by default** (``AUTH_ENABLED=false``) so the demo keeps working
with zero configuration; enable it to require bearer tokens on write routes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import utcnow

logger = get_logger()

try:  # pragma: no cover - depends on environment
    import bcrypt  # type: ignore

    _BCRYPT_AVAILABLE = True
except Exception:  # pragma: no cover
    _BCRYPT_AVAILABLE = False

try:  # pragma: no cover
    from jose import jwt  # type: ignore

    _JOSE_AVAILABLE = True
except Exception:  # pragma: no cover
    _JOSE_AVAILABLE = False

PBKDF2_ITERATIONS = 260_000
_ALGORITHM = "HS256"

# Role hierarchy: a higher rank may perform everything a lower rank may.
ROLE_RANK = {"viewer": 1, "analyst": 2, "admin": 3}


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a salted hash for ``password`` (bcrypt, else PBKDF2)."""
    if _BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return _pbkdf2_hash(password)


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of ``password`` against a stored hash."""
    if not stored:
        return False
    if stored.startswith("$2"):  # bcrypt format
        if not _BCRYPT_AVAILABLE:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return _pbkdf2_verify(password, stored)


def _pbkdf2_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _pbkdf2_verify(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------


@dataclass
class User:
    """An authenticated principal."""

    username: str
    role: str
    hashed_password: str


class UserStore:
    """Process-local user store seeded from configuration.

    Users come from ``AUTH_USERS`` (a JSON list) when provided; otherwise a
    single ``admin`` account is seeded from ``AUTH_ADMIN_PASSWORD`` (default
    ``admin``) so the deployment is usable out of the box.
    """

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        self._seeded = False

    def reset(self) -> None:
        """Drop all users and force re-seeding (used by tests)."""
        self._users = {}
        self._seeded = False

    def _seed(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        settings = get_settings()
        raw = (settings.auth_users or "").strip()
        if raw:
            try:
                for entry in json.loads(raw):
                    username = str(entry["username"])
                    self._users[username] = User(
                        username=username,
                        role=str(entry.get("role", "viewer")),
                        hashed_password=hash_password(str(entry["password"])),
                    )
                logger.info("Loaded {} auth user(s) from AUTH_USERS", len(self._users))
                return
            except Exception as exc:
                logger.warning("AUTH_USERS could not be parsed ({}); seeding defaults.", exc)
        self._users["admin"] = User(
            username="admin",
            role="admin",
            hashed_password=hash_password(settings.auth_admin_password or "admin"),
        )
        logger.warning(
            "Auth enabled with a seeded 'admin' account. Set AUTH_USERS or "
            "AUTH_ADMIN_PASSWORD before exposing this service."
        )

    def get(self, username: str) -> Optional[User]:
        self._seed()
        return self._users.get(username)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.get(username)
        if user and verify_password(password, user.hashed_password):
            return user
        return None

    def all(self) -> List[User]:
        self._seed()
        return list(self._users.values())


user_store = UserStore()


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def create_access_token(username: str, role: str) -> tuple[str, int]:
    """Return ``(jwt, expires_in_seconds)`` for a user."""
    settings = get_settings()
    expires_minutes = settings.auth_token_expire_minutes
    if not _JOSE_AVAILABLE:  # pragma: no cover
        raise RuntimeError("python-jose is not installed; cannot issue tokens")
    now = utcnow()
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    token = jwt.encode(payload, settings.auth_secret_key, algorithm=_ALGORITHM)
    return token, expires_minutes * 60


def decode_access_token(token: str) -> Optional[dict]:
    """Return the token claims, or ``None`` if invalid/expired."""
    if not _JOSE_AVAILABLE:  # pragma: no cover
        return None
    settings = get_settings()
    try:
        return jwt.decode(token, settings.auth_secret_key, algorithms=[_ALGORITHM])
    except Exception:
        return None


def role_allows(user_role: str, allowed: List[str]) -> bool:
    """True if ``user_role`` meets any of the required roles.

    Roles are ranked, so ``admin`` satisfies a requirement of ``analyst``.
    """
    user_rank = ROLE_RANK.get(user_role, 0)
    return any(user_rank >= ROLE_RANK.get(role, 99) for role in allowed)
