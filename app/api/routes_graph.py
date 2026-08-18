"""Graph routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.queries import fetch_graph
from app.services.jobs import list_jobs


router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/{contract_id}")
def get_graph(contract_id: str):
    """Return the subgraph for a contract. Falls back to in-memory job results
    if Neo4j is unavailable so the UI can still render in the demo.
    """
    snapshot = fetch_graph(contract_id)
    if snapshot.nodes:
        return snapshot
    # In-memory fallback
    for j in list_jobs():
        if j.contract_id == contract_id and j.result:
            return _graph_from_result(j.result.contract_id, j.result)
    raise HTTPException(status_code=404, detail="Graph not available")


def _graph_from_result(contract_id: str, result) -> dict:
    """Build a simple in-memory graph when Neo4j is down."""
    nodes: list[dict] = []
    edges: list[dict] = []
    nodes.append(
        {
            "id": contract_id,
            "label": "Contract",
            "properties": {
                "title": result.contract.title,
                "risk_score": result.contract.overall_risk_score,
                "risk_level": result.contract.overall_risk_level.value,
            },
        }
    )
    for cl in result.clauses:
        nodes.append(
            {
                "id": cl.clause_id,
                "label": "Clause",
                "properties": {
                    "heading": cl.heading,
                    "clause_types": cl.clause_types,
                    "risk_score": cl.risk_score,
                    "risk_level": cl.risk_level.value,
                },
            }
        )
        edges.append({"source": contract_id, "target": cl.clause_id, "type": "HAS_CLAUSE"})
    for ob in result.obligations:
        nodes.append(
            {
                "id": ob.obligation_id,
                "label": "Obligation",
                "properties": {
                    "type": ob.obligation_type.value,
                    "action": ob.action,
                    "deadline": ob.deadline_expression,
                },
            }
        )
        edges.append({"source": ob.clause_id, "target": ob.obligation_id, "type": "IMPOSES"})
    for rk in result.risks:
        nodes.append(
            {
                "id": rk.risk_id,
                "label": "Risk",
                "properties": {"name": rk.name, "severity": rk.severity.value},
            }
        )
        if rk.clause_id:
            edges.append({"source": rk.clause_id, "target": rk.risk_id, "type": "TRIGGERS"})
    return {"contract_id": contract_id, "nodes": nodes, "edges": edges}