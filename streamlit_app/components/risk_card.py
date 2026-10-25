"""Streamlit UI components."""
from __future__ import annotations

import html

import streamlit as st

SEVERITY_COLORS = {
    "low": "#10B981",
    "medium": "#F59E0B",
    "high": "#EF4444",
    "critical": "#7C3AED",
}


def risk_badge(level: str) -> str:
    colour = SEVERITY_COLORS.get(level, "#9CA3AF")
    return (
        f"<span style='background:{colour}22;color:{colour};"
        f"padding:2px 10px;border-radius:12px;font-weight:600;'>"
        f"{level.upper()}</span>"
    )


def contract_header(contract: dict) -> None:
    title = html.escape(str(contract.get("title", "Untitled contract")))
    file_name = html.escape(str(contract.get("file_name", "")))
    risk = contract.get("overall_risk_level", "low")
    score = contract.get("overall_risk_score", 0)
    st.markdown(f"## {title}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**File:** `{file_name}`")
        st.markdown(f"**Type:** `{contract.get('contract_type', 'OTHER')}`")
    with col2:
        st.markdown(f"**Jurisdiction:** `{contract.get('jurisdiction', 'India')}`")
        st.markdown(f"**Parties:** {', '.join(contract.get('parties') or []) or '—'}")
    with col3:
        st.markdown(
            f"<div>Overall Risk: {risk_badge(risk)} "
            f"<span style='margin-left:10px;font-weight:700;'>{score:.0f}/100</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<small>{contract.get('clause_count', 0)} clauses · "
            f"{contract.get('obligation_count', 0)} obligations</small>",
            unsafe_allow_html=True,
        )


def risk_card(risk: dict) -> None:
    severity = risk.get("severity", "low")
    colour = SEVERITY_COLORS.get(severity, "#9CA3AF")
    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<strong>{html.escape(str(risk.get('name', 'Risk')))}</strong>"
            f"<span style='background:{colour}22;color:{colour};"
            f"padding:2px 10px;border-radius:12px;font-weight:600;'>"
            f"{severity.upper()}</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Rule: `{risk.get('rule_id', 'N/A')}` · Score: {risk.get('score', 0):.0f}")
        st.write(risk.get("explanation", ""))
        rec = risk.get("recommendation")
        if rec:
            st.info(f"**Recommendation:** {rec}")


def clause_card(clause: dict) -> None:
    risk_level = clause.get("risk_level", "low")
    colour = SEVERITY_COLORS.get(risk_level, "#9CA3AF")
    with st.container(border=True):
        h = clause.get("heading") or clause.get("section_number") or clause.get("clause_id", "Clause")
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<strong>{html.escape(str(h))}</strong>"
            f"<span style='background:{colour}22;color:{colour};"
            f"padding:2px 10px;border-radius:12px;font-weight:600;'>"
            f"{risk_level.upper()} · {clause.get('risk_score', 0):.0f}</span></div>",
            unsafe_allow_html=True,
        )
        types = clause.get("clause_types") or []
        if types:
            st.caption(" · ".join(types))
        text = clause.get("text", "")
        with st.expander("View clause text"):
            st.write(text)
        reasons = clause.get("risk_reasons") or []
        if reasons:
            st.markdown("**Risk reasons:** " + ", ".join(reasons))
        ents = clause.get("entities") or []
        if ents:
            chips = ", ".join(
                f"`{e['label']}: {e['text']}`" for e in ents[:8]
            )
            st.caption("Entities: " + chips)
