"""CUAD (Contract Understanding Atticus Dataset) loader.

Each row in CUAD is a contract (one paragraph with full text) plus a list of
Q&A pairs (one per category). We normalise the gold spans into our
:class:`TrainingExample` schema so downstream training code can consume a
single, uniform format.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from nlp.datasets.unified import (
    TrainingExample,
    map_cuad_label,
    write_jsonl,
)


CATEGORY_QUESTION_RE = re.compile(r'related to "([^"]+)"', re.IGNORECASE)


def iter_examples(cuad_path: Path) -> Iterator[TrainingExample]:
    """Yield TrainingExample rows from a CUAD JSON file."""
    cuad_path = Path(cuad_path)
    with cuad_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    for doc_idx, doc in enumerate(data["data"]):
        title = doc.get("title", f"cuad_doc_{doc_idx}")
        contract_id = re.sub(r"[^A-Za-z0-9]+", "_", title)[:60].strip("_").lower() or f"cuad_{doc_idx}"

        for para in doc["paragraphs"]:
            context = para["context"]
            for q_idx, qa in enumerate(para["qas"]):
                question = qa["question"]
                m = CATEGORY_QUESTION_RE.search(question)
                if not m:
                    continue
                cuad_label = m.group(1)
                internal_category = map_cuad_label(cuad_label)
                if not internal_category:
                    continue

                answers = qa.get("answers", []) or []
                spans: List[dict] = []
                for ans in answers:
                    text = ans.get("text", "")
                    start = ans.get("answer_start")
                    if start is None or not text:
                        continue
                    spans.append(
                        {
                            "start": int(start),
                            "end": int(start) + len(text),
                            "label": cuad_label,
                            "value": text,
                        }
                    )

                # Skip impossible questions (no label) but keep as a negative
                # sample for the classifier.
                if qa.get("is_impossible") and not spans:
                    yield TrainingExample(
                        example_id=f"{contract_id}_q{q_idx}_neg",
                        source="cuad",
                        contract_id=contract_id,
                        text=context,
                        category=internal_category,
                        spans=[],
                        metadata={"cuad_label": cuad_label, "label": "absent", "is_impossible": True},
                    )
                    continue

                # Yield the clause-level snippet containing each answer.
                yielded_for_q = set()
                for span in spans:
                    # Carve out the containing sentence as a clause-level snippet
                    # so we can train a clause classifier on real examples.
                    snippet = _surrounding_sentence(context, span["start"], span["end"])
                    snippet_key = (snippet, internal_category)
                    if snippet_key in yielded_for_q:
                        continue
                    yielded_for_q.add(snippet_key)
                    yield TrainingExample(
                        example_id=f"{contract_id}_q{q_idx}_s{span['start']}",
                        source="cuad",
                        contract_id=contract_id,
                        text=snippet,
                        category=internal_category,
                        spans=[span],
                        metadata={"cuad_label": cuad_label, "label": "present"},
                    )


def _surrounding_sentence(context: str, start: int, end: int, padding: int = 0) -> str:
    """Return a sentence-sized snippet around the [start, end] span."""
    # Expand to sentence boundaries.
    left = context.rfind(".", 0, start)
    right = context.find(".", end)
    if left == -1:
        left = max(0, start - 200)
    else:
        left = left + 1
    if right == -1:
        right = min(len(context), end + 200)
    snippet = context[left:right].strip()
    if padding:
        left = max(0, start - left - padding)
        right = min(len(snippet), (end - left) + padding)
        snippet = snippet[max(0, left - 80) : min(len(snippet), right + 80)]
    return snippet or context[max(0, start - 80) : min(len(context), end + 80)]


def build_corpus(cuad_path: Path, out_path: Path) -> int:
    """Build a JSONL training corpus from CUAD."""
    return write_jsonl(iter_examples(cuad_path), out_path)


def category_counts(examples: Iterable[TrainingExample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ex in examples:
        counts[ex.category] = counts.get(ex.category, 0) + 1
    return counts


def collect_keyword_bank(cuad_path: Path) -> dict[str, list[str]]:
    """Collect real-world span texts per CUAD label — useful as a keyword bank
    for our rule-based NER module."""
    bank: dict[str, set[str]] = {}
    for ex in iter_examples(cuad_path):
        for span in ex.spans:
            value = span.get("value", "").strip()
            if not value or len(value) > 200:
                continue
            bank.setdefault(span["label"], set()).add(value)
    return {k: sorted(v) for k, v in bank.items()}


def main() -> int:  # pragma: no cover - CLI helper
    import argparse

    parser = argparse.ArgumentParser(description="Build CUAD training corpus")
    parser.add_argument(
        "--input",
        default="data/datasets/cuad/CUADv1.json",
        help="Path to CUADv1.json",
    )
    parser.add_argument(
        "--output",
        default="data/processed/cuad_examples.jsonl",
        help="Output JSON-Lines path",
    )
    args = parser.parse_args()

    n = build_corpus(Path(args.input), Path(args.output))
    examples = list(iter_examples(Path(args.input)))
    print(f"Wrote {n} training rows to {args.output}")
    print("Top categories:")
    for cat, count in sorted(category_counts(examples).items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {count:6d}  {cat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())