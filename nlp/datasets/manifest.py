"""Provenance manifests for generated artifacts.

A manifest records where an artifact's rows came from: the source files (with
SHA-256 and split identity), the build command, the code revision, and the
artifact's own hash. ``verify`` fails closed when provenance is missing,
inconsistent, or derived from held-out data.

A manifest is a data-lineage record. It is **not** evidence of model accuracy or
predictive validity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Sequence

from nlp.datasets.splits import (
    ALLOWLIST_AUTHENTICATION,
    ProvenanceError,
    normalise_path,
    resolve_source,
    sha256_file,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SUFFIX = ".manifest.json"


def manifest_path(artifact) -> Path:
    return Path(str(artifact) + MANIFEST_SUFFIX)


def code_revision(project_root: Optional[Path] = None) -> Optional[str]:
    """Best-effort git revision read directly from ``.git`` (no subprocess)."""
    root = Path(project_root) if project_root else PROJECT_ROOT
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = root / ".git" / head[5:]
            return ref.read_text(encoding="utf-8").strip()
        return head or None
    except Exception:
        return None


def source_record(path) -> dict:
    """Describe a source file for a manifest (path, hash, split, doc count later)."""
    spec = resolve_source(path)
    return {
        "path": spec.path,
        "sha256": spec.sha256,
        "split": spec.split,
    }


def build_manifest(
    artifact,
    *,
    sources: Sequence[dict],
    command: Optional[str] = None,
    row_count: Optional[int] = None,
    label_counts: Optional[dict] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Compose a manifest dict for ``artifact`` (does not write)."""
    artifact_path = Path(artifact)
    manifest = {
        "artifact": normalise_path(artifact_path),
        "artifact_sha256": sha256_file(artifact_path) if artifact_path.exists() else None,
        "code_revision": code_revision(),
        "command": command,
        "sources": list(sources),
        "source_authentication": ALLOWLIST_AUTHENTICATION,
        "row_count": row_count,
        "label_counts": label_counts or {},
    }
    if extra:
        manifest["extra"] = extra
    return manifest


def write_manifest(artifact, manifest: dict) -> Path:
    out = manifest_path(artifact)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return out


def load_manifest(artifact) -> Optional[dict]:
    out = manifest_path(artifact)
    if not out.exists():
        return None
    try:
        with out.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def verify(
    artifact,
    *,
    allowed_splits: Iterable[str] = ("train",),
    require: bool = True,
    deep: bool = True,
) -> dict:
    """Verify an artifact's provenance, failing closed.

    Args:
        artifact: path to the generated artifact.
        allowed_splits: splits permitted in the manifest's sources.
        require: when True (default) a missing manifest raises.
        deep: when True, re-hash the source files (catches drifted inputs);
              when False only the recorded split/hash metadata is checked.
    """
    artifact_path = Path(artifact)
    allowed = frozenset(allowed_splits)
    manifest = load_manifest(artifact_path)
    if manifest is None:
        if require:
            raise ProvenanceError(f"manifest missing for {normalise_path(artifact_path)}")
        return {"ok": False, "reason": "manifest-missing", "artifact": normalise_path(artifact_path)}

    problems = []
    if artifact_path.exists() and manifest.get("artifact_sha256"):
        actual = sha256_file(artifact_path)
        if actual != manifest["artifact_sha256"]:
            problems.append(
                f"artifact hash drift: expected {manifest['artifact_sha256']}, actual {actual}"
            )

    for source in manifest.get("sources") or []:
        split = source.get("split")
        if split not in allowed:
            problems.append(f"source {source.get('path')} has split '{split}' (allowed: {sorted(allowed)})")
        if deep:
            try:
                spec = resolve_source(source.get("path"))
            except ProvenanceError as exc:
                problems.append(str(exc))
                continue
            if source.get("sha256") and spec.sha256 != source.get("sha256"):
                problems.append(
                    f"recorded source hash for {spec.path} does not match the allowlist"
                )

    if problems:
        raise ProvenanceError(
            "provenance verification failed for "
            f"{normalise_path(artifact_path)}: " + "; ".join(problems)
        )
    return {
        "ok": True,
        "artifact": normalise_path(artifact_path),
        "allowed_splits": sorted(allowed),
        "deep": deep,
        "source_count": len(manifest.get("sources") or []),
    }
