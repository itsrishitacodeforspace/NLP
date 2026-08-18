"""Tests for the document parser."""
from __future__ import annotations

from pathlib import Path

from app.services.parser import (
    OCR_PAGE_CHAR_THRESHOLD,
    parse_document,
    strip_headers_footers,
)


def test_parse_text_file(tmp_path: Path):
    fp = tmp_path / "sample.txt"
    fp.write_text("1. Heading\n\nThis is the body of a contract clause.", encoding="utf-8")
    parsed = parse_document(fp, contract_id="c_test")
    assert parsed.contract_id == "c_test"
    assert "Heading" in parsed.full_text
    assert parsed.char_count > 0
    assert parsed.pages


def test_strip_headers_footers():
    text = "Page 1 of 10\n\nConfidential\n\nReal content here."
    cleaned = strip_headers_footers(text)
    assert "Confidential" not in cleaned
    assert "Real content" in cleaned


def test_ocr_threshold_constant():
    # sanity check on the OCR threshold
    assert OCR_PAGE_CHAR_THRESHOLD >= 30