"""Run the labelled corpus through the full analysis pipeline and score behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.models.schemas import AnalysisResult, ContractType, PartySide
from app.services.analyzer import analyse_bytes
from nlp.evaluation.cases import CASES, EvalCase, ObligationExpectation


@dataclass
class CaseResult:
    """Outcome of one evaluation case: observed findings vs expected behaviour."""

    case: EvalCase
    status: str  # "pass" | "fail"
    failures: List[str]
    observed_rule_ids: List[str]
    result: AnalysisResult

    @property
    def is_known_limitation(self) -> bool:
        return self.case.known_limitation is not None


@dataclass
class InvariantResult:
    """Outcome of one global evidence-integrity invariant across every finding."""

    name: str
    ok: bool
    violations: List[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """Aggregate of every case result plus the global evidence-integrity invariants."""

    case_results: List[CaseResult]
    invariants: List[InvariantResult]

    @property
    def failing_case_ids(self) -> set[str]:
        return {r.case.case_id for r in self.case_results if r.status == "fail"}

    @property
    def known_limitation_ids(self) -> set[str]:
        return {c.case_id for c in CASES if c.known_limitation}

    @property
    def unexpected_failures(self) -> set[str]:
        """Cases that fail but were NOT declared as known limitations (true regressions)."""
        return self.failing_case_ids - self.known_limitation_ids

    @property
    def resolved_limitations(self) -> set[str]:
        """Declared known limitations that now pass (the fix landed; update the case)."""
        return self.known_limitation_ids - self.failing_case_ids


def _analyse(case: EvalCase) -> AnalysisResult:
    return analyse_bytes(
        case.text.encode("utf-8"),
        f"{case.case_id}.txt",
        contract_id=case.case_id,
        contract_type=ContractType(case.contract_type),
        user_role=PartySide.NEUTRAL,
        jurisdiction=case.jurisdiction,
    )


def _check_obligation(
    exp: ObligationExpectation,
    result: AnalysisResult,
) -> List[str]:
    failures: List[str] = []
    matches = [o for o in result.obligations if exp.locate.lower() in (o.text or "").lower()]
    if not matches:
        return [f"no obligation whose source text contains {exp.locate!r}"]
    # Prefer a single unambiguous match; otherwise evaluate the first.
    ob = matches[0]
    label = f"obligation[{exp.locate!r}]"
    if exp.subject_not_none and not ob.subject:
        failures.append(f"{label}: subject is None (expected a responsible party)")
    if exp.counterparty_is_none and ob.counterparty is not None:
        failures.append(f"{label}: counterparty={ob.counterparty!r} (expected None)")
    if exp.counterparty_equals is not None:
        if (ob.counterparty or "").lower() != exp.counterparty_equals.lower():
            failures.append(
                f"{label}: counterparty={ob.counterparty!r} (expected {exp.counterparty_equals!r})"
            )
    for needle in exp.condition_contains:
        if needle.lower() not in (ob.condition or "").lower():
            failures.append(f"{label}: condition {ob.condition!r} missing {needle!r}")
    if exp.deadline_expression is not None:
        if (ob.deadline_expression or "").lower() != exp.deadline_expression.lower():
            failures.append(
                f"{label}: deadline={ob.deadline_expression!r} (expected {exp.deadline_expression!r})"
            )
    return failures


def run_case(case: EvalCase) -> CaseResult:
    """Analyse one case and compare observed findings/obligations with expectations."""
    result = _analyse(case)
    rule_ids = [r.rule_id for r in result.risks]
    rule_id_set = set(rule_ids)
    severities: Dict[str, set[str]] = {}
    for r in result.risks:
        severities.setdefault(r.rule_id, set()).add(r.severity.value)

    failures: List[str] = []
    for rid in case.expect_present:
        if rid not in rule_id_set:
            failures.append(f"expected rule {rid} present, but it did not fire")
    for rid in case.expect_absent:
        if rid in rule_id_set:
            failures.append(f"expected rule {rid} absent, but it fired (false positive)")
    for rid, sev in case.expect_severity:
        if rid not in rule_id_set:
            failures.append(f"expected {rid}@{sev}, but {rid} did not fire")
        elif sev not in severities.get(rid, set()):
            failures.append(
                f"expected {rid}@{sev}, observed {sorted(severities.get(rid, set()))}"
            )
    for exp in case.obligations:
        failures.extend(_check_obligation(exp, result))

    return CaseResult(
        case=case,
        status="pass" if not failures else "fail",
        failures=failures,
        observed_rule_ids=sorted(rule_id_set),
        result=result,
    )


def _invariants(case_results: List[CaseResult]) -> List[InvariantResult]:
    """Evidence-integrity properties that must hold for every finding in every case."""
    model_unverified = InvariantResult("model_findings_are_unverified", True)
    clause_rule_has_span = InvariantResult("clause_rule_findings_have_direct_span", True)
    contract_level_scoped = InvariantResult("contract_level_findings_are_scoped_unverified", True)

    for cr in case_results:
        for f in cr.result.risks:
            tag = f"{cr.case.case_id}:{f.rule_id}"
            if f.source == "model":
                if f.evidence_status != "unverified":
                    model_unverified.ok = False
                    model_unverified.violations.append(
                        f"{tag} model finding evidence_status={f.evidence_status!r}"
                    )
                continue
            # rule-sourced findings
            if f.clause_id:
                if f.evidence_status != "direct" or not f.evidence_spans:
                    clause_rule_has_span.ok = False
                    clause_rule_has_span.violations.append(
                        f"{tag} clause-level status={f.evidence_status!r} "
                        f"spans={len(f.evidence_spans)}"
                    )
            else:
                if f.evidence_status != "unverified" or not f.search_scope:
                    contract_level_scoped.ok = False
                    contract_level_scoped.violations.append(
                        f"{tag} contract-level status={f.evidence_status!r} "
                        f"search_scope={bool(f.search_scope)}"
                    )
    return [model_unverified, clause_rule_has_span, contract_level_scoped]


def run_all() -> EvaluationReport:
    """Run every case and compute the global evidence-integrity invariants."""
    case_results = [run_case(c) for c in CASES]
    return EvaluationReport(case_results=case_results, invariants=_invariants(case_results))
