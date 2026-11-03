"""PostgreSQL session setup for metadata storage.

The MVP keeps things simple — a single SQLAlchemy engine, metadata tables
created on first request. Heavy use of Neo4j is preferred for relationships.
"""
from __future__ import annotations

import threading
import time as _time
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import utcnow

logger = get_logger()


class Base(DeclarativeBase):
    pass


class ContractRecord(Base):
    __tablename__ = "contracts"

    contract_id = Column(String, primary_key=True)
    title = Column(String, default="")
    file_name = Column(String, default="")
    contract_type = Column(String, default="OTHER")
    owner = Column(String, default="")
    status = Column(String, default="processing")
    overall_risk_score = Column(Float, default=0.0)
    overall_risk_level = Column(String, default="low")
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    contract_id = Column(String, index=True)
    owner = Column(String, default="", index=True)
    status = Column(String, default="queued")
    progress = Column(Float, default=0.0)
    message = Column(Text, default="")
    result = Column(JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)


_engine: Optional[object] = None
_SessionLocal: Optional[sessionmaker] = None
_engine_lock = threading.Lock()


def _ensure_owner_columns(engine) -> None:
    """Add the `owner` column to pre-existing tables (no migration tooling).

    `create_all` only creates missing tables, not missing columns, so a database
    created before row-level security existed would otherwise lack `owner`.
    """
    from sqlalchemy import text

    for table in ("contracts", "jobs"):
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS owner VARCHAR DEFAULT ''"))
        except Exception as exc:
            logger.warning("Could not ensure owner column on {}: {}", table, exc)


def get_engine():
    """Return the shared engine, initialising it on first use.

    Initialisation is guarded by ``_engine_lock`` so concurrent callers
    cannot double-initialise the engine. A failed probe is cached by
    ``set_postgres_unavailable()`` and re-probed at most every 30 seconds,
    so a transient outage does not permanently disable persistence while
    the common down case still fast-fails without touching the network.
    """
    global _engine
    if _engine is not None:
        return _engine
    if postgres_available():
        with _engine_lock:
            if _engine is None:
                # Serialised: exactly one caller probes per window.
                set_probe_window()
                _init_engine()
    return _engine


def _init_engine() -> None:
    """Create and probe the engine. Caller must hold ``_engine_lock``."""
    global _engine
    settings = get_settings()
    try:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=False,
            pool_size=5,
            max_overflow=5,
            future=True,
            connect_args={"connect_timeout": 3},
        )
        # Probe connection with a short timeout; do not block on cold start.
        with _engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        Base.metadata.create_all(_engine)
        _ensure_owner_columns(_engine)
        logger.info("Postgres engine initialised at {}", settings.database_url)
    except Exception as exc:
        logger.warning("Postgres unavailable ({}). Metadata writes will be no-ops.", exc)
        _engine = None
        set_postgres_unavailable()


def get_sessionmaker() -> Optional[sessionmaker]:
    global _SessionLocal
    engine = get_engine()
    if engine is None:
        return None
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Optional[Session]]:
    sm = get_sessionmaker()
    if sm is None:
        yield None
        return
    session = sm()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Availability cache. A failed probe is remembered as a *bounded* outage:
# callers fast-fail for ``PROBE_RETRY_SECONDS`` and then get one re-probe
# attempt, so a transient outage cannot permanently disable persistence.
_PROBE_RETRY_SECONDS = 30.0
_AVAILABLE_CACHE: dict[str, object] = {"postgres": True}


def postgres_available() -> bool:
    """Cheap check; unavailability fast-fails but is re-probed periodically.

    Once the engine probe has failed, this returns ``False`` without
    touching the network for up to ``PROBE_RETRY_SECONDS``. When that window
    has elapsed the flag is reset to ``True`` so a single caller may attempt
    to re-probe (via :func:`get_engine`, which serialises the attempts).
    """
    cache = _AVAILABLE_CACHE
    value = cache.get("postgres", True)
    if value is not False:
        return True
    since = cache.get("unavailable_since")
    if since is None or _time.monotonic() - since >= _PROBE_RETRY_SECONDS:
        cache["postgres"] = True
    return cache.get("postgres", False) is not False


def set_postgres_unavailable() -> None:
    """Mark Postgres as down, fast-failing callers for a bounded window."""
    _AVAILABLE_CACHE["postgres"] = False
    _AVAILABLE_CACHE["unavailable_since"] = _time.monotonic()


