"""API smoke test: upload, poll, then read summary, graph, and job result."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_upload_analysis_roundtrip():
    with TestClient(app) as client:
        with (ROOT / "data" / "raw" / "sample_msa.txt").open("rb") as fh:
            response = client.post(
                "/api/v1/contracts/upload?async_mode=true",
                files={"file": ("sample_msa.txt", fh, "text/plain")},
            )
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]

        status = "queued"
        for _ in range(480):
            poll = client.get(f"/api/v1/jobs/{job_id}")
            assert poll.status_code == 200, poll.text
            status = poll.json()["status"]
            if status in {"succeeded", "failed"}:
                break
            time.sleep(0.25)
        assert status == "succeeded"

        result = poll.json()
        assert result["result"]
        contract_id = result["result"]["contract"]["contract_id"]
        assert client.get(f"/api/v1/contracts/{contract_id}/summary").status_code == 200
        graph = client.get(f"/api/v1/graph/{contract_id}")
        assert graph.status_code == 200
        assert graph.json()["nodes"]
