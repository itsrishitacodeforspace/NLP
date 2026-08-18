"""High-level orchestrator: parser -> segmenter -> NLP -> risk -> graph."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger
from app.models.schemas import (
    AnalysisResult,
    Clause,
    ContractSummary,
    ContractType,
    JobStatus,
    Obligation,
    PartySide,
    RiskFlag,
    RiskSeverity,
)
from app.services.parser import parse_bytes, parse_document
from app.services.segmenter import segment_clauses
from nlp.clause_classification.classifier import classify_clause
from nlp.ner.ner import (
    detect_arbitration_seat,
    detect_governing_law,
    detect_gstin_mention,
    detect_stamp_duty_mention,
    detect_tds_mention,
    extract_entities,
)
from nlp.obligation_extraction.extractor import extract_obligations_from_clause
from nlp.risk_scoring.rules import apply_rules
from nlp.risk_scoring.scorer import _level_for, severity_to_score


logger = get_logger()


def analyse_path(
    file_path: str | Path,
    *,
    contract_id: str,
    contract_type: ContractType = ContractType.OTHER,
    user_role: PartySide = PartySide.CUSTOMER,
    jurisdiction: str = "India",
    enable_ocr: bool = True,
) -> AnalysisResult:
    """Full pipeline for an on-disk contract file."""
    parsed = parse_document(
        file_path,
        contract_id=contract_id,
        enable_ocr=enable_ocr,
    )
    return _analyse(
        parsed.full_text,
        contract_id=contract_id,
        title=parsed.title,
        file_name=parsed.file_name,
        warnings=parsed.warnings,
        contract_type=contract_type,
        user_role=user_role,
        jurisdiction=jurisdiction,
    )


def analyse_bytes(
    file_bytes: bytes,
    original_name: str,
    *,
    contract_id: str,
    contract_type: ContractType = ContractType.OTHER,
    user_role: PartySide = PartySide.CUSTOMER,
    jurisdiction: str = "India",
    enable_ocr: bool = True,
) -> AnalysisResult:
    parsed = parse_bytes(
        file_bytes,
        original_name,
        contract_id=contract_id,
        enable_ocr=enable_ocr,
    )
    return _analyse(
        parsed.full_text,
        contract_id=contract_id,
        title=parsed.title,
        file_name=parsed.file_name,
        warnings=parsed.warnings,
        contract_type=contract_type,
        user_role=user_role,
        jurisdiction=jurisdiction,
    )


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def _analyse(
    full_text: str,
    *,
    contract_id: str,
    title: str,
    file_name: str,
    warnings: List[str],
    contract_type: ContractType,
    user_role: PartySide,
    jurisdiction: str,
) -> AnalysisResult:
    logger.info("Analysing contract {} ({} chars)", contract_id, len(full_text))

    # 1. Clause segmentation
    raw_clauses = segment_clauses(full_text, contract_id=contract_id)
    logger.info("Segmented into {} clauses", len(raw_clauses))

    # 2. Classification + NER + obligation + risk
    clauses: List[Clause] = []
    all_obligations: List[Obligation] = []

    counter = 0
    for raw in raw_clauses:
        cls = classify_clause(raw.text, heading=raw.heading)
        extraction = extract_entities(raw.text, clause_text=raw.text)
        obligations = extract_obligations_from_clause(
            raw.clause_id,
            raw.text,
            obligation_counter=counter,
        )
        counter += len(obligations)
        all_obligations.extend(obligations)

        clause = Clause(
            clause_id=raw.clause_id,
            section_number=raw.section_number,
            heading=raw.heading,
            text=raw.text,
            page_hint=raw.page_hint,
            char_start=raw.char_start,
            char_end=raw.char_end,
            clause_types=cls.labels,
            entities=extraction.entities,
        )
        clauses.append(clause)

    # 3. Summary attributes
    summary_draft = ContractSummary(
        contract_id=contract_id,
        title=title,
        file_name=file_name,
        contract_type=contract_type,
        jurisdiction=jurisdiction,
    )
    summary_draft.governing_law = detect_governing_law(full_text)
    summary_draft.arbitration_seat = detect_arbitration_seat(full_text)
    summary_draft.stamp_duty_mentioned = detect_stamp_duty_mention(full_text)
    summary_draft.tds_mentioned = detect_tds_mention(full_text)
    summary_draft.gstin_mentioned = detect_gstin_mention(full_text)
    summary_draft.parties = _detect_parties(clauses)
    summary_draft.effective_date = _first_date(clauses)
    summary_draft.clause_count = len(clauses)
    summary_draft.obligation_count = len(all_obligations)

    # 4. Risk rules -> flags
    flags = apply_rules(clauses, summary_draft)

    # 5. Annotate clauses with their own risk_score
    clause_index = {f.clause_id: f for f in flags if f.clause_id}
    for cl in clauses:
        cl_flags = [f for f in flags if f.clause_id == cl.clause_id]
        if cl_flags:
            top = max(cl_flags, key=lambda f: severity_to_score(f.severity))
            cl.risk_score = severity_to_score(top.severity)
            cl.risk_level = top.severity
            cl.risk_reasons = [f.name for f in cl_flags]
        else:
            cl.risk_level = RiskSeverity.LOW
            cl.risk_score = 0.0
            cl.risk_reasons = []

    # 6. Aggregate contract risk
    from nlp.risk_scoring.scorer import score_contract

    overall_score, overall_level = score_contract(clauses, flags)
    summary_draft.overall_risk_score = overall_score
    summary_draft.overall_risk_level = overall_level
    summary_draft.high_risk_clauses = sum(
        1 for c in clauses if c.risk_level in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)
    )
    summary_draft.missing_clauses = [
        f.name for f in flags if f.rule_id.startswith("MISSING_CLAUSE_")
    ]
    summary_draft.top_risks = sorted(
        flags, key=lambda f: severity_to_score(f.severity), reverse=True,
    )[:5]

    return AnalysisResult(
        contract=summary_draft,
        clauses=clauses,
        obligations=all_obligations,
        risks=flags,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_parties(clauses: List[Clause]) -> List[str]:
    parties: List[str] = []
    for c in clauses[:8]:
        for ent in c.entities:
            if ent.label in {"PARTY", "ORG"} and ent.text:
                t = ent.text.strip()
                if t and t not in parties and len(t) <= 60:
                    parties.append(t)
        if len(parties) >= 6:
            break
    if not parties:
        # Fallback: capitalised proper-noun spans in early text
        for c in clauses[:3]:
            for line in (c.text or "").splitlines():
                words = line.strip().split()
                if 1 <= len(words) <= 6 and line.strip().istitle():
                    if line.strip() not in parties:
                        parties.append(line.strip())
                if len(parties) >= 4:
                    break
    return parties[:6]


def _first_date(clauses: List[Clause]) -> Optional[str]:
    for c in clauses:
        for ent in c.entities:
            if ent.label == "DATE":
                return ent.text
    return None