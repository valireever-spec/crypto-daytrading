"""Database Synchronization for HA Recovery (FR-015).

Syncs stale database from authoritative database via local copy or SSH.
"""

import hashlib
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DatabaseSyncError(Exception):
    """Raised when database sync fails."""
    pass


class DatabaseSyncer:
    """Syncs database files between machines."""

    def __init__(self, remote_user: str = "claude", remote_host: Optional[str] = None):
        """
        Initialize syncer.

        Args:
            remote_user: SSH user for remote sync (default: claude)
            remote_host: Remote hostname (e.g., 192.168.3.25). If None, assume local.
        """
        self.remote_user = remote_user
        self.remote_host = remote_host

    def sync_from_authoritative(
        self,
        from_path: str,
        to_path: str,
        verify_checksum: bool = True
    ) -> Dict[str, Any]:
        """
        Copy authoritative database to stale database.

        Supports:
        - Local to local: Direct file copy
        - Remote to local: SSH pull
        - Local to remote: SSH push

        Args:
            from_path: Source database path (authoritative)
            to_path: Destination database path (stale)
            verify_checksum: Whether to verify checksums match

        Returns:
            {
                'success': bool,
                'bytes_copied': int,
                'checksum_before': str,
                'checksum_after': str,
                'time_seconds': float,
                'error': str or None
            }

        Raises:
            DatabaseSyncError: If sync fails
        """
        start_time = time.time()

        try:
            logger.info(f"Starting database sync: {from_path} → {to_path}")

            # Verify source exists
            if not Path(from_path).exists():
                raise DatabaseSyncError(f"Source database not found: {from_path}")

            # Get checksum of source before copy
            checksum_before = self._calculate_checksum(from_path)
            logger.info(f"Source checksum: {checksum_before}")

            # Copy file
            bytes_copied = self._copy_file(from_path, to_path)
            logger.info(f"Copied {bytes_copied} bytes")

            # Verify checksum if requested
            checksum_after = None
            if verify_checksum:
                checksum_after = self._calculate_checksum(to_path)
                logger.info(f"Destination checksum: {checksum_after}")

                if checksum_before != checksum_after:
                    raise DatabaseSyncError(
                        f"Checksum mismatch after sync: "
                        f"{checksum_before} != {checksum_after}"
                    )
                logger.info("✅ Checksums match - sync verified")

            elapsed = time.time() - start_time

            result = {
                'success': True,
                'bytes_copied': bytes_copied,
                'checksum_before': checksum_before,
                'checksum_after': checksum_after,
                'time_seconds': elapsed,
                'error': None
            }

            logger.info(f"✅ Database sync complete: {elapsed:.2f}s")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Database sync failed: {e}")

            return {
                'success': False,
                'bytes_copied': 0,
                'checksum_before': None,
                'checksum_after': None,
                'time_seconds': elapsed,
                'error': str(e)
            }

    def _copy_file(self, from_path: str, to_path: str) -> int:
        """
        Copy file from source to destination.

        Supports:
        - Local files: Direct shutil.copy2
        - Remote files: SSH SCP

        Returns: Number of bytes copied
        """
        # Remote paths contain '@' (user@host:path) or start with hostname:
        from_is_local = '@' not in from_path and not (self.remote_host and from_path.startswith(f"{self.remote_host}:"))
        to_is_local = '@' not in to_path and not (self.remote_host and to_path.startswith(f"{self.remote_host}:"))

        if from_is_local and to_is_local:
            # Local to local
            logger.info(f"Local copy: {from_path} → {to_path}")
            shutil.copy2(from_path, to_path)
            return Path(from_path).stat().st_size

        elif from_is_local and not to_is_local:
            # Local to remote (push)
            logger.info(f"SSH push: {from_path} → {self.remote_host}:{to_path}")
            return self._ssh_push(from_path, to_path)

        elif not from_is_local and to_is_local:
            # Remote to local (pull)
            logger.info(f"SSH pull: {self.remote_host}:{from_path} → {to_path}")
            return self._ssh_pull(from_path, to_path)

        else:
            raise DatabaseSyncError("Both source and destination are remote (not supported)")

    def _ssh_pull(self, remote_path: str, local_path: str) -> int:
        """Copy file from remote machine to local."""
        cmd = [
            "scp",
            "-q",  # Quiet mode
            f"{self.remote_user}@{self.remote_host}:{remote_path}",
            local_path
        ]

        try:
            subprocess.run(cmd, check=True, timeout=30)
            return Path(local_path).stat().st_size
        except subprocess.CalledProcessError as e:
            raise DatabaseSyncError(f"SSH pull failed: {e}")
        except FileNotFoundError:
            raise DatabaseSyncError("scp command not found")

    def _ssh_push(self, local_path: str, remote_path: str) -> int:
        """Copy file from local machine to remote."""
        cmd = [
            "scp",
            "-q",  # Quiet mode
            local_path,
            f"{self.remote_user}@{self.remote_host}:{remote_path}"
        ]

        try:
            subprocess.run(cmd, check=True, timeout=30)
            # Get remote file size via SSH
            cmd_size = [
                "ssh",
                f"{self.remote_user}@{self.remote_host}",
                f"ls -la {remote_path} | awk '{{print $5}}'"
            ]
            result = subprocess.run(cmd_size, capture_output=True, text=True, timeout=10)
            size = int(result.stdout.strip())
            return size
        except (subprocess.CalledProcessError, ValueError) as e:
            raise DatabaseSyncError(f"SSH push failed: {e}")
        except FileNotFoundError:
            raise DatabaseSyncError("scp/ssh commands not found")

    @staticmethod
    def _calculate_checksum(file_path: str) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except IOError as e:
            raise DatabaseSyncError(f"Cannot read file for checksum: {e}")
