"""Tests for long-clause splitting in the segmenter."""
from __future__ import annotations

from app.services.segmenter import segment_clauses


def test_long_clause_is_split():
    long_text = "1. Force Majeure\n" + (
        "The Supplier shall not be liable for any failure to perform its obligations under this Agreement "
        "where such failure is caused by an event beyond its reasonable control, including but not limited to "
        "acts of God, war, terrorism, civil unrest, government action, pandemic, epidemic, natural disaster, "
        "fire, flood, earthquake, or failure of public or private telecommunications networks. "
    ) * 5 + (
        "Customer shall give notice within 5 days of becoming aware of any such event. "
        "The Supplier shall use reasonable endeavours to resume performance as soon as reasonably practicable. "
    ) * 3

    clauses = segment_clauses(long_text, contract_id="long_test", long_threshold=1500)
    assert len(clauses) >= 2, "long clause should be split into multiple sub-clauses"
    for c in clauses:
        assert c.char_end >= c.char_start, "char offsets must be monotonic"
        assert c.length > 0


def test_segment_offsets_monotonic():
    text = "1. A\n" + ("a " * 300) + "\n\n2. B\n" + ("b " * 300) + "\n\n3. C\n" + ("c " * 300)
    clauses = segment_clauses(text, contract_id="off")
    for prev, curr in zip(clauses, clauses[1:], strict=False):
        assert curr.char_start >= prev.char_end - 4  # allow small overlap from separator
