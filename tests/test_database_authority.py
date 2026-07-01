"""Unit tests for FR-015 Database Authority Detection.

Tests the DatabaseAuthority class for correctness in detecting which database
is authoritative based on timestamps.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.core.database_authority import DatabaseAuthority, DatabaseAuthorityError


@pytest.fixture
def authority():
    """Create DatabaseAuthority instance."""
    return DatabaseAuthority(divergence_threshold_seconds=60)


class TestDatabaseAuthorityDetection:
    """Test authority detection logic."""

    def test_primary_newer_is_authoritative(self, authority):
        """PRIMARY timestamp is later → PRIMARY is authoritative."""
        primary_ts = datetime(2026, 7, 1, 16, 35, 0)
        backup_ts = datetime(2026, 7, 1, 16, 30, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [primary_ts, backup_ts]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'primary'
        assert result['sync_needed'] is True
        assert result['divergence_seconds'] == 300.0

    def test_backup_newer_is_authoritative(self, authority):
        """BACKUP timestamp is later → BACKUP is authoritative."""
        primary_ts = datetime(2026, 7, 1, 16, 30, 0)
        backup_ts = datetime(2026, 7, 1, 16, 35, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [primary_ts, backup_ts]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'backup'
        assert result['sync_needed'] is True
        assert result['divergence_seconds'] == 300.0

    def test_same_timestamp_returns_unknown(self, authority):
        """If timestamps match → divergence is not a timestamp issue."""
        same_ts = datetime(2026, 7, 1, 16, 30, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [same_ts, same_ts]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'unknown'
        assert result['sync_needed'] is False
        assert result['divergence_seconds'] == 0

    def test_divergence_less_than_threshold_ignored(self, authority):
        """Minor divergence <60s is normal clock drift, ignored."""
        primary_ts = datetime(2026, 7, 1, 16, 30, 30)  # 30s ahead
        backup_ts = datetime(2026, 7, 1, 16, 30, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [primary_ts, backup_ts]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'unknown'
        assert result['sync_needed'] is False
        assert result['divergence_seconds'] == 30.0

    def test_primary_empty_returns_backup_authoritative(self, authority):
        """If PRIMARY database is empty → BACKUP is authoritative."""
        backup_ts = datetime(2026, 7, 1, 16, 30, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [None, backup_ts]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'backup'
        assert result['sync_needed'] is True
        assert result['primary_timestamp'] is None

    def test_backup_empty_returns_primary_authoritative(self, authority):
        """If BACKUP database is empty → PRIMARY is authoritative."""
        primary_ts = datetime(2026, 7, 1, 16, 30, 0)

        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [primary_ts, None]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'primary'
        assert result['sync_needed'] is True
        assert result['backup_timestamp'] is None

    def test_both_empty_returns_unknown(self, authority):
        """If both databases are empty → unknown authority."""
        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = [None, None]

            result = authority.detect_authority("primary.db", "backup.db")

        assert result['authoritative'] == 'unknown'
        assert result['sync_needed'] is False

    def test_error_during_detection_raises(self, authority):
        """If detection fails unexpectedly → raises DatabaseAuthorityError."""
        with patch.object(authority, '_get_latest_timestamp') as mock_get:
            mock_get.side_effect = Exception("Database error")

            with pytest.raises(DatabaseAuthorityError):
                authority.detect_authority("primary.db", "backup.db")


class TestTimestampParsing:
    """Test timestamp parsing logic."""

    def test_parse_iso_timestamp_with_microseconds(self, authority):
        """Parse ISO timestamp with microseconds: 2026-07-01T16:30:00.123456Z"""
        ts_str = "2026-07-01T16:30:00.123456Z"
        result = authority._parse_timestamp(ts_str)

        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 7
        assert result.day == 1
        assert result.hour == 16
        assert result.minute == 30

    def test_parse_iso_timestamp_without_microseconds(self, authority):
        """Parse ISO timestamp without microseconds: 2026-07-01T16:30:00"""
        ts_str = "2026-07-01T16:30:00"
        result = authority._parse_timestamp(ts_str)

        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_parse_iso_timestamp_with_timezone(self, authority):
        """Parse ISO timestamp with timezone: 2026-07-01T16:30:00+00:00"""
        ts_str = "2026-07-01T16:30:00+00:00"
        result = authority._parse_timestamp(ts_str)

        assert isinstance(result, datetime)

    def test_parse_empty_timestamp_returns_none(self, authority):
        """Empty string returns None."""
        result = authority._parse_timestamp("")
        assert result is None

    def test_parse_none_timestamp_returns_none(self, authority):
        """None returns None."""
        result = authority._parse_timestamp(None)
        assert result is None


class TestGetLatestTimestamp:
    """Test database timestamp retrieval."""

    def test_get_latest_timestamp_database_not_found(self, authority):
        """Returns None if database file doesn't exist."""
        result = authority._get_latest_timestamp("/nonexistent/database.db")
        assert result is None

    def test_get_latest_timestamp_empty_database(self, authority):
        """Returns None if database exists but has no data."""
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            # Both tables return None
            mock_cursor.execute.side_effect = [None, None]
            mock_cursor.fetchone.side_effect = [
                {'ts': None},  # account_state empty
                {'ts': None}   # trades empty
            ]

            result = authority._get_latest_timestamp("test.db")

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
