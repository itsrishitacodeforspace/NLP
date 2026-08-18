"""Page 2 — Clause explorer."""
from __future__ import annotations

import streamlit as st

from streamlit_app.api_client import current_contract_id, get_clauses
from streamlit_app.components.risk_card import clause_card

st.set_page_config(page_title="Clause explorer · BharatContract AI", page_icon="📑", layout="wide")


def main() -> None:
    st.title("Clause explorer")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = st.session_state.get("last_result")
    if local:
        clauses = local.get("clauses", [])
    else:
        try:
            clauses = get_clauses(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    if not clauses:
        st.info("No clauses extracted.")
        return

    col1, col2, col3 = st.columns(3)
    types = sorted({t for c in clauses for t in c.get("clause_types") or []})
    risk_levels = sorted({c.get("risk_level", "low") for c in clauses})
    with col1:
        type_filter = st.multiselect("Clause types", types, default=types)
    with col2:
        risk_filter = st.multiselect("Risk levels", risk_levels, default=risk_levels)
    with col3:
        query = st.text_input("Search text", value="")

    filtered = []
    for c in clauses:
        types_present = c.get("clause_types") or []
        if type_filter and not any(t in type_filter for t in types_present):
            continue
        if risk_filter and c.get("risk_level") not in risk_filter:
            continue
        if query and query.lower() not in (c.get("text", "")).lower():
            continue
        filtered.append(c)

    st.write(f"{len(filtered)} of {len(clauses)} clauses match.")
    for cl in filtered:
        clause_card(cl)


if __name__ == "__main__":
    main()
