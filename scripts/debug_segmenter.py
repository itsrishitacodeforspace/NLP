"""Debug the long-clause splitter."""
from pathlib import Path

from app.services.parser import parse_document
from app.services.segmenter import _split_long_clause

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_msa.txt"


def main() -> int:
    parsed = parse_document(SAMPLE, contract_id="debug", enable_ocr=False)
    body = parsed.full_text[3000:17000]  # arbitrary slice containing the body of clause 0
    subs = _split_long_clause(
        body,
        base_id="t",
        section_number="1",
        heading="h",
        char_start=0,
    )
    for s in subs:
        print(f"- {s.clause_id} ({s.length} chars) {s.text[:100]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
