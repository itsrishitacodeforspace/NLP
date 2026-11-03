"""Case-law / statutory pointers for the risk playbook.

Every risk rule can be enriched with the authority that explains *why* it
matters. This is a curated, fully offline mapping — no network calls — so the
feature works with zero infrastructure.

.. warning::
   These are informational pointers only and are **not** legal advice. Citations
   are abbreviated and must be verified against the current text of the statute /
   the reported judgment before being relied upon. Always consult a qualified
   Indian advocate for a live matter.

   Every entry below is a *curated pointer*: it has not been independently
   verified against the primary text, and that honest state is exposed
   machine-readably via ``CaseLawReference.verified_on`` / ``verify_note``.
"""
from __future__ import annotations

from typing import Dict, List

from app.models.schemas import CaseLawReference

# Honest default state of every curated entry below: no primary-source
# verification has been done. Kept as one constant so a future verification
# pass only overrides per-entry where it actually applies.
UNVERIFIED_NOTE = (
    "curated pointer — not independently verified against primary text; "
    "confirm before relying on it"
)


def _entry(citation: str, summary: str) -> dict:
    """Build one authority dict with the standard unverified-by-default metadata."""
    return {
        "citation": citation,
        "summary": summary,
        "verified_on": None,
        "verify_note": UNVERIFIED_NOTE,
    }


