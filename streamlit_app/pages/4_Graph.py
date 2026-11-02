"""Page 4 — Graph explorer."""
from __future__ import annotations

import html

import streamlit as st

from streamlit_app.api_client import current_contract_id, get_graph, local_result

st.set_page_config(page_title="Graph · BharatContract AI", page_icon="🕸️", layout="wide")


# Beautiful palette with high-contrast text-friendly colours.
PALETTE = {
    "Contract": {"fill": "#1E3A8A", "border": "#1E40AF", "font": "#FFFFFF", "size": 40},
    "Clause":   {"fill": "#0EA5E9", "border": "#0369A1", "font": "#FFFFFF", "size": 26},
    "Obligation": {"fill": "#10B981", "border": "#047857", "font": "#FFFFFF", "size": 22},
    "Risk":     {"fill": "#EF4444", "border": "#B91C1C", "font": "#FFFFFF", "size": 22},
    "Party":    {"fill": "#A855F7", "border": "#7E22CE", "font": "#FFFFFF", "size": 24},
}

_RELATION_STYLE = {
    "HAS_CLAUSE":   {"color": "#0EA5E9", "label": "contains"},
    "IMPOSES":      {"color": "#10B981", "label": "imposes"},
    "TRIGGERS":     {"color": "#EF4444", "label": "triggers"},
    "HAS_PARTY":    {"color": "#A855F7", "label": "between"},
    "HAS_OBLIGATION": {"color": "#10B981", "label": "imposes"},
}


def _short(value: str, n: int = 26) -> str:
    if not value:
        return ""
    return value if len(value) <= n else value[: n - 1] + "…"


def main() -> None:
    st.title("Graph explorer")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = local_result(cid)
    if local is not None:
        graph = _local_to_graph(cid, local)
    else:
        try:
            graph = get_graph(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        st.info("Graph is empty for this contract.")
        return

    # Sidebar: filters
    with st.sidebar:
        st.subheader("Filters")
        all_labels = sorted({n["label"] for n in nodes})
        show_labels = st.multiselect(
            "Node types",
            options=all_labels,
            default=all_labels,
        )
        all_rel_types = sorted({e["type"] for e in edges})
        show_rels = st.multiselect(
            "Relationships",
            options=all_rel_types,
            default=all_rel_types,
        )

    filtered_nodes = [n for n in nodes if n["label"] in show_labels]
    filtered_ids = {n["id"] for n in filtered_nodes}
    filtered_edges = [
        e for e in edges
        if e["source"] in filtered_ids and e["target"] in filtered_ids and e["type"] in show_rels
    ]

    # Stats row
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Nodes", len(filtered_nodes))
    with stat_col2:
        st.metric("Edges", len(filtered_edges))
    with stat_col3:
        st.metric("Contract", _short(cid, 18))
    with stat_col4:
        clause_count = sum(1 for n in filtered_nodes if n["label"] == "Clause")
        st.metric("Clauses", clause_count)

    try:
        from streamlit_agraph import Config, Edge, Node, agraph
    except Exception as exc:
        st.error(f"Graph renderer unavailable: {exc}")
        st.json(graph)
        return

    g_nodes = []
    for n in filtered_nodes:
        style = PALETTE.get(n["label"], {"fill": "#9CA3AF", "border": "#6B7280", "font": "#FFFFFF", "size": 20})
        props = n.get("properties", {})
        tooltip = (
            f"<b>{html.escape(str(n['label']))}</b><br/>"
            f"{html.escape(str(props.get('heading') or props.get('name') or n['id']))}"
        )
        g_nodes.append(
            Node(
                id=n["id"],
                label=_short(n["id"].split("_")[-1] if "_" in n["id"] else n["id"], 22),
                size=style["size"],
                color={
                    "background": style["fill"],
                    "border": style["border"],
                    "highlight": {"background": style["fill"], "border": "#FBBF24"},
                    "hover": {"background": style["fill"], "border": "#FBBF24"},
                },
                font={"color": style["font"], "size": 14, "face": "Inter, Arial"},
                title=tooltip,
                shape="dot",
                borderWidth=2,
                shadow=True,
            )
        )

    g_edges = []
    for e in filtered_edges:
        style = _RELATION_STYLE.get(e["type"], {"color": "#94A3B8", "label": e["type"]})
        g_edges.append(
            Edge(
                source=e["source"],
                target=e["target"],
                label=style["label"],
                color={"color": style["color"], "highlight": "#FBBF24"},
                width=1.5,
                smooth={"enabled": True, "type": "curvedCW", "roundness": 0.15},
                arrows={"to": {"enabled": True, "scaleFactor": 0.6}},
                font={"size": 11, "color": "#374151", "face": "Inter, Arial", "strokeWidth": 0},
            )
        )

    config = Config(
        width=1100,
        height=620,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        collapsible=False,
        highlightDegree=1,
        hover=True,
        node={"labelProperty": "label"},
        link={"labelProperty": "label", "renderLabel": True},
        d3={
            "alphaDecay": 0.05,
            "gravity": -120,
            "linkLength": 90,
            "linkStrength": 0.4,
            "disableLinkForce": False,
        },
        interaction={"hover": True, "tooltipDelay": 80, "zoomView": True, "dragView": True},
    )

    st.caption(f"{len(g_nodes)} nodes · {len(g_edges)} edges — hover for details")
    agraph(nodes=g_nodes, edges=g_edges, config=config)

    # Legend
    st.markdown("---")
    st.markdown("**Legend**")
    legend_items = "".join(
        f"<span style='background:{s['fill']};color:{s['font']};padding:4px 10px;"
        f"border-radius:12px;margin:4px;display:inline-block;font-weight:600;'>"
        f"{label}</span>"
        for label, s in PALETTE.items()
    )
    st.markdown(legend_items, unsafe_allow_html=True)


def _local_to_graph(cid: str, local: dict) -> dict:
    """Build a graph from the in-memory AnalysisResult."""
    nodes = []
    edges = []
    contract = local.get("contract", {})
    nodes.append(
        {
            "id": cid,
            "label": "Contract",
            "properties": {
                "title": contract.get("title"),
                "risk_score": contract.get("overall_risk_score"),
                "risk_level": contract.get("overall_risk_level"),
            },
        }
    )
    for c in local.get("clauses", []):
        nodes.append(
            {
                "id": c["clause_id"],
                "label": "Clause",
                "properties": {
                    "heading": c.get("heading"),
                    "clause_types": c.get("clause_types"),
                    "risk_score": c.get("risk_score"),
                },
            }
        )
        edges.append({"source": cid, "target": c["clause_id"], "type": "HAS_CLAUSE"})
    for o in local.get("obligations", []):
        nodes.append(
            {
                "id": o["obligation_id"],
                "label": "Obligation",
                "properties": {
                    "type": o.get("obligation_type"),
                    "action": o.get("action"),
                    "deadline": o.get("deadline_expression"),
                },
            }
        )
        edges.append({"source": o["clause_id"], "target": o["obligation_id"], "type": "IMPOSES"})
    for rk in local.get("risks", []):
        nodes.append(
            {
                "id": rk["risk_id"],
                "label": "Risk",
                "properties": {"name": rk.get("name"), "severity": rk.get("severity")},
            }
        )
        if rk.get("clause_id"):
            edges.append({"source": rk["clause_id"], "target": rk["risk_id"], "type": "TRIGGERS"})
    return {"contract_id": cid, "nodes": nodes, "edges": edges}


if __name__ == "__main__":
    main()
