"""Page 3 — Obligation tracker."""
from __future__ import annotations

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Obligations · BharatContract AI", page_icon="✅", layout="wide")


def main() -> None:
    st.title("Obligation tracker")
    cid = st.session_state.get("contract_id")
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = st.session_state.get("last_result")
    obligations = (local or {}).get("obligations", []) if local else []
    if not obligations:
        try:
            from streamlit_app.api_client import get_obligations

            obligations = get_obligations(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    if not obligations:
        st.info("No obligations extracted.")
        return

    rows = []
    for o in obligations:
        rows.append(
            {
                "ID": o.get("obligation_id"),
                "Type": o.get("obligation_type"),
                "Subject": o.get("subject"),
                "Action": o.get("action"),
                "Object": o.get("object"),
                "Deadline": o.get("deadline_expression") or o.get("deadline_date"),
                "Risk": o.get("risk_level"),
                "Confidence": round(o.get("confidence", 0.7), 2),
                "Clause": o.get("clause_id"),
            }
        )

    df = pd.DataFrame(rows)
    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.multiselect(
            "Type",
            sorted(df["Type"].dropna().unique().tolist()),
            default=sorted(df["Type"].dropna().unique().tolist()),
        )
    with col2:
        risk_filter = st.multiselect(
            "Risk level",
            sorted(df["Risk"].dropna().unique().tolist()),
            default=sorted(df["Risk"].dropna().unique().tolist()),
        )
    with col3:
        subject_filter = st.text_input("Filter by subject")

    view = df[df["Type"].isin(type_filter) & df["Risk"].isin(risk_filter)]
    if subject_filter:
        view = view[view["Subject"].fillna("").str.contains(subject_filter, case=False)]
    st.dataframe(view, width="stretch", hide_index=True)

    st.download_button(
        "Download CSV",
        view.to_csv(index=False).encode("utf-8"),
        file_name=f"obligations_{cid}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
