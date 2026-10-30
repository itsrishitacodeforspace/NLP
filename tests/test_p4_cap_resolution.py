"""Conservative cross-reference cap resolution for RISK_LIABILITY_002.

Suppression is allowed ONLY when an explicit, resolved in-clause reference
points to a clause whose text states a liability cap that verifiably covers
the assessed liability (mutual or matching party scope, no exclusions, no
loss-category mismatch, no unresolved/ambiguous references). Everything else
keeps the finding as a human-review prompt. Related clause text without a
resolved reference never suppresses: keyword suppression stays reverted.
"""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, ContractType
from nlp.risk_scoring.rules import apply_rules


def _clause(cid, text, ctype="Limitation of Liability", context=None):
    return Clause(clause_id=cid, text=text, clause_types=[ctype], context=context)


def _summary():
    return ContractSummary(
        contract_id="t", title="t", file_name="t.txt",
        contract_type=ContractType.OTHER, jurisdiction="India",
    )


def _liability_002(clause):
    return [f for f in apply_rules([clause], _summary()) if f.rule_id == "RISK_LIABILITY_002"]


def _resolved_context(target_id, target_text):
    return {
        "status": "complete",
        "references": [
            {"raw": "Clause 7.4", "kind": "clause",
             "target_clause_ids": [target_id], "status": "resolved"}
        ],
        "related_clause_ids": [target_id],
        "related_clause_texts": [target_text],
        "unresolved_references": [],
    }


ASSESSED = (
    "Except as set out in Clause 7.4, neither party shall be liable for "
    "indirect damages."
)


# --- Suppression cases: the referenced cap verifiably applies ---

def test_valid_cross_referenced_mutual_cap_suppresses_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c7_4",
            "Each party's aggregate liability shall not exceed the total fees "
            "paid under this Agreement in the preceding 12 months.",
        ),
    )
    assert _liability_002(c) == [], "a resolved, applicable mutual cap means the cap is not missing"


def test_same_party_cross_referenced_cap_suppresses_finding():
    c = _clause(
        "c7_1",
        "The Provider's liability under this Agreement is subject to Clause 7.4.",
        context=_resolved_context(
            "c7_4",
            "The Provider's total liability shall not exceed the fees paid.",
        ),
    )
    assert _liability_002(c) == [], "a resolved cap for the same party covers the assessed liability"


# --- Invalid / unresolved / ambiguous references: finding must stand ---

def test_unresolved_reference_keeps_finding():
    ctx = _resolved_context(
        "c7_4",
        "Each party's aggregate liability shall not exceed the fees paid.",
    )
    ctx["unresolved_references"] = ["Clause 9.9"]
    c = _clause("c7_1", ASSESSED + " See also Clause 9.9.", context=ctx)
    assert _liability_002(c), "an unresolved reference means coverage cannot be confirmed"


def test_missing_reference_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context={
            "status": "partial",
            "references": [{"raw": "Clause 9.9", "kind": "clause",
                            "target_clause_ids": [], "status": "missing"}],
            "related_clause_ids": [],
            "related_clause_texts": [],
            "unresolved_references": ["Clause 9.9"],
        },
    )
    assert _liability_002(c), "a missing reference never suppresses"


def test_ambiguous_reference_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context={
            "status": "partial",
            "references": [{"raw": "Section 7.4", "kind": "section",
                            "target_clause_ids": ["c_a", "c_b"], "status": "ambiguous"}],
            "related_clause_ids": [],
            "related_clause_texts": [],
            "unresolved_references": ["Section 7.4"],
        },
    )
    assert _liability_002(c), "an ambiguous reference never suppresses"


def test_unrelated_reference_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c_defs",
            "Definitions. \"Agreement\" means this services agreement between the parties.",
        ),
    )
    assert _liability_002(c), "a resolved reference to a non-cap clause never suppresses"


def test_referenced_clause_without_cap_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c_gov",
            "Governing Law. This Agreement is governed by the laws of India.",
        ),
    )
    assert _liability_002(c), "a referenced clause without cap language never suppresses"


# --- Cap exists but may not cover the assessed risk: finding must stand ---

def test_cap_with_relevant_exclusion_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c7_4",
            "Each party's aggregate liability shall not exceed the fees paid, "
            "excluding indirect and consequential damages.",
        ),
    )
    assert _liability_002(c), "a cap that excludes the assessed category needs human review"


def test_cap_scoped_to_direct_losses_only_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c7_4",
            "Each party's liability for direct damages shall not exceed the fees paid.",
        ),
    )
    assert _liability_002(c), "a direct-losses-only cap does not cover assessed indirect exposure"


def test_cap_for_different_party_keeps_finding():
    c = _clause(
        "c7_1",
        "The Customer's liability under this Agreement is subject to Clause 7.4.",
        context=_resolved_context(
            "c7_4",
            "The Provider's total liability shall not exceed the fees paid.",
        ),
    )
    assert _liability_002(c), "a cap naming only the other party does not cover this liability"


def test_conflicting_cap_language_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c7_4",
            "Each party's liability shall not exceed the fees paid. "
            "Notwithstanding the foregoing, liability for IP infringement is unlimited.",
        ),
    )
    assert _liability_002(c), "conflicting provisions must keep the finding for review"


# --- Negative controls: keyword presence alone never suppresses ---

def test_related_cap_text_without_resolved_reference_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context={
            "status": "complete",
            "related_clause_ids": ["c7_4"],
            "related_clause_texts": [
                "Each party's aggregate liability shall not exceed the fees paid."
            ],
            "unresolved_references": [],
        },
    )
    assert _liability_002(c), "related text without a resolved reference is keyword suppression"


def test_generic_cap_with_unknown_scope_keeps_finding():
    c = _clause(
        "c7_1", ASSESSED,
        context=_resolved_context(
            "c7_4",
            "Liability cap. Total liability shall not exceed the fees paid.",
        ),
    )
    assert _liability_002(c), "a cap with undeterminable party scope is uncertain, not suppressing"


def test_no_context_keeps_finding():
    c = _clause("c7_1", "Limitation of Liability. No cap is stated.")
    assert _liability_002(c), "behaviour without context is unchanged"
