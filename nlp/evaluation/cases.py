"""Small labelled synthetic corpus for evaluating risk, obligation and evidence behaviour."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# All contracts below are synthetic. Parties, figures and clause wording are
# invented for evaluation only; none is a real agreement or legal advice. The
# expectations encode the *desired* behaviour. Where the current system does
# not meet the desired behaviour, the case carries a ``known_limitation`` note
# so the failure stays visible rather than being hidden or asserted away.


@dataclass(frozen=True)
class ObligationExpectation:
    """Field-level expectation for one obligation located by a source substring."""

    locate: str  # substring that must appear in the target obligation's source text
    subject_not_none: bool = False
    counterparty_is_none: bool = False
    counterparty_equals: Optional[str] = None
    condition_contains: Tuple[str, ...] = ()
    deadline_expression: Optional[str] = None


@dataclass(frozen=True)
class EvalCase:
    """One synthetic contract plus the behaviour a correct review should produce."""

    case_id: str
    category: str
    description: str
    text: str
    expect_present: Tuple[str, ...] = ()
    expect_absent: Tuple[str, ...] = ()
    # (rule_id, severity) pairs that must hold for at least one matching finding.
    expect_severity: Tuple[Tuple[str, str], ...] = ()
    obligations: Tuple[ObligationExpectation, ...] = ()
    known_limitation: Optional[str] = None
    jurisdiction: str = "India"
    contract_type: str = "Service"
    notes: str = ""


CASES: Tuple[EvalCase, ...] = (
    # ----- Correct risk detection (true positives) -----------------------
    EvalCase(
        case_id="uncapped_liability_tp",
        category="risk_true_positive",
        description="Explicit unlimited liability must be flagged as uncapped liability.",
        text=(
            "MASTER SERVICES AGREEMENT\n\n"
            "1. LIMITATION OF LIABILITY\n"
            "The Provider shall have unlimited liability for any and all damages "
            "arising out of this Agreement.\n"
        ),
        expect_present=("RISK_LIABILITY_001",),
        expect_severity=(("RISK_LIABILITY_001", "critical"),),
    ),
    EvalCase(
        case_id="auto_renewal_no_notice",
        category="risk_true_positive",
        description="Auto-renewal with no notice period is a high-severity lock-in risk.",
        text=(
            "TERM AND RENEWAL\n\n"
            "3. TERM\n"
            "This Agreement automatically renews for successive one-year terms.\n"
        ),
        expect_present=("RISK_RENEWAL_001",),
        expect_severity=(("RISK_RENEWAL_001", "high"),),
    ),
    EvalCase(
        case_id="auto_renewal_with_notice",
        category="risk_severity_calibration",
        description=(
            "Auto-renewal WITH a clearly stated 60-day non-renewal notice in the same "
            "clause should be medium severity, not high (the lock-in risk is reduced)."
        ),
        text=(
            "TERM AND RENEWAL\n\n"
            "3. TERM\n"
            "This Agreement automatically renews for successive one-year terms unless "
            "either party gives written notice of non-renewal at least sixty (60) days "
            "before the end of the then-current term.\n"
        ),
        expect_present=("RISK_RENEWAL_001",),
        expect_severity=(("RISK_RENEWAL_001", "medium"),),
    ),
    EvalCase(
        case_id="foreign_gov_law",
        category="risk_true_positive",
        description="Foreign governing law in an Indian-jurisdiction contract is flagged.",
        text=(
            "GOVERNING LAW\n\n"
            "9. GOVERNING LAW\n"
            "This Agreement shall be governed by the laws of the State of New York, "
            "and the parties submit to the courts of New York.\n"
        ),
        expect_present=("RISK_GOV_001",),
        expect_severity=(("RISK_GOV_001", "high"),),
    ),
    EvalCase(
        case_id="one_sided_termination",
        category="risk_true_positive",
        description="Termination for convenience in sole discretion is flagged.",
        text=(
            "TERMINATION\n\n"
            "6. TERMINATION\n"
            "The Provider may terminate this Agreement at any time without cause "
            "in its sole discretion.\n"
        ),
        expect_present=("RISK_TERM_001",),
    ),
    EvalCase(
        case_id="broad_indemnity_tp",
        category="risk_true_positive",
        description="Indemnity covering 'any and all claims from any cause whatsoever' is broad.",
        text=(
            "INDEMNIFICATION\n\n"
            "5. INDEMNITY\n"
            "The Supplier shall indemnify the Customer from any and all claims "
            "arising from any cause whatsoever.\n"
        ),
        expect_present=("RISK_INDEMNITY_001",),
        obligations=(
            ObligationExpectation(
                locate="indemnify",
                subject_not_none=True,
                counterparty_equals="Customer",
            ),
        ),
    ),
    EvalCase(
        case_id="data_breach_tight",
        category="risk_true_positive",
        description="A <=24h breach-notification window is flagged as operationally tight.",
        text=(
            "DATA PROTECTION\n\n"
            "4. SECURITY\n"
            "In the event of a data breach, the Processor shall notify the "
            "Controller within 12 hours.\n"
        ),
        expect_present=("RISK_DATA_001",),
    ),
    # ----- True negatives (no false alarm) -------------------------------
    EvalCase(
        case_id="capped_liability_tn",
        category="risk_true_negative",
        description="A stated liability cap must NOT raise an uncapped/missing-cap finding.",
        text=(
            "MASTER SERVICES AGREEMENT\n\n"
            "1. LIMITATION OF LIABILITY\n"
            "The total aggregate liability of each party shall not exceed the fees "
            "paid in the preceding twelve (12) months.\n"
        ),
        expect_absent=("RISK_LIABILITY_001", "RISK_LIABILITY_002"),
    ),
    EvalCase(
        case_id="indemnity_direct_losses",
        category="risk_true_negative",
        description="Indemnity expressly covering direct losses/breach must not raise S124.",
        text=(
            "INDEMNIFICATION\n\n"
            "5. INDEMNITY\n"
            "The Supplier shall indemnify the Customer against any and all claims, "
            "including direct losses and breach of contract.\n"
        ),
        expect_absent=("RISK_S124_001",),
    ),
    EvalCase(
        case_id="complete_contract",
        category="risk_true_negative",
        description=(
            "A contract with governing law, termination and a liability cap must not "
            "raise the keyword-based missing-clause or liability findings."
        ),
        text=(
            "SERVICE AGREEMENT\n\n"
            "1. GOVERNING LAW\n"
            "This Agreement is governed by the laws of India.\n\n"
            "2. TERMINATION\n"
            "Either party may terminate on 30 days written notice for material breach.\n\n"
            "3. LIMITATION OF LIABILITY\n"
            "Each party's aggregate liability shall not exceed the fees paid in the "
            "preceding 12 months.\n\n"
            "4. PAYMENT TERMS\n"
            "The Customer shall pay invoices within 30 days.\n"
        ),
        expect_absent=(
            "RISK_LIABILITY_001",
            "RISK_LIABILITY_002",
            "RISK_RENEWAL_001",
            "RISK_TERM_001",
            "MISSING_CLAUSE_GOVERNING_LAW",
            "MISSING_CLAUSE_TERMINATION",
            "MISSING_CLAUSE_LIMITATION_OF_LIABILITY",
        ),
    ),
    # ----- Uncertain / unsupported legal conclusions ---------------------
    EvalCase(
        case_id="stamp_tds_absent",
        category="uncertain_legal_conclusion",
        description=(
            "Absent stamp-duty/TDS language must surface as 'not found - verify' review "
            "prompts (unverified), never as a confirmed violation."
        ),
        text=(
            "PAYMENT TERMS\n\n"
            "2. PAYMENT\n"
            "The Customer shall pay the Provider INR 5,00,000 within thirty (30) days "
            "of each invoice.\n"
        ),
        expect_present=("RISK_STAMP_001", "RISK_TDS_001"),
        expect_severity=(("RISK_STAMP_001", "medium"), ("RISK_TDS_001", "low")),
    ),
    EvalCase(
        case_id="indemnity_narrow",
        category="uncertain_legal_conclusion",
        description=(
            "A narrow indemnity (no direct-loss wording) must raise S124 as a "
            "qualified 'may be insufficient - verify' prompt, not a defect."
        ),
        text=(
            "INDEMNIFICATION\n\n"
            "5. INDEMNITY\n"
            "The Supplier shall indemnify the Customer against third party claims "
            "arising from infringement of intellectual property.\n"
        ),
        expect_present=("RISK_S124_001",),
        expect_severity=(("RISK_S124_001", "medium"),),
    ),
    # ----- Conditions, exceptions, party/beneficiary ambiguity -----------
    EvalCase(
        case_id="obligation_conditional",
        category="conditions_and_exceptions",
        description="A conditional payment duty must capture both its condition and its exception.",
        text=(
            "PAYMENT TERMS\n\n"
            "2. PAYMENT\n"
            "If the Customer receives a valid invoice, the Customer shall pay the "
            "Provider within thirty (30) days, unless the invoice is disputed in "
            "good faith.\n"
        ),
        obligations=(
            ObligationExpectation(
                locate="shall pay",
                subject_not_none=True,
                condition_contains=("valid invoice", "disputed"),
                deadline_expression="30 days",
            ),
        ),
    ),
    EvalCase(
        case_id="ambiguous_recipient",
        category="party_beneficiary_ambiguity",
        description="A statute reference is not a party; the recipient must stay None, not fabricated.",
        text=(
            "COMPLIANCE\n\n"
            "8. COMPLIANCE\n"
            "The Provider shall comply with the Information Technology Act, 2000 "
            "and all applicable regulations.\n"
        ),
        obligations=(
            ObligationExpectation(
                locate="comply",
                subject_not_none=True,
                counterparty_is_none=True,
            ),
        ),
    ),
    # ----- Cross-reference resolution (known false positive) -------------
    EvalCase(
        case_id="liability_cap_in_crossref",
        category="cross_reference_resolution",
        description=(
            "A liability cap stated in a cross-referenced clause (7.4) should prevent "
            "a 'missing cap' finding on clause 7.1."
        ),
        text=(
            "SERVICE AGREEMENT\n\n"
            "7.1 LIMITATION OF LIABILITY\n"
            "Except as set out in Clause 7.4, neither party shall be liable for "
            "indirect damages.\n\n"
            "7.4 LIABILITY CAP\n"
            "Each party's aggregate liability shall not exceed the total fees paid "
            "under this Agreement in the preceding 12 months.\n"
        ),
        expect_absent=("RISK_LIABILITY_002",),
        known_limitation=(
            "Rules evaluate a single clause; the cap in cross-referenced clause 7.4 "
            "is not consumed, so RISK_LIABILITY_002 is a false positive on 7.1. "
            "Automatic cross-clause suppression was deliberately reverted as unsafe "
            "(a keyword match in a related clause does not establish an applicable cap)."
        ),
    ),
    # ----- Passive voice + written-out compound deadline (known gap) -----
    EvalCase(
        case_id="obligation_passive",
        category="passive_voice",
        description=(
            "A passive duty ('shall be encrypted by the Processor within twenty-four "
            "(24) hours') should recover the by-agent as obligor and the 24h deadline."
        ),
        text=(
            "DATA PROTECTION\n\n"
            "4. SECURITY\n"
            "Personal data shall be encrypted by the Processor within twenty-four "
            "(24) hours of a security incident.\n"
        ),
        obligations=(
            ObligationExpectation(
                locate="encrypted",
                subject_not_none=True,
                deadline_expression="24 hours",
            ),
        ),
        known_limitation=(
            "Hyphenated written compounds ('twenty-four') are not normalised by the "
            "deadline parser, and the passive by-agent is not recovered here, so the "
            "subject and 24h deadline are both missed."
        ),
    ),
    # ----- Detection recall gap for present Indian-statutory language ----
    EvalCase(
        case_id="stamp_tds_present_missed",
        category="detection_recall_gap",
        description=(
            "'duly stamped paper' and 'deduction of tax at source' are present, so the "
            "stamp/TDS 'not found' prompts should NOT fire."
        ),
        text=(
            "PAYMENT TERMS\n\n"
            "2. PAYMENT\n"
            "The Customer shall pay invoices within 30 days, subject to deduction of "
            "tax at source under the Income Tax Act, 1961. This Agreement is executed "
            "on duly stamped paper.\n"
        ),
        expect_absent=("RISK_STAMP_001", "RISK_TDS_001"),
    ),
)
