"""Regression checks for bugs fixed during the hardening pass."""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import (
    AnalysisResult,
    ContractSummary,
    JobInfo,
    JobStatus,
    ObligationType,
)
from app.services import jobs
from nlp.clause_classification.tfidf_model import TrainedClassifier
from nlp.obligation_extraction.extractor import extract_obligations_from_clause


def test_prohibition_subject_uses_first_modal():
    text = (
        "Each party shall keep the other party's confidential information secret "
        "and shall not disclose it to any third party without prior written consent."
    )
    obligations = extract_obligations_from_clause("c1", text, obligation_counter=0)
    prohibitions = [o for o in obligations if o.obligation_type == ObligationType.PROHIBITION]
    assert prohibitions
    assert prohibitions[0].subject == "Each party"


def test_arbitration_seat_is_not_an_obligation():
    for sentence in (
        "The seat of arbitration shall be Singapore.",
        "The venue of arbitration shall be Mumbai.",
    ):
        assert extract_obligations_from_clause("c1", sentence, obligation_counter=0) == []


def test_job_persistence_serialises_datetimes(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(jobs, "upsert_job", captured.append)
    result = AnalysisResult(
        contract=ContractSummary(
            contract_id="c1",
            title="Test",
            file_name="test.txt",
            analyzed_at=datetime(2026, 10, 22, 12, 0, 0),
        )
    )
    jobs._persist(JobInfo(job_id="j1", contract_id="c1", status=JobStatus.SUCCEEDED, result=result))
    assert captured[0]["result"]["contract"]["analyzed_at"] == "2026-10-22T12:00:00"


def test_case_law_is_attached_to_statutory_risks():
    from nlp.risk_scoring.case_law import CASE_LAW, lookup_case_law

    stamp = lookup_case_law("RISK_STAMP_001")
    assert stamp, "stamp-duty rule should carry an authority pointer"
    assert all(ref.citation for ref in stamp)
    # ARB mismatch rule must cite BALCO per the README playbook claim.
    arb = " ".join(ref.citation for ref in lookup_case_law("RISK_ARB_001"))
    assert "BALCO" in arb
    # Unknown rules simply return nothing (no crash).
    assert lookup_case_law("RISK_DOES_NOT_EXIST") == []
    assert all(isinstance(v, list) for v in CASE_LAW.values())


def test_tfidf_outputs_are_canonicalised():
    class FakePipeline:
        classes_ = ["Pricing Terms", "Unknown Label"]

        def predict_proba(self, texts):
            return [[0.8, 0.2] for _ in texts]

        def predict(self, texts):
            return ["Pricing Terms" for _ in texts]

    model = TrainedClassifier(pipeline=FakePipeline(), labels=list(FakePipeline.classes_))
    assert model.predict_one("payment clause") == ["Payment Terms"]
    assert model.predict_top1("payment clause") == "Payment Terms"

    class UnknownPipeline(FakePipeline):
        classes_ = ["Unknown Label"]

        def predict_proba(self, texts):
            return [[1.0] for _ in texts]

        def predict(self, texts):
            return ["Unknown Label" for _ in texts]

    unknown = TrainedClassifier(pipeline=UnknownPipeline(), labels=["Unknown Label"])
    assert unknown.predict_one("unknown clause") == []
    assert unknown.predict_top1("unknown clause") == "Miscellaneous"


def test_obligation_deadline_parenthetical_digits():
    text = "The Vendor shall deliver the goods within thirty (30) days of the order date."
    obligations = extract_obligations_from_clause("c1", text, obligation_counter=0)
    assert obligations, "expected an obligation to be extracted"
    assert obligations[0].deadline_expression == "30 days", obligations[0].deadline_expression


def test_segmenter_markdown_headings():
    from app.services.segmenter import segment_clauses

    text = """\
## 7. Limitation of Liability
Provider's total liability shall not exceed fees paid.

## 8. Confidentiality
Each party shall protect confidential information.
"""
    clauses = segment_clauses(text, contract_id="c1")
    headings = [c.heading for c in clauses if c.heading]
    assert any("Limitation" in (h or "") for h in headings)
    assert any("Confidentiality" in (h or "") for h in headings)
    sections = [c.section_number for c in clauses if c.section_number]
    assert "7" in sections or any(s and s.startswith("7") for s in sections)


# ---------------------------------------------------------------------------
# Stamp-duty / TDS detection recall (eval case stamp_tds_present_missed)
# ---------------------------------------------------------------------------


def test_stamp_duty_detector_covers_stamped_wording():
    from nlp.ner.ner import detect_stamp_duty_mention

    positives = [
        "This Agreement is executed on duly stamped paper.",
        "This Agreement is duly stamped.",
        "The parties shall execute this Agreement on non-judicial stamp paper "
        "of appropriate value.",
        "The stamp duty on this Agreement shall be borne by the Customer.",
        "Stamping of this Agreement shall be the responsibility of the Provider.",
        "Each party shall bear the cost of the stamped copies.",
        "The original stamped agreement shall be retained by the Customer.",
    ]
    for text in positives:
        assert detect_stamp_duty_mention(text), text


def test_stamp_duty_detector_ignores_unrelated_stamp_and_paper_mentions():
    from nlp.ner.ner import detect_stamp_duty_mention

    negatives = [
        "The board rubber-stamped the decision without debate.",
        "The letter bore a postage stamp.",
        "Every notice shall carry a date stamp.",
        "The parties shall cooperate to stamp out fraud.",
        "Each log entry is timestamped.",
        "A paper copy shall be provided on request.",
        "The report bears the stamp of approval of the committee.",
    ]
    for text in negatives:
        assert not detect_stamp_duty_mention(text), text


def test_tds_detector_covers_deduction_at_source_wording():
    from nlp.ner.ner import detect_tds_mention

    positives = [
        "Payments are subject to deduction of tax at source under the "
        "Income Tax Act, 1961.",
        "The Customer shall deduct tax at source as required by law.",
        "The Customer shall deduct at source any applicable taxes.",
        "Fees are subject to tax deducted at source.",
        "TDS shall be withheld as applicable.",
        "Amounts deducted at source shall be remitted to the government.",
        "Tax deduction at source shall apply to all payments under this Agreement.",
    ]
    for text in positives:
        assert detect_tds_mention(text), text


def test_tds_detector_ignores_unrelated_tax_and_deduction_mentions():
    from nlp.ner.ner import detect_tds_mention

    negatives = [
        "The Customer shall pay goods and services tax on each invoice.",
        "No deduction of damages shall be made from the security deposit.",
        "Each party is responsible for filing its own income tax returns.",
        "The fees are exclusive of sales tax.",
        "Any deduction for late delivery shall be capped at five percent.",
        "The source code shall be deposited in escrow.",
        "Tax shall be deducted from the invoice where required.",
    ]
    for text in negatives:
        assert not detect_tds_mention(text), text


# ---------------------------------------------------------------------------
# Negated statutory mentions (audit defect D4): a denied mention is not
# confirmation that the requirement was addressed.
# ---------------------------------------------------------------------------


def test_stamp_duty_negated_mentions_are_not_confirmations():
    from nlp.ner.ner import detect_stamp_duty_mention

    negated = [
        "This Agreement was not executed on duly stamped paper.",
        "The Agreement is not duly stamped.",
        "This Agreement is exempt from stamp duty under the applicable notification.",
        "No stamp duty certificate was obtained by either party.",
        "The parties agreed never to present the Agreement on stamped paper.",
    ]
    for text in negated:
        assert not detect_stamp_duty_mention(text), text


def test_tds_negated_mentions_are_not_confirmations():
    from nlp.ner.ner import detect_tds_mention

    negated = [
        "Payments shall be made without deduction of tax at source.",
        "The Provider is not responsible for deducting tax at source.",
        "No TDS shall apply to payments under this Agreement.",
        "The Customer shall never deduct tax at source from the fees.",
    ]
    for text in negated:
        assert not detect_tds_mention(text), text


def test_unrelated_negation_does_not_hide_valid_mentions():
    from nlp.ner.ner import detect_stamp_duty_mention, detect_tds_mention

    boundary_cases = [
        # A negated earlier sentence must not hide a valid later mention.
        "The Provider shall not be liable for delays. This Agreement is executed on duly stamped paper.",
        # "notwithstanding" is not the cue token "not".
        "Notwithstanding anything herein, this Agreement is executed on duly stamped paper.",
        # "no later than" sits far outside the negation window.
        "The invoice shall be paid no later than thirty days after execution on duly stamped paper.",
    ]
    for text in boundary_cases:
        assert detect_stamp_duty_mention(text), text
    tds_boundary = [
        "The Provider shall not charge for support. Payments are subject to deduction of tax at source.",
        "Notwithstanding the foregoing, the Customer shall deduct tax at source as required by law.",
    ]
    for text in tds_boundary:
        assert detect_tds_mention(text), text


def test_post_mention_negation_does_not_negate():
    from nlp.ner.ner import detect_stamp_duty_mention

    # Negation AFTER the mention does not deny the mention itself.
    assert detect_stamp_duty_mention(
        "The stamp duty on this Agreement shall not be borne by the Provider."
    )
