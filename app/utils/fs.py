"""Filesystem helpers for upload management."""
from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Tuple

from app.core.config import get_settings
from app.core.exceptions import DocumentParseError

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    """Sanitise a filename while preserving extension."""
    name = name.strip().replace(" ", "_")
    name = _SAFE_NAME_RE.sub("_", name)
    return name[:200] or "file"


def save_upload(file_bytes: bytes, original_name: str) -> Tuple[Path, str]:
    """Save uploaded bytes to disk and return (path, contract_id).

    contract_id is derived from a hash of the content + a timestamp, ensuring
    uniqueness even when the same file is uploaded multiple times in the same
    second.
    """
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(file_bytes).hexdigest()[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    contract_id = f"c_{timestamp}_{digest}"

    sanitised = safe_filename(original_name)
    target = upload_dir / f"{contract_id}_{sanitised}"
    try:
        target.write_bytes(file_bytes)
    except OSError as exc:
        raise DocumentParseError(f"Failed to persist upload: {exc}") from exc
    return target, contract_id


def derive_title_from_filename(filename: str) -> str:
    """Make a human-friendly title from an uploaded filename."""
    stem = Path(filename).stem
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "Untitled Contract"


def remove_path_safely(path: str | Path) -> None:
    """Remove a file/directory, ignoring missing-path errors."""
    try:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    except OSError:
        # We deliberately swallow errors during cleanup.
        pass


def unique_id(prefix: str = "id") -> str:
    """Return a short unique identifier with a prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"
