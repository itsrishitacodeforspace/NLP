"""Page 1 — Executive summary."""
from __future__ import annotations

import html

import streamlit as st

from streamlit_app.api_client import (
    current_contract_id,
    get_clauses,
    get_obligations,
    get_risks,
    get_summary,
    local_result,
)
from streamlit_app.components.risk_card import contract_header, risk_card

st.set_page_config(page_title="Summary · BharatContract AI", page_icon="📊", layout="wide")


def _local_result():
    return local_result(current_contract_id())


_SEVERITY_ICON = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}
_BOOL_ICON = {True: "✅", False: "❌"}


def _render_parties(parties: list) -> None:
    if not parties:
        st.markdown(
            "<span style='color:#9CA3AF;'>No parties detected.</span>",
            unsafe_allow_html=True,
        )
        return
    chips = " ".join(
        f"<span style='background:#EEF2FF;color:#1E40AF;padding:4px 10px;"
        f"border-radius:14px;margin:2px;display:inline-block;font-size:13px;'>"
        f"{html.escape(str(p))}</span>"
        for p in parties
    )
    st.markdown(chips, unsafe_allow_html=True)


def _kv(label: str, value: str, *, empty: str = "—") -> None:
    safe = html.escape((value or "").strip())
    body = (
        f"<span style='color:#111827;'>{safe}</span>"
        if safe
        else f"<span style='color:#9CA3AF;font-style:italic;'>{empty}</span>"
    )
    st.markdown(
        f"<div style='margin:6px 0;'><strong style='color:#374151;'>{label}:</strong> {body}</div>",
        unsafe_allow_html=True,
    )


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
    st.subheader(f"Top risks ({len(risks)} total)")
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
        st.markdown("### 👥 Key dates & parties")
        parties = contract.get("parties") or []
        st.markdown("<small><strong>Parties</strong></small>", unsafe_allow_html=True)
        _render_parties(parties)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _kv("📅  Effective date", contract.get("effective_date"))
        _kv("⚖️  Governing law", contract.get("governing_law"))
        _kv("📍  Arbitration seat", contract.get("arbitration_seat"))

    with col_b:
        st.markdown("### 📋 Compliance signals")
        signals = [
            ("Stamp duty mentioned", contract.get("stamp_duty_mentioned")),
            ("TDS mentioned", contract.get("tds_mentioned")),
            ("GSTIN mentioned", contract.get("gstin_mentioned")),
        ]
        for label, val in signals:
            icon = _BOOL_ICON.get(bool(val), "❔")
            color = "#065F46" if val else "#9F1239"
            st.markdown(
                f"<div style='margin:6px 0;'>"
                f"<span style='font-size:18px;'>{icon}</span> "
                f"<strong style='color:#374151;'>{label}:</strong> "
                f"<span style='color:{color};font-weight:600;'>{'Yes' if val else 'No'}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with col_c:
        st.markdown("### ⚠️ Missing clauses")
        missing = contract.get("missing_clauses") or []
        if missing:
            for m in missing:
                st.markdown(
                    f"<div style='background:#FEF2F2;border-left:3px solid #EF4444;"
                    f"padding:6px 10px;margin:4px 0;border-radius:4px;color:#7F1D1D;'>"
                    f"{html.escape(str(m))}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='background:#ECFDF5;border-left:3px solid #10B981;"
                "padding:8px 12px;border-radius:4px;color:#065F46;'>"
                "✅ All mandatory clauses detected.</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    col_o, col_c2 = st.columns(2)
    with col_o:
        st.markdown(f"### 📌 Obligations ({len(obligations)})")
        types = {}
        for o in obligations:
            t = o.get("obligation_type", "obligation")
            types[t] = types.get(t, 0) + 1
        if types:
            for kind, count in sorted(types.items(), key=lambda kv: -kv[1]):
                icon = {"obligation": "📌", "right": "🟢", "prohibition": "🚫"}.get(kind, "•")
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:6px 12px;margin:4px 0;background:#F9FAFB;"
                    f"border-radius:6px;'>"
                    f"<span>{icon} <strong style='text-transform:capitalize;'>{kind}s</strong></span>"
                    f"<span style='color:#1E40AF;font-weight:700;'>{count}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No obligations extracted.")

    with col_c2:
        st.markdown(f"### 🧩 Clauses ({len(clauses)})")
        cat_counts: dict[str, int] = {}
        for c in clauses:
            for t in c.get("clause_types") or []:
                cat_counts[t] = cat_counts.get(t, 0) + 1
        if cat_counts:
            for cat, count in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:6px 12px;margin:4px 0;background:#F9FAFB;"
                    f"border-radius:6px;'>"
                    f"<span>📄 <strong>{cat}</strong></span>"
                    f"<span style='color:#1E40AF;font-weight:700;'>{count}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No clauses classified.")


if __name__ == "__main__":
    main()
