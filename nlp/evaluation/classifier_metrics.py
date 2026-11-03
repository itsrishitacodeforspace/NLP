"""Shared multi-label classifier metrics (per-class P/R/F1, macro, weighted).

Used by the rules-vs-hybrid and family-disjoint held-out evaluations.
Conventions (documented in the generated reports):

* Top-1 = the first predicted label.
* Top-3 = any of the first three predicted labels counts as a hit.
* Gold rows whose category is outside the internal taxonomy are counted in
  ``excluded_rows`` and otherwise ignored.
* Abstention: rule mode abstains only via its ``Miscellaneous`` fallback
  (the rule classifier never returns an empty label list); hybrid mode
  abstains when its label list is empty after the 0.15 TF-IDF threshold.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Sequence, Tuple

ABSTAIN_LABEL = "Miscellaneous"
EMPTY_LABEL = "<abstained>"


def precision_recall_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def compute_label_metrics(
    rows: Sequence[Dict],
    *,
    k: int = 1,
    abstain_as_own_class: bool = False,
) -> Dict[str, object]:
    """Compute per-class + macro + weighted metrics.

    ``rows``: each row has ``gold`` (str), ``preds`` (List[str], ranked) and
    optionally ``abstained`` (bool). ``k`` = top-k membership.
    When ``abstain_as_own_class``, rows with no labels are scored as the
    pseudo-class ``<abstained>`` (gold must also be ``<abstained>`` — used
    only for the abstention distribution, not for macro/weighted numbers).
    """
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    excluded = 0
    for row in rows:
        gold = row.get("gold", "")
        preds = row.get("preds") or []
        if abstain_as_own_class:
            topk = preds[:k] or [EMPTY_LABEL]
            gold_val = EMPTY_LABEL
        else:
            topk = preds[:k]
            gold_val = gold
        if gold_val == EMPTY_LABEL:
            excluded += 1
            continue
        hit = gold_val in topk
        tp[gold_val] += 1 if hit else 0
        for p in topk:
            if p != gold_val:
                fp[p] += 1
        if not hit:
            fn[gold_val] += 1

    classes = sorted(set(tp) | set(fp) | set(fn) | {EMPTY_LABEL})
    per_class: Dict[str, Dict[str, float]] = {}
    for c in classes:
        p, r, f = precision_recall_f1(tp.get(c, 0), fp.get(c, 0), fn.get(c, 0))
        support = tp.get(c, 0) + fn.get(c, 0)
        per_class[c] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "support": support}
    total_support = sum(v["support"] for v in per_class.values()) or 1
    macro_f1 = sum(v["f1"] for v in per_class.values()) / max(1, len(per_class))
    weighted_f1 = sum(v["f1"] * v["support"] for v in per_class.values()) / total_support
    return {
        "per_class": per_class,
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "excluded_rows": excluded,
    }


def confusion_matrix(rows: Sequence[Dict], classes: Sequence[str]) -> Dict[str, Dict[str, int]]:
    """Top-1 confusion matrix (rows = gold, cols = predicted), classes only."""
    matrix = {g: {p: 0 for p in classes} for g in classes}
    for row in rows:
        gold = row.get("gold", "")
        preds = row.get("preds") or []
        pred = preds[0] if preds else ABSTAIN_LABEL
        if gold in matrix and pred in matrix[gold]:
            matrix[gold][pred] += 1
    return matrix


def abstention_distribution(rows: Sequence[Dict]) -> Dict[str, object]:
    """How abstained items (no usable label) distribute across gold categories."""
    counter: Counter = Counter()
    total = 0
    abstained = 0
    for row in rows:
        total += 1
        if not (row.get("preds") or []):
            abstained += 1
            counter[row.get("gold", "?")] += 1
    return {
        "total_rows": total,
        "abstained": abstained,
        "abstention_rate": round(abstained / total, 4) if total else 0.0,
        "by_gold_category": dict(sorted(counter.items(), key=lambda kv: -kv[1])),
    }


def rule_fallback_stats(rows: Sequence[Dict]) -> Dict[str, object]:
    """Count rule-mode 'Miscellaneous' fallback rows (its abstention analogue)."""
    total = 0
    fallback = 0
    counter: Counter = Counter()
    for row in rows:
        total += 1
        if (row.get("preds") or []) == [ABSTAIN_LABEL]:
            fallback += 1
            counter[row.get("gold", "?")] += 1
    return {
        "total_rows": total,
        "misc_fallback": fallback,
        "misc_fallback_rate": round(fallback / total, 4) if total else 0.0,
        "misc_fallback_by_gold_category": dict(sorted(counter.items(), key=lambda kv: -kv[1])),
    }
