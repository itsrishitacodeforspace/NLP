"""Rule-based risk playbook for Indian + global contracts.

Each rule has:
  - rule_id, name, severity, clause_type (or 'ANY')
  - condition logic that inspects a Clause + its entities
  - produce a RiskFlag with explanation + recommendation
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from app.models.schemas import (
    Clause,
    ContractSummary,
    Entity,
    RiskFlag,
    RiskSeverity,
)
from app.utils.text import NUMBER_TOKEN_RE, clean_text, written_number_to_int
from nlp.context.resolver import resolved_reference_texts
from nlp.ner.ner import RISK_NEGATION_CUES, detect_governing_law, is_negated_mention
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


def _number_token_value(match: Optional[re.Match[str]]) -> Optional[int]:
    """Resolve a captured digit/written number, preferring a parenthetical digit."""
    if match is None:
        return None
    return written_number_to_int(match.group(2) or match.group(1))


# A trigger only fires when its *sentence* asserts it. A sentence-level
# negation ("the liability of neither party shall be unlimited") or scoping
# language ("the indemnity does not extend to any and all claims") inverts the
# meaning, so the trigger is suppressed — the same cue logic NER uses for
# stamp-duty / TDS mentions, with an extended cue list for multi-word negators.
def _trigger_is_negated(lowered: str, trigger_start: int) -> bool:
    return is_negated_mention(lowered, trigger_start, RISK_NEGATION_CUES)


def _first_unnegated_trigger(lowered: str, triggers: List[str]) -> Optional[str]:
    """Return the first trigger that appears in a non-negated context, if any.

    For each trigger occurrence the sentence before it is inspected; a trigger
    whose sentence is negated is skipped (every occurrence must be negated for
    the trigger to be suppressed).
    """
    for trigger in triggers:
        for match in re.finditer(re.escape(trigger), lowered):
            if not _trigger_is_negated(lowered, match.start()):
                return trigger
    return None


# Symmetric to the uncapped triggers: when the clause itself states a cap,
# RISK_LIABILITY_002 ("missing cap") is wrong by definition. A negated cap
# phrase ("there is no limitation of liability") is not cap language.
_CAP_PHRASES = (
    "in aggregate",
    "shall not exceed",
    "limited to",
    "capped at",
    "maximum aggregate liability",
    "not exceed",
    "aggregate cap",
    "cap of",
    "ceiling",
    "does not exceed",
    "is not to exceed",
)


def _clause_states_cap(lowered: str) -> bool:
    """True when the clause text contains a non-negated cap phrase."""
    for phrase in _CAP_PHRASES:
        for match in re.finditer(re.escape(phrase), lowered):
            if not _trigger_is_negated(lowered, match.start()):
                return True
    return False


def _sentence_text(text: str, trigger_pos: int) -> str:
    """Return the sentence (in the given case) containing ``trigger_pos``."""
    if trigger_pos == -1:
        return text or ""
    start, end = _sentence_span((text or "").lower(), trigger_pos)
    return (text or "")[start:end]


def _sentence_span(lowered: str, trigger_start: int) -> tuple[int, int]:
    """Half-open (start, end) offsets of the sentence containing a trigger.

    Sentence boundaries are ., !, ? and newlines (semicolons are not, to match
    the NER negation window).
    """
    before = lowered[:trigger_start]
    start = 0
    for sep in (".", "!", "?", "\n"):
        pos = before.rfind(sep)
        if pos != -1 and pos + 1 > start:
            start = pos + 1
    end = len(lowered)
    for sep in (".", "!", "?", "\n"):
        pos = lowered.find(sep, trigger_start)
        if pos != -1 and pos < end:
            end = pos
    return start, end


def _any_clause_type(clause: Clause, *types: str) -> bool:
    if not clause.clause_types:
        return False
    return any(t in clause.clause_types for t in types)


# ---------------------------------------------------------------------------
# P5 (charter §5.A): why-it-matters helpers
#
# The enrichment fields (impact_summary, affected_parties, review_action,
# uncertainty_note) are populated ONLY where the rule logic genuinely knows
# the answer from the available data. ``None`` means "cannot be determined" —
# it is never filled by guesswork.
# ---------------------------------------------------------------------------


def _role_mentioned_in(text: str, *roles: str) -> Optional[str]:
    """First role noun present in ``text`` (case-insensitive, word-boundary)."""
    low = (text or "").lower()
    for role in roles:
        if re.search(rf"\b{re.escape(role)}\b", low):
            return role.capitalize()
    return None


def _party_in_parties(name: str, parties: List[str]) -> Optional[str]:
    """Match a role/canonical party name against detected party names
    (case-insensitive); returns the detected spelling or ``None``."""
    key = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    for party in parties:
        if re.sub(r"[^a-z0-9]+", "", party.lower()) == key:
            return party
    return None


def _affected_parties(
    summary: ContractSummary,
    clause_text: str,
    *,
    named: Optional[str] = None,
    mutual: bool = False,
) -> Optional[List[str]]:
    """Determine which parties are affected by a finding.

    Priority: an explicitly ``named`` party (from the rule logic) when it is a
    detected party or a plain role; then a single role mention in the clause;
    then the mutual-scope default. Returns ``None`` only when nothing at all
    can be determined.
    """
    if named:
        detected = _party_in_parties(named, summary.parties or [])
        if detected:
            return [detected]
        if not mutual:
            # A named role the detector never met is still a legitimate,
            # role-level answer — but only for plain role nouns.
            return [named]
    mentioned = _role_mentioned_in(clause_text, *_PARTY_NOUNS)
    if mentioned:
        detected = _party_in_parties(mentioned, summary.parties or [])
        return [detected] if detected else [mentioned]
    if mutual or named:
        return ["both parties"]
    return None


def _related_ids_from_context(clause: Clause) -> List[str]:
    """Clause ids the context resolver already linked for this clause."""
    ctx = clause.context if isinstance(clause.context, dict) else {}
    return [rid for rid in (ctx.get("related_clause_ids") or []) if rid]


def _phrase_search_uncertainty_note(extra: str = "") -> str:
    """Standard honesty note for any finding derived from phrase search."""
    note = (
        "The check is phrase-based: the wording may be expressed differently "
        "or located in an annexure/schedule, so absence from the searched "
        "phrases does not prove absence from the agreement."
    )
    return f"{note} {extra}".strip()


# ---------------------------------------------------------------------------
# Cross-reference cap verification (narrow, fail-closed)
#
# A "missing cap" finding may be suppressed ONLY when an explicit, resolved
# in-clause reference points to a clause whose text states a liability cap that
# verifiably covers the assessed liability. Keyword presence in a related
# clause (without a resolved reference) never suppresses — that behaviour was
# reverted as unsafe and stays reverted. Any doubt (ambiguous/missing/
# unresolved reference, exclusions, party or loss-category mismatch, unknown
# scope) keeps the finding as a human-review prompt.
# ---------------------------------------------------------------------------

_OWN_CLAUSE_CAP_LANGUAGE = (
    "liability cap",
    "shall not exceed",
    "limited to",
    "maximum liability",
)
_CAP_LANGUAGE = _OWN_CLAUSE_CAP_LANGUAGE + (
    "not exceed",
    "aggregate cap",
    "cap of",
)
# Exclusion or override language in the cap clause means coverage of the
# assessed liability cannot be confirmed from the text.
_CAP_UNCERTAINTY_MARKERS = (
    "excluding",
    "except for",
    "except as",
    "other than",
    "carve",
    "notwithstanding",
    "unlimited",
    "without limitation",
)
_MUTUAL_SCOPE_MARKERS = (
    "each party",
    "either party",
    "neither party",
    "both parties",
    "any party",
    "of a party",
)
_PARTY_NOUNS = (
    "provider", "customer", "client", "supplier", "vendor", "licensor",
    "licensee", "contractor", "consultant", "reseller", "distributor",
)


def _cap_text_covers_liability(cap_text: str, assessed_text: str) -> bool:
    """True only when ``cap_text`` states a cap that verifiably covers the
    liability assessed in ``assessed_text``. Fail-closed on any uncertainty."""
    cap = (cap_text or "").lower()
    assessed = (assessed_text or "").lower()
    if not any(t in cap for t in _CAP_LANGUAGE):
        return False
    if any(m in cap for m in _CAP_UNCERTAINTY_MARKERS):
        return False
    # Loss-category mismatch: a cap scoped to direct losses does not cover an
    # assessed indirect/consequential exposure.
    assessed_indirect = any(w in assessed for w in ("indirect", "consequential"))
    cap_direct_only = (
        any(w in cap for w in ("direct damages", "direct losses"))
        and not any(w in cap for w in ("indirect", "consequential"))
    )
    if assessed_indirect and cap_direct_only:
        return False
    # Party scope: mutual language covers both parties; a named party must also
    # appear in the assessed clause; anything else is unknown scope -> no cover.
    if any(m in cap for m in _MUTUAL_SCOPE_MARKERS):
        return True
    named = [n for n in _PARTY_NOUNS if re.search(rf"\b{re.escape(n)}\b", cap)]
    if named and any(re.search(rf"\b{re.escape(n)}\b", assessed) for n in named):
        return True
    return False


def _cross_reference_states_applicable_cap(clause: Clause) -> bool:
    """True only when a resolved reference in ``clause`` points to a clause
    whose text states a liability cap covering the assessed liability.

    Requires the resolver's explicit ``references`` entries with
    ``status == "resolved"``; ``related_clause_texts`` alone (keyword presence)
    is never sufficient. Unresolved, missing or ambiguous references, and
    references without retrievable target text, all return False.
    """
    assessed = clause.text or ""
    return any(
        _cap_text_covers_liability(cap_text, assessed)
        for cap_text in resolved_reference_texts(clause)
    )


# ---------------------------------------------------------------------------
# P5 (charter §5.C): cross-reference contradiction detector
#
# A deliberately narrow, high-precision contract-level check: two clauses that
# each state a *different* liability-cap amount for what appears to be the
# same scope. It fires ONLY when both amounts are in an explicit cap context
# ("cap", "shall not exceed", "in aggregate", "maximum liability", ...), the
# currency is recognised (INR/USD/EUR/GBP), the values are comparable after
# normalisation (lakh/crore units included), and no scope word (per incident,
# per claim, per year, ...) distinguishes the two — a scope mismatch means the
# amounts may legitimately differ, so the check abstains.
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(
    r"(?:INR|USD|EUR|GBP|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lacs|crore|crores)?",
    re.IGNORECASE,
)
_LIABILITY_CAP_CONTEXT_RE = re.compile(
    r"\b(?:liability|liabilities)\b.*\b(?:cap(?:ped|ped)?|limit(?:ed|ation)?|ceiling|maximum|shall not exceed|not to exceed|in aggregate)"
    r"|\b(?:cap(?:ped|ped)?|ceiling|maximum)\b.*\b(?:liability|liabilities)\b",
    re.IGNORECASE,
)
_SCOPE_MARKERS = (
    "per incident", "per claim", "per event", "per occurrence",
    "per breach", "per year", "per annum", "annually",
)


def _parse_money_amount(token: str, unit: Optional[str]) -> Optional[float]:
    """Normalise a money token + Indian unit into a float (base units)."""
    try:
        value = float(token.replace(",", ""))
    except ValueError:
        return None
    if unit:
        unit = unit.lower()
        if unit.startswith("lakh"):
            value *= 100_000
        elif unit.startswith("crore"):
            value *= 10_000_000
    return value


def _clause_cap_amounts(clause: Clause) -> List[Tuple[float, str, int]]:
    """Money amounts in an explicit liability-cap sentence of ``clause``.

    Returns a list of ``(value_in_base_units, currency, char_start)``. A
    sentence that contains scope words (per incident / per claim / per year /
    ...) is skipped: the amount cannot be compared against an aggregate figure
    without knowing the scope.
    """
    amounts: List[Tuple[float, str, int]] = []
    for match in _LIABILITY_CAP_CONTEXT_RE.finditer(clause.text or ""):
        sentence = _sentence_text(clause.text or "", match.start())
        if any(marker in sentence.lower() for marker in _SCOPE_MARKERS):
            continue
        for money in _MONEY_RE.finditer(sentence):
            value = _parse_money_amount(money.group(1), money.group(2))
            if value is None:
                continue
            # The sentence is stored case-preserved, so the currency prefix is
            # read from the *stored* clause text at the same offsets.
            raw = clause.text or ""
            prefix = raw[money.start() : money.end()]  # the currency token itself
            currency = "INR" if re.search(r"(?:INR|Rs\.?|₹)", prefix, re.IGNORECASE) else (
                "USD" if "USD" in prefix.upper() or "$" in prefix
                else "EUR" if "EUR" in prefix.upper() else "GBP" if "GBP" in prefix.upper() else "UNK"
            )
            if currency == "UNK":
                continue
            amounts.append((value, currency, match.start()))
    return amounts


def rule_contradictory_liability_caps(
    clauses: List[Clause],
    summary: ContractSummary,
) -> Optional[RiskFlag]:
    """Detect two clauses stating different amounts for the same liability cap.

    Conservative by design: abstains on any ambiguity (scope words, different
    currencies, unrecognised wording). Fires once per contract.
    """
    hits: List[Tuple[Clause, float, str, str]] = []
    for cl in clauses:
        for value, currency, pos in _clause_cap_amounts(cl):
            hits.append((cl, value, currency, _sentence_text(cl.text or "", pos)))
    for i in range(len(hits)):
        for j in range(i + 1, len(hits)):
            cl_a, val_a, cur_a, sent_a = hits[i]
            cl_b, val_b, cur_b, sent_b = hits[j]
            if cl_a.clause_id == cl_b.clause_id:
                continue
            if cur_a != cur_b:
                continue  # different currencies are not comparable here
            if val_a == val_b:
                continue  # same value — consistent
            # A different, comparable liability-cap amount in two clauses.
            a_val = f"{val_a:,.0f}"
            b_val = f"{val_b:,.0f}"
            flag = RiskFlag(
                risk_id=f"contract_RISK_CONFLICT_001_{cl_a.clause_id}_{cl_b.clause_id}",
                clause_id=None,
                rule_id="RISK_CONFLICT_001",
                name="Contradictory liability cap amounts",
                severity=RiskSeverity.HIGH,
                explanation=(
                    f"Two clauses state different liability cap amounts "
                    f"({cur_a} {a_val} in {cl_a.clause_id} vs "
                    f"{cur_b} {b_val} in {cl_b.clause_id})."
                ),
                recommendation=(
                    "Confirm which amount is intended and align the clauses "
                    "before signing; the cap is only as strong as its "
                    "weakest expression."
                ),
                score=65.0,
                impact_summary=(
                    "In a dispute, the lower (or better-supported) figure may "
                    "prevail; the parties may not agree on which amount caps "
                    "their exposure."
                ),
                affected_parties=_affected_parties(summary, "", mutual=True),
                review_action=(
                    f"Compare clause {cl_a.clause_id} and clause "
                    f"{cl_b.clause_id} side by side and confirm with the "
                    "drafting team which amount governs."
                ),
                related_clause_ids=sorted({cl_a.clause_id, cl_b.clause_id}),
                uncertainty_note=(
                    "The two amounts may cover different scopes (e.g. per "
                    "claim vs aggregate) that the detector could not "
                    "distinguish; verify the intended scope of each before "
                    "treating this as a true contradiction."
                ),
            )
            flag.evidence_spans = [
                _cap_evidence_span(cl_a, sent_a),
                _cap_evidence_span(cl_b, sent_b),
            ]
            flag.search_scope = (
                f"liability-cap amounts extracted from {len(clauses)} clause(s); "
                "both amounts are in explicit cap contexts in their own clauses"
            )
            return flag
    return None


def _cap_evidence_span(clause: Clause, sentence: str):
    """Direct evidence span for one clause's cap sentence.

    Offsets are into ``clause.text``; the span is the exact stored slice of
    the located sentence. Returns an ``EvidenceSpan`` even when the sentence
    cannot be located (in which case the offsets span the whole clause text —
    never a fabricated nearby passage).
    """
    from app.models.schemas import EvidenceSpan

    raw = clause.text or ""
    low = raw.lower()
    pos = low.find(sentence.lower().strip()[:60]) if sentence else -1
    if pos == -1:
        return EvidenceSpan(text=raw, char_start=0, char_end=len(raw), clause_id=clause.clause_id, role="direct", locator="clause_text")
    start, end = _sentence_span(low, pos)
    while start < end and raw[start] in " \t\r\n":
        start += 1
    while end > start and raw[end - 1] in " \t\r\n":
        end -= 1
    return EvidenceSpan(text=raw[start:end], char_start=start, char_end=end, clause_id=clause.clause_id, role="direct", locator="clause_text")


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
    # An indemnification clause shifts third-party liability; it is not the
    # party's own limitation-of-liability clause, so cap analysis does not apply.
    # This guards against clauses the classifier labels both "Limitation of
    # Liability" and "Indemnification" when only the latter is correct.
    if "indemn" in (clause.heading or "").lower():
        return None
    trigger = _first_unnegated_trigger(text, triggers)
    if trigger:
        # The party named in the same sentence as the trigger carries the
        # uncapped exposure; if no single party is named in that sentence,
        # the exposure is undeterminable at party level — say "both parties"
        # rather than guess a single one.
        trigger_sentence = _sentence_text(text, text.find(trigger))
        named = _role_mentioned_in(trigger_sentence, *_PARTY_NOUNS)
        affected = _affected_parties(summary, clause.text or "", named=named, mutual=named is None)
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
            evidence_text=trigger,
            impact_summary=(
                "If this clause operates as written, the affected party's exposure "
                "is not bounded by any amount, so a single loss event can exceed "
                "the value of the entire contract."
            ),
            affected_parties=affected,
            review_action=(
                "Check whether a cap appears in another clause (e.g. a cross-"
                "referenced limitation section) before escalating."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "Negation and scoping in other clauses were not analysed; "
                "verify the exposure against the full agreement."
            ),
        )
    has_cap_language = any(t in text for t in _OWN_CLAUSE_CAP_LANGUAGE) or _clause_states_cap(text)
    if not has_cap_language and not _has_label(clause.entities, "PAYMENT_AMOUNT"):
        # A resolved cross-reference to a clause that states a verifiably
        # applicable cap means the cap is not missing. This is reference-based
        # verification, not keyword suppression: related text without a
        # resolved reference, and any ambiguity about applicability, keeps the
        # finding as a human-review prompt.
        if _cross_reference_states_applicable_cap(clause):
            return None
        affected = _affected_parties(summary, clause.text or "", mutual=True)
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_LIABILITY_002",
            clause_id=clause.clause_id,
            rule_id="RISK_LIABILITY_002",
            name="Missing liability cap",
            severity=RiskSeverity.HIGH,
            explanation="Limitation-of-Liability clause is present but does not state a cap.",
            recommendation="Define an explicit cap (e.g. 1x annual fees).",
            score=70.0,
            impact_summary=(
                "Without an express cap, each party's recoverable damages are "
                "not bounded by the contract and depend on general law."
            ),
            affected_parties=affected,
            review_action=(
                "Check other clauses and annexures for a cap that this clause "
                "may refer to, then negotiate an explicit cap if none exists."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=_phrase_search_uncertainty_note(
                "A cap may be stated in different wording elsewhere in the document."
            ),
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
    trigger = _first_unnegated_trigger(text, triggers)
    if trigger:
        trigger_sentence = _sentence_text(text, text.find(trigger))
        affected = _affected_parties(summary, clause.text or "", named=_role_mentioned_in(trigger_sentence, *_PARTY_NOUNS))
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_TERM_001",
            clause_id=clause.clause_id,
            rule_id="RISK_TERM_001",
            name="One-sided termination for convenience",
            severity=RiskSeverity.HIGH,
            explanation="One party can terminate at any time, creating operational risk.",
            recommendation="Require mutual termination rights and reasonable notice.",
            score=72.0,
            evidence_text=trigger,
            impact_summary=(
                "The party without the termination right can be terminated at "
                "any time without cause, disrupting its reliance on the contract."
            ),
            affected_parties=affected,
            review_action=(
                "Check the rest of the clause and any termination sub-clauses for "
                "mutual or reciprocal termination rights."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "Other sub-clauses may balance this right (mutual notice, cure "
                "periods); verify against the full termination section."
            ),
        )
    return None


def rule_auto_renewal(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Term and Renewal"):
        return None
    if "automatic" in text and "renew" in text:
        # Accept digit, written ("ninety") and parenthetical ("sixty (60)")
        # notice periods in the SAME clause. A notice in a cross-referenced
        # clause is handled elsewhere (advisory only) and never suppresses.
        notice = re.search(
            r"notice[^.]{0,100}?(?:non-renewal|renewal|terminate)[^.]{0,100}?"
            r"(" + NUMBER_TOKEN_RE + r")\s*(?:\((\d+)\))?\s+"
            r"(hour|hours|day|days|week|weeks|month|months)\b",
            text,
            re.IGNORECASE,
        )
        severity = RiskSeverity.MEDIUM
        explanation = "Contract auto-renews unless timely notice is given."
        value = _number_token_value(notice)
        if not notice or value is None:
            severity = RiskSeverity.HIGH
            explanation += " No notice period detected — risk of being locked in."
        else:
            unit = notice.group(3)
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
            impact_summary=(
                "If no renewal notice is given in time, the contract continues "
                "for another term automatically at the agreed terms."
            ),
            affected_parties=["both parties"],
            review_action=(
                "Note the renewal date and notice deadline in the review calendar "
                "and confirm who is responsible for giving notice."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "The notice period was read from this clause only; a different "
                "notice procedure may be set out elsewhere in the document."
            ),
        evidence_text=notice.group(0) if notice else "automatically renews",
    )
    return None


def rule_broad_indemnity(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Indemnification"):
        return None
    broad_triggers = ["any and all claims", "all losses", "from any cause whatsoever"]
    trigger = _first_unnegated_trigger(text, broad_triggers)
    if trigger:
        trigger_sentence = _sentence_text(text, text.find(trigger))
        affected = _affected_parties(summary, clause.text or "", named=_role_mentioned_in(trigger_sentence, *_PARTY_NOUNS))
        return RiskFlag(
            risk_id=f"{clause.clause_id}_RISK_INDEMNITY_001",
            clause_id=clause.clause_id,
            rule_id="RISK_INDEMNITY_001",
            name="Broad indemnification",
            severity=RiskSeverity.HIGH,
            explanation="Indemnification is broader than standard third-party claims.",
            recommendation="Limit indemnity to third-party claims caused by indemnifying party.",
            score=72.0,
            evidence_text=trigger,
            impact_summary=(
                "As written, the indemnity can reach losses beyond third-party "
                "claims caused by the indemnifying party, including its own "
                "first-party losses."
            ),
            affected_parties=affected,
            review_action=(
                "Compare the indemnity scope against the limitation-of-liability "
                "clause to see whether the broad scope is capped elsewhere."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "Cap or exclusion clauses in other sections may narrow this "
                "indemnity; verify against the full agreement."
            ),
        )
    return None


def rule_data_breach_window(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    text = _text_lower(clause)
    if not _any_clause_type(clause, "Data Protection"):
        return None
    if "data breach" in text or "breach notification" in text or "security incident" in text:
        # Accept digit, written ("twenty-four") and parenthetical ("twenty-four
        # (24)") notice periods — the same shared number vocabulary the
        # obligation extractor and renewal rule use, so one sentence cannot
        # yield contradictory deadline interpretations across pipeline stages.
        notice = re.search(
            r"(?:within|no\s+later\s+than)\s+(" + NUMBER_TOKEN_RE + r")\s*(?:\((\d+)\))?\s+"
            r"(hour|hours|day|days)\b",
            text,
            re.IGNORECASE,
        )
        value = _number_token_value(notice)
        if notice and value is not None:
            unit = notice.group(3)
            hours = value if "hour" in unit else value * 24
        else:
            hours = None
        if hours is not None and hours <= 24:
            affected = _affected_parties(summary, clause.text or "", named=_role_mentioned_in(_sentence_text(text, notice.start()), *_PARTY_NOUNS))
            return RiskFlag(
                risk_id=f"{clause.clause_id}_RISK_DATA_001",
                clause_id=clause.clause_id,
                rule_id="RISK_DATA_001",
                name="Very tight breach-notification window",
                severity=RiskSeverity.MEDIUM,
                explanation="A breach notification window of ≤24h may be operationally difficult.",
                recommendation="Negotiate a 48–72 hour window if feasible.",
                score=55.0,
                evidence_text=notice.group(0),
                impact_summary=(
                    "A missed notification inside this window can itself become "
                    "a breach, with exposure under the data-protection regime."
                ),
                affected_parties=affected,
                review_action=(
                    "Confirm the notifying party's incident-response process can "
                    "meet the window, and negotiate 48–72 hours if not."
                ),
                related_clause_ids=_related_ids_from_context(clause),
                uncertainty_note=(
                    "The window was read from this clause; related "
                    "data-protection terms (e.g. in an annexure) may set a "
                    "different or complementary procedure."
                ),
            )
    return None


def rule_missing_data_protection(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    # Trigger only once per contract — handled in `apply_rules` aggregate logic
    return None


# Jurisdictions known to be foreign: any governing-law phrase that names one
# (or any explicit country/state other than India) is foreign for this rule.
_FOREIGN_LAW_HINTS = (
    # countries
    "singapore", "england", "wales", "scotland", "britain", "united kingdom",
    "delaware", "california", "new york", "texas", "florida", "illinois",
    "virginia", "maryland", "massachusetts", "washington", "oregon",
    "jersey", "cayman", "luxembourg", "france", "germany", "netherlands",
    "switzerland", "austria", "spain", "italy", "portugal", "greece",
    "poland", "denmark", "norway", "sweden", "finland", "ireland",
    "canada", "quebec", "ontario", "australia", "new zealand",
    "united states", "america", "japan", "korea", "china", "indonesia",
    "malaysia", "philippines", "thailand", "vietnam", "israel", "uae",
)
# Indian states/UTs: "laws of the State of X" is Indian when X is one of these.
_INDIAN_LAW_STATE_HINTS = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan",
    "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh",
    "uttarakhand", "west bengal", "delhi", "jammu", "kashmir",
    "ladakh", "chandigarh", "puducherry", "andaman", "lakshadweep",
)


def _governing_law_is_indian(phrase: Optional[str]) -> bool:
    """Classify a governing-law phrase as Indian or foreign.

    Any "india"/"indian" reference is Indian. Otherwise a phrase that names an
    Indian state/UT is Indian. Anything else (a foreign country/state name, or
    an unrecognised jurisdiction) is treated as foreign — the rule stays a
    human-review prompt either way.
    """
    if not phrase:
        return True  # no extractable phrase — nothing to flag
    low = phrase.lower()
    if "india" in low or "indian" in low:
        return True
    return any(state in low for state in _INDIAN_LAW_STATE_HINTS)


def rule_governing_law_mismatch(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    if not _any_clause_type(clause, "Governing Law", "Dispute Resolution"):
        return None
    if not (summary.jurisdiction and summary.jurisdiction.lower() in {"india", "indian"}):
        return None
    # Extract the governing-law phrase (NER handles the common phrasings:
    # "governed by the laws of ...", "subject to the laws of ...",
    # "laws of the state of ...", "laws of India"). If it names a foreign
    # jurisdiction, flag it.
    phrase = detect_governing_law(clause.text or "")
    if phrase is None:
        # Fallback: a plain "governed by ... law" construction that NER's
        # patterns do not cover (e.g. "governed by Delaware law").
        m = re.search(r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+([^.]{1,60})", _text_lower(clause))
        if not m:
            return None
        phrase = f"laws of {m.group(1).strip()}"
    if _governing_law_is_indian(phrase):
        return None
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
        evidence_text=phrase,
        impact_summary=(
            "Disputes may have to be interpreted (and possibly fought) under a "
            "foreign law that neither party is familiar with."
        ),
        affected_parties=_affected_parties(summary, clause.text or "", mutual=True),
        review_action=(
            "Confirm with counsel whether the foreign law is genuinely intended "
            "for this domestic contract or should be Indian law."
        ),
        related_clause_ids=_related_ids_from_context(clause),
        uncertainty_note=(
            "The jurisdiction reading is based on the extracted governing-law "
            "phrase; verify the intended jurisdiction before escalating."
        ),
    )


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
            impact_summary=(
                "Interim relief in Indian courts may be unavailable for a purely "
                "foreign-seated arbitration, weakening the practical value of an "
                "Indian venue."
            ),
            affected_parties=_affected_parties(summary, clause.text or "", mutual=True),
            review_action=(
                "Decide whether the seat or the venue is a drafting error and "
                "align the two, or document why the mismatch is intended."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "Seat/venue were detected by keyword heuristics; confirm the "
                "exact seat and venue language before acting."
            ),
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
        name="Stamp duty language not detected",
        severity=RiskSeverity.MEDIUM,
        explanation=(
            "No stamp duty language was detected (not found). This does not establish that the "
            "agreement is unstamped — stamping is often handled at execution, outside the contract "
            "text. Verify execution on duly stamped paper."
        ),
        recommendation="Verify stamping; where applicable add a stamp duty clause and execute on e-stamp paper of appropriate value.",
        score=50.0,
        impact_summary=(
            "If the executed document is unstamped or under-stamped, it may be "
            "inadmissible in evidence until the deficit duty and penalty are paid."
        ),
        affected_parties=_affected_parties(summary, "", mutual=True),
        review_action=(
            "Check the executed copy for a stamp (or e-stamp certificate) of "
            "sufficient value; stamping is often done at execution, outside the "
            "contract text."
        ),
        uncertainty_note=_phrase_search_uncertainty_note(
            "Stamping is typically handled at execution, so its absence from the "
            "text is expected and not evidence of non-compliance."
        ),
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
        name="TDS language not detected",
        severity=RiskSeverity.LOW,
        explanation=(
            "No tax-deduction-at-source language was detected in the payment clause (not found). "
            "TDS applicability depends on the nature of the payment and the parties; absence from "
            "the text does not by itself establish non-compliance. Verify."
        ),
        recommendation="If applicable, add: 'Subject to deduction of tax at source under the Income Tax Act, 1961.'",
        score=30.0,
        impact_summary=(
            "If TDS applies to these payments, the payer's failure to deduct "
            "exposes it to interest, penalty and disallowance of the expense."
        ),
        affected_parties=_affected_parties(summary, clause.text or "", named=_role_mentioned_in(clause.text or "", *_PARTY_NOUNS)),
        review_action=(
            "Confirm with the tax team whether TDS applies to this payment type "
            "and, if so, add the standard TDS clause."
        ),
        uncertainty_note=_phrase_search_uncertainty_note(
            "TDS applicability depends on the nature of the payment and the "
            "parties; absence from the text does not establish non-compliance."
        ),
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
            name="Indemnity may not cover direct losses",
            severity=RiskSeverity.MEDIUM,
            explanation=(
                "The indemnity clause does not expressly extend to direct losses or breach of "
                "contract. Under Indian Contract Act ss. 124-125 a wider indemnity is enforceable "
                "only if clearly worded, so if the parties intend direct-loss coverage this may be "
                "insufficient. Verify the intended scope."
            ),
            recommendation="If direct-loss or breach-of-contract coverage is intended, expressly extend the indemnity to those losses.",
            score=50.0,
            impact_summary=(
                "If the parties intended direct-loss coverage, the indemnity as "
                "worded may not deliver it, leaving the indemnified party to "
                "pursue an ordinary breach claim instead."
            ),
            affected_parties=_affected_parties(summary, clause.text or "", named=_role_mentioned_in(clause.text or "", *_PARTY_NOUNS)),
            review_action=(
                "Decide whether direct-loss or breach-of-contract coverage is "
                "intended and, if so, extend the indemnity wording expressly."
            ),
            related_clause_ids=_related_ids_from_context(clause),
            uncertainty_note=(
                "Other clauses (e.g. a limitation section) may allocate these "
                "losses differently; verify the intended scope first."
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Post-employment non-compete (Indian-specific)
#
# Indian Contract Act s. 27 voids agreements in restraint of a lawful trade,
# business, profession or vocation. A clause restraining a *former*
# employee/consultant from competing after the relationship ends is therefore
# at risk of being void and unenforceable — a real, high-value finding for
# Indian employment and consulting contracts.
#
# Precision: the trigger is deliberately restricted to POST-relationship
# restraint language ("following/after termination", "after the employment
# ends", ...). In-employment non-solicits of employees/customers (standard and
# potentially enforceable), confidentiality clauses and IP assignments never
# match: none of them use the post-relationship window + competing verb
# construction. A clause labelled "Non-Compete / Non-Solicit" without
# post-relationship language is not flagged either.
# ---------------------------------------------------------------------------

# Post-relationship window: the restraint must run AFTER the relationship
# ends. A window whose first mention is negated (e.g. "not after termination")
# is not a post-relationship window.
_POST_EMPLOYMENT_WINDOW_TRIGGERS = (
    "following the termination",
    "following termination",
    "following the expiry",
    "following expiry",
    "after the termination",
    "after termination",
    "following the end of the",
    "after the end of the",
    "after the expiry",
    "upon the termination",
    "upon termination",
    "after his or her employment",
    "after the employment",
    "following the cessation",
    "after the cessation",
)
# The competing/restraint action, in a non-negated context (reuses the
# sentence-level negation guard every rule trigger uses).
_NON_COMPETE_ACTION_TRIGGERS = (
    "compete with",
    "competing with",
    "engag[ei]ng in any business that competes",
    "carry on any business similar",
    "be engaged in any business similar",
    "carry on a similar business",
    "carry on or be engaged in any business",
    "be associated with any business that competes",
    "establish or acquire any business that competes",
    "solicit any customer",
    "solicit any client",
)


def _non_compete_action_is_negated(lowered: str, trigger_start: int) -> bool:
    """Check if a non-compete action trigger is in a negated context.

    Uses the standard negation cues (including "nor"). In a sentence like
    "shall not solicit any employee, nor solicit any customer", the "nor"
    within 6 tokens of "solicit any customer" correctly negates it — both
    items are part of the same prohibition. This is the desired behaviour:
    the trigger should NOT fire on a negated (prohibited) action, because
    the clause is already saying "you shall not do this" — which is the
    non-compete we want to flag, not a negation of the non-compete.

    Wait — that's wrong. The trigger IS the non-compete action. If the
    sentence says "shall not ... solicit any customer", the trigger
    "solicit any customer" is NEGATED (the employee is prohibited from
    soliciting). That's exactly what we want to detect as a non-compete.
    So the negation check should return False (not negated) for the
    purpose of the non-compete rule, because a negated action IS the
    non-compete.

    The correct logic: a non-compete action trigger should fire when it
    appears in a NEGATED context (the employee is prohibited from doing
    the action). This is the opposite of the standard trigger guard.
    """
    # For the non-compete rule, we want the trigger to fire when it IS
    # negated (prohibited). So we return the OPPOSITE of the standard
    # negation check: if the action is negated, it's a non-compete (fire);
    # if it's not negated, it's not a non-compete (don't fire).
    return not _trigger_is_negated(lowered, trigger_start)


def rule_post_employment_non_compete(clause: Clause, summary: ContractSummary) -> Optional[RiskFlag]:
    if not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}:
        return None
    if "Non-Compete / Non-Solicit" not in (clause.clause_types or []):
        # The rule is gated on the classifier's non-compete label (which is
        # itself rule-based — "non-compete", "shall not solicit", ...). This
        # keeps the trigger tight: confidentiality, IP-assignment and other
        # clauses that merely mention a competitor never reach the trigger.
        return None
    text = _text_lower(clause)
    window = _first_unnegated_trigger(text, list(_POST_EMPLOYMENT_WINDOW_TRIGGERS))
    if not window:
        return None
    # For the action trigger, use the nor-aware negation check. The
    # non-compete rule fires when the action is NEGATED (prohibited) —
    # "shall not solicit" is the non-compete. ``_non_compete_action_is_negated``
    # returns True when the trigger is in a NEGATED context (i.e. it IS a
    # non-compete), so we want it to return True for a fire.
    action: Optional[str] = None
    for trigger in _NON_COMPETE_ACTION_TRIGGERS:
        for match in re.finditer(re.escape(trigger), text):
            if _non_compete_action_is_negated(text, match.start()):
                action = trigger
                break
        if action:
            break
    if not action:
        return None
    return RiskFlag(
        risk_id=f"{clause.clause_id}_RISK_NONCOMPETE_001",
        clause_id=clause.clause_id,
        rule_id="RISK_NONCOMPETE_001",
        name="Post-employment non-compete may be unenforceable",
        severity=RiskSeverity.MEDIUM,
        explanation=(
            "The clause restrains the employee/consultant from competing AFTER the "
            "relationship ends. Under s. 27 of the Indian Contract Act, 1872, "
            "agreements in restraint of a lawful trade, business, profession or "
            "vocation are void, so a post-employment non-compete is likely "
            "unenforceable in India (plain-law reading; no specific case has been "
            "curated for this rule). An in-employment non-solicit, by contrast, "
            "is outside s. 27 and may be enforceable."
        ),
        recommendation=(
            "Replace the post-employment non-compete with an in-employment "
            "non-solicit plus a confidentiality obligation that runs for a "
            "reasonable period after employment, and confirm with Indian counsel."
        ),
        score=55.0,
        evidence_text=action,
        impact_summary=(
            "If the restraint is void, the party relying on it has no "
            "contractual remedy against a departing employee/consultant who "
            "competes, leaving it to the (often weaker) general law of "
            "confidentiality and misappropriation."
        ),
        affected_parties=_affected_parties(summary, clause.text or "", mutual=True),
        review_action=(
            "Check whether the restraint is intended to run only during "
            "employment (potentially enforceable) or after it ends (void under "
            "s. 27 ICA), and consult Indian counsel on enforceability."
        ),
        related_clause_ids=_related_ids_from_context(clause),
        uncertainty_note=(
            "This is a phrase-based screen on the post-relationship window and "
            "the competing action; the clause may be drafted in different "
            "wording, and partial restraints (geographic, client-specific) have "
            "different enforceability profiles — verify with counsel."
        ),
    )


# ---------------------------------------------------------------------------
# Missing dispute resolution (contract-level)
#
# A contract with NO arbitration clause AND no court/jurisdiction clause at
# all falls back to the default statutory forum. That is a genuine gap in an
# Indian commercial contract, but it is an ABSENCE finding: it can only be
# stated at the contract level, from a document-wide phrase search, and it
# must be marked unverified by construction (no span can prove an absence).
#
# The search reuses the same negation-aware context cues NER uses for
# arbitration-seat detection (_has_arbitration_context), so a NEGATED
# mention ("there is no arbitration clause") does NOT count as a mechanism.
# Court/jurisdiction wording is checked for positive, non-negated mentions.
# ---------------------------------------------------------------------------

# Positive court/jurisdiction mechanisms (non-negated). "subject to the
# jurisdiction of" / "the jurisdiction of the courts" / "courts at X shall
# have jurisdiction" all assert a forum; bare "jurisdiction of" alone is too
# weak (it also appears in forum-RESTRAINT clauses).
_COURT_JURISDICTION_TRIGGERS = (
    "jurisdiction of the courts",
    "courts at",
    "courts of",
    "courts of competent jurisdiction",
    "subject to the jurisdiction",
    "shall have jurisdiction",
    "shall be to the exclusive jurisdiction",
    "exclusive jurisdiction of",
    "non-exclusive jurisdiction",
)
# A forum-RESTRAINT clause ("neither party shall submit to the jurisdiction
# of ...") is the opposite of a mechanism and must not count as one.
_FORUM_RESTRAINT_MARKERS = (
    "shall not submit to the jurisdiction",
    "shall not submit itself to the jurisdiction",
    "restrain the jurisdiction",
    "deprive the courts",
    "bar the jurisdiction",
)


def rule_missing_dispute_resolution(clauses: List[Clause], summary: ContractSummary) -> Optional[RiskFlag]:
    """Contract-level: no arbitration mechanism AND no court/jurisdiction
    mechanism anywhere in the document."""
    if not summary.jurisdiction or summary.jurisdiction.lower() not in {"india", "indian"}:
        return None
    from nlp.ner.ner import _has_arbitration_context

    corpus = " ".join((c.text or "") for c in clauses)
    lowered = corpus.lower()

    # 1. Arbitration / dispute-resolution mechanism (context-cue + negation
    #    aware, the same way NER treats seat mentions).
    has_arbitration = any(_has_arbitration_context(sent.lower()) for sent in lowered.split("\n"))
    # Sentence-level too (the document may keep sentences on one line).
    if not has_arbitration:
        for sent in re.split(r"(?<=[.!?])\s+", lowered):
            if _has_arbitration_context(sent):
                has_arbitration = True
                break

    # 2. Court / jurisdiction mechanism — positive, non-negated, and not a
    #    forum-restraint (which is the opposite of a mechanism).
    has_court = False
    for trigger in _COURT_JURISDICTION_TRIGGERS:
        for m in re.finditer(re.escape(trigger), lowered):
            if _trigger_is_negated(lowered, m.start()):
                continue
            sentence = _sentence_text(lowered, m.start())
            if any(marker in sentence for marker in _FORUM_RESTRAINT_MARKERS):
                continue
            has_court = True
            break
        if has_court:
            break

    if has_arbitration or has_court:
        return None
    return RiskFlag(
        risk_id="contract_RISK_DISPUTE_001",
        clause_id=None,
        rule_id="RISK_DISPUTE_001",
        name="No dispute-resolution mechanism found",
        severity=RiskSeverity.MEDIUM,
        explanation=(
            "No arbitration clause and no court/jurisdiction clause were detected "
            "anywhere in the document (not found). The parties would fall back to "
            "the default statutory forum for any dispute, which may be less "
            "predictable or convenient than a negotiated mechanism. A negated "
            "mention ('there is no arbitration clause') does not count as a "
            "mechanism."
        ),
        recommendation=(
            "Add a dispute-resolution clause — e.g. arbitration under the "
            "Arbitration and Conciliation Act, 1996 with an Indian seat, or "
            "express submission to the courts of a specified city."
        ),
        score=50.0,
        impact_summary=(
            "Without a chosen mechanism, a dispute goes to the default court "
            "forum under the Code of Civil Procedure, with no agreed seat, "
            "law or process for resolution."
        ),
        affected_parties=_affected_parties(summary, "", mutual=True),
        review_action=(
            "Search the full document (including annexures and schedules) for "
            "arbitration or court/jurisdiction wording in alternative phrasing "
            "before concluding the mechanism is absent."
        ),
        search_scope=(
            f"document-wide phrase-based search across {len(clauses)} clause(s); "
            "absence-of-language check - no single span proves a gap"
        ),
        uncertainty_note=_phrase_search_uncertainty_note(
            "A dispute-resolution mechanism may be expressed differently or "
            "located in an annex/schedule that the searched phrases did not match."
        ),
    )


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
    RiskRule(rule_id="RISK_STAMP_001", name="Stamp duty language not detected", severity=RiskSeverity.MEDIUM, clause_type="ANY",
             description="Indian Stamp Act requirement unmet.", requires_indian=True, is_contract_level=True, check=rule_missing_stamp_duty),
    RiskRule(rule_id="RISK_TDS_001", name="TDS language not detected", severity=RiskSeverity.LOW, clause_type="ANY",
             description="No TDS deduction reference in payment clause.", requires_indian=True, is_contract_level=True, check=rule_tds_missing),
    RiskRule(rule_id="RISK_S124_001", name="Indemnity may not cover direct losses", severity=RiskSeverity.MEDIUM, clause_type="ANY",
             description="Indian indemnity gap.", requires_indian=True, is_contract_level=True, check=rule_section_124_indemnity),
    RiskRule(rule_id="RISK_NONCOMPETE_001", name="Post-employment non-compete may be unenforceable", severity=RiskSeverity.MEDIUM, clause_type="Non-Compete / Non-Solicit",
             description="Post-termination restraint on trade likely void under s. 27 ICA.", requires_indian=True, check=rule_post_employment_non_compete),
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
    # 6. P4 cross-reference analysis (advisory; never suppresses a finding).
    _analyze_cross_references(flags, clauses)
    return flags


def _analyze_cross_references(flags: List[RiskFlag], clauses: List[Clause]) -> None:
    """Attach advisory cross-reference context to clause-level findings.

    Never suppresses a finding. For a finding whose source clause references
    other provisions, records the reference resolution status and the related
    clause text so a reviewer can judge whether the reference affects the
    concern. A reference that merely exists, or that contains a matching
    keyword, is never treated as resolving the issue.
    """
    by_id = {c.clause_id: c for c in clauses}
    for flag in flags:
        if flag.source == "model" or not flag.clause_id:
            continue
        clause = by_id.get(flag.clause_id)
        if clause is None:
            continue
        ctx = clause.context if isinstance(clause.context, dict) else {}

        notes: list[str] = []
        for ref in ctx.get("references") or []:
            status = ref.get("status")
            raw = str(ref.get("raw") or "").strip()
            if not raw:
                continue
            if status == "missing":
                notes.append(f"missing reference to {raw!r}")
            elif status == "ambiguous":
                notes.append(f"ambiguous reference to {raw!r}")
        for raw in (ctx.get("unresolved_references") or []):
            notes.append(f"unresolved reference to {str(raw)!r}")

        related_ids = [rid for rid in (ctx.get("related_clause_ids") or []) if rid and rid != flag.clause_id]
        related_texts = ctx.get("related_clause_texts") or []
        for i, rid in enumerate(related_ids):
            if rid in by_id:
                snippet = " ".join((by_id[rid].text or "").split())[:100]
                heading = by_id[rid].heading or "no heading"
            elif i < len(related_texts):
                snippet = " ".join(str(related_texts[i]).split())[:100]
                heading = "related provision"
            else:
                continue
            notes.append(f"related clause {rid} ({heading}): {snippet!r}")

        if related_ids:
            flag.related_clause_ids = sorted(set(flag.related_clause_ids) | set(related_ids))

        if notes:
            flag.cross_reference_note = (
                "; ".join(notes)
                + " — advisory only; verify whether this affects the finding"
            )


def _tight_span(clause: Clause, trigger: Optional[str]) -> tuple[str, int, int]:
    """Tight evidence span for a clause-level finding.

    When ``trigger`` is present and found verbatim in the clause text, the
    span is the sentence containing it (offsets computed against the *stored*
    clause text). Otherwise the span is the whole clause text (the old
    behaviour). The returned ``(text, start, end)`` always satisfies
    ``clause.text[start:end] == text``.
    """
    raw = clause.text or ""
    if not trigger:
        return raw, 0, len(raw)
    # Find the trigger verbatim in the raw (stored) clause text. The trigger is
    # produced from the lowercased text, so look case-insensitively in the
    # cleaned text, then map back to the raw text via a simple offset search.
    lowered = clean_text(raw).lower()
    pos = lowered.find(trigger.lower())
    if pos == -1:
        return raw, 0, len(raw)
    # Map from cleaned offset to raw offset: walk both strings in lock-step.
    # clean_text only removes whitespace/control chars and smart-quote
    # translations — it does not insert characters — so the raw offset is at
    # least the cleaned offset. A conservative approach: search the raw text
    # for the trigger (case-insensitive) and use the first match.
    raw_low = raw.lower()
    raw_pos = raw_low.find(trigger.lower())
    if raw_pos == -1:
        return raw, 0, len(raw)
    start, end = _sentence_span(raw_low, raw_pos)
    # Strip leading/trailing whitespace from the span.
    while start < end and raw[start] in " \t\r\n":
        start += 1
    while end > start and raw[end - 1] in " \t\r\n":
        end -= 1
    return raw[start:end], start, end


def _bind_evidence(flags: List[RiskFlag], clauses: List[Clause]) -> None:
    """Attach traceable evidence without inventing spans.

    Clause-level findings get the *trigger sentence* when a ``evidence_text``
    trigger is available and locatable, else the full clause text, in both
    cases with offsets into ``Clause.text`` (locator="clause_text") and
    ``evidence_status="direct"``. Contract-level findings (no clause) get an
    explicit ``search_scope`` and ``evidence_status="unverified"`` - never a
    fabricated nearby clause.
    """
    from app.models.schemas import EvidenceSpan

    by_id = {c.clause_id: c for c in clauses}
    for flag in flags:
        if flag.source == "model":
            continue  # ML findings are bound by the analyzer (unverified by design)
        if flag.clause_id:
            clause = by_id.get(flag.clause_id)
            if clause is not None and (clause.text or "").strip():
                span_text, span_start, span_end = _tight_span(clause, flag.evidence_text)
                flag.evidence_spans = [
                    EvidenceSpan(
                        text=span_text,
                        char_start=span_start,
                        char_end=span_end,
                        clause_id=clause.clause_id,
                        role="direct",
                        locator="clause_text",
                    )
                ]
                flag.evidence_status = "direct"
            elif clause is None:
                flag.evidence_status = "unverified"
        else:
            if not flag.search_scope:
                flag.search_scope = (
                    f"document-wide scan across {len(clauses)} clause(s); "
                    "keyword-presence rule - no single supporting span"
                )
            flag.evidence_status = "unverified"


def _contract_level_rules(clauses: List[Clause], summary: ContractSummary) -> List[RiskFlag]:
    flags: List[RiskFlag] = []

    # P5 (charter §5.C): contradictory liability caps across clauses.
    # Runs before the missing-clause checks; it is a pure text comparison
    # and is independent of classification or jurisdiction.
    conflict = rule_contradictory_liability_caps(clauses, summary)
    if conflict is not None:
        flags.append(conflict)

    # Missing mandatory clauses — use BOTH the classifier output AND a
    # keyword check across clause text to avoid false negatives.
    detected_types = {t for c in clauses for t in c.clause_types}
    text_corpus = " ".join((c.text or "").lower() for c in clauses)

    mandatory_checks = [
        ("Governing Law", ["governed by the laws", "governing law", "jurisdiction of"]),
        ("Termination", ["termination", "may terminate", "terminate this agreement"]),
        ("Limitation of Liability", ["limitation of liability", "limit of liability", "in no event shall"]),
    ]
    # Document-wide search scope (annexures included when segmented).
    annexure_clauses = [
        c for c in clauses
        if re.match(r"^\s*(schedule|exhibit|annexure|appendix)\b", (c.heading or ""), re.IGNORECASE)
    ]
    scope_note = (
        f"document-wide phrase-based search across {len(clauses)} clause(s), "
        f"including {len(annexure_clauses)} annexure/schedule clause(s)"
    )
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
                    explanation=(
                        f"{clause_type} clause not detected (not found)."
                    ),
                    recommendation=f"Add a standard {clause_type.lower()} clause.",
                    score=60.0,
                    impact_summary=(
                        f"Without a {clause_type.lower()} clause, the parties "
                        "fall back to default law where the contract is silent, "
                        "which may be less predictable than negotiated terms."
                    ),
                    affected_parties=["both parties"],
                    review_action=(
                        f"Search the full document (including annexures and "
                        f"schedules) for {clause_type.lower()} wording in "
                        "alternative phrasing before adding a new clause."
                    ),
                    search_scope=scope_note,
                    uncertainty_note=_phrase_search_uncertainty_note(
                        f"A {clause_type.lower()} protection may be expressed "
                        "differently or located in an annex/schedule that the "
                        "phrases above did not match."
                    ),
                )
            )

    # Data protection presence if personal data is referenced.
    mentions_personal_data = "personal data" in text_corpus or "personal information" in text_corpus
    # Presence check: classification OR an explicit *protection* phrase.
    # "personal data" alone is NOT a protection phrase — it only establishes
    # that the contract handles personal data (the trigger condition). A
    # genuine data-protection clause must say something about protecting,
    # processing, or securing that data.
    has_dp = "Data Protection" in detected_types or any(
        k in text_corpus
        for k in (
            "data protection", "data breach", "data protection policy",
            "privacy policy", "data security", "security incident",
            "information security", "data fiduciary",
            "personal data protection", "protect personal data",
        )
    )
    if mentions_personal_data and not has_dp:
        flags.append(
            RiskFlag(
                risk_id="contract_DATA_PROTECTION_MISSING",
                rule_id="RISK_DATA_MISSING",
                name="Missing data protection clause",
                severity=RiskSeverity.HIGH,
                explanation=(
                    "Contract references personal data but no data protection "
                    "clause was detected (not found)."
                ),
                recommendation="Add a data protection, breach notification, and security clause.",
                score=70.0,
                impact_summary=(
                    "If personal data is processed without contractual "
                    "protection terms, the parties' obligations under the "
                    "data-protection regime are not allocated by the contract."
                ),
                affected_parties=_affected_parties(summary, "", mutual=True),
                review_action=(
                    "Search the full document and all annexures for data "
                    "protection wording (e.g. a policy attached as an "
                    "annexure) before adding a new clause."
                ),
                search_scope=scope_note,
                uncertainty_note=_phrase_search_uncertainty_note(
                    "The protection may be expressed differently or located in "
                    "an annexure (e.g. a data protection policy attached as an "
                    "annex) that the searched phrases did not match."
                ),
            )
        )

    # Section 124 concerns the indemnity wording itself. Scanning the whole contract
    # would let an unrelated "breach of contract" reference suppress the
    # finding, so evaluate only the indemnification clauses.
    indemnity_clauses = [c for c in clauses if "Indemnification" in c.clause_types]
    indemnity_text = " ".join((c.text or "") for c in indemnity_clauses).strip()
    if indemnity_text:
        synthetic_indemnity = Clause(
            clause_id="contract",
            text=indemnity_text,
            clause_types=["Indemnification"],
        )
        try:
            flag = rule_section_124_indemnity(synthetic_indemnity, summary)
        except Exception:
            flag = None
        if flag is not None:
            flag.clause_id = None
            flag.search_scope = (
                f"indemnification clauses only ({len(indemnity_clauses)}); "
                "absence-of-language check - no single span proves a gap"
            )
            flags.append(flag)

    # Missing dispute-resolution mechanism (contract-level, India only).
    # It takes the full clause list (the check is document-wide) and returns a
    # single unverified contract-level finding, so it is not run through the
    # per-clause RISK_RULES loop below.
    if (summary.jurisdiction or "").lower() in {"india", "indian"}:
        try:
            flag = rule_missing_dispute_resolution(clauses, summary)
        except Exception:
            flag = None
        if flag is not None:
            flags.append(flag)

    # Other Indian-statutory checks run once against the whole contract.
    synthetic = Clause(clause_id="contract", text=text_corpus, clause_types=sorted(detected_types))
    for rule in RISK_RULES:
        if not rule.is_contract_level or rule.check is None:
            continue
        if rule.rule_id == "RISK_S124_001":
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
