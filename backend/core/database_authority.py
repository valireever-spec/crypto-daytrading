"""Database Authority Detection for HA Recovery (FR-015).

Determines which database is authoritative based on chronological timestamps.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseAuthorityError(Exception):
    """Raised when authority detection fails."""
    pass


class DatabaseAuthority:
    """Detects which database is authoritative based on timestamps."""

    def __init__(self, divergence_threshold_seconds: int = 60):
        """
        Initialize authority detector.

        Args:
            divergence_threshold_seconds: Minimum divergence to consider as sync error.
                                        <60s is normal time drift, ignore.
        """
        self.divergence_threshold = divergence_threshold_seconds

    def detect_authority(
        self,
        primary_db_path: str,
        backup_db_path: str
    ) -> Dict[str, Any]:
        """
        Determine which database is authoritative.

        Compares account_state.updated_at (or latest trade timestamp if account_state empty).
        The database with the later timestamp is authoritative.

        Args:
            primary_db_path: Path to PRIMARY machine database
            backup_db_path: Path to BACKUP machine database

        Returns:
            {
                'authoritative': 'primary' | 'backup' | 'diverged' | 'unknown',
                'primary_timestamp': datetime or None,
                'backup_timestamp': datetime or None,
                'divergence_seconds': float,
                'reason': str,
                'sync_needed': bool
            }

        Raises:
            DatabaseAuthorityError: If authority cannot be determined safely
        """
        try:
            primary_ts = self._get_latest_timestamp(primary_db_path)
            backup_ts = self._get_latest_timestamp(backup_db_path)

            logger.info(f"Authority detection: PRIMARY={primary_ts}, BACKUP={backup_ts}")

            # Handle missing timestamps
            if primary_ts is None and backup_ts is None:
                return {
                    'authoritative': 'unknown',
                    'primary_timestamp': None,
                    'backup_timestamp': None,
                    'divergence_seconds': 0,
                    'reason': 'Both databases empty or unreadable',
                    'sync_needed': False
                }

            if primary_ts is None:
                return {
                    'authoritative': 'backup',
                    'primary_timestamp': None,
                    'backup_timestamp': backup_ts,
                    'divergence_seconds': float('inf'),
                    'reason': 'PRIMARY database empty or unreadable, BACKUP is authoritative',
                    'sync_needed': True
                }

            if backup_ts is None:
                return {
                    'authoritative': 'primary',
                    'primary_timestamp': primary_ts,
                    'backup_timestamp': None,
                    'divergence_seconds': float('inf'),
                    'reason': 'BACKUP database empty or unreadable, PRIMARY is authoritative',
                    'sync_needed': True
                }

            # Both timestamps exist - compare them
            divergence = (primary_ts - backup_ts).total_seconds()
            abs_divergence = abs(divergence)

            # Small divergence (<60s) is normal clock drift, not a sync error
            if abs_divergence < self.divergence_threshold:
                return {
                    'authoritative': 'unknown',
                    'primary_timestamp': primary_ts,
                    'backup_timestamp': backup_ts,
                    'divergence_seconds': abs_divergence,
                    'reason': f'Divergence {abs_divergence:.1f}s is within threshold ({self.divergence_threshold}s), normal clock drift',
                    'sync_needed': False
                }

            # Divergence >60s indicates sync error
            if primary_ts > backup_ts:
                return {
                    'authoritative': 'primary',
                    'primary_timestamp': primary_ts,
                    'backup_timestamp': backup_ts,
                    'divergence_seconds': divergence,
                    'reason': f'PRIMARY is {divergence:.1f}s ahead of BACKUP (authoritative)',
                    'sync_needed': True
                }
            else:
                return {
                    'authoritative': 'backup',
                    'primary_timestamp': primary_ts,
                    'backup_timestamp': backup_ts,
                    'divergence_seconds': -divergence,
                    'reason': f'BACKUP is {-divergence:.1f}s ahead of PRIMARY (authoritative)',
                    'sync_needed': True
                }

        except Exception as e:
            logger.error(f"Authority detection failed: {e}")
            raise DatabaseAuthorityError(f"Failed to detect authority: {e}")

    def _get_latest_timestamp(self, db_path: str) -> Optional[datetime]:
        """
        Get latest timestamp from database.

        Checks:
        1. MAX(account_state.updated_at) - most recent account update
        2. MAX(trades.created_at) - most recent trade if no account state

        Returns None if database is empty, unreadable, or error occurs.
        """
        try:
            path = Path(db_path)
            if not path.exists():
                logger.warning(f"Database not found: {db_path}")
                return None

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Try account_state first (most reliable)
            try:
                cursor.execute("SELECT MAX(updated_at) as ts FROM account_state")
                row = cursor.fetchone()
                if row and row['ts']:
                    ts_str = row['ts']
                    conn.close()
                    return self._parse_timestamp(ts_str)
            except sqlite3.OperationalError:
                pass  # Table doesn't exist, try trades

            # Fallback to trades table
            try:
                cursor.execute("SELECT MAX(created_at) as ts FROM trades")
                row = cursor.fetchone()
                if row and row['ts']:
                    ts_str = row['ts']
                    conn.close()
                    return self._parse_timestamp(ts_str)
            except sqlite3.OperationalError:
                pass  # Table doesn't exist either

            conn.close()
            return None  # Database exists but is empty

        except Exception as e:
            logger.error(f"Failed to get timestamp from {db_path}: {e}")
            return None

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse ISO 8601 timestamp string to datetime."""
        if not ts_str:
            return None

        # Handle ISO format: "2026-07-01T16:52:14.123456Z"
        try:
            # Remove 'Z' if present
            ts_str = ts_str.replace('Z', '+00:00')
            # Try parsing with microseconds
            return datetime.fromisoformat(ts_str)
        except ValueError:
            # Try without microseconds
            return datetime.fromisoformat(ts_str.split('.')[0])
