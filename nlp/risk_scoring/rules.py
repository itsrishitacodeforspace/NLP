"""Rule-based risk playbook for Indian + global contracts.

Each rule has:
  - rule_id, name, severity, clause_type (or 'ANY')
  - condition logic that inspects a Clause + its entities
  - produce a RiskFlag with explanation + recommendation
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from app.models.schemas import (
    Clause,
    ContractSummary,
    Entity,
    RiskFlag,
    RiskSeverity,
)
from nlp.risk_scoring.case_law import lookup_case_law


@dataclass
class RiskRule:
    rule_id: str
    name: str
    severity: RiskSeverity
    clause_type: str  # 'ANY' or a specific clause type
    description: str
    recommendation: Optional[str] = None
    requires_indian: bool = False
    is_contract_level: bool = False  # if True, fired once per contract not per clause
    check: Optional[Callable[[Clause, ContractSummary], Optional[RiskFlag]]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_label(entities: List[Entity], *labels: str) -> bool:
    label_set = {e.label for e in entities}
    return any(label in label_set for label in labels)


def _text_lower(clause: Clause) -> str:
    return (clause.text or "").lower()


def _any_clause_type(clause: Clause, *types: str) -> bool:
    if not clause.clause_types:
        return False
    return any(t in clause.clause_types for t in types)


# ---------------------------------------------------------------------------
# Risk rules
# ---------------------------------------------------------------------------


def rule_uncapped_liability(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    triggers = [
        "unlimited liability",
        "without limitation of liability",
        "no limitation on liability",
        "shall be liable for all damages",
        "liable for any and all damages",
        "fully liable",
    ]
    if not _any_clause_type(clause, "Limitation of Liability"):
        return None
    if any(t in text for t in triggers):
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_LIABILITY_001",
            clause_id=clause.clause_id,
            rule_id="RISK_LIABILITY_001",
            name="Uncapped liability",
            severity=RiskSeverity.CRITICAL,
            explanation="Liability is uncapped or explicitly unlimited.",
            recommendation=(
                "Add a liability cap, e.g. fees paid in the preceding 12 months "
                "for direct damages, with standard carve-outs."
            ),
            score=85.0,
        )
    has_cap_language = any(
        t in text for t in ("liability cap", "shall not exceed", "limited to", "maximum liability")
    )
    if not has_cap_language and not _has_label(clause.entities, "PAYMENT_AMOUNT"):
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_LIABILITY_002",
            clause_id=clause.clause_id,
            rule_id="RISK_LIABILITY_002",
            name="Missing liability cap",
            severity=RiskSeverity.HIGH,
            explanation="Limitation-of-Liability clause is present but does not state a cap.",
            recommendation="Define an explicit cap (e.g. 1x annual fees).",
            score=70.0,
        )
    return None


def rule_one_sided_termination(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Termination"):
        return None
    triggers = [
        "may terminate this agreement at any time",
        "terminate at any time without cause",
        "sole discretion",
    ]
    if any(t in text for t in triggers):
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_TERM_001",
            clause_id=clause.clause_id,
            rule_id="RISK_TERM_001",
            name="One-sided termination for convenience",
            severity=RiskSeverity.HIGH,
            explanation="One party can terminate at any time, creating operational risk.",
            recommendation="Require mutual termination rights and reasonable notice.",
            score=72.0,
        )
    return None


def rule_auto_renewal(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Term and Renewal"):
        return None
    if "automatic" in text and "renew" in text:
        notice = re.search(
            r"notice[^.]{0,100}?(?:non-renewal|renewal|terminate)[^.]{0,100}?"
            r"(\d+)\s+(hour|hours|day|days|week|weeks|month|months)\b",
            text,
            re.IGNORECASE,
        )
        severity = RiskSeverity.MEDIUM
        explanation = "Contract auto-renews unless timely notice is given."
        if not notice:
            severity = RiskSeverity.HIGH
            explanation += " No notice period detected — risk of being locked in."
        else:
            value = int(notice.group(1))
            unit = notice.group(2)
            days = value / 24 if "hour" in unit else value * 7 if "week" in unit else value * 30 if "month" in unit else value
            if days < 30:
                severity = RiskSeverity.HIGH
                explanation += f" Only {value} {unit} notice required."
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_RENEWAL_001",
            clause_id=clause.clause_id,
            rule_id="RISK_RENEWAL_001",
            name="Automatic renewal",
            severity=severity,
            explanation=explanation,
            recommendation="Add a calendar reminder at least 60 days before renewal.",
            score=70.0 if severity == RiskSeverity.HIGH else 50.0,
        )
    return None


def rule_broad_indemnity(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Indemnification"):
        return None
    broad_triggers = ["any and all claims", "all losses", "from any cause whatsoever"]
    if any(t in text for t in broad_triggers):
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_INDEMNITY_001",
            clause_id=clause.clause_id,
            rule_id="RISK_INDEMNITY_001",
            name="Broad indemnification",
            severity=RiskSeverity.HIGH,
            explanation="Indemnification is broader than standard third-party claims.",
            recommendation="Limit indemnity to third-party claims caused by indemnifying party.",
            score=72.0,
        )
    return None


def rule_data_breach_window(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Data Protection"):
        return None
    if "data breach" in text or "breach notification" in text or "security incident" in text:
        notice = re.search(
            r"(?:within|no\s+later\s+than)\s+(\d+)\s+(hour|hours|day|days)\b",
            text,
            re.IGNORECASE,
        )
        if notice:
            value = int(notice.group(1))
            unit = notice.group(2)
            hours = value if "hour" in unit else value * 24
        else:
            hours = None
        if hours is not None and hours <= 24:
            return RiskFlag(
                risk_id=f"{clause.clause_id}_RISK_DATA_001",
                clause_id=clause.clause_id,
                rule_id="RISK_DATA_001",
                name="Very tight breach-notification window",
                severity=RiskSeverity.MEDIUM,
                explanation="A breach notification window of ≤24h may be operationally difficult.",
                recommendation="Negotiate a 48–72 hour window if feasible.",
                score=55.0,
            )
    return None


def rule_missing_data_protection(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    # Trigger only once per contract — handled in `apply_rules` aggregate logic
    return None


def rule_governing_law_mismatch(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Governing Law", "Dispute Resolution"):
        return None
    if summary.jurisdiction and summary.jurisdiction.lower() in {"india", "indian"}:
        if any(foreign in text for foreign in [
            "laws of new york", "state of new york", "laws of england",
            "laws of singapore", "laws of the state of california",
        ]):
            return RiskFlag(
                risk_id=f"{clause.clause_id}_RISK_GOV_001",
                clause_id=clause.clause_id,
                rule_id="RISK_GOV_001",
                name="Foreign governing law in domestic contract",
                severity=RiskSeverity.HIGH,
                explanation=(
                    "Both parties appear Indian but governing law is foreign. "
                    "Indian courts may refuse to enforce, leading to unenforceable awards."
                ),
                recommendation="Negotiate Indian governing law or limit to cross-border elements.",
                score=68.0,
            )
    return None


def rule_arbitration_seat_mismatch(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Dispute Resolution", "Arbitration Seat"):
        return None
    has_foreign_seat = any(
        e.label == "ARBITRATION_SEAT_FOREIGN" for e in clause.entities
    )
    has_indian_venue = bool(
        re.search(
            r"\b(new delhi|mumbai|bengaluru|bangalore|chennai|kolkata|hyderabad|pune|ahmedabad)\b",
            text,
        )
    )
    is_indian = (summary.jurisdiction or "").lower() in {"india", "indian"}
    if has_foreign_seat and has_indian_venue and is_indian:
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_ARB_001",
            clause_id=clause.clause_id,
            rule_id="RISK_ARB_001",
            name="Arbitration seat vs. venue mismatch",
            severity=RiskSeverity.HIGH,
            explanation=(
                "Seat is foreign while venue is in India. Per *BALCO*/*BGS SGS*, "
                "Indian courts cannot intervene in purely foreign-seated arbitrations."
            ),
            recommendation="Align seat with venue, or justify the foreign seat with rationale.",
            score=70.0,
        )
    return None


def rule_missing_stamp_duty(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    if not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}:
        return None
    if summary.stamp_duty_mentioned:
        return None
    return RiskFlag(
        risk_id="contract_RISK_STAMP_001",
        clause_id=None,
        rule_id="RISK_STAMP_001",
        name="Missing stamp duty provision",
        severity=RiskSeverity.CRITICAL,
        explanation=(
            "Indian Stamp Act, 1899 requires adequate stamping. "
            "Unstamped / inadequately stamped agreements are inadmissible in Indian courts."
        ),
        recommendation="Add an explicit stamp duty clause and execute on e-stamp paper of appropriate value.",
        score=92.0,
    )


def rule_tds_missing(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    if not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}:
        return None
    if not _any_clause_type(clause, "Payment Terms"):
        return None
    if summary.tds_mentioned:
        return None
    return RiskFlag(
        risk_id=f"{clause.clause_id}_RISK_TDS_001",
        clause_id=clause.clause_id,
        rule_id="RISK_TDS_001",
        name="TDS provision missing",
        severity=RiskSeverity.MEDIUM,
        explanation="Payment clause does not reference TDS deduction under the Income Tax Act, 1961.",
        recommendation="Add: 'Subject to deduction of tax at source under section 194/195 of the Income Tax Act, 1961.'",
        score=55.0,
    )


def rule_section_124_indemnity(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    if not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}:
        return None
    if not _any_clause_type(clause, "Indemnification"):
        return None
    text = _text_lower(clause)
    if "indemnify" not in text:
        return None
    if "direct losses" not in text and "breach of contract" not in text:
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_S124_001",
            clause_id=clause.clause_id,
            rule_id="RISK_S124_001",
            name="Section 124 indemnity gap (Indian Contract Act)",
            severity=RiskSeverity.MEDIUM,
            explanation=(
                "Historically, Indian indemnity (Section 124) only covered third-party claims "
                "unless expressly drafted to cover direct losses / breach of contract."
            ),
            recommendation="Explicitly extend indemnity to losses arising from breach of contract.",
            score=50.0,
        )
    return None


# ---------------------------------------------------------------------------
# Risk rule registry
# ---------------------------------------------------------------------------


RISK_RULES: List[RiskRule] = [
    RiskRule(rule_id="RISK_LIABILITY_001", name="Uncapped liability", severity=RiskSeverity.CRITICAL, clause_type="Limitation of Liability",
             description="Liability cap missing or unlimited.", check=rule_uncapped_liability),
    RiskRule(rule_id="RISK_TERM_001", name="One-sided termination for convenience", severity=RiskSeverity.HIGH, clause_type="Termination",
             description="One party may terminate at any time.", check=rule_one_sided_termination),
    RiskRule(rule_id="RISK_RENEWAL_001", name="Automatic renewal", severity=RiskSeverity.HIGH, clause_type="Term and Renewal",
             description="Auto-renewal without explicit notice period.", check=rule_auto_renewal),
    RiskRule(rule_id="RISK_INDEMNITY_001", name="Broad indemnification", severity=RiskSeverity.HIGH, clause_type="Indemnification",
             description="Indemnity covers any and all losses.", check=rule_broad_indemnity),
    RiskRule(rule_id="RISK_DATA_001", name="Tight breach-notification window", severity=RiskSeverity.MEDIUM, clause_type="Data Protection",
             description="Notification window <= 24 hours.", check=rule_data_breach_window),
    RiskRule(rule_id="RISK_GOV_001", name="Foreign governing law in domestic contract", severity=RiskSeverity.HIGH, clause_type="Governing Law",
             description="Foreign law applied to a domestic contract.", check=rule_governing_law_mismatch),
    RiskRule(rule_id="RISK_ARB_001", name="Arbitration seat/venue mismatch", severity=RiskSeverity.HIGH, clause_type="Dispute Resolution",
             description="Seat foreign but venue Indian.", check=rule_arbitration_seat_mismatch),
    # Indian-statutory rules fire ONCE per contract (not per clause).
    RiskRule(rule_id="RISK_STAMP_001", name="Missing stamp duty provision", severity=RiskSeverity.CRITICAL, clause_type="ANY",
             description="Indian Stamp Act requirement unmet.", requires_indian=True, is_contract_level=True, check=rule_missing_stamp_duty),
    RiskRule(rule_id="RISK_TDS_001", name="TDS provision missing", severity=RiskSeverity.MEDIUM, clause_type="ANY",
             description="No TDS deduction reference in payment clause.", requires_indian=True, is_contract_level=True, check=rule_tds_missing),
    RiskRule(rule_id="RISK_S124_001", name="Section 124 indemnity gap", severity=RiskSeverity.MEDIUM, clause_type="ANY",
             description="Indian indemnity gap.", requires_indian=True, is_contract_level=True, check=rule_section_124_indemnity),
]


def apply_rules(
    clauses: List[Clause],
    summary: ContractSummary,
) -> List[RiskFlag]:
    """Run all registered rules against every clause. Returns a flat list.

    Rules with `is_contract_level=True` run once at the contract level and are
    NOT duplicated per clause. All other rules may fire per-clause; we then
    dedupe by rule_id keeping the highest-severity occurrence so the UI does
    not show the same rule three times for three matching clauses.
    """
    raw_flags: List[RiskFlag] = []

    # 1. Per-clause rules
    for cl in clauses:
        for rule in RISK_RULES:
            if rule.is_contract_level:
                continue
            if rule.requires_indian and (
                not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}
            ):
                continue
            try:
                flag = rule.check(cl, summary) if rule.check else None
            except Exception:
                continue
            if flag:
                raw_flags.append(flag)

    # 2. Contract-level rules
    raw_flags.extend(_contract_level_rules(clauses, summary))

    # 3. Dedupe by rule_id — keep highest severity + score, attach to first
    #    matching clause if available.
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    by_rule: dict[str, RiskFlag] = {}
    for f in raw_flags:
        existing = by_rule.get(f.rule_id)
        if existing is None:
            by_rule[f.rule_id] = f
            continue
        new_sev = severity_order.get(f.severity.value, 0)
        old_sev = severity_order.get(existing.severity.value, 0)
        if new_sev > old_sev or (new_sev == old_sev and f.score > existing.score):
            by_rule[f.rule_id] = f

    # 4. Enrich each finding with its statutory / case-law pointers.
    flags = list(by_rule.values())
    for flag in flags:
        if not flag.case_law:
            flag.case_law = lookup_case_law(flag.rule_id)
    # 5. P2 evidence binding (additive; does not alter triggers/severity).
    _bind_evidence(flags, clauses)
    return flags


def _bind_evidence(flags: List[RiskFlag], clauses: List[Clause]) -> None:
    """Attach traceable evidence without inventing spans.

    Clause-level findings get the owning clause's full text with offsets into
    ``Clause.text`` (locator="clause_text") and ``evidence_status="direct"``.
    Contract-level findings (no clause) get an explicit ``search_scope`` and
    ``evidence_status="unverified"`` - never a fabricated nearby clause.
    """
    from app.models.schemas import EvidenceSpan

    by_id = {c.clause_id: c for c in clauses}
    for flag in flags:
        if flag.source == "model":
            continue  # ML findings are bound by the analyzer (unverified by design)
        if flag.clause_id:
            clause = by_id.get(flag.clause_id)
            if clause is not None and (clause.text or "").strip():
                flag.evidence_spans = [
                    EvidenceSpan(
                        text=clause.text,
                        char_start=0,
                        char_end=len(clause.text),
                        clause_id=clause.clause_id,
                        role="direct",
                        locator="clause_text",
                    )
                ]
                flag.evidence_status = "direct"
            elif clause is None:
                flag.evidence_status = "unverified"
        else:
            flag.search_scope = (
                f"document-wide scan across {len(clauses)} clause(s); "
                "keyword-presence rule - no single supporting span"
            )
            flag.evidence_status = "unverified"


def _contract_level_rules(clauses: List[Clause], summary: ContractSummary) -> List[RiskFlag]:
    flags: List[RiskFlag] = []

    # Missing mandatory clauses — use BOTH the classifier output AND a
    # keyword check across clause text to avoid false negatives.
    detected_types = {t for c in clauses for t in c.clause_types}
    text_corpus = " ".join((c.text or "").lower() for c in clauses)

    mandatory_checks = [
        ("Governing Law", ["governed by the laws", "governing law", "jurisdiction of"]),
        ("Termination", ["termination", "may terminate", "terminate this agreement"]),
        ("Limitation of Liability", ["limitation of liability", "limit of liability", "in no event shall"]),
    ]
    for clause_type, keywords in mandatory_checks:
        classified_present = clause_type in detected_types
        keyword_present = any(k in text_corpus for k in keywords)
        if not (classified_present or keyword_present):
            flags.append(
                RiskFlag(
                    risk_id=f"contract_{clause_type.replace(' ', '_').upper()}_MISSING",
                    rule_id=f"MISSING_CLAUSE_{clause_type.upper().replace(' ', '_')}",
                    name=f"Missing clause: {clause_type}",
                    severity=RiskSeverity.HIGH,
                    explanation=f"{clause_type} clause not detected.",
                    recommendation=f"Add a standard {clause_type.lower()} clause.",
                    score=60.0,
                )
            )

    # Data protection presence if personal data is referenced.
    mentions_personal_data = "personal data" in text_corpus or "personal information" in text_corpus
    has_dp = "Data Protection" in detected_types or any(
        k in text_corpus for k in ("data protection", "data breach", "personal data")
    )
    if mentions_personal_data and not has_dp:
        flags.append(
            RiskFlag(
                risk_id="contract_DATA_PROTECTION_MISSING",
                rule_id="RISK_DATA_MISSING",
                name="Missing data protection clause",
                severity=RiskSeverity.HIGH,
                explanation="Contract references personal data but lacks a data protection clause.",
                recommendation="Add a data protection, breach notification, and security clause.",
                score=70.0,
            )
        )

    # Indian-statutory checks run once against the whole contract.
    synthetic = Clause(clause_id="contract", text=text_corpus, clause_types=sorted(detected_types))
    for rule in RISK_RULES:
        if not rule.is_contract_level or rule.check is None:
            continue
        if rule.requires_indian and (summary.jurisdiction or "").lower() not in {"india", "indian"}:
            continue
        try:
            flag = rule.check(synthetic, summary)
        except Exception:
            continue
        if flag is not None:
            flag.clause_id = None
            flags.append(flag)

    return flags
