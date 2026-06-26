"""Structured logging configuration (JSON format for observability)."""

import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured observability."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON string.

        Args:
            record: Log record from Python logging

        Returns:
            JSON-formatted log line
        """
        log_dict: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
            "module": record.module,
        }

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        # Add request ID if in extras (from middleware)
        if hasattr(record, "request_id"):
            log_dict["request_id"] = record.request_id  # type: ignore

        # Add user ID if in extras (from auth context)
        if hasattr(record, "user_id"):
            log_dict["user_id"] = record.user_id  # type: ignore

        # Add any extra fields
        if hasattr(record, "extra_fields"):
            log_dict.update(record.extra_fields)  # type: ignore

        return json.dumps(log_dict)


def setup_structured_logging(
    level: int = logging.INFO,
    json_format: bool = True,
    log_dir: str = "logs",
) -> None:
    """Configure structured logging for entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format if True, else plain text
        log_dir: Directory for log files (auto-created if missing)
    """
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add rotating file handlers for persistent logging
    if json_format:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # Main API log file (100MB, keep 10 files = ~1GB)
        api_log = log_path / "api.log"
        api_handler = RotatingFileHandler(
            str(api_log),
            maxBytes=100 * 1024 * 1024,  # 100 MB
            backupCount=10,
        )
        api_handler.setLevel(level)
        api_handler.setFormatter(formatter)
        root_logger.addHandler(api_handler)

        # Trade execution log file (50MB, keep 5 files)
        trades_log = log_path / "trades.jsonl"
        trades_handler = RotatingFileHandler(
            str(trades_log),
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=5,
        )
        trades_handler.setLevel(logging.INFO)
        trades_handler.setFormatter(formatter)
        root_logger.addHandler(trades_handler)

    root_logger.setLevel(level)


class RequestContextFilter(logging.Filter):
    """Add request context (ID, user, etc.) to all logs within a request.

    Usage:
        In middleware or request handler, set request ID:
        request_id = str(uuid.uuid4())
        logging.getLogger().handlers[0].addFilter(
            RequestContextFilter(request_id=request_id)
        )
    """

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Initialize filter with request context.

        Args:
            request_id: Unique request identifier (UUID)
            user_id: User identifier from auth token
        """
        super().__init__()
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to log record.

        Args:
            record: Log record to filter

        Returns:
            True to allow record to be logged
        """
        record.request_id = self.request_id  # type: ignore
        if self.user_id:
            record.user_id = self.user_id  # type: ignore
        return True


def get_logger_with_context(
    name: str,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> logging.Logger:
    """Get logger with request context attached.

    Args:
        name: Logger name (usually __name__)
        request_id: Request ID from middleware
        user_id: User ID from auth

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    if request_id or user_id:
        context_filter = RequestContextFilter(request_id=request_id, user_id=user_id)
        logger.addFilter(context_filter)
    return logger
