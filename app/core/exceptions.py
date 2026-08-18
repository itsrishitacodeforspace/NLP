"""Custom exception types for the BharatContract AI stack."""
from __future__ import annotations


class BharatContractError(Exception):
    """Base exception for all domain errors."""

    status_code: int = 500

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class DocumentParseError(BharatContractError):
    """Raised when a contract cannot be parsed or extracted."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class UnsupportedFormatError(DocumentParseError):
    """Raised when the uploaded file type is not supported."""

    def __init__(self, ext: str) -> None:
        super().__init__(f"Unsupported file format: {ext}")


class ModelNotAvailableError(BharatContractError):
    """Raised when an NLP model is requested but cannot be loaded."""

    def __init__(self, model_name: str) -> None:
        super().__init__(f"NLP model not available: {model_name}", status_code=503)


class GraphWriteError(BharatContractError):
    """Raised when Neo4j writes fail and rollback did not resolve the issue."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
