"""Run the synthetic evaluation corpus and write a reproducible results report."""
from __future__ import annotations

import json
from pathlib import Path

from nlp.evaluation import run_all

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "evaluations"
MD_PATH = OUT_DIR / "synthetic_eval_results.md"
JSON_PATH = OUT_DIR / "synthetic_eval_results.json"


def _status_word(cr) -> str:
    if cr.status == "pass":
        return "PASS"
    return "KNOWN LIMITATION" if cr.is_known_limitation else "REGRESSION"


def main() -> int:
    report = run_all()

    passed = sum(1 for cr in report.case_results if cr.status == "pass")
    known = sorted(report.known_limitation_ids & report.failing_case_ids)
    regressions = sorted(report.unexpected_failures)
    resolved = sorted(report.resolved_limitations)

    lines: list[str] = []
    lines.append("# Synthetic Evaluation Results\n")
    lines.append(
        "Deterministic run of the synthetic corpus in `nlp/evaluation/cases.py` through "
        "the full `analyse_bytes` pipeline. All contracts are synthetic; expectations "
        "encode desired behaviour. This is a software-behaviour check, **not** a "
        "measure of legal accuracy or real-world reliability.\n"
    )
    lines.append("## Summary\n")
    lines.append(f"- Cases: {len(report.case_results)}")
    lines.append(f"- Passing: {passed}")
    lines.append(f"- Known limitations (declared, still failing): {len(known)}")
    lines.append(f"- Unexpected regressions: {len(regressions)}")
    lines.append(f"- Resolved limitations (declared but now passing): {len(resolved)}")
    lines.append("")
    if regressions:
        lines.append(f"> REGRESSIONS: {', '.join(regressions)}")
        lines.append("")
    if resolved:
        lines.append(
            f"> RESOLVED (remove the known_limitation note): {', '.join(resolved)}"
        )
        lines.append("")

    lines.append("## Evidence-integrity invariants\n")
    for inv in report.invariants:
        mark = "OK" if inv.ok else "VIOLATED"
        lines.append(f"- [{mark}] {inv.name}")
        for v in inv.violations[:10]:
            lines.append(f"    - {v}")
    lines.append("")

    lines.append("## Cases\n")
    for cr in report.case_results:
        lines.append(f"### {cr.case.case_id} — {_status_word(cr)}")
        lines.append(f"- Category: `{cr.case.category}`")
        lines.append(f"- Expected: {cr.case.description}")
        lines.append(f"- Observed rule findings: {', '.join(cr.observed_rule_ids) or '(none)'}")
        if cr.failures:
            lines.append("- Deviations from expected:")
            for f in cr.failures:
                lines.append(f"    - {f}")
        if cr.is_known_limitation:
            lines.append(f"- Known limitation: {cr.case.known_limitation}")
        lines.append("")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "cases": [
            {
                "case_id": cr.case.case_id,
                "category": cr.case.category,
                "status": cr.status,
                "known_limitation": cr.case.known_limitation,
                "observed_rule_ids": cr.observed_rule_ids,
                "failures": cr.failures,
            }
            for cr in report.case_results
        ],
        "invariants": [
            {"name": inv.name, "ok": inv.ok, "violations": inv.violations}
            for inv in report.invariants
        ],
        "summary": {
            "cases": len(report.case_results),
            "passing": passed,
            "known_limitations": known,
            "regressions": regressions,
            "resolved": resolved,
        },
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"cases={len(report.case_results)} passing={passed} "
          f"known_limitations={len(known)} regressions={len(regressions)} resolved={len(resolved)}")
    print(f"wrote {MD_PATH.relative_to(ROOT)}")
    print(f"wrote {JSON_PATH.relative_to(ROOT)}")
    for inv in report.invariants:
        print(f"invariant {inv.name}: {'OK' if inv.ok else 'VIOLATED'}")

    # Non-zero exit on an *unexpected* regression or a violated invariant, so the
    # script is fail-closed when run in CI. Declared known limitations do not fail.
    if regressions or any(not inv.ok for inv in report.invariants):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
