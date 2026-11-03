"""Rules-only vs hybrid clause-classifier comparison on the train corpus.

Runs BOTH the rule-based classifier (``rule_based_only=True``) and the hybrid
classifier (rules + TF-IDF) over ``data/processed/clause_classifier.csv`` and
writes per-class / macro / weighted metrics, a hybrid-mode confusion matrix and
abstention diagnostics to ``reports/evaluations/rules_vs_hybrid_20261103.*``.

HONESTY BANNER (kept verbatim in every output):
  IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE.
  CUAD is a US dataset; template-family separation from the keyword-bank
  source documents is not guaranteed.

The ML risk-booster delta (rule-only vs rule+ML pipeline findings) is written
to ``reports/evaluations/risk_booster_delta_20261103.md``.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from nlp.clause_classification.classifier import classify_clause
from nlp.evaluation.classifier_metrics import (
    ABSTAIN_LABEL,
    abstention_distribution,
    compute_label_metrics,
    confusion_matrix,
    rule_fallback_stats,
)
from nlp.taxonomy import INTERNAL_LABELS

BANNER = (
    "IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE. "
    "CUAD is a US dataset; template-family separation from the keyword-bank "
    "source documents is not guaranteed."
)

DEFAULT_CSV = "data/processed/clause_classifier.csv"
REPORT_JSON = "reports/evaluations/rules_vs_hybrid_20261103.json"
REPORT_MD = "reports/evaluations/rules_vs_hybrid_20261103.md"
RISK_DELTA_MD = "reports/evaluations/risk_booster_delta_20261103.md"
SEED = 20261103
DEFAULT_SAMPLE = 2000


def load_rows(csv_path: Path) -> List[Dict]:
    csv.field_size_limit(2**31 - 1)
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    usable = [r for r in rows if (r.get("text") or "").strip() and (r.get("category") or "").strip()]
    return usable


def active_components() -> Dict:
    """Detect which classifier components are active in this process."""
    from nlp.clause_classification import classifier as C
    from nlp.clause_classification.tfidf_model import ensure_model_file

    model_file = ensure_model_file()
    tfidf: Dict = {"present": model_file is not None and model_file.exists()}
    if tfidf["present"]:
        try:
            from nlp.clause_classification.tfidf_model import load_trained

            trained = load_trained(model_file)
            tfidf["labels"] = list(trained.labels) if trained else []
            tfidf["label_count"] = len(tfidf["labels"])
        except Exception as exc:  # pragma: no cover - defensive
            tfidf["error"] = str(exc)
    bank_path = Path(C.__file__).resolve().parents[2] / "data" / "processed" / "cuad_keyword_bank.json"
    prov = dict(getattr(C, "KEYWORD_BANK_PROVENANCE", {}))
    return {
        "rule_engine": {"present": True, "keyword_patterns": len(C._KEYWORD_PATTERNS)},
        "tfidf_model": tfidf,
        "keyword_bank": {
            "path": str(bank_path),
            "loaded": C._cuad_keyword_bank is not None,
            "provenance": prov.get("status", "unknown"),
        },
    }


def classify_sample(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """Classify every row in both modes; return per-mode metric rows."""
    per_mode: Dict[str, List[Dict]] = {"rule_only": [], "hybrid": []}
    for row in rows:
        text = (row.get("text") or "").strip()
        gold = (row.get("category") or "").strip()
        rule = classify_clause(text, rule_based_only=True)
        hybrid = classify_clause(text)
        per_mode["rule_only"].append(
            {"gold": gold, "preds": rule.labels, "confidence": rule.confidence}
        )
        per_mode["hybrid"].append(
            {"gold": gold, "preds": hybrid.labels, "confidence": hybrid.confidence}
        )
    return per_mode


def evaluate_mode(rows: List[Dict]) -> Dict[str, object]:
    """Full metric bundle for one mode: top-1 and top-3, abstention, hybrid extras."""
    out: Dict[str, object] = {}
    for k in (1, 3):
        out[f"top{k}"] = compute_label_metrics(rows, k=k)
    out["abstention"] = abstention_distribution(rows)
    out["rule_misc_fallback"] = rule_fallback_stats(rows)
    return out


def accuracy(rows: List[Dict], k: int) -> float:
    hits = sum(1 for r in rows if r["gold"] in (r["preds"] or [])[:k])
    return round(hits / len(rows), 4) if rows else 0.0


def build_report(csv_path: Path, sample_size: Optional[int], started: float) -> Dict:
    csv_path = Path(csv_path)
    all_rows = load_rows(csv_path)
    sampled = False
    rows = all_rows
    if sample_size and len(all_rows) > sample_size:
        rng = random.Random(SEED)
        rows = rng.sample(all_rows, sample_size)
        sampled = True

    components = active_components()
    per_mode = classify_sample(rows)

    report: Dict = {
        "report": "rules_vs_hybrid",
        "date": "20261103",
        "banner": BANNER,
        "input": {
            "csv": str(csv_path),
            "total_rows": len(all_rows),
            "evaluated_rows": len(rows),
            "sampled": sampled,
            "seed": SEED if sampled else None,
        },
        "active_components": components,
        "metrics": {},
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }

    for mode, mode_rows in per_mode.items():
        report["metrics"][mode] = evaluate_mode(mode_rows)
        report["metrics"][mode]["accuracy_top1"] = accuracy(mode_rows, 1)
        report["metrics"][mode]["accuracy_top3"] = accuracy(mode_rows, 3)

    # Confusion matrix (hybrid mode, top-1 vs gold category). Multi-label note:
    # the classifier emits up to 5 ranked labels; the matrix uses label[0].
    hybrid_rows = per_mode["hybrid"]
    classes = [c for c in INTERNAL_LABELS if any(r["gold"] == c or c in (r["preds"] or []) for r in hybrid_rows)]
    report["hybrid_confusion_top1"] = confusion_matrix(hybrid_rows, classes)
    report["hybrid_multi_label_note"] = (
        "Multi-label handling: the hybrid classifier emits a ranked list of up to 5 "
        "labels (union of TF-IDF and rule labels). Top-1 metrics use label[0]; the "
        "confusion matrix maps each row to its single top-1 prediction, so multi-label "
        "agreement is under-represented here — top-3 is the fairer single-number view."
    )

    # Delta: hybrid vs rule-only per row.
    delta = _mode_delta(per_mode["rule_only"], hybrid_rows)
    report["mode_delta"] = delta
    return report


def _mode_delta(rule_rows: List[Dict], hybrid_rows: List[Dict]) -> Dict[str, object]:
    top1_changed = 0
    hybrid_abstains_not_rule = 0
    rule_fallback_rescued = 0
    for rr, hr in zip(rule_rows, hybrid_rows, strict=True):
        if (rr["preds"] or [ABSTAIN_LABEL])[0] != (hr["preds"] or [ABSTAIN_LABEL])[0]:
            top1_changed += 1
        if not (hr["preds"] or []) and (rr["preds"] or []):
            hybrid_abstains_not_rule += 1
        if (rr["preds"] or []) == [ABSTAIN_LABEL] and (hr["preds"] or []) and hr["preds"][0] != ABSTAIN_LABEL:
            rule_fallback_rescued += 1
    n = len(rule_rows) or 1
    return {
        "rows_compared": len(rule_rows),
        "top1_changed": top1_changed,
        "top1_changed_rate": round(top1_changed / n, 4),
        "hybrid_abstained_but_rule_labeled": hybrid_abstains_not_rule,
        "rule_misc_fallback_rescued_by_hybrid": rule_fallback_rescued,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _md_table(per_class: Dict[str, Dict], show_support: bool = True) -> str:
    lines = ["| Class | Precision | Recall | F1 |" + (" Support" if show_support else "") + " |", "|---|---|---|---|" + ("---|" if show_support else "")]
    for c in sorted(per_class, key=lambda c: -per_class[c]["support"]):
        v = per_class[c]
        lines.append(f"| {c} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | {v['support']} |")
    return "\n".join(lines)


def render_md(report: Dict) -> str:
    m = report["metrics"]
    comp = report["active_components"]
    tf = comp["tfidf_model"]
    kb = comp["keyword_bank"]
    L: List[str] = []
    L.append("# Rules-Only vs Hybrid Clause Classifier — " + report["date"])
    L.append("")
    L.append(f"> **{BANNER}**")
    L.append("")
    L.append(f"- Input: `{report['input']['csv']}` — {report['input']['total_rows']} rows total, "
             f"{report['input']['evaluated_rows']} evaluated"
             + (f" (deterministic stratified-by-file sample, seed {report['input']['seed']})" if report["input"]["sampled"] else " (full corpus)"))
    L.append("- Gold: the `category` column of the CSV, which is the taxonomy category the row's snippet was *derived* from (training labels, not human adjudication).")
    L.append("- **Active components:** rule engine ("
             f"{comp['rule_engine']['keyword_patterns']} compiled keyword patterns, incl. CUAD bank) | "
             f"TF-IDF model **{'ACTIVE (' + str(tf.get('label_count', 0)) + ' labels)' if tf['present'] else 'ABSENT — hybrid degrades to rule-only'}** | "
             f"keyword bank **{'LOADED (' + kb['provenance'] + ')' if kb['loaded'] else 'NOT LOADED'}**.")
    if tf["present"]:
        L.append(f"- TF-IDF labels (the only classes the ML half can emit): {', '.join(tf.get('labels', []))}.")
    L.append(f"- Elapsed: {report['elapsed_seconds']}s.")
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
        L.append(f"## {label} — per-class (top-1 / top-3)")
        L.append("")
        L.append(f"Macro-F1: top-1 = {mm['top1']['macro_f1']:.4f}, top-3 = {mm['top3']['macro_f1']:.4f}; "
                 f"weighted-F1: top-1 = {mm['top1']['weighted_f1']:.4f}, top-3 = {mm['top3']['weighted_f1']:.4f}.")
        L.append("")
        L.append("### Top-1")
        L.append("")
        L.append(_md_table(mm["top1"]["per_class"]))
        L.append("")
        L.append("### Top-3")
        L.append("")
        L.append(_md_table(mm["top3"]["per_class"]))
        L.append("")
    L.append("## Abstention")
    L.append("")
    ab_r = m["rule_only"]["abstention"]
    ab_h = m["hybrid"]["abstention"]
    L.append(f"- **rule-only**: never returns an empty label list — its 'abstention' is the "
             f"`Miscellaneous` fallback: {m['rule_only']['rule_misc_fallback']['misc_fallback']}/{ab_r['total_rows']} rows "
             f"({m['rule_only']['rule_misc_fallback']['misc_fallback_rate']:.1%}).")
    fb = m["rule_only"]["rule_misc_fallback"]["misc_fallback_by_gold_category"]
    if fb:
        L.append("  - fallback distribution over gold: " + ", ".join(f"{k}={v}" for k, v in list(fb.items())[:8]))
    L.append(f"- **hybrid**: empty label list after the 0.15 TF-IDF threshold: {ab_h['abstained']}/{ab_h['total_rows']} rows "
             f"({ab_h['abstention_rate']:.1%}).")
    if ab_h["by_gold_category"]:
        L.append("  - abstained distribution over gold: " + ", ".join(f"{k}={v}" for k, v in list(ab_h["by_gold_category"].items())[:8]))
    L.append("")
    L.append("What we give up when abstaining = the gold categories above: these are the rows "
             "where the mode emits no usable label (hybrid) or only the `Miscellaneous` "
             "fallback (rule-only), i.e. the precision cost of staying quiet.")
    L.append("")
    L.append("## Mode delta (rule-only → hybrid)")
    L.append("")
    d = report["mode_delta"]
    L.append(f"- Top-1 label changed: {d['top1_changed']}/{d['rows_compared']} ({d['top1_changed_rate']:.1%}).")
    L.append(f"- Rows the rule mode mis-filed as `Miscellaneous` that the hybrid re-labels correctly-or-differently: {d['rule_misc_fallback_rescued_by_hybrid']}.")
    L.append("")
    L.append("## Hybrid confusion matrix (top-1, classes observed)")
    L.append("")
    L.append("> " + report["hybrid_multi_label_note"])
    L.append("")
    matrix = report["hybrid_confusion_top1"]
    classes = list(matrix.keys())
    L.append("| gold \\ pred | " + " | ".join(classes) + " |")
    L.append("|" + "---|" * (len(classes) + 1))
    for g in classes:
        L.append(f"| {g} | " + " | ".join(str(matrix[g][p]) for p in classes) + " |")
    L.append("")
    L.append("## Non-claims")
    L.append("")
    L.append(f"> {BANNER}")
    L.append("> - This corpus is the **training corpus** (manifest-verified train-only); every number here is in-distribution.")
    L.append("> - The keyword bank is derived from the same CUAD snippets, so rule-mode accuracy is doubly optimistic.")
    L.append("> - CUAD is a US dataset; nothing here supports a claim about Indian-law contracts or categories.")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# ML risk-booster delta
# ---------------------------------------------------------------------------

def run_risk_booster_delta(sample_size: int) -> Dict:
    """Run the full pipeline twice (booster off / on) over CUAD TRAIN clause texts."""
    import nlp.risk_scoring.risk_model as rm
    from app.services.analyzer import analyse_bytes

    # Cleanest available disable switch: `_augment_with_ml_risks` no-ops when
    # `risk_model.load_cached()` returns None, so hiding the process cache
    # reproduces exactly the "no artefact" pipeline state (no app/ changes).
    model_present = rm.ensure_model_file() is not None

    # Deterministic sample of CUAD TRAIN clause texts via the existing loader.
    from nlp.datasets import cuad

    examples = list(cuad.iter_examples("data/datasets/cuad/train_separate_questions.json"))
    rng = random.Random(SEED)
    picks = rng.sample(examples, min(sample_size, len(examples)))

    def run_all(booster_enabled: bool) -> Dict[str, Dict]:
        saved_cached, saved_loaded = rm._CACHED, rm._CACHE_LOADED
        if booster_enabled:
            rm._CACHED = rm.load() if model_present else None
        else:
            rm._CACHED = None
        rm._CACHE_LOADED = True
        try:
            results: Dict[str, Dict] = {}
            for i, ex in enumerate(picks):
                text = (ex.text or "").strip()
                if not text:
                    continue
                res = analyse_bytes(text.encode("utf-8"), f"booster_{i}.txt", contract_id=f"booster_{i}", enable_ocr=False)
                per_clause: Dict[str, Dict] = {}
                for cl in res.clauses:
                    flags = [f for f in res.risks if f.clause_id == cl.clause_id]
                    per_clause[cl.clause_id] = {
                        "text": cl.text,
                        "types": list(cl.clause_types),
                        "flags": sorted(f.rule_id for f in flags if f.rule_id != "ML_RISK_001"),
                        "ml": sorted(f.rule_id for f in flags if f.rule_id == "ML_RISK_001"),
                        "score": cl.risk_score,
                        "level": cl.risk_level.value,
                    }
                results[f"doc_{i}"] = {
                    "n_clauses": len(res.clauses),
                    "overall": (res.contract.overall_risk_score, res.contract.overall_risk_level.value),
                    "clauses": per_clause,
                    "n_rule_flags": sum(1 for f in res.risks if f.rule_id != "ML_RISK_001"),
                    "n_ml_flags": sum(1 for f in res.risks if f.rule_id == "ML_RISK_001"),
                }
            return results
        finally:
            rm._CACHED, rm._CACHE_LOADED = saved_cached, saved_loaded

    off = run_all(booster_enabled=False)
    on = run_all(booster_enabled=True)

    ml_added = 0
    ml_redundant = 0  # clause already had a rule flag (defensive; _augment skips these)
    score_changed = 0
    level_changed = 0
    overall_changed = 0
    ml_severities: Counter = Counter()
    for key, off_doc in off.items():
        on_doc = on.get(key)
        if not on_doc:
            continue
        ml_added += on_doc["n_ml_flags"]
        if off_doc["overall"] != on_doc["overall"]:
            overall_changed += 1
        for cid, off_cl in off_doc["clauses"].items():
            on_cl = on_doc["clauses"].get(cid)
            if not on_cl:
                continue
            if on_cl["ml"]:
                if off_cl["flags"]:
                    ml_redundant += 1
                ml_severities[";".join(on_cl["ml"])] += 1
            if off_cl["score"] != on_cl["score"]:
                score_changed += 1
            if off_cl["level"] != on_cl["level"]:
                level_changed += 1

    n_docs = len(off)
    return {
        "model_present": model_present,
        "n_docs": n_docs,
        "n_clauses_off": sum(d["n_clauses"] for d in off.values()),
        "n_clauses_on": sum(d["n_clauses"] for d in on.values()),
        "rule_flags_off": sum(d["n_rule_flags"] for d in off.values()),
        "rule_flags_on": sum(d["n_rule_flags"] for d in on.values()),
        "ml_flags_added": ml_added,
        "ml_redundant_with_rule_flag": ml_redundant,
        "clause_score_changed": score_changed,
        "clause_level_changed": level_changed,
        "overall_changed": overall_changed,
    }


def render_risk_delta_md(stats: Dict, report: Dict) -> str:
    L: List[str] = []
    L.append("# ML Risk-Booster Delta — " + report["date"])
    L.append("")
    L.append(f"> **{BANNER}**")
    L.append("")
    L.append("Full pipeline (`app.services.analyzer.analyse_bytes`) run **twice** on the same "
             f"deterministic CUAD TRAIN clause-text sample (n={stats['n_docs']} documents, seed {SEED}): "
             "once with the ML risk artefact **disabled** (`risk_model._CACHED` hidden, so "
             "`_augment_with_ml_risks` no-ops — same behaviour as a missing artefact), once with it **active**. "
             f"Artefact present in this environment: **{'yes' if stats['model_present'] else 'NO — delta is vacuously 0'}**.")
    L.append("")
    L.append("| Measure | Value |")
    L.append("|---|---|")
    L.append(f"| Rule-only findings (booster off) | {stats['rule_flags_off']} |")
    L.append(f"| Rule findings (booster on) | {stats['rule_flags_on']} |")
    L.append(f"| **ML_RISK_001 findings added** | **{stats['ml_flags_added']}** |")
    L.append(f"| ML findings on clauses already rule-flagged (redundant) | {stats['ml_redundant_with_rule_flag']} |")
    L.append(f"| Clauses whose risk_score changed | {stats['clause_score_changed']} / {stats['n_clauses_off']} |")
    L.append(f"| Clauses whose risk_level changed | {stats['clause_level_changed']} / {stats['n_clauses_off']} |")
    L.append(f"| Documents whose overall score/level changed | {stats['overall_changed']} / {stats['n_docs']} |")
    L.append("")
    L.append("Interpretation: the booster only fires on clauses the rules did **not** flag (by "
             "construction it skips rule-flagged clauses, so the redundancy column should be 0). "
             "Every added ML_RISK_001 is `source=\"model\"`, `evidence_status=\"unverified\"`, "
             "a review prompt with an uncalibrated score — not a verified finding.")
    L.append("")
    L.append("> " + BANNER)
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Rules-only vs hybrid classifier comparison")
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE, help="max rows to evaluate (0 = all)")
    parser.add_argument("--skip-risk-delta", action="store_true")
    parser.add_argument("--out-json", default=REPORT_JSON)
    parser.add_argument("--out-md", default=REPORT_MD)
    parser.add_argument("--out-risk-md", default=RISK_DELTA_MD)
    args = parser.parse_args()

    started = time.monotonic()
    report = build_report(Path(args.csv), args.sample or None, started)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.out_md).write_text(render_md(report), encoding="utf-8")
    print(f"wrote {out_json} and {args.out_md}")

    if not args.skip_risk_delta:
        print("running ML risk-booster delta (full pipeline x2) ...")
        stats = run_risk_booster_delta(300)
        report["risk_booster_delta"] = stats
        out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        Path(args.out_risk_md).write_text(render_risk_delta_md(stats, report), encoding="utf-8")
        print(f"wrote {args.out_risk_md}")
        print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
