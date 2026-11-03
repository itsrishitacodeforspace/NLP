"""Family-disjoint held-out evaluation of the clause classifier.

Evaluates the rule-only AND hybrid classifier (top-1 and top-3) on ONLY the
CUAD test documents whose template family (normalised title + 8-gram shingle
near-duplicate proxy) has NO train presence — the closest thing to a
legitimate generalization estimate this project can produce.

Gold = CUAD's own annotations: each example is a snippet from an answer span
of its QA pair, labelled with the category mapped through
``nlp/taxonomy.py`` (the category set differs from the internal 26-label
taxonomy).

HONESTY BANNER (kept verbatim in the output):
  CUAD test split, family-disjoint by title+shingle proxy; US contracts;
  category set differs from the internal 26-label taxonomy (mapped via
  nlp/taxonomy.py); results indicate in-dataset generalization within CUAD
  only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from nlp.clause_classification.classifier import classify_clause
from nlp.datasets import cuad
from nlp.evaluation.classifier_metrics import (
    abstention_distribution,
    compute_label_metrics,
    rule_fallback_stats,
)
from nlp.evaluation.family_split import (
    disjoint_test_keys,
    leakage_report_cached,
)

BANNER = (
    "CUAD test split, family-disjoint by title+shingle proxy; US contracts; "
    "category set differs from the internal 26-label taxonomy (mapped via "
    "nlp/taxonomy.py); results indicate in-dataset generalization within "
    "CUAD only."
)

DEFAULT_TRAIN = "data/datasets/cuad/train_separate_questions.json"
DEFAULT_TEST = "data/datasets/cuad/test.json"
DEFAULT_OUT_JSON = "reports/evaluations/heldout_family_disjoint_20261103.json"
DEFAULT_OUT_MD = "reports/evaluations/heldout_family_disjoint_20261103.md"
DEFAULT_THRESHOLD = 0.5


def accuracy(rows: List[Dict], k: int) -> float:
    hits = sum(1 for r in rows if r["gold"] in (r["preds"] or [])[:k])
    return round(hits / len(rows), 4) if rows else 0.0


def _collect_disjoint_examples(test_path: Path, disjoint_keys: set, limit: Optional[int]) -> List[Dict]:
    """Examples from test docs whose family has no train presence."""
    rows: List[Dict] = []
    for ex in cuad.iter_examples(test_path):
        if ex.metadata.get("title") not in disjoint_keys:
            continue
        if limit and len(rows) >= limit:
            break
        rows.append(
            {
                "example_id": ex.example_id,
                "title": ex.metadata.get("title"),
                "text": ex.text,
                "gold": ex.category,
                "cuad_label": ex.metadata.get("cuad_label"),
            }
        )
    return rows


def build_report(
    train_path: Path,
    test_path: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    evaluate: bool = True,
) -> Dict:
    started = time.monotonic()
    leak = leakage_report_cached(train_path, test_path, threshold=threshold)
    disjoint_keys = disjoint_test_keys(leak)

    if not evaluate:
        # --leakage-only mode: pure family-leakage artifact (no classification).
        report: Dict = {
            "report": "cuad_family_leakage",
            "date": "20261103",
            "description": (
                "CUAD template-family leakage between train and test splits. "
                "Family proxy: exact normalised-title equality OR >= threshold "
                "overlap of 8-character shingles (fraction of the smaller set). "
                "This measures template-family separation, NOT legal independence."
            ),
            "inputs": {
                "train": str(train_path),
                "test": str(test_path),
                "shingle_threshold": threshold,
            },
            "family_leakage": leak,
            "non_claims": [
                "Proxy-based estimate: the title is a proxy for SEC-filing "
                "identity (not verified against EDGAR); shingle similarity is "
                "not legal independence.",
                "The threshold is a hyperparameter: lower = more conservative "
                "(more docs grouped as same family).",
            ],
        }
        return report

    rows = _collect_disjoint_examples(test_path, disjoint_keys, None)

    per_mode: Dict[str, List[Dict]] = {"rule_only": [], "hybrid": []}
    for row in rows:
        gold = row["gold"]
        rule = classify_clause(row["text"], rule_based_only=True)
        hybrid = classify_clause(row["text"])
        per_mode["rule_only"].append({"gold": gold, "preds": rule.labels})
        per_mode["hybrid"].append({"gold": gold, "preds": hybrid.labels})

    metrics: Dict[str, Dict] = {}
    for mode, mode_rows in per_mode.items():
        bundle: Dict = {}
        for k in (1, 3):
            bundle[f"top{k}"] = compute_label_metrics(mode_rows, k=k)
        bundle["accuracy_top1"] = accuracy(mode_rows, 1)
        bundle["accuracy_top3"] = accuracy(mode_rows, 3)
        bundle["abstention"] = abstention_distribution(mode_rows)
        bundle["rule_misc_fallback"] = rule_fallback_stats(mode_rows)
        metrics[mode] = bundle

    gold_counts = Counter(r["gold"] for r in rows)
    report: Dict = {
        "report": "heldout_family_disjoint",
        "date": "20261103",
        "banner": BANNER,
        "inputs": {
            "train": str(train_path),
            "test": str(test_path),
            "shingle_threshold": threshold,
            "leakage_method": (
                "title equality (normalised) + 8-gram character-shingle near-duplicate "
                "proxy (overlap fraction of the smaller set >= threshold) between the "
                "whole documents of the two splits"
            ),
        },
        "family_leakage": leak,
        "evaluated_examples": len(rows),
        "gold_category_counts": dict(sorted(gold_counts.items(), key=lambda kv: -kv[1])),
        "metrics": metrics,
        "non_claims": [
            BANNER,
            "Family separation is a template proxy (title + 8-gram shingle), NOT legal "
            "independence — disjoint families can still share boilerplate/jurisdiction.",
            "This is an in-dataset generalization estimate within CUAD only; it does not "
            "support any claim about Indian-law contracts or out-of-CUAD generalization.",
            "Gold labels come from CUAD's QA annotations (mapped via nlp/taxonomy.py), not "
            "independent human adjudication of clause category.",
        ],
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    return report


def _md_table(per_class: Dict[str, Dict]) -> str:
    lines = ["| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for c in sorted(per_class, key=lambda c: -per_class[c]["support"]):
        v = per_class[c]
        lines.append(f"| {c} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | {v['support']} |")
    return "\n".join(lines)


def render_md(report: Dict) -> str:
    m = report["metrics"]
    leak = report["family_leakage"]
    L: List[str] = []
    L.append("# Family-Disjoint Held-Out Evaluation — " + report["date"])
    L.append("")
    L.append(f"> **{BANNER}**")
    L.append("")
    L.append("## Family leakage (the realistic held-out set)")
    L.append("")
    c = leak["counts"]
    L.append(f"- Train docs: {leak['train_docs']} across {leak['train_families']} families; "
             f"test docs: {leak['test_docs']} across {leak['test_families']} families "
             f"(shingle threshold {leak['threshold']}).")
    L.append(f"- Test docs whose family ALSO appears in train: **{c['test_in_train_family']}** (excluded from evaluation): "
             + ", ".join(leak["test_docs_in_train_family"]) + ".")
    L.append(f"- **Test docs family-disjoint from train: {c['test_family_disjoint']}** (evaluated set).")
    L.append(f"- Reverse: train docs whose family appears in test: {len(leak['train_docs_in_test_family'])}.")
    L.append(f"- Method: {report['inputs']['leakage_method']}. This measures template-family "
             "separation, NOT legal independence.")
    L.append("")
    L.append(f"Evaluated {report['evaluated_examples']} CUAD-annotated examples from those "
             f"{c['test_family_disjoint']} disjoint documents.")
    L.append("")
    L.append("## Summary (top-1 / top-3)")
    L.append("")
    L.append("| Mode | Acc@1 | Acc@3 | Macro-F1@1 | Weighted-F1@1 | Macro-F1@3 | Weighted-F1@3 |")
    L.append("|---|---|---|---|---|---|---|")
    for mode, label in (("rule_only", "rule-only"), ("hybrid", "hybrid")):
        mm = m[mode]
        L.append(f"| {label} | {mm['accuracy_top1']:.4f} | {mm['accuracy_top3']:.4f} | "
                 f"{mm['top1']['macro_f1']:.4f} | {mm['top1']['weighted_f1']:.4f} | "
                 f"{mm['top3']['macro_f1']:.4f} | {mm['top3']['weighted_f1']:.4f} |")
    L.append("")
    for mode, label in (("rule_only", "Rule-only"), ("hybrid", "Hybrid")):
        mm = m[mode]
        L.append(f"## {label}")
        L.append("")
        L.append(f"Abstention: {mm['abstention']['abstained']}/{mm['abstention']['total_rows']} "
                 f"({mm['abstention']['abstention_rate']:.1%}); "
                 f"Miscellaneous fallback: {mm['rule_misc_fallback']['misc_fallback']}.")
        L.append("")
        L.append("### Top-1")
        L.append("")
        L.append(_md_table(mm["top1"]["per_class"]))
        L.append("")
        L.append("### Top-3")
        L.append("")
        L.append(_md_table(mm["top3"]["per_class"]))
        L.append("")
    L.append("## Gold category distribution (disjoint set)")
    L.append("")
    L.append("| Category | Count |")
    L.append("|---|---|")
    for cat, n in report["gold_category_counts"].items():
        L.append(f"| {cat} | {n} |")
    L.append("")
    L.append("## Non-claims")
    L.append("")
    for claim in report["non_claims"]:
        L.append(f"> {claim}")
    L.append("")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description="Family-disjoint held-out clause-classifier evaluation")
    parser.add_argument("--train", default=DEFAULT_TRAIN)
    parser.add_argument("--test", default=DEFAULT_TEST)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--leakage-only", action="store_true",
        help="write only the family-leakage artifact (no classification run)",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    report = build_report(Path(args.train), Path(args.test), threshold=args.threshold,
                          evaluate=not args.leakage_only)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.leakage_only:
        print(f"wrote {out_json}")
        return 0
    Path(args.out_md).write_text(render_md(report), encoding="utf-8")
    c = report["family_leakage"]["counts"]
    print(f"family-disjoint test docs: {c['test_family_disjoint']}/{c['test_total']}; "
          f"evaluated examples: {report['evaluated_examples']}")
    for mode in ("rule_only", "hybrid"):
        mm = report["metrics"][mode]
        print(f"{mode}: acc@1={mm['accuracy_top1']} acc@3={mm['accuracy_top3']} "
              f"macro@1={mm['top1']['macro_f1']} macro@3={mm['top3']['macro_f1']}")
    print(f"wrote {out_json} and {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
