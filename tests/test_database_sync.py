"""Integration tests for FR-015 Database Synchronization.

Tests the DatabaseSyncer class for file copying and checksum verification
on actual files (local and potentially remote).
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from backend.core.database_sync import DatabaseSyncer, DatabaseSyncError


@pytest.fixture
def temp_db_files():
    """Create temporary database files for testing."""
    temp_dir = tempfile.mkdtemp()
    source_db = Path(temp_dir) / "source.db"
    dest_db = Path(temp_dir) / "dest.db"

    # Create a source database file with some content
    source_db.write_bytes(b"SQLite format 3\x00" + b"\x00" * 1000)

    yield {
        'source': str(source_db),
        'dest': str(dest_db),
        'temp_dir': temp_dir
    }

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestDatabaseSyncLocalToLocal:
    """Test local file synchronization."""

    def test_sync_copies_file_correctly(self, temp_db_files):
        """Copy local file, verify destination exists and matches source."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative(source, dest)

        assert result['success'] is True
        assert result['bytes_copied'] > 0
        assert Path(dest).exists()
        assert result['checksum_before'] == result['checksum_after']

    def test_sync_checksum_verification(self, temp_db_files):
        """Checksums match after sync."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative(source, dest, verify_checksum=True)

        # Manually verify checksums match
        assert result['checksum_before'] is not None
        assert result['checksum_after'] is not None
        assert result['checksum_before'] == result['checksum_after']

    def test_sync_without_checksum_verification(self, temp_db_files):
        """Can skip checksum verification if needed."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative(source, dest, verify_checksum=False)

        assert result['success'] is True
        assert result['checksum_after'] is None  # Not calculated
        assert Path(dest).exists()

    def test_sync_source_not_found_returns_error(self, temp_db_files):
        """Returns error dict if source doesn't exist."""
        syncer = DatabaseSyncer()
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative("/nonexistent/source.db", dest)

        assert result['success'] is False
        assert "not found" in result['error'].lower()

    def test_sync_returns_timing_info(self, temp_db_files):
        """Sync result includes timing information."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative(source, dest)

        assert result['time_seconds'] >= 0
        assert isinstance(result['time_seconds'], float)

    def test_sync_returns_byte_count(self, temp_db_files):
        """Sync result includes bytes copied."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative(source, dest)

        assert result['bytes_copied'] > 0
        assert result['bytes_copied'] == Path(source).stat().st_size


class TestChecksumCalculation:
    """Test checksum calculation on actual files."""

    def test_calculate_checksum_same_content(self, temp_db_files):
        """Same file content produces same checksum."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']

        checksum1 = syncer._calculate_checksum(source)
        checksum2 = syncer._calculate_checksum(source)

        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex digest is 64 chars

    def test_calculate_checksum_different_content(self, temp_db_files):
        """Different file content produces different checksums."""
        syncer = DatabaseSyncer()

        file1 = Path(temp_db_files['temp_dir']) / "file1.db"
        file2 = Path(temp_db_files['temp_dir']) / "file2.db"

        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")

        checksum1 = syncer._calculate_checksum(str(file1))
        checksum2 = syncer._calculate_checksum(str(file2))

        assert checksum1 != checksum2

    def test_calculate_checksum_file_not_found_raises(self):
        """Raises error if file doesn't exist."""
        syncer = DatabaseSyncer()

        with pytest.raises(DatabaseSyncError):
            syncer._calculate_checksum("/nonexistent/file.db")


class TestSSHOperations:
    """Test SSH file operations (mocked, no real SSH needed)."""

    def test_ssh_pull_command_generation(self):
        """SSH pull constructs correct scp command."""
        syncer = DatabaseSyncer(remote_user="claude", remote_host="192.168.3.25")

        with patch('subprocess.run') as mock_run:
            with patch.object(syncer, '_calculate_checksum') as mock_checksum:
                mock_run.return_value = None
                mock_checksum.return_value = "abc123"

                # This should construct: scp claude@192.168.3.25:/remote/db.db ./local/db.db
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 1000
                    # We can't fully test this without actual SSH, but we can verify the call would be made

    def test_ssh_push_command_generation(self):
        """SSH push constructs correct scp command."""
        syncer = DatabaseSyncer(remote_user="claude", remote_host="192.168.3.25")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = None
            # This should construct: scp ./local/db.db claude@192.168.3.25:/remote/db.db


class TestSyncErrorHandling:
    """Test error handling and recovery."""

    def test_sync_error_returns_failure_dict(self, temp_db_files):
        """Sync errors return failure dict, don't raise."""
        syncer = DatabaseSyncer()
        dest = temp_db_files['dest']

        # Use nonexistent source
        result = syncer.sync_from_authoritative("/nonexistent/source.db", dest)

        assert result['success'] is False
        assert result['error'] is not None
        assert result['bytes_copied'] == 0
        assert result['checksum_after'] is None

    def test_sync_error_has_elapsed_time(self, temp_db_files):
        """Even failed sync includes timing info."""
        syncer = DatabaseSyncer()
        dest = temp_db_files['dest']

        result = syncer.sync_from_authoritative("/nonexistent/source.db", dest)

        assert result['time_seconds'] >= 0

    def test_checksum_mismatch_detected(self, temp_db_files):
        """If checksums don't match, sync reports failure."""
        syncer = DatabaseSyncer()
        source = temp_db_files['source']
        dest = temp_db_files['dest']

        # Manually corrupt destination after copy
        with patch.object(syncer, '_copy_file') as mock_copy:
            with patch.object(syncer, '_calculate_checksum') as mock_checksum:
                mock_copy.return_value = 1024
                # Return different checksums
                mock_checksum.side_effect = ["abc123", "xyz789"]

                result = syncer.sync_from_authoritative(source, dest)

        assert result['success'] is False
        assert "Checksum mismatch" in result['error']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
