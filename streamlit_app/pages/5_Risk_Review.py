"""Page 5 — Risk review."""
from __future__ import annotations

import streamlit as st

from streamlit_app.api_client import current_contract_id, get_risks
from streamlit_app.components.risk_card import risk_card

st.set_page_config(page_title="Risk review · BharatContract AI", page_icon="⚠️", layout="wide")


def main() -> None:
    st.title("Risk review")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = st.session_state.get("last_result")
    if local:
        risks = local.get("risks", [])
    else:
        try:
            risks = get_risks(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    if not risks:
        st.success("No risks detected — review the playbook rules if needed.")
        return

    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    risks = sorted(risks, key=lambda r: severity_order.get(r.get("severity"), 0), reverse=True)

    sev_filter = st.multiselect(
        "Severity filter",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
    )
    for r in risks:
        if r.get("severity") not in sev_filter:
            continue
        risk_card(r)

    st.download_button(
        "Download risk JSON",
        str(risks).encode("utf-8"),
        file_name=f"risks_{cid}.json",
        mime="application/json",
    )


if __name__ == "__main__":
    main()
