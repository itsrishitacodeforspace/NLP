"""Cypher query library + graph writer."""
from __future__ import annotations

from typing import List

from app.core.logging import get_logger
from app.db.neo4j import run_read, run_write
from app.models.schemas import (
    AnalysisResult,
    Clause,
    ContractSummary,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    Obligation,
    RiskFlag,
)

logger = get_logger()


# ---------------------------------------------------------------------------
# Write helpers (idempotent via MERGE)
# ---------------------------------------------------------------------------


def upsert_contract(contract: ContractSummary) -> bool:
    query = """
    MERGE (c:Contract {contract_id: $contract_id})
    SET c.title = $title,
        c.file_name = $file_name,
        c.contract_type = $contract_type,
        c.parties = $parties,
        c.effective_date = $effective_date,
        c.expiry_date = $expiry_date,
        c.governing_law = $governing_law,
        c.arbitration_seat = $arbitration_seat,
        c.stamp_duty_mentioned = $stamp_duty_mentioned,
        c.tds_mentioned = $tds_mentioned,
        c.gstin_mentioned = $gstin_mentioned,
        c.overall_risk_score = $overall_risk_score,
        c.overall_risk_level = $overall_risk_level,
        c.analyzed_at = datetime($analyzed_at)
    RETURN c
    """
    try:
        run_write(
            query,
            {
                "contract_id": contract.contract_id,
                "title": contract.title,
                "file_name": contract.file_name,
                "contract_type": contract.contract_type.value,
                "parties": contract.parties,
                "effective_date": contract.effective_date,
                "expiry_date": contract.expiry_date,
                "governing_law": contract.governing_law,
                "arbitration_seat": contract.arbitration_seat,
                "stamp_duty_mentioned": contract.stamp_duty_mentioned,
                "tds_mentioned": contract.tds_mentioned,
                "gstin_mentioned": contract.gstin_mentioned,
                "overall_risk_score": contract.overall_risk_score,
                "overall_risk_level": contract.overall_risk_level.value,
                "analyzed_at": contract.analyzed_at.isoformat(),
            },
        )
        return True
    except Exception as exc:
        logger.warning("upsert_contract failed: {}", exc)
        return False


def upsert_clause(contract_id: str, clause: Clause) -> bool:
    query = """
    MATCH (c:Contract {contract_id: $contract_id})
    MERGE (cl:Clause {clause_id: $clause_id})
    SET cl.contract_id = $contract_id,
        cl.section_number = $section_number,
        cl.heading = $heading,
        cl.text = $text,
        cl.page_hint = $page_hint,
        cl.char_start = $char_start,
        cl.char_end = $char_end,
        cl.clause_types = $clause_types,
        cl.risk_score = $risk_score,
        cl.risk_level = $risk_level
    MERGE (c)-[:HAS_CLAUSE]->(cl)
    RETURN cl
    """
    try:
        run_write(
            query,
            {
                "contract_id": contract_id,
                "clause_id": clause.clause_id,
                "section_number": clause.section_number,
                "heading": clause.heading,
                "text": clause.text,
                "page_hint": clause.page_hint,
                "char_start": clause.char_start,
                "char_end": clause.char_end,
                "clause_types": clause.clause_types,
                "risk_score": clause.risk_score,
                "risk_level": clause.risk_level.value,
            },
        )
        return True
    except Exception as exc:
        logger.warning("upsert_clause failed for {}: {}", clause.clause_id, exc)
        return False


def upsert_obligation(contract_id: str, obligation: Obligation) -> bool:
    query = """
    MATCH (cl:Clause {clause_id: $clause_id})
    MERGE (o:Obligation {obligation_id: $obligation_id})
    SET o.contract_id = $contract_id,
        o.text = $text,
        o.obligation_type = $obligation_type,
        o.subject = $subject,
        o.counterparty = $counterparty,
        o.action = $action,
        o.object = $object,
        o.condition = $condition,
        o.deadline_expression = $deadline_expression,
        o.deadline_date = $deadline_date,
        o.risk_level = $risk_level,
        o.confidence = $confidence
    MERGE (cl)-[:IMPOSES]->(o)
    RETURN o
    """
    try:
        run_write(
            query,
            {
                "clause_id": obligation.clause_id,
                "contract_id": contract_id,
                "obligation_id": obligation.obligation_id,
                "text": obligation.text,
                "obligation_type": obligation.obligation_type.value,
                "subject": obligation.subject,
                "counterparty": obligation.counterparty,
                "action": obligation.action,
                "object": obligation.object,
                "condition": obligation.condition,
                "deadline_expression": obligation.deadline_expression,
                "deadline_date": obligation.deadline_date,
                "risk_level": obligation.risk_level.value,
                "confidence": obligation.confidence,
            },
        )
        return True
    except Exception as exc:
        logger.warning("upsert_obligation failed: {}", exc)
        return False


