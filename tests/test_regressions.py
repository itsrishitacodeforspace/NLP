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
