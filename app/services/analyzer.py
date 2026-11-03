"""High-level orchestrator: parser -> segmenter -> NLP -> risk -> graph."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger
from app.models.schemas import (
    AnalysisResult,
    Clause,
    ContractSummary,
    ContractType,
    Obligation,
    PartySide,
    RiskFlag,
    RiskSeverity,
)
from app.services.parser import parse_bytes, parse_document
from app.services.segmenter import segment_clauses
from app.utils.text import clean_text
from nlp.clause_classification.classifier import classify_clause
from nlp.context import resolve_context
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
from nlp.risk_scoring.scorer import severity_to_score

logger = get_logger()

# Maximum number of parties reported per contract (keeps the summary
# focused; guarantees/guarantors beyond this must be reviewed manually).
MAX_PARTIES = 4


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
        pages=parsed.pages,
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
        pages=parsed.pages,
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
    pages: Optional[list] = None,
    contract_type: ContractType,
    user_role: PartySide,
    jurisdiction: str,
) -> AnalysisResult:
    logger.info("Analysing contract {} ({} chars)", contract_id, len(full_text))

    # 1. Clause segmentation
    raw_clauses = segment_clauses(full_text, contract_id=contract_id)
    logger.info("Segmented into {} clauses", len(raw_clauses))
    # Stamp page-level provenance (char offset -> page number). Never
    # guesses: clauses that cannot be located on a page keep page_hint=None.
    _stamp_page_hints(raw_clauses, pages)
    # P1: resolve cross-references/definitions/precedence (read-only enrichment;
    # no rule, severity or trigger behaviour is changed).
    context_bundle = resolve_context(raw_clauses)

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
            context=context_bundle.get(raw.clause_id),
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

    # 4. Risk rules -> flags, then ML recall booster for unflagged clauses
    # P4: enrich each clause's context bundle with the text of its related
    # clauses so risk rules can perform whole-contract (cross-reference) checks
    # without treating a resolved reference as proof of override.
    clause_by_id = {c.clause_id: c for c in clauses}
    for cl in clauses:
        ctx = cl.context
        if not isinstance(ctx, dict):
            continue
        related_ids = ctx.get("related_clause_ids") or []
        related_texts = [
            clause_by_id[rid].text
            for rid in related_ids
            if rid in clause_by_id and rid != cl.clause_id
        ]
        ctx = dict(ctx)
        ctx["related_clause_texts"] = related_texts
        cl.context = ctx

    flags = apply_rules(clauses, summary_draft)
    flags = _augment_with_ml_risks(clauses, flags)

    # 5. Annotate clauses with their own risk_score
    for cl in clauses:
        cl_flags = [f for f in flags if f.clause_id == cl.clause_id]
        if cl_flags:
            top = max(cl_flags, key=lambda f: f.score)
            cl.risk_score = top.score
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
        f.name
        for f in flags
        if f.rule_id.startswith("MISSING_CLAUSE_") or f.rule_id == "RISK_DATA_MISSING"
    ]
    summary_draft.top_risks = sorted(
        flags, key=lambda f: severity_to_score(f.severity), reverse=True,
    )[:5]

    # 7. Surface runtime provenance verdicts (data-lineage only, not accuracy).
    analysis_warnings = list(warnings)
    if not summary_draft.parties:
        analysis_warnings.append("No parties detected — review the preamble manually")
    try:
        from nlp import provenance as _provenance

        analysis_warnings.extend(_provenance.warnings())
    except Exception:  # pragma: no cover - provenance must never break analysis
        pass

    return AnalysisResult(
        contract=summary_draft,
        clauses=clauses,
        obligations=all_obligations,
        risks=flags,
        warnings=analysis_warnings,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stamp_page_hints(raw_clauses: List, pages: Optional[list]) -> None:
    """Set ``clause.page_hint`` from parser page boundaries.

    The segmenter works on ``clean_text(full_text)``, and the parser built
    ``full_text`` by joining its (already cleaned, header-stripped) page
    texts — so rebuilding that join puts us in exactly the segmenter's
    coordinate space. Each non-empty page is located inside the joined text;
    a page whose text cannot be located (cleaning changed it) is left out,
    and a clause falling in a gap between located pages keeps
    ``page_hint=None`` unless the gap is pure whitespace (a page that
    cleaned away to nothing).
    """
    if not pages or not raw_clauses:
        return
    doc = clean_text("\n\n".join(pg.text for pg in pages if pg.text))
    bounds: List[tuple[int, int, int]] = []  # (start, end, page_number)
    for pg in pages:
        if not pg.text.strip():
            continue
        found = doc.find(pg.text)
        if found == -1:
            continue
        bounds.append((found, found + len(pg.text), pg.page_number))
    if not bounds:
        return
    for clause in raw_clauses:
        page_at: Optional[int] = None
        for start, end, num in bounds:
            if start <= clause.char_start < end:
                page_at = num
                break
        if page_at is None:
            for (_s1, e1, n1), (s2, _e2, _n2) in zip(bounds, bounds[1:], strict=False):
                if e1 < clause.char_start < s2:
                    if doc[e1:s2].isspace():
                        page_at = n1
                    break
        clause.page_hint = page_at


_ML_FALLBACK_SCORE = {"medium": 45.0, "high": 60.0, "critical": 75.0}


def _augment_with_ml_risks(clauses: List[Clause], flags: List[RiskFlag]) -> List[RiskFlag]:
    """Add model-predicted findings for clauses the rules did not flag.

    The ML risk classifier is a *recall booster*: it never overrides a rule, it
    only surfaces additional candidates for human review. A no-op when no
    trained model artefact is present, so the rule-only pipeline is unaffected.
    """
    from app.models.schemas import EvidenceSpan
    from nlp.risk_scoring.risk_model import load_cached, predict_clause_risk

    if load_cached() is None:
        return flags

    flagged = {f.clause_id for f in flags if f.clause_id}
    extra: List[RiskFlag] = []
    for clause in clauses:
        if clause.clause_id in flagged:
            continue
        prediction = predict_clause_risk(clause.text)
        if prediction is None:
            continue
        extra.append(
            RiskFlag(
                risk_id=f"{clause.clause_id}_ML_RISK_001",
                clause_id=clause.clause_id,
                rule_id="ML_RISK_001",
                name=f"Model-suggested {prediction.severity.value} risk",
                severity=prediction.severity,
                explanation=(
                    f"The ML risk classifier suggests {prediction.severity.value} severity with an "
                    f"uncalibrated model score of {prediction.confidence:.0%} (raw classifier output, "
                    "not a calibrated probability) from the clause wording, although no explicit rule "
                    "matched. Treat as a review prompt, not a definitive finding."
                ),
                recommendation="Manually review this clause against the standard playbook.",
                score=_ML_FALLBACK_SCORE.get(prediction.severity.value, 45.0),
                # P2: model-only suggestion - distinguishable and NOT evidence-backed.
                source="model",
                evidence_status="unverified",
                evidence_spans=[
                    EvidenceSpan(
                        text=clause.text,
                        char_start=0,
                        char_end=len(clause.text),
                        clause_id=clause.clause_id,
                        role="contextual",
                        locator="clause_text",
                    )
                ],
            )
        )
    if extra:
        logger.info("ML risk classifier added {} extra finding(s)", len(extra))
    return flags + extra


def _detect_parties(clauses: List[Clause]) -> List[str]:
    """Detect party names using NER entities + preamble + pattern-3 fallbacks."""
    parties: List[str] = []
    section_starts = re.compile(r"^\s*\d+(\.\d+)*\s*\.?\s*[A-Z]")
    blacklist = {
        "agreement", "indemnification", "confidentiality", "between",
        "stamp duty", "force majeure", "term and renewal", "data protection",
        "intellectual property", "limitation of liability", "definitions",
        "governing law", "dispute resolution", "termination", "miscellaneous",
        "notice", "payment terms", "warranty", "service levels",
        "change control", "acceptance", "compliance", "insurance",
        "audit rights", "assignment", "non-compete", "non-solicit",
    }

    def _scan(text: str) -> List[str]:
        """Extract party candidates from a chunk of text."""
        found: List[str] = []
        if not text:
            return found
        # 1. Suffix-based extraction (most reliable for Indian companies).
        pvt_suffix = re.compile(
            r"\b((?:[A-Z][\w'.-]+\s+){0,5}(?:Pvt\.?\s*Ltd\.?|Limited|LLP|Inc\.?|Corporation|Corp\.?|LLC|PLC))\b"
        )
        # Noise words that END a candidate name when walking back from the
        # corporate suffix. Role/context words belong here ("agent",
        # "customer"); words that are legitimate *inside* a legal entity name
        # ("Services", "Company") do NOT — treating them as noise truncated
        # real names like "ABC Services Pvt Ltd" to nothing (audit defect D6).
        noise_words = {
            "having", "with", "between", "of", "the", "and", "from", "pan",
            "cin", "gstin", "represented", "incorporated", "registered", "its",
            "their", "whose", "whereas", "recital", "by", "as", "for",
            "annexure", "annexed", "schedule", "section", "clause",
            "agent", "customer", "resident", "client",
            "party", "parties", "provider", "recipient",
            "january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december",
        }
        # Corporate-suffix tokens: the current match's own suffix is kept, but
        # hitting a SECOND suffix while walking back means we have crossed
        # into an earlier party name ("Acme Services Pvt Ltd and Zenith
        # Technologies Pvt Ltd") — stop there or the names glue together.
        suffix_tokens = {
            "pvt", "ltd", "limited", "llp", "inc", "corp", "corporation",
            "llc", "plc", "pte", "private",
        }
        pan_noise = re.compile(r"^[A-Z]{5}\d{4}[A-Z],?\s*(?:and\s+)?", re.IGNORECASE)
        # Also catch "DTwelve Accommodations Private Limited" style names
        # where "Private Limited" or "Pte Ltd" appears.
        generic_corp = re.compile(
            r"\b((?:[A-Z][\w'.-]+\s+){0,5}(?:Private\s+Limited|Pte\.?\s+Ltd\.?|Private\s+Ltd\.?|Ltd\.?))\b"
        )
        for pat in (pvt_suffix, generic_corp):
            for match in pat.finditer(text):
                end = match.end()
                start = match.start()
                prefix = text[:start]
                cut = max(prefix.rfind("\n"), prefix.rfind(". "), prefix.rfind(" ("), -1)
                # Walk back through tokens but stop at noise words.
                tokens_back = re.findall(r"[A-Z][\w'.-]+", text[max(0, cut + 1) : end])
                kept: List[str] = []
                for tok in reversed(tokens_back):
                    low = tok.lower().strip(".,")
                    if low in noise_words or low in blacklist:
                        break
                    if (
                        low in suffix_tokens
                        and any(t.lower().strip(".,") not in suffix_tokens for t in kept)
                    ):
                        break
                    kept.append(tok)
                    if len(kept) >= 7:
                        break
                if not kept:
                    continue
                kept.reverse()
                name = " ".join(kept)
                name = pan_noise.sub("", name).strip().strip(",.;:")
                # Strip leading noise tokens like "Private Limited" that
                # bleed in from a previous match.
                while name:
                    first = name.split()[0].lower()
                    if first in {"private", "limited", "pvt", "llp", "inc", "corp",
                                  "the", "and", "of", "company", "agent", "customer"}:
                        name = " ".join(name.split()[1:]).strip()
                    else:
                        break
                # A candidate built only from generic suffix/name words
                # ("Services Pvt Ltd") is a fragment, not an entity: require at
                # least one distinctive token.
                generic_tokens = {
                    "private", "limited", "ltd", "pvt", "pte", "llp", "inc",
                    "corp", "corporation", "llc", "plc", "services", "company",
                }
                if not any(
                    tok.lower().strip(".,") not in generic_tokens for tok in name.split()
                ):
                    continue
                if 4 <= len(name) <= 100 and name not in parties and name not in found:
                    found.append(name)
                if len(found) >= 6:
                    return found
        return found

    # 1. Scan the heading + body of the first AND last 3 clauses (preamble
    # often appears as the heading of clause 0; parties sometimes appear
    # only in the signature block at the end). Union is de-duplicated.
    window: List[Clause] = []
    for c in list(clauses[:3]) + list(clauses[-3:]):
        if c not in window:
            window.append(c)
    for c in window:
        for chunk in ((c.heading or ""), (c.text or "")[:2000]):
            for name in _scan(chunk):
                if name not in parties:
                    parties.append(name)
            if len(parties) >= MAX_PARTIES:
                break

    # 2. NER entities (PARTY/ORG) from the first 6 clauses.
    if len(parties) < 2:
        for c in clauses[:6]:
            for ent in c.entities:
                if ent.label not in {"PARTY", "ORG"}:
                    continue
                t = (ent.text or "").strip().strip(",.;:")
                if not t or len(t) > 80 or section_starts.match(t):
                    continue
                if t.lower() in blacklist:
                    continue
                if re.search(r"\b[A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+\b", t) and t not in parties:
                    parties.append(t)
            if len(parties) >= MAX_PARTIES:
                break

    # 3. Preamble "between X and Y" pattern (last-ditch).
    if len(parties) < 2:
        preamble_patterns = [
            re.compile(
                r"(?im)^\s*this\s+\w+\s+agreement\s*(?:\([^)]*\))?\s*is\s+(?:made|entered\s+into)?\s*"
                r"(?:on|as\s+of)?\s*[^\n]{0,40}?\n+\s*between\s+"
                r"([^\n,;]+?)\s*(?:\(|,|having)\s*"
                r".*?\s*(?:and|&)\s+"
                r"([^\n,;]+?)(?:\s*\(|\s*,|\s*having|\.|\n|$)",
                re.DOTALL,
            ),
            re.compile(
                r"(?im)between\s+([A-Z][^\n,;(]{2,80}?)\s+(?:and|&)\s+([A-Z][^\n,;(]{2,80}?)\s*(?:\(|,|\.|having|$)",
            ),
        ]
        search_text = "\n".join(
            (c.heading or "") + "\n" + (c.text or "")[:1500] for c in clauses[:2]
        )
        for pat in preamble_patterns:
            m = pat.search(search_text)
            if not m:
                continue
            break
            for grp in (m.group(1), m.group(2)):
                name = grp.strip().strip(",.;:")
                if not name:
                    continue
                name = re.sub(r"^\s*the\s+", "", name, flags=re.IGNORECASE)
                drop = {"having", "with", "between", "and", "of", "the"}
                while name and name.split()[0].lower() in drop:
                    name = " ".join(name.split()[1:])
                while name and name.split()[-1].lower() in drop:
                    name = " ".join(name.split()[:-1])
                if 3 <= len(name) <= 80 and name not in parties:
                    parties.append(name)
            if len(parties) >= MAX_PARTIES:
                break

    # Dedupe case-insensitively, prefer the most-complete spelling.
    deduped: List[str] = []
    seen_lower: set[str] = set()
    for name in parties:
        key = name.lower().strip()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        deduped.append(name)
    return deduped[:MAX_PARTIES]


# Context cues that mark a date as the *operative/effective* one rather
# than a recital of the original instrument's date. Bare "dated" is
# deliberately NOT a cue ("Agreement dated 1 January 2020" recites the
# original instrument).
_EFFECTIVE_DATE_CUES = re.compile(
    r"(?ix)\b(?:effective\s+date|effective\s+as\s+of|commence[sd]?|"
    r"made\s+on|entered\s+into|dated\s+as\s+of)\b"
)

# "was amended on" is an effective-date cue: for a document that is an
# amendment, the amendment date is its operative date ("This Agreement
# dated 1 January 2020 was amended on 15 April 2024 ...").
_AMENDMENT_RECITAL_RE = re.compile(
    r"(?ix)\bwas\s+amended\s+on\b|\bwere\s+amended\s+on\b"
)

# Sentence splitter good enough for cue scoring (dates rarely straddle
# paragraph boundaries).
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_GENERIC_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})\b",
    re.IGNORECASE,
)


def _effective_date_cues(sentence: str) -> bool:
    """Whether a sentence carries an effective-date cue."""
    if _EFFECTIVE_DATE_CUES.search(sentence):
        return True
    return bool(_AMENDMENT_RECITAL_RE.search(sentence))


def _first_date(clauses: List[Clause]) -> Optional[str]:
    """Pick the effective date: context-scored first, first-DATE fallback.

    Sentences containing an effective-date cue ("effective date",
    "commences", "made on", "entered into", ...) win; among them the first
    in document order is used. With no cue, behaviour is unchanged: the
    first DATE entity (or first generic date match) is returned.
    """
    for c in clauses:
        for sentence in _SENTENCE_RE.split(c.text or ""):
            if not _effective_date_cues(sentence):
                continue
            # Score every date mention in the cue sentence: prefer the one
            # the cue actually points at. For an amendment recital
            # ("... dated X was amended on Y"), the operative date is the
            # one *after* "amended on"; otherwise the sentence's first
            # date follows the cue ("made on X", "commences on X").
            cue_dates = [m.group(1).strip() for m in _GENERIC_DATE_RE.finditer(sentence)]
            if cue_dates:
                m_cue = _AMENDMENT_RECITAL_RE.search(sentence)
                if m_cue:
                    tail_dates = _GENERIC_DATE_RE.findall(sentence[m_cue.end():])
                    return tail_dates[0] if tail_dates else cue_dates[-1]
                return cue_dates[0]
            m = _GENERIC_DATE_RE.search(sentence)
            if m:
                return m.group(1).strip()
    for c in clauses:
        for ent in c.entities:
            if ent.label == "DATE":
                value = ent.text.strip()
                if value and len(value) > 4:
                    return value
    for c in clauses[:10]:
        text = c.text or ""
        m = _GENERIC_DATE_RE.search(text)
        if m:
            return m.group(1).strip()
    return None


