"""FastAPI entrypoint for BharatContract AI."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_auth, routes_contracts, routes_graph, routes_jobs
from app.core.config import get_settings
from app.core.exceptions import BharatContractError
from app.core.logging import get_logger, setup_logging
from app.db.neo4j import Neo4jConnection, ensure_indexes

setup_logging()
logger = get_logger()


# Shipped development secret (see app.core.config.Settings.auth_secret_key).
DEFAULT_AUTH_SECRET_KEY = "dev-insecure-secret-change-me"
# Environments where starting with the default secret is a hard failure.
PRODUCTIONISH_ENVS = {"production", "prod", "staging"}


def guard_auth_secret(settings) -> None:
    """Refuse (or warn) to start with the shipped default JWT secret.

    With ``AUTH_ENABLED=true`` and ``AUTH_SECRET_KEY`` still the dev default,
    every bearer token in existence is forgeable. In production-like
    environments that is a startup error; elsewhere it is logged as CRITICAL
    so it stands out in the logs.
    """
    if not settings.auth_enabled:
        return
    if settings.auth_secret_key != DEFAULT_AUTH_SECRET_KEY:
        return
    env = settings.app_env.strip().lower()
    if env in PRODUCTIONISH_ENVS:
        raise RuntimeError(
            "AUTH_SECRET_KEY is the shipped development default while "
            "AUTH_ENABLED=true in a production-like environment "
            f"({settings.app_env!r}). Set a long random AUTH_SECRET_KEY before starting."
        )
    logger.critical(
        "AUTH_ENABLED=true but AUTH_SECRET_KEY is the shipped development "
        "default. Anyone can forge tokens — set a strong AUTH_SECRET_KEY."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    guard_auth_secret(settings)
    logger.info("Starting {} (env={})", settings.app_name, settings.app_env)
    # Touch Neo4j once so failures show in startup logs.
    conn = Neo4jConnection.instance()
    _ = conn.available
    if conn.available:
        ensure_indexes()
    yield
    conn.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="BharatContract AI API",
    description="Legal Contract Intelligence — Indian-context risk-aware clause extraction & obligation tracker.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BharatContractError)
async def _bharatcontract_error_handler(request: Request, exc: BharatContractError):
    logger.warning("Domain error on {}: {}", request.url.path, exc)
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on {}", request.url.path)
    content = {"detail": "Internal server error"}
    # Only surface the exception class in development — never in production.
    if settings.app_env.lower() in {"development", "dev", "local"}:
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(routes_auth.router)
app.include_router(routes_contracts.router)
app.include_router(routes_jobs.router)
app.include_router(routes_graph.router)


@app.get("/")
def root():
    return {
        "name": "BharatContract AI",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/healthz",
        "auth": "/api/v1/auth/token",
    }


@app.get("/healthz")
def healthz():
    settings = get_settings()
    neo4j_ok = Neo4jConnection.instance().available
    try:
        from nlp import provenance

        provenance_block = provenance.summary()
    except Exception:  # pragma: no cover - health must never fail on provenance
        provenance_block = {}
    return {
        "status": "ok",
        "neo4j": neo4j_ok,
        "env": settings.app_env,
        "auth_enabled": settings.auth_enabled,
        # Data-lineage only; says nothing about evaluation or predictive validity.
        "provenance": provenance_block,
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
