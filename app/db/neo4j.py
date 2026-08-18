"""Database adapters: Neo4j (graph) and PostgreSQL (metadata)."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import List, Optional

from app.core.config import get_settings
from app.core.exceptions import GraphWriteError
from app.core.logging import get_logger

logger = get_logger()
_stdlib_logger = logging.getLogger("neo4j")
_stdlib_logger.setLevel(logging.WARNING)


class Neo4jConnection:
    """Lazy, retry-aware Neo4j driver wrapper."""

    _instance: Optional["Neo4jConnection"] = None

    def __init__(self) -> None:
        self._driver = None
        self._available = False
        self._connect_attempts = 0
        self._last_connect_attempt: float = 0.0

    @classmethod
    def instance(cls) -> "Neo4jConnection":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def driver(self):
        if self._driver is None:
            self._connect()
        return self._driver

    def _connect(self) -> None:
        import time as _time

        from neo4j import GraphDatabase
        from neo4j.exceptions import ServiceUnavailable

        # Throttle connection attempts to once per 10 seconds when failing.
        now = _time.time()
        if self._connect_attempts >= 1 and (now - self._last_connect_attempt) < 10:
            return
        self._last_connect_attempt = now
        self._connect_attempts += 1

        s = get_settings()
        try:
            self._driver = GraphDatabase.driver(
                s.neo4j_uri,
                auth=(s.neo4j_user, s.neo4j_password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=3,
                encrypted=False,
            )
            with self._driver.session() as session:
                session.run("RETURN 1").consume()
            self._available = True
            self._connect_attempts = 0
            logger.info("Connected to Neo4j at {}", s.neo4j_uri)
        except (ServiceUnavailable, Exception) as exc:
            self._available = False
            logger.warning("Neo4j unavailable: {}", exc)
            self._driver = None

    @property
    def available(self) -> bool:
        return self._available

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # pragma: no cover
                pass
        self._driver = None
        self._available = False


# ---------------------------------------------------------------------------
# Index bootstrap
# ---------------------------------------------------------------------------


INDEX_QUERIES = [
    "CREATE INDEX contract_id_idx IF NOT EXISTS FOR (n:Contract) ON (n.contract_id)",
    "CREATE INDEX clause_id_idx IF NOT EXISTS FOR (n:Clause) ON (n.clause_id)",
    "CREATE INDEX company_cin_idx IF NOT EXISTS FOR (n:Company) ON (n.cin)",
    "CREATE INDEX obligation_id_idx IF NOT EXISTS FOR (n:Obligation) ON (n.obligation_id)",
    "CREATE INDEX party_name_idx IF NOT EXISTS FOR (n:Party) ON (n.name)",
    "CREATE CONSTRAINT contract_id_unique IF NOT EXISTS FOR (n:Contract) REQUIRE n.contract_id IS UNIQUE",
]


def ensure_indexes() -> bool:
    """Create Neo4j indexes. Returns True if successful."""
    conn = Neo4jConnection.instance()
    if not conn.available:
        return False
    try:
        with conn.driver.session() as session:
            for q in INDEX_QUERIES:
                session.run(q).consume()
        logger.info("Neo4j indexes ensured")
        return True
    except Exception as exc:
        logger.warning("Failed to create Neo4j indexes: {}", exc)
        return False


# ---------------------------------------------------------------------------
# Context manager helpers
# ---------------------------------------------------------------------------


@contextmanager
def neo4j_session():
    conn = Neo4jConnection.instance()
    if not conn.available:
        raise GraphWriteError("Neo4j is not available")
    session = conn.driver.session()
    try:
        yield session
    finally:
        session.close()


def run_write(query: str, parameters: dict | None = None) -> dict:
    """Execute a write query with retry. Fast-fails if Neo4j is unreachable."""
    from neo4j.exceptions import ServiceUnavailable, TransientError

    conn = Neo4jConnection.instance()
    if not conn.available:
        raise GraphWriteError("Neo4j is not available")
    try:
        driver = conn.driver
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                with driver.session() as session:
                    return session.execute_write(
                        lambda tx: tx.run(query, parameters or {}).consume()
                    )
            except TransientError as exc:
                last_exc = exc
                import time as _time
                _time.sleep(0.5 * (attempt + 1))
                continue
            except ServiceUnavailable as exc:
                # Driver knows Neo4j is gone — abort immediately.
                conn._available = False
                raise GraphWriteError(str(exc)) from exc
        raise GraphWriteError(str(last_exc) if last_exc else "Transient write error")
    except GraphWriteError:
        raise
    except Exception as exc:
        raise GraphWriteError(str(exc)) from exc


def run_read(query: str, parameters: dict | None = None) -> List[dict]:
    """Execute a read query and return list of dicts."""
    conn = Neo4jConnection.instance()
    if not conn.available:
        return []
    try:
        with conn.driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]
    except Exception as exc:
        logger.warning("Neo4j read failed: {}", exc)
        return []
