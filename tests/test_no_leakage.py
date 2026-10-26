"""Fail-closed provenance tests.

Structure (Stage 3, Rev. 6):
  * ``T1a/T2a/T3a/T8``  - manifest/provenance gates on the real artifacts;
  * ``T1b``             - substantive invariant: full-corpus exact normalised-text
                          containment of every corpus row in the held-out corpus;
  * ``T1c``             - near-duplicate heuristic, REPORTED ONLY (never proof);
  * ``T1d``             - source lineage: train and held-out document ids are disjoint;
  * ``T2b/T3b``         - manifest content assertions (require manifests);
  * ``F1-F4``           - isolated ``tmp_path`` fixtures proving the machinery works
                          and that verification never extracts archives.

Isolation: no writes to ``data/processed/``; temporary fixtures only; no archive
extraction; no service startup; no git; no network.

Artifact-dependent tests FAIL when an artifact exists but violates provenance (that
is the point), FAIL when a required input is missing in CI mode, and SKIP with an
explicit reason only when the artifact is absent in exploratory mode.
"""
from __future__ import annotations

import csv
import functools
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

from nlp import provenance
from nlp.datasets import cuad as cuad_mod
from nlp.datasets import splits
from nlp.datasets.manifest import build_manifest, load_manifest, verify, write_manifest
from nlp.datasets.splits import ProvenanceError, SourceSpec, resolve_source, validate_training_sources

pytestmark = pytest.mark.provenance

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CUAD = ROOT / "data" / "datasets" / "cuad"
CI_MODE = os.environ.get("BCC_EVAL_MODE", "").lower() == "ci"
SHINGLE = 8
NEAR_DUP_THRESHOLD = 0.80


