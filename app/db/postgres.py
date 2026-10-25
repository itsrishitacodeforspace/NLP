"""PostgreSQL session setup for metadata storage.

The MVP keeps things simple — a single SQLAlchemy engine, metadata tables
created on first request. Heavy use of Neo4j is preferred for relationships.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
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

logger = get_logger()


class Base(DeclarativeBase):
    pass


class ContractRecord(Base):
    __tablename__ = "contracts"

    contract_id = Column(String, primary_key=True)
    title = Column(String, default="")
    file_name = Column(String, default="")
    contract_type = Column(String, default="OTHER")
    status = Column(String, default="processing")
    overall_risk_score = Column(Float, default=0.0)
    overall_risk_level = Column(String, default="low")
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    contract_id = Column(String, index=True)
    status = Column(String, default="queued")
    progress = Column(Float, default=0.0)
    message = Column(Text, default="")
    result = Column(JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


_engine: Optional[object] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine():
    global _engine
    if _engine is None:
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
            logger.info("Postgres engine initialised at {}", settings.database_url)
        except Exception as exc:
            logger.warning("Postgres unavailable ({}). Metadata writes will be no-ops.", exc)
            _engine = None
            set_postgres_unavailable()
    return _engine


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


_AVAILABLE_CACHE: dict[str, bool] = {"postgres": True}


def postgres_available() -> bool:
    """Cheap check; if engine init failed once, skip for the rest of this process."""
    return _AVAILABLE_CACHE.get("postgres", False)


def set_postgres_unavailable() -> None:
    _AVAILABLE_CACHE["postgres"] = False


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
                "status",
                "progress",
                "message",
                "result",
                "error",
            ):
                if key in record:
                    setattr(obj, key, record[key])
            if record.get("status") in {"succeeded", "failed"}:
                obj.finished_at = datetime.utcnow()
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
        return {
            "job_id": obj.job_id,
            "contract_id": obj.contract_id,
            "status": obj.status,
            "progress": obj.progress,
            "message": obj.message,
            "result": obj.result,
            "error": obj.error,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "finished_at": obj.finished_at.isoformat() if obj.finished_at else None,
        }


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
