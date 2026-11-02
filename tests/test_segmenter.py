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


# ---------------------------------------------------------------------------
# Source-integrity contract (audit defects D1/D2/D3): every clause slices the
# source exactly; preamble content is never dropped.
# ---------------------------------------------------------------------------


def _assert_all_slice_exact(text, clauses):
    # Offsets index the cleaned document — the exact text the pipeline
    # processes (parsed.full_text). For already-clean inputs this is the
    # input itself.
    from app.utils.text import clean_text

    cleaned = clean_text(text)
    for c in clauses:
        assert cleaned[c.char_start:c.char_end] == c.text, (
            f"{c.clause_id}: offsets do not slice the source"
        )


def test_one_line_preamble_is_preserved():
    text = "This Agreement is made today.\n\n1. PAYMENT\nThe Customer shall pay within 30 days."
    clauses = segment_clauses(text, contract_id="p1")
    assert any("made today" in c.text for c in clauses)
    _assert_all_slice_exact(text, clauses)


def test_multi_line_preamble_keeps_every_line():
    text = (
        "This Agreement is made today.\nIt is between A and B.\nIt supersedes prior drafts.\n\n"
        "1. PAYMENT\nThe Customer shall pay within 30 days."
    )
    clauses = segment_clauses(text, contract_id="p2")
    preamble = clauses[0].text
    assert "made today" in preamble
    assert "between A and B" in preamble
    assert "supersedes prior drafts" in preamble
    _assert_all_slice_exact(text, clauses)


def test_blank_lines_between_preamble_and_clauses():
    text = "MASTER AGREEMENT\n\n\n1. PAYMENT\nThe Customer shall pay within 30 days."
    clauses = segment_clauses(text, contract_id="p3")
    assert clauses[0].heading == "MASTER AGREEMENT"
    assert any("pay within 30 days" in c.text for c in clauses)
    _assert_all_slice_exact(text, clauses)


def test_document_without_headings_preserves_all_content():
    text = "First sentence of the deal.\nSecond sentence of the deal.\n\nThird paragraph sentence."
    clauses = segment_clauses(text, contract_id="p4")
    joined = "\n".join(c.text for c in clauses)
    for needle in ("First sentence", "Second sentence", "Third paragraph"):
        assert needle in joined
    _assert_all_slice_exact(text, clauses)


def test_oversized_paragraph_sentence_split_slices_exactly():
    body = (
        "The Supplier shall not be liable for failures beyond its reasonable control. "
        "Each party shall give notice of any event affecting performance. "
        "Remedies are limited to direct losses actually incurred. "
    ) * 8
    text = "1. FORCE MAJEURE\n" + body
    clauses = segment_clauses(text, contract_id="p5", long_threshold=500)
    assert len(clauses) >= 2
    _assert_all_slice_exact(text, clauses)


def test_long_clause_without_heading_slices_exactly():
    body = (
        "The Supplier shall deliver the goods in accordance with the schedule. "
        "The Customer shall inspect the goods on receipt. "
    ) * 10
    clauses = segment_clauses(body, contract_id="p6", long_threshold=400)
    assert len(clauses) >= 2
    _assert_all_slice_exact(body, clauses)


def test_headed_clauses_slice_exactly_across_layouts():
    layouts = [
        # heading and body on the next single line
        "7.1 LIMITATION OF LIABILITY\nNeither party shall be liable for indirect damages.",
        # heading separated by a blank line
        "7.1 LIMITATION OF LIABILITY\n\nNeither party shall be liable for indirect damages.",
        # heading inline with body on one line
        "7.1 LIMITATION OF LIABILITY Neither party shall be liable for indirect damages.",
    ]
    for text in layouts:
        clauses = segment_clauses(text, contract_id="p7")
        _assert_all_slice_exact(text, clauses)