def upsert_risk(contract_id: str, risk: RiskFlag) -> bool:
    """Persist a RiskFlag. If risk has a clause_id, link via :TRIGGERS."""
    base_query = """
    MERGE (r:Risk {risk_id: $risk_id})
    SET r.contract_id = $contract_id,
        r.rule_id = $rule_id,
        r.name = $name,
        r.severity = $severity,
        r.explanation = $explanation,
        r.recommendation = $recommendation,
        r.score = $score
    """
    try:
        run_write(
            base_query,
            {
                "risk_id": risk.risk_id,
                "contract_id": contract_id,
                "rule_id": risk.rule_id,
                "name": risk.name,
                "severity": risk.severity.value,
                "explanation": risk.explanation,
                "recommendation": risk.recommendation,
                "score": risk.score,
            },
        )
        if risk.clause_id:
            link_query = """
            MATCH (r:Risk {risk_id: $risk_id}), (cl:Clause {clause_id: $clause_id})
            MERGE (cl)-[:TRIGGERS]->(r)
            """
            run_write(link_query, {"risk_id": risk.risk_id, "clause_id": risk.clause_id})
        return True
    except Exception as exc:
        logger.warning("upsert_risk failed: {}", exc)
        return False


def upsert_party(contract_id: str, party_name: str) -> bool:
    query = """
    MATCH (c:Contract {contract_id: $contract_id})
    MERGE (p:Party {name: $name})
    MERGE (c)-[:HAS_PARTY]->(p)
    RETURN p
    """
    try:
        run_write(query, {"contract_id": contract_id, "name": party_name})
        return True
    except Exception as exc:
        logger.warning("upsert_party failed: {}", exc)
        return False


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def fetch_graph(contract_id: str) -> GraphSnapshot:
    """Return the subgraph for a contract as plain Python dicts."""
    nodes_query = """
    MATCH (n)
    WHERE (n.contract_id = $cid) OR
          (n)-[:HAS_CLAUSE|IMPOSES|TRIGGERS|HAS_PARTY]-({contract_id: $cid})
    RETURN DISTINCT
        coalesce(n.contract_id, n.clause_id, n.obligation_id, n.risk_id, n.name) AS id,
        labels(n)[0] AS label,
        properties(n) AS properties
    """
    edges_query = """
    MATCH (a)-[r]->(b)
    WHERE (a.contract_id = $cid OR b.contract_id = $cid OR
           a.clause_id IN $clause_ids OR b.clause_id IN $clause_ids)
    RETURN DISTINCT
        coalesce(a.contract_id, a.clause_id, a.obligation_id, a.risk_id, a.name) AS source,
        coalesce(b.contract_id, b.clause_id, b.obligation_id, b.risk_id, b.name) AS target,
        type(r) AS type
    """

    raw_nodes = run_read(nodes_query, {"cid": contract_id})
    if not raw_nodes:
        return GraphSnapshot(contract_id=contract_id, nodes=[], edges=[])

    clause_ids = [
        n["properties"].get("clause_id")
        for n in raw_nodes
        if n.get("label") == "Clause" and n["properties"].get("clause_id")
    ]
    raw_edges = run_read(edges_query, {"cid": contract_id, "clause_ids": clause_ids})

    nodes: List[GraphNode] = []
    for n in raw_nodes:
        props = dict(n.get("properties") or {})
        # Trim noisy fields
        for k in ("text", "heading"):
            if k in props and isinstance(props[k], str) and len(props[k]) > 280:
                props[k] = props[k][:280] + "..."
        nodes.append(GraphNode(id=str(n["id"]), label=str(n["label"]), properties=props))
    edges: List[GraphEdge] = [
        GraphEdge(source=str(e["source"]), target=str(e["target"]), type=str(e["type"]))
        for e in raw_edges
    ]
    return GraphSnapshot(contract_id=contract_id, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# High-level writer
# ---------------------------------------------------------------------------


def write_analysis(analysis: AnalysisResult) -> bool:
    """Persist an entire analysis result. Returns True if everything succeeded."""
    contract = analysis.contract
    success = True
    success &= upsert_contract(contract)
    for party in contract.parties:
        success &= upsert_party(contract.contract_id, party)
    for clause in analysis.clauses:
        success &= upsert_clause(contract.contract_id, clause)
    for obligation in analysis.obligations:
        success &= upsert_obligation(contract.contract_id, obligation)
    for risk in analysis.risks:
        success &= upsert_risk(contract.contract_id, risk)
    logger.info("Graph write for {}: {}", contract.contract_id, "ok" if success else "partial failure")
    return success
