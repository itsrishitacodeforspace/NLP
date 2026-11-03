"""CUAD document-family detection for held-out evaluation.

Two documents are in the *same template family* when their document titles
match exactly after normalisation, **or** when their normalised texts share at
least ``shingle_overlap_threshold`` (default 50%) of 8-character shingles
(near-duplicate proxy: same or closely related contract template).

The title is a practical proxy for SEC-filing / template-family identity
(CUAD titles are EDGAR-style filing identifiers such as
``COMPANY_01_01_2019-EX-10.1_LICENSE AGREEMENT``); the shingle test catches
re-filed or near-identical templates whose titles differ. This measures
*template-family separation*, NOT legal independence: two documents from
disjoint families can still cite the same boilerplate or jurisdiction.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Set

# 8-character shingles over lowercase, whitespace-collapsed text.
_SHINGLE_LEN = 8
_WS_RE = re.compile(r"\s+")


def normalise_title(title: str) -> str:
    """Case-folded, whitespace-collapsed document title (family key)."""
    return _WS_RE.sub(" ", (title or "").strip().lower())


def text_shingles(text: str, n: int = _SHINGLE_LEN) -> Set[str]:
    """Character n-grams of the whitespace-collapsed, lowercased text."""
    collapsed = _WS_RE.sub("", (text or "").lower())
    if len(collapsed) <= n:
        return {collapsed} if collapsed else set()
    return {collapsed[i : i + n] for i in range(len(collapsed) - n + 1)}


def shingle_overlap(a: Set[str], b: Set[str]) -> float:
    """Fraction of the smaller shingle set shared by both sets (0.0-1.0)."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


class FamilyMap:
    """Document -> template-family-id assignment for a set of CUAD docs.

    Families are formed greedily: documents with identical normalised titles
    share a family (the first such title's key); otherwise each new document
    joins the first existing family whose reference shingle set overlaps it by
    at least ``threshold``. Each family keeps one reference document.
    """

    def __init__(self, threshold: float = 0.5) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.threshold = threshold
        self.families: List[Dict] = []  # [{"id", "title", "shingles", "docs": []}]
        self._title_index: Dict[str, int] = {}

    @property
    def n_families(self) -> int:
        return len(self.families)

    def add(self, doc_key: str, title: str, shingles: Set[str]) -> str:
        """Assign ``doc_key`` to a family and return the family id."""
        tkey = normalise_title(title)
        if tkey and tkey in self._title_index:
            fid = self.families[self._title_index[tkey]]["id"]
            self.families[self._title_index[tkey]]["docs"].append(doc_key)
            return fid
        if shingles:
            for fam in self.families:
                if shingle_overlap(fam["shingles"], shingles) >= self.threshold:
                    fam["docs"].append(doc_key)
                    return fam["id"]
        fid = f"family_{len(self.families):04d}"
        self.families.append({"id": fid, "title": tkey, "shingles": shingles, "docs": [doc_key]})
        if tkey:
            self._title_index[tkey] = len(self.families) - 1
        return fid

    def titles(self) -> List[str]:
        """Normalised titles present in this map (empty string = untitled)."""
        return [fam["title"] for fam in self.families]

    def family_of(self, doc_key: str) -> Dict:
        for fam in self.families:
            if doc_key in fam["docs"]:
                return fam
        raise KeyError(doc_key)


def load_cuad_docs(path) -> List[Dict]:
    """Load a CUAD JSON file into ``[{key, title, shingles, n_paragraphs}]``.

    ``key`` is the CUAD document title itself (unique within each split).
    """
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    docs: List[Dict] = []
    for doc in data["data"]:
        title = doc.get("title", "")
        context = " ".join(p.get("context", "") for p in doc.get("paragraphs", []))
        docs.append(
            {
                "key": title,
                "title": title,
                "shingles": text_shingles(context),
                "n_paragraphs": len(doc.get("paragraphs", [])),
            }
        )
    return docs


def family_map_for(path, *, threshold: float = 0.5) -> FamilyMap:
    """Build a FamilyMap for one CUAD split file."""
    fmap = FamilyMap(threshold=threshold)
    for doc in load_cuad_docs(path):
        fmap.add(doc["key"], doc["title"], doc["shingles"])
    return fmap


def leakage_report(
    train_map: FamilyMap,
    test_map: FamilyMap,
    *,
    threshold: float = 0.5,
) -> Dict:
    """Compare train vs test family presence.

    Two independent FamilyMaps cannot know each other's family ids, so
    cross-membership is decided by (a) exact normalised-title equality or
    (b) shingle overlap >= threshold against any member of the opposite map.
    """
    train_docs = {d: fam for fam in train_map.families for d in fam["docs"]}
    test_docs = {d: fam for fam in test_map.families for d in fam["docs"]}

    # Index train docs for cross-checks.
    train_by_title: Dict[str, List[str]] = {}
    train_shingles: Dict[str, Set[str]] = {}
    for d, fam in train_docs.items():
        train_by_title.setdefault(fam["title"], []).append(d)
        train_shingles[d] = fam["shingles"]

    def in_train_family(d: str, fam: Dict) -> bool:
        if fam["title"] and fam["title"] in train_by_title:
            return True
        for td in train_docs:
            if shingle_overlap(train_shingles[td], fam["shingles"]) >= threshold:
                return True
        return False

    test_in_train_family: List[str] = []
    test_disjoint: List[str] = []
    for d, fam in test_docs.items():
        (test_in_train_family if in_train_family(d, fam) else test_disjoint).append(d)

    # The reverse direction (train docs whose family appears in test) is also
    # computed so the report can state both directions of overlap.
    test_by_title: Dict[str, List[str]] = {}
    test_shingles: Dict[str, Set[str]] = {}
    for d, fam in test_docs.items():
        test_by_title.setdefault(fam["title"], []).append(d)
        test_shingles[d] = fam["shingles"]

    def in_test_family(d: str, fam: Dict) -> bool:
        if fam["title"] and fam["title"] in test_by_title:
            return True
        for td in test_docs:
            if shingle_overlap(test_shingles[td], fam["shingles"]) >= threshold:
                return True
        return False

    train_in_test_family = [d for d, fam in train_docs.items() if in_test_family(d, fam)]

    return {
        "threshold": threshold,
        "train_docs": len(train_docs),
        "train_families": train_map.n_families,
        "test_docs": len(test_docs),
        "test_families": test_map.n_families,
        "test_docs_in_train_family": sorted(test_in_train_family),
        "test_docs_family_disjoint": sorted(test_disjoint),
        "train_docs_in_test_family": sorted(train_in_test_family),
        "counts": {
            "test_total": len(test_docs),
            "test_in_train_family": len(test_in_train_family),
            "test_family_disjoint": len(test_disjoint),
            "train_in_test_family": len(train_in_test_family),
        },
    }


def disjoint_test_keys(report: Dict) -> Set[str]:
    """Set of test document keys that are family-disjoint from train."""
    return set(report["test_docs_family_disjoint"])
