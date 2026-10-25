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
