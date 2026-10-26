"""Dataset split identity: a hash-pinned source allowlist.

Split identity is resolved from the *file* (path + SHA-256), never from a
caller-supplied label, so a renamed copy or a drifted dataset fails closed.

Authentication note: the hashes below were computed locally from the checked-out
files and cross-validated only by internal partition consistency
(``train ∪ test = CUADv1`` on distinct normalized texts). No upstream CUAD
checksum was consulted, so these entries are **not** authenticated against the
upstream release. That limitation is machine-readable via
``ALLOWLIST_AUTHENTICATION``.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ALLOWLIST_AUTHENTICATION: dict = {
    "upstream_authenticated": False,
    "basis": "internal-partition-consistency",
    "source": None,
    "checked_at": None,
    "note": (
        "Hashes computed locally from the checkout and validated only by internal "
        "partition consistency (train union test == CUADv1 on distinct normalized "
        "texts). No upstream CUAD checksum was consulted. Internal consistency "
        "does not prove upstream authenticity."
    ),
}

TRAINING_SPLITS = frozenset({"train"})
NON_TRAINING_SPLITS = frozenset({"dev", "test", "mixed"})


class ProvenanceError(RuntimeError):
    """Raised when source identity cannot be established or a split is misused."""


@dataclass(frozen=True)
class SourceSpec:
    """An allowlisted source file and the split it represents."""

    path: str
    split: str
    sha256: str

    @property
    def is_training(self) -> bool:
        return self.split in TRAINING_SPLITS


SOURCE_ALLOWLIST: Dict[str, SourceSpec] = {
    "data/datasets/cuad/CUADv1.json": SourceSpec(
        "data/datasets/cuad/CUADv1.json",
        "mixed",
        "ed0b77d85bdf4014d7495800e8e4a70565b48ee6f8a2e5dca9cf8655dbf10eae",
    ),
    "data/datasets/cuad/train_separate_questions.json": SourceSpec(
        "data/datasets/cuad/train_separate_questions.json",
        "train",
        "7de21d2bb741ac939e2a839ef9640634a5e0f9f40ea2b82c6833baf7db33dab4",
    ),
    "data/datasets/cuad/test.json": SourceSpec(
        "data/datasets/cuad/test.json",
        "test",
        "007b6a40b0c65247f881627375c3d2e9b6aeeb5dfa89957494feed0765a1a073",
    ),
    "data/datasets/maud/data/MAUD_train.csv": SourceSpec(
        "data/datasets/maud/data/MAUD_train.csv",
        "train",
        "43b0989a68a774c8a43cd83de22a238902eb633f72395e15980215d3ae71a95d",
    ),
    "data/datasets/maud/data/MAUD_dev.csv": SourceSpec(
        "data/datasets/maud/data/MAUD_dev.csv",
        "dev",
        "b183f9685ceb4f8cc67e09c2dd00a8bb2608ee7cbf77b6a889d22eb4a186155f",
    ),
    "data/datasets/maud/data/MAUD_test.csv": SourceSpec(
        "data/datasets/maud/data/MAUD_test.csv",
        "test",
        "6360b510059619c1d7aeea9ac1e7794080862dfd73ae24a8cebb2d7d45af741a",
    ),
}


def normalise_path(path) -> str:
    """Return a project-root-relative, forward-slash key for ``path``."""
    p = str(path).replace("\\", "/")
    root = str(PROJECT_ROOT).replace("\\", "/").rstrip("/") + "/"
    if p.startswith(root):
        p = p[len(root):]
    while p.startswith("./"):
        p = p[2:]
    return p


def sha256_file(path) -> str:
    """Stream a file through SHA-256."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing(path) -> Path:
    fp = Path(path)
    if fp.exists():
        return fp
    alt = PROJECT_ROOT / normalise_path(path)
    if alt.exists():
        return alt
    return fp


def resolve_source(path, *, verify_hash: bool = True) -> SourceSpec:
    """Resolve ``path`` to its allowlisted spec, failing closed on any doubt."""
    key = normalise_path(path)
    spec = SOURCE_ALLOWLIST.get(key)
    if spec is None:
        raise ProvenanceError(f"source not allowlisted: {key}")
    fp = _existing(path)
    if not fp.exists():
        raise ProvenanceError(f"source missing: {key}")
    if verify_hash:
        actual = sha256_file(fp)
        if actual != spec.sha256:
            raise ProvenanceError(
                f"source hash drift for {key}: expected {spec.sha256}, actual {actual}"
            )
    return spec


def resolve_split(path, *, verify_hash: bool = True) -> str:
    """Return the split for ``path`` (never trust a caller-supplied label)."""
    return resolve_source(path, verify_hash=verify_hash).split


def assert_training_source(path, *, verify_hash: bool = True) -> SourceSpec:
    """Require ``path`` to be an allowlisted *training* source."""
    spec = resolve_source(path, verify_hash=verify_hash)
    if not spec.is_training:
        raise ProvenanceError(
            f"source {spec.path} has split '{spec.split}'; training requires 'train'"
        )
    return spec


def validate_training_sources(
    cuad_train,
    cuad_test,
    maud_train,
    maud_dev,
    *,
    allow_whole_corpus: bool = False,
) -> dict:
    """Resolve and validate every source, failing closed.

    Held-out (test) sources are recorded but never permitted for training.
    """
    cuad_spec = resolve_source(cuad_train)
    if cuad_spec.split == "test":
        raise ProvenanceError(
            f"refusing to build training data from the CUAD test split: {cuad_spec.path}"
        )
    if cuad_spec.split == "mixed" and not allow_whole_corpus:
        raise ProvenanceError(
            "whole-corpus source requires --allow-whole-corpus: "
            f"{cuad_spec.path} embeds the held-out documents"
        )
    test_spec = resolve_source(cuad_test)
    if test_spec.split != "test":
        raise ProvenanceError(
            f"expected the CUAD test split for the held-out source, got split '{test_spec.split}'"
        )
    maud_train_spec = resolve_source(maud_train)
    if maud_train_spec.split != "train":
        raise ProvenanceError(
            f"MAUD training source must have split 'train', got '{maud_train_spec.split}'"
        )
    maud_dev_spec = resolve_source(maud_dev)
    if maud_dev_spec.split != "dev":
        raise ProvenanceError(f"MAUD dev source must have split 'dev', got '{maud_dev_spec.split}'")
    return {
        "cuad_train": cuad_spec,
        "cuad_test": test_spec,
        "maud_train": maud_train_spec,
        "maud_dev": maud_dev_spec,
    }
