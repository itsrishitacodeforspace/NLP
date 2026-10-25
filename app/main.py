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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
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
    return {
        "status": "ok",
        "neo4j": neo4j_ok,
        "env": settings.app_env,
        "auth_enabled": settings.auth_enabled,
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
