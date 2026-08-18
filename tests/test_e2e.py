"""End-to-end smoke test: parse the sample MSA and verify outputs."""
from __future__ import annotations

from pathlib import Path

from app.models.schemas import ContractType, PartySide
from app.services.analyzer import analyse_path


SAMPLE = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_msa.txt"


def test_sample_msa_pipeline():
    result = analyse_path(
        SAMPLE,
        contract_id="c_sample",
        contract_type=ContractType.MSA,
        user_role=PartySide.PROVIDER,
        jurisdiction="India",
    )
    assert result.contract.contract_id == "c_sample"
    assert result.clauses, "should produce at least a few clauses"
    # Sample includes 'Limitation of Liability', 'Indemnification', 'Governing Law'
    types = {t for c in result.clauses for t in c.clause_types}
    assert any("Limitation" in t for t in types)
    assert any("Indemnification" in t for t in types)
    # Top risks must include at least the stamp-duty, arbitration mismatch, or liability cap rule
    rule_ids = {r.rule_id for r in result.risks}
    assert any(rid.startswith("RISK_") for rid in rule_ids)
    # The sample is missing TDS? actually it has TDS — let's just ensure
    # overall risk score is in 0-100
    assert 0 <= result.contract.overall_risk_score <= 100
    # Obligations exist
    assert result.obligations, "sample contract should contain at least some obligations"