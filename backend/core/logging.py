"""Structured JSON logging configuration."""

import json
import logging
from pathlib import Path
from datetime import datetime


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured JSON logging."""

    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    class JSONFormatter(logging.Formatter):
        """Format logs as JSON for structured logging."""

        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            # Add custom fields
            if hasattr(record, "extra"):
                log_data.update(record.extra)

            return json.dumps(log_data)

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # File handler (system logs)
    file_handler = logging.FileHandler(log_dir / "system.log")
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    # Console handler (development)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.LoggerAdapter:
    """Get a logger with structured logging support."""
    return logging.getLogger(name)
