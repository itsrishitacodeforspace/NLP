"""Case-law / statutory pointers for the risk playbook.

Every risk rule can be enriched with the authority that explains *why* it
matters. This is a curated, fully offline mapping — no network calls — so the
feature works with zero infrastructure.

.. warning::
   These are informational pointers only and are **not** legal advice. Citations
   are abreviated and must be verified against the current text of the statute /
   the reported judgment before being relied upon. Always consult a qualified
   Indian advocate for a live matter.
"""
from __future__ import annotations

from typing import Dict, List

from app.models.schemas import CaseLawReference

# rule_id -> ordered list of authorities most relevant to that finding.
CASE_LAW: Dict[str, List[dict]] = {
    "RISK_STAMP_001": [
        {
            "citation": "Indian Stamp Act, 1899, ss. 33 & 35",
            "summary": (
                "An instrument that is unstamped or inadequately stamped is inadmissible "
                "in evidence and cannot be acted upon by a court until the deficit duty "
                "and penalty are paid."
            ),
        },
        {
            "citation": "Hindustan Steel Ltd. v. Dilip Construction Co., (1969) 1 SCC 597",
            "summary": (
                "Insufficient stamping is a curable defect, but the instrument remains "
                "inadmissible until the deficiency is made good."
            ),
        },
    ],
    "RISK_ARB_001": [
        {
            "citation": "Bharat Aluminium Co. v. Kaiser Aluminium Technical Services Inc., "
            "(2012) 9 SCC 552 (BALCO)",
            "summary": (
                "Part I of the Arbitration and Conciliation Act, 1996 is confined to "
                "arbitrations seated in India; Indian courts cannot grant interim measures "
                "in a purely foreign-seated arbitration."
            ),
        },
        {
            "citation": "BGS SGS Soma JV v. NHPC Ltd., (2020) 4 SCC 234",
            "summary": (
                "The 'seat' is the juridical seat that fixes curial law; a 'venue' is only "
                "a physical location unless the agreement indicates otherwise."
            ),
        },
        {
            "citation": "Arbitration and Conciliation Act, 1996, ss. 2(2) & 20",
            "summary": (
                "Place of arbitration determines the seat absent contrary indication; "
                "the seat in turn determines which courts have supervisory jurisdiction."
            ),
        },
    ],
    "RISK_S124_001": [
        {
            "citation": "Indian Contract Act, 1872, ss. 124–125",
            "summary": (
                "The statutory promise of indemnity covers losses caused to the promisee by "
                "the promisor's conduct or a third party; courts have historically read it "
                "narrowly unless the contract expressly covers direct losses."
            ),
        },
        {
            "citation": "Gajanan Moreshwar Parelkar v. Moreshwar Madan Mantri, AIR 1942 Bom 302",
            "summary": (
                "Sections 124–125 are not exhaustive; a wider contractual indemnity is "
                "enforceable if clearly and expressly worded."
            ),
        },
    ],
    "RISK_TDS_001": [
        {
            "citation": "Income Tax Act, 1961, ss. 194C / 194J, 201 & 40(a)(ia)",
            "summary": (
                "Failure to deduct tax at source exposes the payer to interest and penalty "
                "under s. 201 and disallowance of the underlying expense under s. 40(a)(ia)."
            ),
        },
    ],
    "RISK_GOV_001": [
        {
            "citation": "Indian Contract Act, 1872, s. 28",
            "summary": (
                "Agreements that oust the jurisdiction of competent Indian courts, or that "
                "restrict a party's right to enforce its rights, are void to that extent."
            ),
        },
    ],
    "RISK_LIABILITY_001": [
        {
            "citation": "Central Inland Water Transport Corp. v. Brojo Nath Ganguly, (1986) 3 SCC 156",
            "summary": (
                "Courts may decline to enforce grossly unfair or unconscionable terms that "
                "result from unequal bargaining power."
            ),
        },
        {
            "citation": "ONGC Ltd. v. Saw Pipes Ltd., (2003) 5 SCC 705",
            "summary": (
                "For s. 74, a genuine pre-estimate of loss (a valid liquidated-damages cap) "
                "is enforceable; sums in the nature of a penalty are not."
            ),
        },
    ],
    "RISK_DATA_001": [
        {
            "citation": "Digital Personal Data Protection Act, 2023, ss. 8 & 33",
            "summary": (
                "A data fiduciary must notify the Data Protection Board and affected data "
                "principals of a personal-data breach in the prescribed manner and time."
            ),
        },
    ],
    "RISK_DATA_MISSING": [
        {
            "citation": "Digital Personal Data Protection Act, 2023, ss. 8 & 33",
            "summary": (
                "Processing personal data requires a lawful basis, purpose limitation and "
                "breach-notification duties; a contract handling personal data should "
                "allocate these obligations expressly."
            ),
        },
    ],
}


def lookup_case_law(rule_id: str) -> List[CaseLawReference]:
    """Return the case-law pointers for a rule id (empty list if none)."""
    return [CaseLawReference(**ref) for ref in CASE_LAW.get(rule_id, [])]


def has_case_law(rule_id: str) -> bool:
    return rule_id in CASE_LAW
