"""Unified training-corpus schema.

Every public legal NLP dataset we consume (CUAD, MAUD, future Indian datasets)
is normalised to the :class:`TrainingExample` dataclass so downstream
training scripts only have to understand one shape.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List


@dataclass
class TrainingExample:
    """A single annotated clause / span training row."""

    example_id: str
    source: str  # 'cuad', 'maud', 'kaggle-indian', etc.
    contract_id: str
    text: str  # clause text or context snippet
    category: str  # our internal clause category (CUAD label or mapped)
    spans: List[dict] = field(default_factory=list)  # [{start, end, label, value}]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def write_jsonl(examples: Iterable[TrainingExample], out_path: Path) -> int:
    """Write examples as a JSON-Lines file. Returns the count written."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> List[TrainingExample]:
    """Read a JSON-Lines corpus into a list of TrainingExample."""
    examples: List[TrainingExample] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            examples.append(TrainingExample(**json.loads(line)))
    return examples
