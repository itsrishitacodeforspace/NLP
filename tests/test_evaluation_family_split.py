"""Unit tests for nlp.evaluation.family_split (CUAD template-family proxy)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nlp.evaluation.family_split import (
    FamilyMap,
    disjoint_test_keys,
    family_map_for,
    leakage_report,
    load_cuad_docs,
    normalise_title,
    shingle_overlap,
    text_shingles,
)


def _cuad_file(path: Path, docs: list[dict]) -> None:
    path.write_text(
        json.dumps({"version": "aok_v1.0", "data": [{"title": t, "paragraphs": [{"context": c, "qas": []}]} for t, c in docs]}),
        encoding="utf-8",
    )


class TestPrimitives:
    def test_normalise_title_case_and_whitespace(self):
        assert normalise_title("  License   Agreement ") == "license agreement"
        assert normalise_title("LICENSE AGREEMENT") == "license agreement"

    def test_text_shingles_identical(self):
        a = text_shingles("the quick brown fox jumps over the lazy dog " * 5)
        b = text_shingles("THE  Quick brown FOX jumps over the lazy dog " * 5)
        assert a == b
        assert all(len(s) == 8 for s in a)

    def test_text_shingles_short_text(self):
        assert text_shingles("abc") == {"abc"}
        assert text_shingles("") == set()

    def test_shingle_overlap_bounds(self):
        a = text_shingles("alpha alpha alpha alpha alpha alpha")
        assert shingle_overlap(a, a) == 1.0
        b = text_shingles("completely different content entirely different")
        assert shingle_overlap(a, b) < 0.1
        assert shingle_overlap(set(), a) == 0.0

    def test_shingle_overlap_smaller_set_denominator(self):
        small = {"aaaaaaaa"}
        big = small | {f"xxxxxxxx{i:04d}" for i in range(99)}
        assert shingle_overlap(small, big) == 1.0  # fraction of the smaller set


class TestFamilyMap:
    def test_identical_titles_same_family(self):
        fam = FamilyMap()
        f1 = fam.add("doc_a", "Acme Corp_01_01_2020-EX-10_LICENSE AGREEMENT", set())
        f2 = fam.add("doc_b", "acme corp_01_01_2020-ex-10_license agreement", set())
        assert f1 == f2
        assert fam.n_families == 1

    def test_disjoint_shingles_different_families(self):
        fam = FamilyMap()
        a = text_shingles("the first contract document with entirely unique wording " * 10)
        b = text_shingles("a wholly unrelated second contract with no shared content here " * 10)
        f1 = fam.add("doc_a", "Title One", a)
        f2 = fam.add("doc_b", "Title Two", b)
        assert f1 != f2
        assert fam.n_families == 2

    def test_threshold_behavior(self):
        # Two docs that share ~60% of shingles: same family at threshold 0.5,
        # different at 0.75.
        # Non-repeating, sentence-like text: doc B reuses roughly half of
        # doc A's wording (in the first half of the document).
        part_a = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon "
        a = text_shingles(part_a + "one two three four five six seven eight nine ten eleven twelve ")
        b = text_shingles(part_a + "twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million ")
        overlap = shingle_overlap(a, b)
        assert 0.3 < overlap < 0.8

        low = FamilyMap(threshold=0.25)
        assert low.add("a", "T1", a) == low.add("b", "T2", b)

        high = FamilyMap(threshold=0.99)
        assert high.add("a", "T1", a) != high.add("b", "T2", b)

    def test_invalid_threshold_rejected(self):
        with pytest.raises(ValueError):
            FamilyMap(threshold=0.0)
        with pytest.raises(ValueError):
            FamilyMap(threshold=1.5)


class TestLeakageReport:
    def _train_file(self, path: Path):
        _cuad_file(
            path,
            [
                ("FAMILY_A_DOC", "alpha contract text one " * 40),
                ("FAMILY_B_DOC", "beta contract text two " * 40),
            ],
        )

    def _test_file(self, path: Path):
        _cuad_file(
            path,
            [
                # title-exact leak: same title as a train doc
                ("FAMILY_A_DOC", "entirely new text that does not resemble the train family " * 20),
                # near-duplicate leak: different title but shares shingles with FAMILY_B
                ("FAMILY_B_COPY", "beta contract text two " * 30 + " small extra change " * 5),
                # genuinely disjoint
                ("FAMILY_C_DOC", "gamma contract text three " * 40),
            ],
        )

    def test_disjoint_selection_excludes_leaked(self, tmp_path):
        tr, te = tmp_path / "train.json", tmp_path / "test.json"
        self._train_file(tr)
        self._test_file(te)
        train_map = family_map_for(tr, threshold=0.5)
        test_map = family_map_for(te, threshold=0.5)
        report = leakage_report(train_map, test_map, threshold=0.5)

        disjoint = disjoint_test_keys(report)
        assert disjoint == {"FAMILY_C_DOC"}
        assert report["counts"]["test_in_train_family"] == 2
        assert report["counts"]["test_total"] == 3

    def test_report_shape(self, tmp_path):
        tr, te = tmp_path / "train.json", tmp_path / "test.json"
        self._train_file(tr)
        self._test_file(te)
        report = leakage_report(family_map_for(tr), family_map_for(te), threshold=0.5)
        for key in (
            "train_docs",
            "train_families",
            "test_docs",
            "test_families",
            "test_docs_in_train_family",
            "test_docs_family_disjoint",
            "counts",
        ):
            assert key in report


def test_load_cuad_docs_roundtrip(tmp_path):
    path = tmp_path / "cuad.json"
    _cuad_file(path, [("TITLE_ONE", "some contract body " * 30)])
    docs = load_cuad_docs(path)
    assert len(docs) == 1
    assert docs[0]["key"] == "TITLE_ONE"
    assert docs[0]["n_paragraphs"] == 1
    assert len(docs[0]["shingles"]) > 0
