"""Page 1 — Executive summary."""
from __future__ import annotations

import streamlit as st

from streamlit_app.api_client import (
    current_contract_id,
    get_clauses,
    get_obligations,
    get_risks,
    get_summary,
)
from streamlit_app.components.risk_card import contract_header, risk_card

st.set_page_config(page_title="Summary · BharatContract AI", page_icon="📊", layout="wide")


def _local_result():
    return st.session_state.get("last_result")


def main() -> None:
    st.title("Executive summary")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet. Go to Home and upload one.")
        return
    local = _local_result()
    if local:
        contract = local["contract"]
        risks = local.get("risks", [])
        obligations = local.get("obligations", [])
        clauses = local.get("clauses", [])
    else:
        try:
            contract = get_summary(cid)
            risks = get_risks(cid)
            obligations = get_obligations(cid)
            clauses = get_clauses(cid)
        except Exception as exc:
            st.error(f"Failed to fetch summary: {exc}")
            return

    contract_header(contract)

    st.divider()

    # Top risks
    st.subheader("Top risks")
    top = sorted(
        risks,
        key=lambda r: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(r.get("severity"), 0),
        reverse=True,
    )[:5]
    if not top:
        st.success("No major risks detected.")
    for r in top:
        risk_card(r)

    st.divider()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.subheader("Key dates & parties")
        st.write(
            {
                "Parties": contract.get("parties") or [],
                "Effective date": contract.get("effective_date"),
                "Governing law": contract.get("governing_law"),
                "Arbitration seat": contract.get("arbitration_seat"),
            }
        )
    with col_b:
        st.subheader("Compliance signals")
        st.write(
            {
                "Stamp duty mentioned": contract.get("stamp_duty_mentioned"),
                "TDS mentioned": contract.get("tds_mentioned"),
                "GSTIN mentioned": contract.get("gstin_mentioned"),
            }
        )
    with col_c:
        st.subheader("Missing clauses")
        missing = contract.get("missing_clauses") or []
        if missing:
            for m in missing:
                st.warning(m)
        else:
            st.success("All mandatory clauses detected.")

    st.divider()
    st.subheader(f"Obligation summary ({len(obligations)})")
    types = {}
    for o in obligations:
        t = o.get("obligation_type", "obligation")
        types[t] = types.get(t, 0) + 1
    st.write(types if types else "No obligations extracted.")

    st.divider()
    st.subheader(f"Clause summary ({len(clauses)})")
    cat_counts: dict[str, int] = {}
    for c in clauses:
        for t in c.get("clause_types") or []:
            cat_counts[t] = cat_counts.get(t, 0) + 1
    st.write(cat_counts)


if __name__ == "__main__":
    main()
