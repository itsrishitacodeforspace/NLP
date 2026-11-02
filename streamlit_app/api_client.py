"""Shared API helpers for the Streamlit UI."""
from __future__ import annotations

import os
from typing import Optional

import httpx
import streamlit as st

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def api_base() -> str:
    return st.session_state.get("api_base", DEFAULT_API_BASE)


def set_api_base(url: str) -> None:
    st.session_state["api_base"] = url


def upload_contract(
    file_bytes: bytes,
    filename: str,
    *,
    contract_type: str,
    user_role: str,
    jurisdiction: str,
    playbook_id: Optional[str] = None,
) -> dict:
    data = {
        "contract_type": contract_type,
        "user_role": user_role,
        "jurisdiction": jurisdiction,
    }
    if playbook_id:
        data["playbook_id"] = playbook_id
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    r = httpx.post(
        f"{api_base()}/api/v1/contracts/upload",
        data=data,
        files=files,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def get_job(job_id: str) -> dict:
    r = httpx.get(f"{api_base()}/api/v1/jobs/{job_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def get_summary(contract_id: str) -> dict:
    r = httpx.get(f"{api_base()}/api/v1/contracts/{contract_id}/summary", timeout=30)
    r.raise_for_status()
    return r.json()


def get_clauses(contract_id: str) -> list[dict]:
    r = httpx.get(f"{api_base()}/api/v1/contracts/{contract_id}/clauses", timeout=30)
    r.raise_for_status()
    return r.json().get("clauses", [])


def get_obligations(contract_id: str) -> list[dict]:
    r = httpx.get(f"{api_base()}/api/v1/contracts/{contract_id}/obligations", timeout=30)
    r.raise_for_status()
    return r.json().get("obligations", [])


def get_risks(contract_id: str) -> list[dict]:
    r = httpx.get(f"{api_base()}/api/v1/contracts/{contract_id}/risks", timeout=30)
    r.raise_for_status()
    return r.json().get("risks", [])


def get_graph(contract_id: str) -> dict:
    r = httpx.get(f"{api_base()}/api/v1/graph/{contract_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def analyse_locally(
    file_bytes: bytes,
    filename: str,
    *,
    contract_type: str,
    user_role: str,
    jurisdiction: str,
) -> dict:
    """Fallback when the API server is unreachable — analyse in-process."""
    from app.models.schemas import ContractType, PartySide
    from app.services.analyzer import analyse_bytes

    result = analyse_bytes(
        file_bytes,
        filename,
        contract_id="local",
        contract_type=ContractType(contract_type),
        user_role=PartySide(user_role),
        jurisdiction=jurisdiction,
    )
    return {
        "contract": result.contract.model_dump(mode="json"),
        "clauses": [c.model_dump(mode="json") for c in result.clauses],
        "obligations": [o.model_dump(mode="json") for o in result.obligations],
        "risks": [r.model_dump(mode="json") for r in result.risks],
        "warnings": result.warnings,
    }


def current_contract_id() -> Optional[str]:
    return st.session_state.get("contract_id")


def local_result(cid: Optional[str]) -> Optional[dict]:
    """Return the in-process result only when it belongs to the active contract."""
    result = st.session_state.get("last_result")
    if result and result.get("contract", {}).get("contract_id") == cid:
        return result
    return None


def set_current_contract_id(cid: Optional[str], title: Optional[str] = None) -> None:
    st.session_state["contract_id"] = cid
    if title:
        st.session_state["contract_title"] = title