def _require(path: Path) -> Path:
    if path.exists():
        return path
    if CI_MODE:
        pytest.fail(f"required provenance input missing in CI mode: {path}")
    pytest.skip(f"artifact absent; exploratory mode only (set BCC_EVAL_MODE=ci): {path}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


@functools.lru_cache(maxsize=1)
def _held_docs() -> tuple[str, ...]:
    with (CUAD / "test.json").open(encoding="utf-8") as fh:
        data = json.load(fh)
    return tuple(
        _norm(" ".join(p.get("context", "") for p in doc.get("paragraphs", [])))
        for doc in data["data"]
    )


@functools.lru_cache(maxsize=1)
def _held_concat() -> str:
    # " ||| " sentinel prevents a match spanning two documents.
    return " ||| ".join(_held_docs())


def _shingles(text: str, k: int = SHINGLE) -> set[int]:
    toks = text.split()
    return {hash(" ".join(toks[i : i + k])) for i in range(max(0, len(toks) - k + 1))}


@functools.lru_cache(maxsize=1)
def _held_index() -> frozenset[int]:
    return frozenset(_shingles(_held_concat()))


def _corpus_rows(path: Path):
    csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8") as fh:
        for idx, row in enumerate(csv.DictReader(fh)):
            yield idx, _norm(row.get("text"))


# --------------------------------------------------------------------------- T1

def test_t1a_training_corpus_has_train_only_provenance():
    corpus = _require(PROCESSED / "clause_classifier.csv")
    result = verify(corpus, allowed_splits=("train",), require=True, deep=True)
    assert result["ok"]


def test_t1b_full_corpus_has_no_exact_held_out_text():
    """Exact invariant: no corpus row occurs verbatim in a held-out document.

    Candidate filter (exact, not approximate): containment implies the row's first
    ``SHINGLE`` tokens occur in the held-out corpus, so rows whose first shingle is
    absent cannot be contained. Hash collisions only add exact checks.
    """
    corpus = _require(PROCESSED / "clause_classifier.csv")
    held = _held_concat()
    index = _held_index()
    flagged: list[tuple[int, str]] = []
    total = 0
    for idx, text in _corpus_rows(corpus):
        if not text:
            continue
        total += 1
        toks = text.split()
        if len(toks) >= SHINGLE and hash(" ".join(toks[:SHINGLE])) not in index:
            continue
        if text in held:
            flagged.append((idx, text[:80]))
    assert not flagged, (
        f"{len(flagged)}/{total} corpus rows occur verbatim in held-out documents "
        f"(first 5: {flagged[:5]})"
    )


def test_t1c_near_duplicate_heuristic_is_reported_not_asserted(capsys):
    """Report-only heuristic. It does NOT prove absence of leakage."""
    corpus = _require(PROCESSED / "clause_classifier.csv")
    index = _held_index()
    shares: list[float] = []
    for _, text in _corpus_rows(corpus):
        toks = text.split()
        if len(toks) < SHINGLE:
            continue
        row_shingles = _shingles(text)
        if row_shingles:
            shares.append(len(row_shingles & index) / len(row_shingles))
    n = len(shares)
    mean = (sum(shares) / n) if n else 0.0
    peak = max(shares) if shares else 0.0
    high = sum(1 for s in shares if s >= NEAR_DUP_THRESHOLD)
    print(
        f"[T1c] near-duplicate heuristic (k={SHINGLE}, threshold={NEAR_DUP_THRESHOLD}): "
        f"rows={n} mean_share={mean:.3f} max_share={peak:.3f} rows>=threshold={high}"
    )
    # Sanity only - this is not a leakage assertion and not a proof of absence.
    assert 0.0 <= mean <= 1.0 and 0.0 <= peak <= 1.0


def test_t1d_source_lineage_train_and_held_out_are_disjoint():
    train = cuad_mod.doc_ids(CUAD / "train_separate_questions.json")
    held = cuad_mod.doc_ids(CUAD / "test.json")
    whole = cuad_mod.doc_ids(CUAD / "CUADv1.json")
    assert not (set(train) & set(held)), "train and held-out share document titles"
    assert not (set(train.values()) & set(held.values())), "train and held-out share document text"
    assert set(train.values()) <= set(whole.values())
    assert set(held.values()) <= set(whole.values())
    assert splits.ALLOWLIST_AUTHENTICATION["upstream_authenticated"] is False


# --------------------------------------------------------------------------- T2

def test_t2a_keyword_bank_is_provenance_verified():
    bank = _require(PROCESSED / "cuad_keyword_bank.json")
    assert verify(bank, allowed_splits=("train",), require=True, deep=True)["ok"]


def test_t2b_keyword_bank_manifest_declares_train_only():
    bank = _require(PROCESSED / "cuad_keyword_bank.json")
    manifest = load_manifest(bank)
    assert manifest and manifest.get("sources"), "keyword bank has no manifest sources"
    for source in manifest["sources"]:
        assert source["split"] == "train"
        assert not str(source["path"]).endswith("test.json")
    assert manifest.get("source_authentication", {}).get("upstream_authenticated") is False


# --------------------------------------------------------------------------- T3

def test_t3a_maud_artifacts_have_manifests():
    for name in ("maud_examples.jsonl", "unified_examples.jsonl"):
        artifact = _require(PROCESSED / name)
        assert load_manifest(artifact), f"{name} has no manifest"


def test_t3b_maud_artifacts_exclude_test_split():
    for name in ("maud_examples.jsonl", "unified_examples.jsonl"):
        artifact = _require(PROCESSED / name)
        manifest = load_manifest(artifact)
        assert manifest, f"{name} has no manifest"
        seen = {source["split"] for source in manifest.get("sources") or []}
        assert "test" not in seen, f"{name} was built from a test split: {seen}"


# --------------------------------------------------------------------------- T8

def test_t8_cuad_examples_provenance():
    artifact = _require(PROCESSED / "cuad_examples.jsonl")
    assert verify(artifact, allowed_splits=("train",), require=True, deep=True)["ok"]


# ------------------------------------------------------- T4-T7 (guard behaviour)

def test_t4_whole_corpus_requires_explicit_flag():
    args = (
        "data/datasets/cuad/CUADv1.json",
        "data/datasets/cuad/test.json",
        "data/datasets/maud/data/MAUD_train.csv",
        "data/datasets/maud/data/MAUD_dev.csv",
    )
    with pytest.raises(ProvenanceError, match="allow-whole-corpus"):
        validate_training_sources(*args, allow_whole_corpus=False)
    assert validate_training_sources(*args, allow_whole_corpus=True)["cuad_train"].split == "mixed"
    with pytest.raises(ProvenanceError, match="test split"):
        validate_training_sources(
            "data/datasets/cuad/test.json",
            "data/datasets/cuad/test.json",
            "data/datasets/maud/data/MAUD_train.csv",
            "data/datasets/maud/data/MAUD_dev.csv",
        )


def test_t5_missing_source_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(splits, "_existing", lambda p: tmp_path / "absent.json")
    with pytest.raises(ProvenanceError, match="missing"):
        resolve_source("data/datasets/cuad/test.json")


def test_t6_drifted_source_fails_closed(monkeypatch, tmp_path):
    raw = (CUAD / "test.json").read_bytes()
    drifted = tmp_path / "test_copy.json"
    drifted.write_bytes(raw[:-1] + bytes([raw[-1] ^ 0xFF]))
    key = splits.normalise_path(drifted)
    spec = splits.SOURCE_ALLOWLIST["data/datasets/cuad/test.json"]
    monkeypatch.setitem(splits.SOURCE_ALLOWLIST, key, SourceSpec(key, spec.split, spec.sha256))
    with pytest.raises(ProvenanceError, match="hash drift"):
        splits.resolve_source(drifted)


def _load_eval_module():
    path = ROOT / "scripts" / "eval_classifier.py"
    spec = importlib.util.spec_from_file_location("_bcc_eval_classifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t7_evaluation_cannot_claim_benchmark_without_provenance(monkeypatch, tmp_path):
    module = _load_eval_module()
    assert "NOT A BENCHMARK" in module.BANNER
    corpus = tmp_path / "corpus.csv"
    corpus.write_text("text,category,source\npay within 30 days,Payment Terms,cuad\n", encoding="utf-8")
    info = module.describe_input(corpus, require_provenance=True)
    assert info["provenance"] == "unverified"
    assert "manifest" in info.get("provenance_error", "").lower()
    monkeypatch.setattr(sys, "argv", ["eval_classifier.py", "--input", str(corpus), "--require-provenance"])
    assert module.main() == 3


# ------------------------------------------------------------------- F1-F4 (isolated fixtures)

def _tmp_artifact_with_manifest(tmp_path: Path, *, source_split: str = "train") -> Path:
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("text,category\npay within 30 days,Payment Terms\n", encoding="utf-8")
    train = splits.SOURCE_ALLOWLIST["data/datasets/cuad/train_separate_questions.json"]
    source = {"path": train.path, "sha256": train.sha256, "split": source_split}
    write_manifest(artifact, build_manifest(artifact, sources=[source], row_count=1))
    return artifact


def test_f1_valid_manifest_passes(tmp_path):
    artifact = _tmp_artifact_with_manifest(tmp_path)
    assert verify(artifact, allowed_splits=("train",), require=True, deep=True)["ok"]


def test_f2_test_split_source_is_rejected(tmp_path):
    artifact = _tmp_artifact_with_manifest(tmp_path, source_split="test")
    with pytest.raises(ProvenanceError, match="split 'test'"):
        verify(artifact, allowed_splits=("train",), require=True, deep=True)


def test_f3_verification_never_extracts_archives(monkeypatch, tmp_path):
    import py7zr

    import nlp.clause_classification.tfidf_model as tfidf_model
    import nlp.risk_scoring.risk_model as risk_model

    class _Boom:
        def __init__(self, *a, **k):
            raise AssertionError("archive extraction attempted during provenance verification")

    def _boom(*a, **k):
        raise AssertionError("ensure_model_file() called during provenance verification")

    monkeypatch.setattr(py7zr, "SevenZipFile", _Boom)
    monkeypatch.setattr(tfidf_model, "ensure_model_file", _boom)
    monkeypatch.setattr(risk_model, "ensure_model_file", _boom)

    artifact = _tmp_artifact_with_manifest(tmp_path)
    assert verify(artifact, allowed_splits=("train",), require=True, deep=True)["ok"]


def test_f4_loaded_model_status_tracks_exact_joblib_bytes(tmp_path):
    provenance.reset()
    fake_cache = tmp_path / "tfidf_classifier.joblib"
    fake_cache.write_bytes(b"deliberately-not-the-declared-cache")
    entry = provenance.record_loaded_model("tfidf_classifier.7z", fake_cache)
    assert entry["status"] == provenance.STATUS_UNVERIFIED
    assert "cache-drift" in entry["reason"]
    assert entry["declared_cache_sha256"] and entry["loaded_sha256"]
    assert entry["declared_cache_sha256"] != entry["loaded_sha256"]
    assert entry["loaded_path"] == str(fake_cache)
    provenance.reset()


def test_provenance_registry_surfaces_absent_artifacts(tmp_path):
    provenance.reset()
    entry = provenance.record("unit-test.json", path=tmp_path / "nope.json", kind="model")
    assert entry["status"] == provenance.STATUS_ABSENT
    assert any("PROVENANCE_ABSENT" in token for token in provenance.warnings())
    assert provenance.summary()["upstream_authenticated"] is False
    provenance.reset()


# --------------------------------------- L1-L5: row-level lineage (adversarial)
# These prove that a *forged manifest* cannot rescue an artifact whose rows come
# from unknown/held-out documents. No text-similarity inference is used.

def _load_verify_module():
    path = ROOT / "scripts" / "verify_provenance.py"
    spec = importlib.util.spec_from_file_location("_bcc_verify_provenance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, rows: list[dict]) -> Path:
    columns = ("text", "category", "source", "doc_id", "split")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    return path


def _train_title() -> str:
    return sorted(cuad_mod.doc_ids(CUAD / "train_separate_questions.json"))[0]


def _held_title() -> str:
    return sorted(cuad_mod.doc_ids(CUAD / "test.json"))[0]


def test_l1_lineage_accepts_training_rows(tmp_path):
    module = _load_verify_module()
    art = _write_csv(
        tmp_path / "clause_classifier.csv",
        [{"text": "pay within 30 days", "category": "Payment Terms", "source": "cuad",
          "doc_id": _train_title(), "split": "train"}],
    )
    assert module.check_csv_lineage(art, ("train",))["rows"] == 1


def test_l2_lineage_rejects_injected_held_out_document(tmp_path):
    module = _load_verify_module()
    art = _write_csv(
        tmp_path / "clause_classifier.csv",
        [{"text": "x", "category": "Payment Terms", "source": "cuad",
          "doc_id": _held_title(), "split": "train"}],
    )
    with pytest.raises(ProvenanceError, match="held-out document"):
        module.check_csv_lineage(art, ("train",))


def test_l3_lineage_rejects_missing_columns(tmp_path):
    module = _load_verify_module()
    art = tmp_path / "clause_classifier.csv"
    art.write_text("text,category\nx,Payment Terms\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="missing lineage columns"):
        module.check_csv_lineage(art, ("train",))


def test_l4_lineage_rejects_non_training_split(tmp_path):
    module = _load_verify_module()
    art = _write_csv(
        tmp_path / "clause_classifier.csv",
        [{"text": "x", "category": "Payment Terms", "source": "cuad",
          "doc_id": _train_title(), "split": "test"}],
    )
    with pytest.raises(ProvenanceError, match="not permitted"):
        module.check_csv_lineage(art, ("train",))


def test_l5_forged_manifest_cannot_rescue_invalid_artifact(tmp_path):
    module = _load_verify_module()
    art = _write_csv(
        tmp_path / "clause_classifier.csv",
        [{"text": "x", "category": "Payment Terms", "source": "cuad",
          "doc_id": _held_title(), "split": "train"}],
    )
    spec = splits.SOURCE_ALLOWLIST["data/datasets/cuad/train_separate_questions.json"]
    write_manifest(
        art,
        build_manifest(
            art,
            sources=[{"path": spec.path, "sha256": spec.sha256, "split": "train"}],
            row_count=1,
        ),
    )
    # The forged manifest alone passes ...
    assert verify(art, allowed_splits=("train",), require=True, deep=True)["ok"]
    # ... but row lineage still fails, so the artifact cannot be accepted.
    with pytest.raises(ProvenanceError, match="held-out document"):
        module.verify_artifact(art, ("train",))
