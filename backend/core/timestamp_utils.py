"""
Timestamp utilities for consistent parsing across all modules.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse ISO 8601 timestamp string safely.

    Handles multiple formats:
    - 2026-06-24T08:30:00Z
    - 2026-06-24T08:30:00+00:00
    - 2026-06-24T08:30:00 (assumed UTC)

    Parameters:
    -----------
    timestamp_str : str
        Timestamp string to parse

    Returns:
    --------
    datetime object (UTC) or None if parsing fails
    """
    if not timestamp_str or not isinstance(timestamp_str, str):
        logger.debug(f"Invalid timestamp: {timestamp_str}")
        return None

    # Clean up common issues
    ts = timestamp_str.strip()

    # Replace Z with +00:00 for compatibility
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None


def timestamp_to_iso(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string.

    Parameters:
    -----------
    dt : datetime
        Datetime object (should be UTC)

    Returns:
    --------
    ISO 8601 string with Z suffix
    """
    if not isinstance(dt, datetime):
        dt = datetime.now(timezone.utc)

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    """Get current time as ISO 8601 string with Z suffix."""
    return timestamp_to_iso(datetime.now(timezone.utc))
