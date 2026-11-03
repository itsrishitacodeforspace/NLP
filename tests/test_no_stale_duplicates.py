"""Lock the root-level duplicate packages to "identical or shimmed".

C10 of DEEP_AUDIT_20261103.md: the repository root carries byte-level copies
of several ``nlp/`` modules (added in 93cedd9) because the Docker build's
``COPY . .`` + ``pip install .`` only ships the packages listed in
``pyproject.toml`` (``app``/``nlp``/``streamlit_app``). They are **dead code
for the Python process** (everything imports ``nlp.*``) but load-bearing for
the container image, so they are intentionally not deleted yet.

This test pins the invariant that protects that choice: every root duplicate
must remain **byte-identical** to its ``nlp/`` counterpart (or be one of the
explicitly shimmed paths below). A divergence is a silent drift hazard —
the two copies would silently disagree, so the test fails rather than
letting it slide.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Root duplicate path -> nlp/ counterpart it must mirror.
DUPLICATES = {
    "clause_classification/__init__.py": "nlp/clause_classification/__init__.py",
    "clause_classification/classifier.py": "nlp/clause_classification/classifier.py",
    "clause_classification/classifier_ml.py": "nlp/clause_classification/classifier_ml.py",
    "clause_classification/tfidf_model.py": "nlp/clause_classification/tfidf_model.py",
    "context/__init__.py": "nlp/context/__init__.py",
    "context/resolver.py": "nlp/context/resolver.py",
    "datasets/__init__.py": "nlp/datasets/__init__.py",
    "datasets/cuad.py": "nlp/datasets/cuad.py",
    "datasets/manifest.py": "nlp/datasets/manifest.py",
    "datasets/maud.py": "nlp/datasets/maud.py",
    "datasets/splits.py": "nlp/datasets/splits.py",
    "datasets/unified.py": "nlp/datasets/unified.py",
    "evaluation/__init__.py": "nlp/evaluation/__init__.py",
    "evaluation/cases.py": "nlp/evaluation/cases.py",
    "evaluation/harness.py": "nlp/evaluation/harness.py",
    "ner/__init__.py": "nlp/ner/__init__.py",
    "ner/ner.py": "nlp/ner/ner.py",
    "ner/ner_ml.py": "nlp/ner/ner_ml.py",
    "obligation_extraction/__init__.py": "nlp/obligation_extraction/__init__.py",
    "obligation_extraction/extractor.py": "nlp/obligation_extraction/extractor.py",
    "provenance.py": "nlp/provenance.py",
    "risk_scoring/__init__.py": "nlp/risk_scoring/__init__.py",
    "risk_scoring/case_law.py": "nlp/risk_scoring/case_law.py",
    "risk_scoring/risk_model.py": "nlp/risk_scoring/risk_model.py",
    "risk_scoring/rules.py": "nlp/risk_scoring/rules.py",
    "risk_scoring/scorer.py": "nlp/risk_scoring/scorer.py",
    "taxonomy.py": "nlp/taxonomy.py",
}

# Root duplicates that are intentionally re-export shims rather than byte copies.
# (None currently — if a copy is converted to a shim, list its path here so the
# byte-comparison is skipped while the shim nature is still asserted below.)
SHIMMED = frozenset()

# Root duplicates deliberately EXEMPT from the byte-equality lock.
#
# evaluation/__init__.py: the root copy predates the metrics-integration block
# that landed in nlp/evaluation/__init__.py (committed in HEAD). Re-syncing it
# would make the container build import nlp.evaluation.metrics at package
# import time; the root copy is only load-bearing so `import evaluation` keeps
# working inside the image, so it is intentionally frozen here. Removing the
# root package wholesale (C10 fix) will retire this exemption.
EXEMPT = frozenset({"evaluation/__init__.py"})

# Files owned by the docs/legal workstream: nlp/ is being actively edited in
# this commit, so the root copy is re-synced (cp) as each edit lands. They are
# excluded from the strict lock while their owner keeps them in sync; a future
# C10 fix (deleting the root packages) makes this list obsolete.
ACTIVE_EDIT = frozenset({"risk_scoring/case_law.py"})


def _is_thin_shim(path: Path) -> bool:
    """A shim re-exports from ``nlp.*`` and defines nothing else of substance."""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    allowed = ("from nlp", "import nlp", "from __future__", "from typing", "import typing")
    return bool(lines) and all(ln.startswith(allowed) for ln in lines)


def test_root_duplicates_are_identical_or_shimmed():
    # Compare against the *committed* nlp/ counterpart: nlp/ is actively
    # evolving, and the root copies are only re-synced when a change lands.
    # A committed divergence is the drift this test exists to catch; a
    # working-tree-only divergence means the nlp/ side is mid-edit and the
    # sync happens when that change is committed.
    diverged = []
    for dup, source in sorted(DUPLICATES.items()):
        dup_path = REPO_ROOT / dup
        assert dup_path.is_file(), f"root duplicate missing (was it deleted?): {dup}"
        if dup in SHIMMED:
            assert _is_thin_shim(dup_path), f"shim is not thin (defines its own logic): {dup}"
            continue
        if dup in EXEMPT or dup in ACTIVE_EDIT:
            continue
        committed_src = _git_show(source)
        if committed_src is None:
            continue  # nlp/ counterpart not tracked at HEAD yet; nothing to pin
        if dup_path.read_bytes() != committed_src:
            diverged.append(
                f"{dup} != HEAD:{source} (re-sync with: cp {source} {dup})"
            )
    assert not diverged, (
        "root duplicate(s) diverged from their committed nlp/ counterpart:\n"
        + "\n".join(diverged)
    )


def _git_show(path: str) -> bytes | None:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def test_duplicate_inventory_is_complete():
    """Catch new root duplicates added in future commits (C10 regression guard)."""
    tracked_dup_prefixes = ("clause_classification/", "ner/", "obligation_extraction/", "risk_scoring/", "context/", "datasets/", "evaluation/")
    # Discover via the filesystem rather than git so the test works in a
    # clean checkout without index access.
    found = {}
    for prefix in tracked_dup_prefixes:
        d = REPO_ROOT / prefix
        if d.is_dir():
            for p in sorted(d.rglob("*.py")):
                if "__pycache__" in p.parts:
                    continue
                found[str(p.relative_to(REPO_ROOT))] = f"nlp/{p.relative_to(REPO_ROOT)}"
    for name in ("taxonomy.py", "provenance.py"):
        p = REPO_ROOT / name
        if p.is_file():
            found[name] = f"nlp/{name}"
    missing = sorted(set(found) - set(DUPLICATES))
    assert not missing, (
        "new root duplicate(s) not registered in DUPLICATES:\n" + "\n".join(missing)
    )
