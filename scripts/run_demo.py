"""Quick demo: analyse the bundled sample MSA and print a summary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.models.schemas import ContractType, PartySide
from app.services.analyzer import analyse_path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sample = ROOT / "data" / "raw" / "sample_msa.txt"
    if not sample.exists():
        print(f"Sample not found: {sample}", file=sys.stderr)
        return 1

    result = analyse_path(
        sample,
        contract_id="demo_msa",
        contract_type=ContractType.MSA,
        user_role=PartySide.PROVIDER,
        jurisdiction="India",
    )

    summary = {
        "title": result.contract.title,
        "parties": result.contract.parties,
        "effective_date": result.contract.effective_date,
        "governing_law": result.contract.governing_law,
        "arbitration_seat": result.contract.arbitration_seat,
        "stamp_duty_mentioned": result.contract.stamp_duty_mentioned,
        "tds_mentioned": result.contract.tds_mentioned,
        "gstin_mentioned": result.contract.gstin_mentioned,
        "risk_score": result.contract.overall_risk_score,
        "risk_level": result.contract.overall_risk_level.value,
        "clauses": result.contract.clause_count,
        "obligations": result.contract.obligation_count,
        "top_risks": [
            {
                "severity": r.severity.value,
                "name": r.name,
                "explanation": r.explanation,
            }
            for r in result.risks[:5]
        ],
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
