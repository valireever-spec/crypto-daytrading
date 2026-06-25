"""Structured JSON logging configuration (unified module).

This module provides the canonical logging setup for the application.
All logs are formatted as JSON for structured observability.
"""

from backend.core.structured_logging import (
    JSONFormatter,
    RequestContextFilter,
    setup_structured_logging as setup_logging,
    get_logger_with_context,
)

__all__ = [
    "JSONFormatter",
    "RequestContextFilter",
    "setup_logging",
    "get_logger_with_context",
]
