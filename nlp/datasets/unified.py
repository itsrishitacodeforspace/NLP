"""Unified training-corpus schema.

Every public legal NLP dataset we consume (CUAD, MAUD, future Indian datasets)
is normalised to the :class:`TrainingExample` dataclass so downstream
training scripts only have to understand one shape.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


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


# ---------------------------------------------------------------------------
# Mapping from CUAD labels to our internal categories
# ---------------------------------------------------------------------------

CUAD_TO_INTERNAL = {
    "Document Name": "Definitions",
    "Parties": "Definitions",
    "Agreement Date": "Definitions",
    "Effective Date": "Definitions",
    "Expiration Date": "Term and Renewal",
    "Renewal Term": "Term and Renewal",
    "Notice Period To Terminate Renewal": "Term and Renewal",
    "Governing Law": "Governing Law",
    "Most Favored Nation": "Pricing Terms",
    "Non-Compete": "Non-Compete / Non-Solicit",
    "Exclusivity": "Non-Compete / Non-Solicit",
    "No-Solicit Of Customers": "Non-Compete / Non-Solicit",
    "No-Solicit Of Employees": "Non-Compete / Non-Solicit",
    "Non-Disparagement": "Non-Compete / Non-Solicit",
    "Termination For Convenience": "Termination",
    "Rofr/Rofo/Rofn": "Assignment",
    "Change Of Control": "Assignment",
    "Anti-Assignment": "Assignment",
    "Revenue/Profit Sharing": "Payment Terms",
    "Price Restrictions": "Payment Terms",
    "Minimum Commitment": "Payment Terms",
    "Volume Restriction": "Payment Terms",
    "Ip Ownership Assignment": "Intellectual Property",
    "Joint Ip Ownership": "Intellectual Property",
    "License Grant": "Intellectual Property",
    "Non-Transferable License": "Intellectual Property",
    "Affiliate License-Licensor": "Intellectual Property",
    "Affiliate License-Licensee": "Intellectual Property",
    "Unlimited/All-You-Can-Eat-License": "Intellectual Property",
    "Irrevocable Or Perpetual License": "Intellectual Property",
    "Source Code Escrow": "Intellectual Property",
    "Post-Termination Services": "Termination",
    "Audit Rights": "Audit Rights",
    "Uncapped Liability": "Limitation of Liability",
    "Cap On Liability": "Limitation of Liability",
    "Liquidated Damages": "Limitation of Liability",
    "Warranty Duration": "Warranty",
    "Insurance": "Insurance",
    "Covenant Not To Sue": "Miscellaneous",
    "Third Party Beneficiary": "Miscellaneous",
}


def map_cuad_label(label: str) -> Optional[str]:
    return CUAD_TO_INTERNAL.get(label)


# Mapping MAUD sub-questions to our internal categories.
MAUD_TO_INTERNAL = {
    "matching rights": "Non-Compete / Non-Solicit",
    "no-shop": "Non-Compete / Non-Solicit",
    "exclusivity": "Non-Compete / Non-Solicit",
    "non-compete": "Non-Compete / Non-Solicit",
    "non-solicit": "Non-Compete / Non-Solicit",
    "term": "Term and Renewal",
    "termination": "Termination",
    "indemnification": "Indemnification",
    "limitation of liability": "Limitation of Liability",
    "governing law": "Governing Law",
    "venue": "Governing Law",
    "dispute resolution": "Dispute Resolution",
    "anti-assignment": "Assignment",
    "change of control": "Assignment",
    "right of first refusal": "Assignment",
    "drag-along": "Miscellaneous",
    "tag-along": "Miscellaneous",
    "fraud": "Warranty",
    "representations and warranties": "Warranty",
}


def map_maud_label(label: str) -> Optional[str]:
    label_l = label.lower()
    for needle, mapped in MAUD_TO_INTERNAL.items():
        if needle in label_l:
            return mapped
    return None