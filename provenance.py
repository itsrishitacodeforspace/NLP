"""Runtime provenance surface.

Single place that answers "is the artifact I just loaded provenance-verified?"
for the runtime keyword bank and the two bundled model archives, and formats the
machine-readable tokens surfaced through analysis warnings, ``/healthz`` and logs.

A provenance verdict is a **data-lineage** statement only. It says nothing about
evaluation results or predictive validity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "models"
STATUS_PATH = MODEL_DIR / "PROVENANCE_STATUS.json"

TOKEN_VERIFIED = "PROVENANCE_VERIFIED"
TOKEN_UNVERIFIED = "PROVENANCE_UNVERIFIED"
TOKEN_ABSENT = "PROVENANCE_ABSENT"

STATUS_VERIFIED = "verified"
STATUS_UNVERIFIED = "provenance-unverified"
STATUS_ABSENT = "absent"
STATUS_UNKNOWN = "unknown"

_HASH_CACHE: Dict[str, str] = {}
_REGISTRY: Dict[str, dict] = {}


def sha256_cached(path) -> Optional[str]:
    """SHA-256 of ``path``, cached per process (never raises)."""
    key = str(path)
    if key in _HASH_CACHE:
        return _HASH_CACHE[key]
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        _HASH_CACHE[key] = digest.hexdigest()
        return _HASH_CACHE[key]
    except Exception:
        return None


def load_status() -> dict:
    """Read ``models/PROVENANCE_STATUS.json``; empty dict when unavailable."""
    try:
        with STATUS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def artifact_status(name: str) -> dict:
    """Declared status for a model archive, e.g. ``tfidf_classifier.7z``."""
    entry = (load_status().get("artifacts") or {}).get(name) or {}
    return {
        "status": entry.get("status", STATUS_UNKNOWN),
        "reason": entry.get("reason", ""),
    }


def token(name: str, status: str) -> str:
    """Stable, parseable token used in warnings and logs."""
    if status == STATUS_VERIFIED:
        kind = TOKEN_VERIFIED
    elif status == STATUS_ABSENT:
        kind = TOKEN_ABSENT
    else:
        kind = TOKEN_UNVERIFIED
    return f"{kind}[artifact={name};status={status}]"


def _log_entry(entry: dict) -> None:
    """Log the provenance verdict once, with the same machine-readable token."""
    try:
        from app.core.logging import get_logger

        log = get_logger()
        marker = token(entry.get("name", "?"), entry.get("status", STATUS_UNKNOWN))
        if entry.get("status") == STATUS_VERIFIED:
            log.info("{} path={} sha256={}", marker, entry.get("path"), entry.get("sha256"))
        else:
            log.warning("{} path={} reason={}", marker, entry.get("path"), entry.get("reason"))
    except Exception:  # pragma: no cover - logging must never break loading
        pass


def record(name: str, *, path=None, kind: str = "model", status: Optional[str] = None, reason: Optional[str] = None) -> dict:
    """Register the *actually loaded* artifact for the runtime surface.

    Reports the loaded path and its hash. Never extracts or mutates anything:
    when ``path`` is missing the status is ``absent``. For models the declared
    status comes from ``PROVENANCE_STATUS.json``; callers may override
    ``status``/``reason`` (e.g. after a manifest check).
    """
    if path is None or not Path(path).exists():
        entry = {
            "name": name,
            "kind": kind,
            "status": STATUS_ABSENT,
            "reason": "artifact not present at load time",
            "path": None,
            "sha256": None,
        }
    else:
        if status is None:
            declared = artifact_status(name) if kind == "model" else {}
            status = declared.get("status", STATUS_VERIFIED) or STATUS_VERIFIED
            reason = declared.get("reason", "")
        entry = {
            "name": name,
            "kind": kind,
            "status": status,
            "reason": reason or "",
            "path": str(path),
            "sha256": sha256_cached(path),
        }
    _REGISTRY[name] = entry
    _log_entry(entry)
    return entry


def record_loaded_model(archive_name: str, loaded_path) -> dict:
    """Register a model artifact tied to the **exact .joblib bytes executed**.

    The declared status comes from the archive entry in ``PROVENANCE_STATUS.json``,
    but if that entry declares a ``cache_sha256`` and the loaded cache differs,
    the verdict is downgraded to ``provenance-unverified`` with
    ``reason=cache-drift``. Never extracts or mutates anything.
    """
    entry_declared = (load_status().get("artifacts") or {}).get(archive_name) or {}
    status = entry_declared.get("status", STATUS_UNKNOWN) or STATUS_UNKNOWN
    reason = entry_declared.get("reason", "")
    loaded_sha = sha256_cached(loaded_path) if loaded_path and Path(loaded_path).exists() else None
    declared_cache = entry_declared.get("cache_sha256")
    if loaded_sha is None:
        status, reason = STATUS_ABSENT, "loaded artifact not present"
    elif declared_cache and declared_cache != loaded_sha:
        status = STATUS_UNVERIFIED
        reason = "cache-drift: loaded .joblib bytes differ from the declared cache hash"
    entry = {
        "name": archive_name,
        "kind": "model",
        "status": status,
        "reason": reason,
        "path": str(loaded_path) if loaded_path else None,
        "loaded_path": str(loaded_path) if loaded_path else None,
        "loaded_sha256": loaded_sha,
        "archive": archive_name,
        "declared_cache_sha256": declared_cache,
    }
    _REGISTRY[archive_name] = entry
    _log_entry(entry)
    return entry


def registry() -> Dict[str, dict]:
    return dict(_REGISTRY)


def summary() -> dict:
    """Machine-readable provenance block for ``/healthz``."""
    return {
        "upstream_authenticated": False,
        "artifacts": registry(),
    }


def warnings() -> List[str]:
    """Tokens for every registered artifact that is not provenance-verified."""
    return [
        token(entry["name"], entry["status"])
        for entry in _REGISTRY.values()
        if entry.get("status") != STATUS_VERIFIED
    ]


def reset() -> None:
    """Clear the in-process registry (tests only)."""
    _REGISTRY.clear()
    _HASH_CACHE.clear()
