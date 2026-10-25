"""Canonical clause taxonomy shared by dataset loaders and the classifier.

Keeping a single source of truth prevents the drift where the same CUAD or
MAUD label mapped to different internal categories in different modules.
"""
from __future__ import annotations

from typing import Optional

# These MUST stay in sync with nlp.clause_classification.classifier.CLAUSE_RULES.
INTERNAL_LABELS = (
    "Payment Terms",
    "Term and Renewal",
    "Termination",
    "Indemnification",
    "Limitation of Liability",
    "Warranty",
    "Confidentiality",
    "Data Protection",
    "Intellectual Property",
    "Non-Compete / Non-Solicit",
    "Governing Law",
    "Dispute Resolution",
    "Force Majeure",
    "Assignment",
    "Audit Rights",
    "Insurance",
    "Compliance",
    "Service Levels",
    "Change Control",
    "Notice",
    "Acceptance",
    "Definitions",
    "Miscellaneous",
    "Stamp Duty",
    "TDS / GST",
    "Arbitration Seat",
)

# All 41 CUAD categories.
CUAD_TO_INTERNAL = {
    "Document Name": "Definitions",
    "Parties": "Definitions",
    "Agreement Date": "Definitions",
    "Effective Date": "Term and Renewal",
    "Expiration Date": "Term and Renewal",
    "Renewal Term": "Term and Renewal",
    "Notice Period To Terminate Renewal": "Term and Renewal",
    "Governing Law": "Governing Law",
    "Most Favored Nation": "Payment Terms",
    "Non-Compete": "Non-Compete / Non-Solicit",
    "Exclusivity": "Non-Compete / Non-Solicit",
    "No-Solicit Of Customers": "Non-Compete / Non-Solicit",
    "No-Solicit Of Employees": "Non-Compete / Non-Solicit",
    "Competitive Restriction Exception": "Non-Compete / Non-Solicit",
    "Non-Disparagement": "Confidentiality",
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

# MAUD's 22 `text_type` values (its actual clause-level taxonomy).
MAUD_TEXT_TYPE_TO_INTERNAL = {
    "MAE Definition": "Definitions",
    "Accuracy of Target R&W Closing Condition": "Warranty",
    "Tail Period & Acquisition Proposal Details": "Non-Compete / Non-Solicit",
    "Limitations on FTR Exercise": "Non-Compete / Non-Solicit",
    "Fiduciary exception to COR covenant": "Non-Compete / Non-Solicit",
    "Agreement provides for matching rights in connection with COR": "Non-Compete / Non-Solicit",
    "Ordinary course covenant": "Compliance",
    "Intervening Event Definition": "Definitions",
    "Fiduciary exception:  Board determination (no-shop)": "Non-Compete / Non-Solicit",
    "Superior Offer Definition": "Definitions",
    "Negative interim operating covenant": "Compliance",
    "Agreement provides for matching rights in connection with FTR": "Non-Compete / Non-Solicit",
    "Knowledge Definition": "Definitions",
    "General Antitrust Efforts Standard": "Compliance",
    "No-Shop": "Non-Compete / Non-Solicit",
    "Type of Consideration": "Payment Terms",
    "Compliance with Covenant Closing Condition": "Compliance",
    "Specific Performance": "Miscellaneous",
    "FTR Triggers": "Non-Compete / Non-Solicit",
    "Breach of No Shop": "Non-Compete / Non-Solicit",
    "Absence of Litigation Closing Condition": "Compliance",
    "Breach of Meeting Covenant": "Compliance",
}

# Substring hints used only when `text_type` is absent/unknown.
MAUD_QUESTION_HINTS = {
    "mae": "Definitions",
    "material adverse": "Definitions",
    "knowledge": "Definitions",
    "superior offer": "Definitions",
    "intervening event": "Definitions",
    "indemnif": "Indemnification",
    "liability": "Limitation of Liability",
    "governing law": "Governing Law",
    "jurisdiction": "Governing Law",
    "arbitration": "Dispute Resolution",
    "venue": "Dispute Resolution",
    "termination": "Termination",
    "renewal": "Term and Renewal",
    "term": "Term and Renewal",
    "non-compete": "Non-Compete / Non-Solicit",
    "non-solicit": "Non-Compete / Non-Solicit",
    "no-shop": "Non-Compete / Non-Solicit",
    "exclusiv": "Non-Compete / Non-Solicit",
    "matching rights": "Non-Compete / Non-Solicit",
    "fiduciary": "Non-Compete / Non-Solicit",
    "anti-assignment": "Assignment",
    "change of control": "Assignment",
    "right of first refusal": "Assignment",
    "warrant": "Warranty",
    "representations": "Warranty",
    "consideration": "Payment Terms",
    "price": "Payment Terms",
    "revenue": "Payment Terms",
    "insurance": "Insurance",
    "audit": "Audit Rights",
    "books and records": "Audit Rights",
    "compliance": "Compliance",
    "covenant": "Compliance",
}


def _map(label: str, mapping: dict[str, str]) -> Optional[str]:
    label = (label or "").strip()
    if label in mapping:
        return mapping[label]
    lowered = {k.lower(): v for k, v in mapping.items()}
    return lowered.get(label.lower())


def map_cuad_label(label: str) -> Optional[str]:
    return _map(label, CUAD_TO_INTERNAL)


def map_maud_label(label: str) -> Optional[str]:
    """Map a MAUD text_type, or fall back to a coarse question hint."""
    mapped = _map(label, MAUD_TEXT_TYPE_TO_INTERNAL)
    if mapped:
        return mapped
    lowered = (label or "").lower()
    for needle, target in MAUD_QUESTION_HINTS.items():
        if needle in lowered:
            return target
    return None
