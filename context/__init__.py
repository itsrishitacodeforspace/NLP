"""Deterministic, dependency-free cross-reference resolution (P1).

Read-only enrichment: this package never mutates clause text, offsets, labels,
severities or rule output. It records *what references a clause makes*, *what
they resolve to within this document*, and *whether resolution is complete*.
"""
from __future__ import annotations

from nlp.context.resolver import resolve_context

__all__ = ["resolve_context"]
