"""Page 4 — Graph explorer."""
from __future__ import annotations

import streamlit as st

from streamlit_app.api_client import current_contract_id, get_graph

st.set_page_config(page_title="Graph · BharatContract AI", page_icon="🕸️", layout="wide")


def main() -> None:
    st.title("Graph explorer")
    cid = current_contract_id()
    if not cid:
        st.warning("No contract analyzed yet.")
        return

    local = st.session_state.get("last_result")
    if local:
        graph = _local_to_graph(cid, local)
    else:
        try:
            graph = get_graph(cid)
        except Exception as exc:
            st.error(f"Failed: {exc}")
            return

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    st.caption(f"{len(nodes)} nodes · {len(edges)} edges")

    if not nodes:
        st.info("Graph is empty.")
        return

    try:
        from streamlit_agraph import Config, Edge, Node, agraph
    except Exception as exc:
        st.error(f"Graph renderer unavailable: {exc}")
        st.json(graph)
        return

    palette = {
        "Contract": "#1E40AF",
        "Clause": "#0EA5E9",
        "Obligation": "#10B981",
        "Risk": "#EF4444",
        "Party": "#A855F7",
    }

    g_nodes = [
        Node(
            id=n["id"],
            label=n["id"][:24] + ("…" if len(n["id"]) > 24 else ""),
            size=24 if n["label"] == "Contract" else 16,
            color=palette.get(n["label"], "#9CA3AF"),
            title=f"{n['label']}: {n.get('properties', {}).get('name') or n['id']}",
        )
        for n in nodes
    ]
    g_edges = [
        Edge(source=e["source"], target=e["target"], label=e["type"])
        for e in edges
    ]
    config = Config(width=900, height=600, directed=True, nodeHighlightBehavior=True, collapsible=False)
    agraph(nodes=g_nodes, edges=g_edges, config=config)


def _local_to_graph(cid: str, local: dict) -> dict:
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
    for r in local.get("risks", []):
        nodes.append(
            {
                "id": r["risk_id"],
                "label": "Risk",
                "properties": {"name": r.get("name"), "severity": r.get("severity")},
            }
        )
        if r.get("clause_id"):
            edges.append({"source": r["clause_id"], "target": r["risk_id"], "type": "TRIGGERS"})
    return {"contract_id": cid, "nodes": nodes, "edges": edges}


if __name__ == "__main__":
    main()