# rule_id -> ordered list of authorities most relevant to that finding.
CASE_LAW: Dict[str, List[dict]] = {
    "RISK_STAMP_001": [
        _entry(
            "Indian Stamp Act, 1899, ss. 33 & 35",
            (
                "An instrument that is unstamped or inadequately stamped is inadmissible "
                "in evidence and cannot be acted upon by a court until the deficit duty "
                "and penalty are paid."
            ),
        ),
        _entry(
            "Hindustan Steel Ltd. v. Dilip Construction Co., (1969) 1 SCC 597",
            (
                "Insufficient stamping is a curable defect, but the instrument remains "
                "inadmissible until the deficiency is made good."
            ),
        ),
    ],
    "RISK_ARB_001": [
        _entry(
            "Bharat Aluminium Co. v. Kaiser Aluminium Technical Services Inc., "
            "(2012) 9 SCC 552 (BALCO)",
            (
                "Part I of the Arbitration and Conciliation Act, 1996 is confined to "
                "arbitrations seated in India; Indian courts cannot grant interim measures "
                "in a purely foreign-seated arbitration."
            ),
        ),
        _entry(
            "BGS SGS Soma JV v. NHPC Ltd., (2020) 4 SCC 234",
            (
                "The 'seat' is the juridical seat that fixes curial law; a 'venue' is only "
                "a physical location unless the agreement indicates otherwise."
            ),
        ),
        _entry(
            "Arbitration and Conciliation Act, 1996, ss. 2(2) & 20",
            (
                "Place of arbitration determines the seat absent contrary indication; "
                "the seat in turn determines which courts have supervisory jurisdiction."
            ),
        ),
    ],
    "RISK_S124_001": [
        _entry(
            "Indian Contract Act, 1872, ss. 124–125",
            (
                "The statutory promise of indemnity covers losses caused to the promisee by "
                "the promisor's conduct or a third party; courts have historically read it "
                "narrowly unless the contract expressly covers direct losses."
            ),
        ),
        _entry(
            "Gajanan Moreshwar Parelkar v. Moreshwar Madan Mantri, AIR 1942 Bom 302",
            (
                "Sections 124–125 are not exhaustive; a wider contractual indemnity is "
                "enforceable if clearly and expressly worded."
            ),
        ),
    ],
    "RISK_TDS_001": [
        _entry(
            "Income Tax Act, 1961, ss. 194C / 194J, 201 & 40(a)(ia)",
            (
                "Failure to deduct tax at source exposes the payer to interest and penalty "
                "under s. 201 and disallowance of the underlying expense under s. 40(a)(ia)."
            ),
        ),
    ],
    "RISK_GOV_001": [
        _entry(
            "Indian Contract Act, 1872, s. 28",
            (
                "Caveat: this rule flags a foreign governing-law clause. Foreign "
                "governing-law clauses are generally enforceable in India unless they are "
                "against public policy; s. 28 (restraint of legal proceedings) is cited "
                "for the *related* forum-restraint concern — agreements that oust the "
                "jurisdiction of competent Indian courts, or that unduly restrict a "
                "party's right to enforce its rights, are void to that extent. Verify "
                "applicability to the specific clause before relying on this pointer."
            ),
        ),
    ],
    "RISK_LIABILITY_001": [
        _entry(
            "Central Inland Water Transport Corp. v. Brojo Nath Ganguly, (1986) 3 SCC 156",
            (
                "Courts may decline to enforce grossly unfair or unconscionable terms that "
                "result from unequal bargaining power."
            ),
        ),
        _entry(
            "ONGC Ltd. v. Saw Pipes Ltd., (2003) 5 SCC 705",
            (
                "For s. 74, a genuine pre-estimate of loss (a valid liquidated-damages cap) "
                "is enforceable; sums in the nature of a penalty are not."
            ),
        ),
    ],
    "RISK_TERM_001": [
        _entry(
            "Indian Contract Act, 1872, ss. 23 & 27 (plain-law note — no case citation)",
            (
                "Indian law generally upholds termination clauses as a matter of freedom "
                "of contract (s. 10), subject to the void-contract grounds: agreements "
                "opposed to public policy are void (s. 23) and agreements in restraint of "
                "legal proceedings are void to that extent (s. 27). A one-sided "
                "termination-for-convenience right is therefore reviewable, but the "
                "principal exposure is commercial (loss of the counterparty), not "
                "statutory. No specific authority has been curated for this rule yet; "
                "confirm with counsel for the specific clause."
            ),
        ),
    ],
    "RISK_RENEWAL_001": [
        _entry(
            "See counsel — no verified authority curated for this rule yet",
            (
                "Plain-law note: Indian law generally enforces automatic-renewal terms, "
                "including short notice windows, as a matter of freedom of contract; the "
                "principal exposure is commercial (locking in on a lapsed notice window), "
                "not statutory. No specific authority has been curated for this rule yet "
                "(no confident, verified citation exists in this codebase); confirm with "
                "counsel for the specific clause."
            ),
        ),
    ],
    "RISK_INDEMNITY_001": [
        _entry(
            "Gajanan Moreshwar Parelkar v. Moreshwar Madan Mantri, AIR 1942 Bom 302",
            (
                "A wide contractual indemnity ('any and all claims' style) is enforceable "
                "if clearly and expressly worded; the statutory ss. 124–125 are not "
                "exhaustive. The exposure flagged here is that such breadth runs to the "
                "indemnifier's own acts and third-party claims beyond its conduct."
            ),
        ),
    ],
    "RISK_LIABILITY_002": [
        _entry(
            "ONGC Ltd. v. Saw Pipes Ltd., (2003) 5 SCC 705",
            (
                "A genuine pre-estimate of loss is enforceable as liquidated damages under "
                "s. 74 ICA, while sums in the nature of a penalty are not. An "
                "indeterminate (uncapped) liability exposure defeats the pre-estimate "
                "test that s. 74 protection requires, which is why an explicit cap is the "
                "standard recommendation."
            ),
        ),
    ],
    "RISK_DATA_001": [
        _entry(
            "Digital Personal Data Protection Act, 2023, s. 8(6)",
            (
                "A data fiduciary must notify the Data Protection Board and affected data "
                "principals of a personal-data breach in the prescribed manner and time; "
                "non-compliance attracts penalties under s. 33."
            ),
        ),
    ],
    "RISK_NONCOMPETE_001": [
        _entry(
            "Indian Contract Act, 1872, s. 27",
            (
                "Every agreement in restraint of a lawful trade, business, "
                "profession or vocation is void. The section is ordinarily "
                "read to void a POST-employment restraint on trade; a restraint "
                "during the term of employment, and a non-solicit, fall outside "
                "it. Statute-only pointer — no case citation is curated for "
                "this rule, so confirm the current position (including the "
                "treatment of partial and client-specific restraints) with "
                "Indian counsel before relying on it."
            ),
        ),
    ],
    "RISK_DISPUTE_001": [
        _entry(
            "Plain-law note (statute pointers) — no case citation curated",
            (
                "What is verified by this pointer: the existence of the two "
                "statutory defaults an Indian contract falls back to when it is "
                "silent on dispute resolution — arbitration under the "
                "Arbitration and Conciliation Act, 1996 (Part I applies to "
                "arbitrations seated in India), and the civil jurisdiction of "
                "the courts under the Code of Civil Procedure, 1908 (including "
                "the territorial limits in ss. 5-6 that determine which court "
                "can entertain a suit). What is NOT verified: no specific case "
                "has been curated for this rule, and whether a given silence "
                "creates a practical gap is fact-specific (the default forum "
                "is a valid, enforceable fallback, not a defect in law). "
                "Confirm applicability to the specific contract with counsel."
            ),
        ),
    ],
    "RISK_DATA_MISSING": [
        _entry(
            "Digital Personal Data Protection Act, 2023, s. 8(6)",
            (
                "Processing personal data requires a lawful basis, purpose limitation and "
                "breach-notification duties (s. 8, incl. the s. 8(6) notification duty); "
                "non-compliance attracts penalties under s. 33. A contract handling "
                "personal data should allocate these obligations expressly."
            ),
        ),
    ],
}


def lookup_case_law(rule_id: str) -> List[CaseLawReference]:
    """Return the case-law pointers for a rule id (empty list if none)."""
    return [CaseLawReference(**ref) for ref in CASE_LAW.get(rule_id, [])]


def has_case_law(rule_id: str) -> bool:
    return rule_id in CASE_LAW
