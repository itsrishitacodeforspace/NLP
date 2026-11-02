"""DeBERTa-v3 clause classifier wrapper.

This module is imported lazily — only if the heavy ML deps are installed.
It provides a `classify_with_deberta(text)` function that returns a
ClassificationResult with model confidence.
"""
from __future__ import annotations

from typing import List, Optional

from nlp.clause_classification.classifier import CLAUSE_RULES, ClassificationResult

try:  # pragma: no cover - optional
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
    _TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover
    _TRANSFORMERS_AVAILABLE = False


_MODEL = None
_TOKENIZER = None
_LABEL_MAP: Optional[List[str]] = None


def _load_model():  # pragma: no cover - large download
    """Lazy-load the DeBERTa classifier once per process."""
    global _MODEL, _TOKENIZER, _LABEL_MAP
    if _MODEL is not None:
        return
    from app.core.config import get_settings

    settings = get_settings()
    model_name = settings.clause_model
    _TOKENIZER = AutoTokenizer.from_pretrained(model_name, cache_dir=settings.hf_home)
    _MODEL = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        cache_dir=settings.hf_home,
        num_labels=len(CLAUSE_RULES),
        ignore_mismatched_sizes=True,
    )
    _MODEL.eval()
    _LABEL_MAP = list(CLAUSE_RULES.keys())


def classify_with_deberta(text: str, *, top_k: int = 3) -> Optional[ClassificationResult]:
    """Run zero-shot / fine-tuned DeBERTa classification. Returns None on failure."""
    if not _TRANSFORMERS_AVAILABLE:
        return None
    if not text or not text.strip():
        return None
    try:
        _load_model()
    except Exception:
        return None

    try:  # pragma: no cover - inference
        import torch
        inputs = _TOKENIZER(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        with torch.no_grad():
            logits = _MODEL(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0].cpu().tolist()
        ranked = sorted(enumerate(probs), key=lambda kv: -kv[1])[:top_k]
        labels = [_LABEL_MAP[i] for i, _ in ranked if _LABEL_MAP]
        confidence = float(ranked[0][1]) if ranked else 0.0
        return ClassificationResult(labels=labels, confidence=round(confidence, 3), method="ml")
    except Exception:
        return None
