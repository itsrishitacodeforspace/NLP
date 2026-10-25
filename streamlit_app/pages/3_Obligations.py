"""Page 3 — Obligation tracker."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from streamlit_app.api_client import local_result

st.set_page_config(page_title="Obligations · BharatContract AI", page_icon="✅", layout="wide")


_TYPE_ICON = {
    "obligation": "📌",
    "right": "🟢",
    "prohibition": "🚫",
    "condition": "❓",
}

_RISK_COLOR = {
    "critical": "#7C3AED",
    "high": "#EF4444",
    "medium": "#F59E0B",
    "low": "#10B981",
}


def main() -> None:
    st.title("Obligation tracker")
    cid = st.session_state.get("contract_id")
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = local_result(cid)
    obligations = (local or {}).get("obligations", []) if local is not None else []
    if local is None:
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

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        type_filter = st.multiselect(
            "🏷️ Type",
            options=sorted(df["Type"].dropna().unique().tolist()),
            default=sorted(df["Type"].dropna().unique().tolist()),
        )
    with col2:
        risk_filter = st.multiselect(
            "🚦 Risk",
            options=sorted(df["Risk"].dropna().unique().tolist()),
            default=sorted(df["Risk"].dropna().unique().tolist()),
        )
    with col3:
        subject_filter = st.text_input("🔍 Filter by subject", value="")

    view = df[df["Type"].isin(type_filter) & df["Risk"].isin(risk_filter)]
    if subject_filter:
        view = view[view["Subject"].fillna("").str.contains(subject_filter, case=False, na=False)]

    # Summary chips
    chips = " ".join(
        f"<span style='background:{_RISK_COLOR.get(r, '#9CA3AF')}22;color:{_RISK_COLOR.get(r, '#9CA3AF')};"
        f"padding:4px 10px;border-radius:12px;margin:2px;font-weight:600;'>"
        f"{_TYPE_ICON.get(t, '•')} {t}: {(view['Type']==t).sum()}</span>"
        for t, r in [("obligation", "low"), ("right", "low"), ("prohibition", "low")]
    )
    if chips:
        st.markdown(chips, unsafe_allow_html=True)
    st.markdown("---")

    # Type icon column for the dataframe
    if not view.empty:
        view = view.copy()
        view["Type"] = view["Type"].apply(lambda t: f"{_TYPE_ICON.get(t, '')} {t}" if pd.notna(t) else t)

    st.dataframe(view, use_container_width=True, hide_index=True, height=420)

    st.download_button(
        "📥 Download CSV",
        view.to_csv(index=False).encode("utf-8"),
        file_name=f"obligations_{cid}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
