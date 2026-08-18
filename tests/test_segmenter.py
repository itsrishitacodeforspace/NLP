"""Tests for clause segmentation."""
from __future__ import annotations

from app.services.segmenter import segment_clauses


SAMPLE = """\
1. Payment Terms
Customer shall pay Provider within 30 days of invoice receipt. Late payments
will incur interest at 1.5% per month.

2. Confidentiality
Each party shall protect the Confidential Information of the other party for
3 years.

3. Limitation of Liability
Provider's total liability shall not exceed fees paid in the preceding
12 months.
"""


def test_segment_produces_clauses():
    clauses = segment_clauses(SAMPLE, contract_id="c1")
    assert len(clauses) >= 3
    headings = [c.heading for c in clauses if c.heading]
    assert any("Payment" in (h or "") for h in headings)
    assert any("Confidentiality" in (h or "") for h in headings)


def test_segment_char_offsets():
    clauses = segment_clauses(SAMPLE, contract_id="c2")
    for c in clauses:
        assert c.char_end >= c.char_start
        assert c.length > 0