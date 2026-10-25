"""Time helpers.

``datetime.utcnow()`` is deprecated from Python 3.12 onward. We keep the
database columns and Pydantic defaults timezone-naive (as they were declared)
but compute them from an explicit UTC source so the value is unambiguous and
no deprecation warning is emitted.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (``tzinfo=None``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
