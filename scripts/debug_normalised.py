"""Inspect normalised segments after the segmenter preprocessing."""
from app.services.parser import parse_document
from app.services.segmenter import _looks_like_heading_line
from app.utils.text import clean_text, split_into_paragraphs


def main() -> int:
    parsed = parse_document(
        "uploads/c_20260818_070241_27255d78d61f_agreement_01K35HTFJE4G8JJF7MDEWPKG3S-3.pdf",
        contract_id="debug",
        enable_ocr=False,
    )
    cleaned = clean_text(parsed.full_text)
    paragraphs = split_into_paragraphs(cleaned)
    print(f"paragraphs: {len(paragraphs)}")

    normalised: list[str] = []
    for p in paragraphs:
        lines = p.split("\n")
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        if _looks_like_heading_line(first) and rest:
            normalised.append(first)
            normalised.append(rest)
        else:
            normalised.append(p)

    print(f"normalised: {len(normalised)} items")
    for i, n in enumerate(normalised[:8]):
        print(f"--- {i} ({len(n)} chars) ---")
        print(repr(n[:200]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
