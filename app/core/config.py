"""Centralised configuration loader for BharatContract AI.

Loads values from environment variables and the optional `.env` file.
Uses pydantic-settings for type-validated config objects so downstream
modules can rely on attribute access rather than `os.getenv`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Top-level settings object.

    All values are environment-overridable. Defaults are development-friendly.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = Field(default="BharatContract AI")
    app_env: str = Field(default="development")

    # PostgreSQL
    database_url: str = Field(default="postgresql://bharat:contractpass@localhost:5432/bharatcontract")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="contractpass")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_base_url: str = Field(default="http://localhost:8000")

    # Streamlit
    streamlit_port: int = Field(default=8501)

    # Models
    model_cache_dir: str = Field(default=str(PROJECT_ROOT / "models"))
    hf_home: str = Field(default=str(PROJECT_ROOT / "models" / "hf"))
    clause_model: str = Field(default="microsoft/deberta-v3-base")
    ner_model: str = Field(default="microsoft/deberta-v3-base")
    spacy_model: str = Field(default="en_core_web_sm")

    # Uploads
    upload_dir: str = Field(default=str(PROJECT_ROOT / "uploads"))
    max_upload_mb: int = Field(default=25)

    # Logging
    log_level: str = Field(default="INFO")
    log_file: str = Field(default=str(PROJECT_ROOT / "logs" / "bharatcontract.log"))

    # Indian context
    default_jurisdiction: str = Field(default="India")

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:8501", "http://127.0.0.1:8501"]
    )

    # Internal toggles
    enable_background_jobs: bool = Field(default=True)
    enable_ocr_fallback: bool = Field(default=True)

    # Authentication (OFF by default so the demo needs zero configuration)
    auth_enabled: bool = Field(default=False)
    auth_secret_key: str = Field(default="dev-insecure-secret-change-me")
    auth_token_expire_minutes: int = Field(default=60)
    auth_admin_password: str = Field(default="admin")
    # JSON list of {"username": ..., "password": ..., "role": ...} entries.
    auth_users: str = Field(default="")

    # NLP toggles (used in MVP to gracefully fall back when models missing)
    use_rule_based_classifier: bool = Field(default=True)

    def ensure_dirs(self) -> None:
        """Create required directories on disk if missing."""
        for path in (self.upload_dir, self.model_cache_dir, self.hf_home,
                     Path(self.log_file).parent):
            Path(path).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    s = Settings()
    s.ensure_dirs()
    os.environ.setdefault("HF_HOME", s.hf_home)
    return s