def set_probe_window() -> None:
    """Arm the fast-fail window so at most one re-probe is attempted per window."""
    _AVAILABLE_CACHE["unavailable_since"] = _time.monotonic()


def upsert_contract_metadata(record: dict) -> bool:
    if not postgres_available():
        return False
    try:
        with session_scope() as session:
            if session is None:
                return False
            obj = session.get(ContractRecord, record["contract_id"])
            if obj is None:
                obj = ContractRecord(contract_id=record["contract_id"])
                session.add(obj)
            for key in (
                "title",
                "file_name",
                "contract_type",
                "owner",
                "status",
                "overall_risk_score",
                "overall_risk_level",
                "payload",
            ):
                if key in record:
                    setattr(obj, key, record[key])
            return True
    except Exception as exc:
        logger.warning("Contract metadata write failed: {}", exc)
        return False


def upsert_job(record: dict) -> bool:
    if not postgres_available():
        return False
    try:
        with session_scope() as session:
            if session is None:
                return False
            obj = session.get(JobRecord, record["job_id"])
            if obj is None:
                obj = JobRecord(job_id=record["job_id"])
                session.add(obj)
            for key in (
                "contract_id",
                "owner",
                "status",
                "progress",
                "message",
                "result",
                "error",
                "created_at",
                "finished_at",
            ):
                if key in record and record[key] is not None:
                    setattr(obj, key, record[key])
            return True
    except Exception as exc:
        logger.warning("Job write failed: {}", exc)
        return False


def get_job(job_id: str) -> Optional[dict]:
    if not postgres_available():
        return None
    with session_scope() as session:
        if session is None:
            return None
        obj = session.get(JobRecord, job_id)
        if obj is None:
            return None
        return _job_record_dict(obj)


def list_job_ids_for_contract(
    contract_id: str,
    *,
    owner: Optional[str] = None,
    limit: int = 20,
) -> list[str]:
    """Return recent job ids for a contract, newest first.

    When ``owner`` is given the query is additionally scoped to that owner
    (row-level security). ``owner=None`` means "any owner".
    """
    if not postgres_available():
        return []
    with session_scope() as session:
        if session is None:
            return []
        query = session.query(JobRecord.job_id).filter(JobRecord.contract_id == contract_id)
        if owner is not None:
            query = query.filter(JobRecord.owner == owner)
        rows = (
            query.order_by(
                JobRecord.finished_at.desc().nulls_last(),
                JobRecord.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [r[0] for r in rows]


def list_jobs(limit: int = 200) -> list[dict]:
    if not postgres_available():
        return []
    with session_scope() as session:
        if session is None:
            return []
        rows = (
            session.query(JobRecord)
            .order_by(JobRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [{"job_id": r.job_id} for r in rows]


def get_jobs_by_ids(job_ids: list[str], *, owner: Optional[str] = None) -> list[dict]:
    """Fetch full job records in a single batched ``WHERE job_id IN (...)`` query.

    Mirrors the :func:`get_job` record shape. When ``owner`` is given the rows
    are additionally scoped to that owner (row-level security).
    """
    if not postgres_available() or not job_ids:
        return []
    with session_scope() as session:
        if session is None:
            return []
        query = session.query(JobRecord).filter(JobRecord.job_id.in_(job_ids))
        if owner is not None:
            query = query.filter(JobRecord.owner == owner)
        return [_job_record_dict(r) for r in query.all()]


def _job_record_dict(obj: JobRecord) -> dict:
    """Build the plain-dict shape shared by ``get_job`` and ``get_jobs_by_ids``."""
    return {
        "job_id": obj.job_id,
        "contract_id": obj.contract_id,
        "owner": obj.owner or "",
        "status": obj.status,
        "progress": obj.progress,
        "message": obj.message,
        "result": obj.result,
        "error": obj.error,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "finished_at": obj.finished_at.isoformat() if obj.finished_at else None,
    }


def list_contracts(limit: int = 100) -> list[dict]:
    if not postgres_available():
        return []
    with session_scope() as session:
        if session is None:
            return []
        rows = (
            session.query(ContractRecord)
            .order_by(ContractRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "contract_id": r.contract_id,
                "title": r.title,
                "file_name": r.file_name,
                "status": r.status,
                "overall_risk_score": r.overall_risk_score,
                "overall_risk_level": r.overall_risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
