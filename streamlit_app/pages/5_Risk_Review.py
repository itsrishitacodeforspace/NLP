"""Page 5 — Risk review."""
from __future__ import annotations

import json

import streamlit as st

from streamlit_app.api_client import current_contract_id, get_risks, local_result
from streamlit_app.components.risk_card import risk_card

st.set_page_config(page_title="Risk review · BharatContract AI", page_icon="⚠️", layout="wide")


def main() -> None:
    st.title("Risk review")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = local_result(cid)
    if local is not None:
        risks = local.get("risks", [])
    else:
        try:
            risks = get_risks(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    if not risks:
        st.success("✅ No risks detected — review the playbook rules if needed.")
        return

    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    risks = sorted(risks, key=lambda r: severity_order.get(r.get("severity"), 0), reverse=True)

    col1, col2 = st.columns([2, 3])
    with col1:
        sev_filter = st.multiselect(
            "🚦 Severity filter",
            options=["critical", "high", "medium", "low"],
            default=["critical", "high", "medium", "low"],
        )
    with col2:
        # Count summary
        counts = {sev: sum(1 for r in risks if r.get("severity") == sev) for sev in severity_order}
        chips = " ".join(
            f"<span style='background:{('#7C3AED' if s=='critical' else '#EF4444' if s=='high' else '#F59E0B' if s=='medium' else '#10B981')}22;"
            f"color:{('#7C3AED' if s=='critical' else '#EF4444' if s=='high' else '#F59E0B' if s=='medium' else '#10B981')};"
            f"padding:4px 10px;border-radius:12px;margin:2px;font-weight:600;'>"
            f"{s.upper()}: {counts[s]}</span>"
            for s in ["critical", "high", "medium", "low"]
            if counts[s]
        )
        if chips:
            st.markdown(chips, unsafe_allow_html=True)

    shown = 0
    for r in risks:
        if r.get("severity") not in sev_filter:
            continue
        risk_card(r)
        shown += 1

    if shown == 0:
        st.info("No risks match the current filter.")

    if shown:
        st.download_button(
            "📥 Download risks JSON",
            json.dumps(risks, indent=2, default=str).encode("utf-8"),
            file_name=f"risks_{cid}.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
