"""DeBERTa-v3 NER enrichment wrapper. Loaded lazily."""
from __future__ import annotations

from typing import List

from app.models.schemas import Entity

try:  # pragma: no cover - optional import
    from transformers import AutoModelForTokenClassification, AutoTokenizer  # type: ignore
    _TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover
    _TRANSFORMERS_AVAILABLE = False


_MODEL = None
_TOKENIZER = None


def _load_model():  # pragma: no cover
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return
    from app.core.config import get_settings

    settings = get_settings()
    model_name = settings.ner_model
    _TOKENIZER = AutoTokenizer.from_pretrained(model_name, cache_dir=settings.hf_home)
    _MODEL = AutoModelForTokenClassification.from_pretrained(
        model_name, cache_dir=settings.hf_home, ignore_mismatched_sizes=True,
    )
    _MODEL.eval()


def enrich_entities_with_deberta(text: str, *, existing: List[Entity]) -> List[Entity]:
    """Append PARTY/ORG/DATE entities that regex missed. Best-effort."""
    if not _TRANSFORMERS_AVAILABLE or not text or not text.strip():
        return existing
    try:
        _load_model()
    except Exception:
        return existing

    try:  # pragma: no cover
        import torch
        tokens = _TOKENIZER(
            text, return_tensors="pt", truncation=True, max_length=512, padding=True,
        )
        with torch.no_grad():
            logits = _MODEL(**tokens).logits
        predictions = torch.argmax(logits, dim=-1)[0].cpu().tolist()
        id2label = _MODEL.config.id2label
        offsets = _TOKENIZER(
            text, return_offsets_mapping=True, truncation=True, max_length=512,
        )["offset_mapping"][0]
        seen = {(e.label, e.text.lower()) for e in existing}
        for pred, (start, end) in zip(predictions, offsets):
            if start == end:
                continue
            label = id2label.get(pred, "O")
            if not label or label == "O":
                continue
            value = label.split("-")[-1]
            if value not in {"PARTY", "ORG", "DATE"}:
                continue
            span = text[start:end]
            key = (value, span.lower())
            if key in seen:
                continue
            seen.add(key)
            existing.append(
                Entity(
                    text=span,
                    label=value,
                    start_char=start,
                    end_char=end,
                    confidence=0.75,
                    source="ner",
                )
            )
    except Exception:
        return existing
    return existing
