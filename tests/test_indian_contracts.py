"""Regression lock for Indian-contract scenario behavior.

Each of the 5 bundled synthetic Indian contract samples (data/raw/sample_*.txt)
is run through the FULL pipeline (parse → segment → classify → NER →
obligations → risk rules → score) and asserted against the EXPECTED findings
with a documented rationale per assertion — positive AND negative.

These tests lock the behavior of the rule engine on realistic Indian
commercial contracts. They are the regression lock for Indian-contract
behavior: if a rule change causes a previously-correct finding to disappear
or a previously-absent finding to appear, these tests fail.

Run: ``uv run pytest tests/test_indian_contracts.py -q``
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models.schemas import ContractType, PartySide
from app.services.analyzer import analyse_path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "data" / "raw"

# (file_name, contract_id, scenario_label)
SAMPLES = [
    ("sample_nda.txt", "sample_nda", "one-way NDA"),
    ("sample_employment.txt", "sample_employment", "employment agreement"),
    ("sample_vsa.txt", "sample_vsa", "vendor/procurement agreement"),
    ("sample_data_processing.txt", "sample_dpa", "DPA annex"),
    ("sample_consulting.txt", "sample_consulting", "consulting agreement"),
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _analyse(name: str, cid: str):
    path = SAMPLES_DIR / name
    assert path.is_file(), f"missing sample: {path}"
    return analyse_path(
        path,
        contract_id=cid,
        contract_type=ContractType.OTHER,
        user_role=PartySide.NEUTRAL,
        jurisdiction="India",
        enable_ocr=True,
    )


def _rule_ids(result) -> set[str]:
    return {f.rule_id for f in result.risks}


def _has(result, rule_id: str) -> bool:
    return rule_id in _rule_ids(result)


def _not_has(result, rule_id: str) -> bool:
    return rule_id not in _rule_ids(result)


def _span_check(result) -> None:
    """Assert that every evidence span slices the source exactly.

    Reuses the pattern from tests/test_evidence_binding.py: for every
    clause-level finding with an evidence span, ``clause.text[char_start:char_end]``
    must equal ``span.text``.
    """
    by_id = {c.clause_id: c.text for c in result.clauses}
    bad = []
    for f in result.risks:
        if f.source == "model":
            continue
        for s in f.evidence_spans:
            clause_text = by_id.get(s.clause_id)
            if clause_text is None:
                bad.append(f"{f.rule_id}: span references unknown clause {s.clause_id}")
                continue
            if clause_text[s.char_start : s.char_end] != s.text:
                bad.append(
                    f"{f.rule_id} [{s.clause_id}]: span "
                    f"({s.char_start}:{s.char_end}) != source slice"
                )
    assert not bad, "evidence span(s) do not slice the source exactly:\n" + "\n".join(bad)


# ---------------------------------------------------------------------------
# Per-sample tests
# ---------------------------------------------------------------------------


# --- sample_nda.txt: one-way NDA -------------------------------------------


def test_nda_missing_dispute_resolution():
    """POSITIVE: the NDA has no arbitration or court clause, so the new
    RISK_DISPUTE_001 (missing dispute resolution) must fire."""
    r = _analyse("sample_nda.txt", "nda")
    assert _has(r, "RISK_DISPUTE_001"), (
        "NDA has no arbitration or court clause; RISK_DISPUTE_001 should fire"
    )


def test_nda_stamp_duty_fires():
    """POSITIVE: the NDA has no stamp duty language, so RISK_STAMP_001 fires
    (jurisdiction-gated to India, which it is)."""
    r = _analyse("sample_nda.txt", "nda")
    assert _has(r, "RISK_STAMP_001")


def test_nda_no_non_compete():
    """NEGATIVE: the NDA has no post-employment non-compete clause, so
    RISK_NONCOMPETE_001 must NOT fire."""
    r = _analyse("sample_nda.txt", "nda")
    assert _not_has(r, "RISK_NONCOMPETE_001"), (
        "NDA has no post-employment non-compete; RISK_NONCOMPETE_001 should not fire"
    )


def test_nda_no_gov_law_mismatch():
    """NEGATIVE: the NDA is governed by Indian law, so RISK_GOV_001 must NOT
    fire."""
    r = _analyse("sample_nda.txt", "nda")
    assert _not_has(r, "RISK_GOV_001"), (
        "NDA is governed by Indian law; RISK_GOV_001 should not fire"
    )


def test_nda_parties_effective_obligations():
    """Shared assertions: ≥2 parties, effective date found, ≥1 obligation,
    zero bad evidence spans."""
    r = _analyse("sample_nda.txt", "nda")
    assert len(r.contract.parties) >= 2, f"expected ≥2 parties, got {r.contract.parties}"
    assert r.contract.effective_date, "expected effective_date to be found"
    assert len(r.obligations) >= 1, "expected ≥1 obligation"
    _span_check(r)


# --- sample_employment.txt: employment agreement ---------------------------


def test_employment_tds_does_not_fire():
    """NEGATIVE: the employment agreement mentions TDS in the salary clause,
    so RISK_TDS_001 must NOT fire (TDS is present)."""
    r = _analyse("sample_employment.txt", "emp")
    assert _not_has(r, "RISK_TDS_001"), (
        "Employment agreement mentions TDS; RISK_TDS_001 should not fire"
    )


def test_employment_stamp_duty_fires():
    """POSITIVE: the employment agreement has no stamp duty language, so
    RISK_STAMP_001 fires."""
    r = _analyse("sample_employment.txt", "emp")
    assert _has(r, "RISK_STAMP_001")


def test_employment_missing_dispute_resolution():
    """POSITIVE: the employment agreement has no arbitration or court clause,
    so RISK_DISPUTE_001 fires."""
    r = _analyse("sample_employment.txt", "emp")
    assert _has(r, "RISK_DISPUTE_001"), (
        "Employment agreement has no dispute-resolution clause; RISK_DISPUTE_001 should fire"
    )


def test_employment_non_compete_fires():
    """POSITIVE: the employment agreement has a post-employment non-compete
    clause (s. 27 ICA risk), so RISK_NONCOMPETE_001 fires."""
    r = _analyse("sample_employment.txt", "emp")
    assert _has(r, "RISK_NONCOMPETE_001"), (
        "Employment agreement has a post-employment non-compete; RISK_NONCOMPETE_001 should fire"
    )


def test_employment_parties_effective_obligations():
    r = _analyse("sample_employment.txt", "emp")
    assert len(r.contract.parties) >= 2, f"expected ≥2 parties, got {r.contract.parties}"
    assert r.contract.effective_date, "expected effective_date to be found"
    assert len(r.obligations) >= 1, "expected ≥1 obligation"
    _span_check(r)


# --- sample_vsa.txt: vendor/procurement agreement --------------------------


def test_vsa_stamp_duty_does_not_fire():
    """NEGATIVE: the VSA mentions stamp duty in the payment clause, so
    RISK_STAMP_001 must NOT fire (stamp duty is mentioned)."""
    r = _analyse("sample_vsa.txt", "vsa")
    assert _not_has(r, "RISK_STAMP_001"), (
        "VSA mentions stamp duty; RISK_STAMP_001 should not fire"
    )


def test_vsa_tds_does_not_fire():
    """NEGATIVE: the VSA mentions TDS in the payment clause, so RISK_TDS_001
    must NOT fire (TDS is present)."""
    r = _analyse("sample_vsa.txt", "vsa")
    assert _not_has(r, "RISK_TDS_001"), (
        "VSA mentions TDS; RISK_TDS_001 should not fire"
    )


def test_vsa_auto_renewal_fires():
    """POSITIVE: the VSA has an auto-renewal clause with a 60-day notice
    period, so RISK_RENEWAL_001 fires at MEDIUM severity (notice period ≥ 30
    days → lower severity tier)."""
    r = _analyse("sample_vsa.txt", "vsa")
    assert _has(r, "RISK_RENEWAL_001"), (
        "VSA has auto-renewal; RISK_RENEWAL_001 should fire"
    )
    renewal_flags = [f for f in r.risks if f.rule_id == "RISK_RENEWAL_001"]
    assert renewal_flags, "expected RISK_RENEWAL_001 finding"
    assert renewal_flags[0].severity.value == "medium", (
        f"expected MEDIUM severity for auto-renewal with 60-day notice, "
        f"got {renewal_flags[0].severity.value}"
    )


def test_vsa_one_sided_termination_fires():
    """POSITIVE: the VSA has a one-sided termination-for-convenience clause
    (customer can terminate at any time), so RISK_TERM_001 fires."""
    r = _analyse("sample_vsa.txt", "vsa")
    assert _has(r, "RISK_TERM_001"), (
        "VSA has one-sided termination for convenience; RISK_TERM_001 should fire"
    )


def test_vsa_no_dispute_resolution_missing():
    """NEGATIVE: the VSA has an arbitration clause (New Delhi seat), so
    RISK_DISPUTE_001 must NOT fire (a dispute-resolution mechanism is
    present)."""
    r = _analyse("sample_vsa.txt", "vsa")
    assert _not_has(r, "RISK_DISPUTE_001"), (
        "VSA has an arbitration clause; RISK_DISPUTE_001 should not fire"
    )


def test_vsa_parties_effective_obligations():
    r = _analyse("sample_vsa.txt", "vsa")
    assert len(r.contract.parties) >= 2, f"expected ≥2 parties, got {r.contract.parties}"
    assert r.contract.effective_date, "expected effective_date to be found"
    assert len(r.obligations) >= 1, "expected ≥1 obligation"
    _span_check(r)


# --- sample_data_processing.txt: DPA annex ---------------------------------


def test_dpa_tight_breach_window_fires():
    """POSITIVE: the DPA has a 24-hour breach-notification deadline, so
    RISK_DATA_001 (very tight breach-notification window) fires."""
    r = _analyse("sample_data_processing.txt", "dpa")
    assert _has(r, "RISK_DATA_001"), (
        "DPA has a 24-hour breach-notification deadline; RISK_DATA_001 should fire"
    )


def test_dpa_data_protection_present_no_missing():
    """NEGATIVE: the DPA has data protection clauses, so RISK_DATA_MISSING
    must NOT fire (data protection is present)."""
    r = _analyse("sample_data_processing.txt", "dpa")
    assert _not_has(r, "RISK_DATA_MISSING"), (
        "DPA has data protection clauses; RISK_DATA_MISSING should not fire"
    )


def test_dpa_missing_dispute_resolution():
    """POSITIVE: the DPA has no arbitration or court clause, so
    RISK_DISPUTE_001 fires."""
    r = _analyse("sample_data_processing.txt", "dpa")
    assert _has(r, "RISK_DISPUTE_001"), (
        "DPA has no dispute-resolution clause; RISK_DISPUTE_001 should fire"
    )


def test_dpa_24h_obligation_extracted():
    """POSITIVE: the obligation extractor should pick up the 24-hour
    breach-notification deadline as an obligation with a deadline
    expression containing '24'."""
    r = _analyse("sample_data_processing.txt", "dpa")
    breach_obligs = [
        o for o in r.obligations
        if o.deadline_expression and "24" in o.deadline_expression
    ]
    assert breach_obligs, (
        "expected at least one obligation with a 24-hour deadline"
    )


def test_dpa_parties_effective_obligations():
    r = _analyse("sample_data_processing.txt", "dpa")
    assert len(r.contract.parties) >= 2, f"expected ≥2 parties, got {r.contract.parties}"
    assert r.contract.effective_date, "expected effective_date to be found"
    assert len(r.obligations) >= 1, "expected ≥1 obligation"
    _span_check(r)


# --- sample_consulting.txt: consulting agreement ---------------------------


def test_consulting_foreign_gov_law_fires():
    """POSITIVE: the consulting agreement is governed by Delaware law, so
    RISK_GOV_001 (foreign governing law in domestic contract) fires."""
    r = _analyse("sample_consulting.txt", "con")
    assert _has(r, "RISK_GOV_001"), (
        "Consulting agreement is governed by Delaware law; RISK_GOV_001 should fire"
    )


def test_consulting_narrow_indemnity_no_broad():
    """NEGATIVE: the consulting agreement's indemnity is narrow (third-party
    IP claims only, capped), so RISK_INDEMNITY_001 (broad indemnification)
    must NOT fire."""
    r = _analyse("sample_consulting.txt", "con")
    assert _not_has(r, "RISK_INDEMNITY_001"), (
        "Consulting agreement has a narrow, capped indemnity; "
        "RISK_INDEMNITY_001 should not fire"
    )


def test_consulting_missing_dispute_resolution():
    """POSITIVE: the consulting agreement has no arbitration or court
    clause, so RISK_DISPUTE_001 fires."""
    r = _analyse("sample_consulting.txt", "con")
    assert _has(r, "RISK_DISPUTE_001"), (
        "Consulting agreement has no dispute-resolution clause; RISK_DISPUTE_001 should fire"
    )


def test_consulting_s124_fires():
    """POSITIVE: the consulting agreement's indemnity does not expressly
    extend to direct losses or breach of contract, so RISK_S124_001 (Indian
    §124 indemnity gap) fires."""
    r = _analyse("sample_consulting.txt", "con")
    assert _has(r, "RISK_S124_001"), (
        "Consulting agreement's indemnity does not cover direct losses; RISK_S124_001 should fire"
    )


def test_consulting_parties_effective_obligations():
    r = _analyse("sample_consulting.txt", "con")
    assert len(r.contract.parties) >= 2, f"expected ≥2 parties, got {r.contract.parties}"
    assert r.contract.effective_date, "expected effective_date to be found"
    assert len(r.obligations) >= 1, "expected ≥1 obligation"
    _span_check(r)


# ---------------------------------------------------------------------------
# Cross-sample invariants
# ---------------------------------------------------------------------------


def test_all_samples_have_no_bad_evidence_spans():
    """Every sample: zero findings whose evidence span does not slice the
    source exactly (reuses the pattern from test_evidence_binding.py)."""
    for name, cid, _label in SAMPLES:
        r = _analyse(name, cid)
        _span_check(r)  # raises AssertionError with a clear message


def test_all_samples_have_parties_and_effective_date():
    """Every sample: ≥2 parties detected and effective date found."""
    for name, cid, label in SAMPLES:
        r = _analyse(name, cid)
        assert len(r.contract.parties) >= 2, (
            f"{label} ({name}): expected ≥2 parties, got {r.contract.parties}"
        )
        assert r.contract.effective_date, (
            f"{label} ({name}): expected effective_date to be found"
        )


def test_all_samples_have_obligations():
    """Every sample: at least one obligation extracted."""
    for name, cid, label in SAMPLES:
        r = _analyse(name, cid)
        assert len(r.obligations) >= 1, (
            f"{label} ({name}): expected ≥1 obligation, got 0"
        )
