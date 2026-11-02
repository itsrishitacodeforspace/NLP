"""Streamlit Home page — upload + dashboard entry."""
from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from streamlit_app.api_client import (
    analyse_locally,
    api_base,
    get_job,
    set_api_base,
    set_current_contract_id,
    upload_contract,
)

st.set_page_config(
    page_title="BharatContract AI",
    page_icon="📜",
    layout="wide",
)


def main() -> None:
    st.title("BharatContract AI")
    st.caption("Risk-aware contract analysis for Indian & global agreements.")

    with st.sidebar:
        st.subheader("Backend")
        current_base = api_base()
        new_base = st.text_input("API base URL", value=current_base)
        if new_base and new_base != current_base:
            set_api_base(new_base)
            st.rerun()

        st.divider()
        st.subheader("Contract metadata")
        contract_type = st.selectbox(
            "Contract type",
            options=["MSA", "NDA", "SPA", "Employment", "Vendor", "Lease", "Service", "Other"],
            index=0,
        )
        user_role = st.selectbox(
            "Your role",
            options=[
                "Provider", "Customer", "Employer", "Employee",
                "Vendor", "Buyer", "Seller", "Neutral",
            ],
            index=1,
        )
        jurisdiction = st.text_input("Jurisdiction", value="India")
        st.session_state["contract_type"] = contract_type
        st.session_state["user_role"] = user_role
        st.session_state["jurisdiction"] = jurisdiction

    st.subheader("Upload a contract")
    uploaded = st.file_uploader(
        "Drop a PDF / DOCX / TXT file",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=False,
    )

    if not uploaded:
        st.info("Upload a contract to start. While you wait, here's a tiny demo:")
        if st.button("Run demo analysis on bundled sample MSA"):
            _run_local(st, Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_msa.txt")
        return

    if st.button("Analyze contract", type="primary"):
        _handle_upload(st, uploaded.read(), uploaded.name)


def _handle_upload(st, file_bytes: bytes, filename: str) -> None:
    contract_type = st.session_state.get("contract_type", "Other")
    user_role = st.session_state.get("user_role", "Customer")
    jurisdiction = st.session_state.get("jurisdiction", "India")

    # Try the API first
    try:
        job = upload_contract(
            file_bytes,
            filename,
            contract_type=contract_type,
            user_role=user_role,
            jurisdiction=jurisdiction,
        )
        progress = st.progress(0.05, text="Queued...")
        for _ in range(60):
            j = get_job(job["job_id"])
            progress.progress(
                min(1.0, float(j.get("progress", 0.0))),
                text=f"{j.get('status', '...')} — {j.get('message', '')}",
            )
            if j.get("status") == "succeeded":
                set_current_contract_id(j["contract_id"], j.get("result", {}).get("contract", {}).get("title"))
                st.session_state["last_result"] = j.get("result")
                progress.progress(1.0, text="Analysis complete")
                st.success(f"Contract analyzed — ID: `{j['contract_id']}`")
                st.page_link("pages/1_Summary.py", label="Open summary", icon="📄")
                return
            if j.get("status") == "failed":
                progress.progress(1.0, text="Failed")
                st.error(f"Analysis failed: {j.get('error', 'unknown error')}")
                return
            time.sleep(1)
        st.warning("Analysis is taking longer than expected — try opening the summary page.")
    except Exception as exc:
        st.warning(f"Backend API unreachable ({exc.__class__.__name__}); running in-process.")
        _run_local_bytes(st, file_bytes, filename)


def _run_local(st, path: Path) -> None:
    file_bytes = path.read_bytes()
    _run_local_bytes(st, file_bytes, path.name)


def _run_local_bytes(st, file_bytes: bytes, filename: str) -> None:
    with st.spinner("Analysing in-process..."):
        result = analyse_locally(
            file_bytes,
            filename,
            contract_type=st.session_state.get("contract_type", "Other"),
            user_role=st.session_state.get("user_role", "Customer"),
            jurisdiction=st.session_state.get("jurisdiction", "India"),
        )
    st.session_state["last_result"] = result
    set_current_contract_id(result["contract"]["contract_id"], result["contract"]["title"])
    st.success("Analysis complete — open the Summary page.")
    st.page_link("pages/1_Summary.py", label="Open summary", icon="📄")


if __name__ == "__main__":
    main()
