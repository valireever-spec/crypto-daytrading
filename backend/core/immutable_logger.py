"""Immutable transaction logging - write-once, append-only, audit-safe."""

import logging
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ImmutableTransactionLogger:
    """
    Write-once transaction log for regulatory compliance and incident investigation.

    Features:
    - Append-only (no deletion, no modification)
    - Automatic archival with timestamps
    - Audit trail for all rotations
    - Hash verification for integrity
    - Never overwrites historical data
    """

    def __init__(
        self,
        log_dir: str = "logs/immutable",
        max_log_size_mb: int = 100,
        active_log_name: str = "trades_active.jsonl",
    ):
        """Initialize immutable logger.

        Args:
            log_dir: Directory for logs (created if not exists)
            max_log_size_mb: Size threshold for automatic archival
            active_log_name: Name of currently-active log file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_log_size = max_log_size_mb * 1024 * 1024  # Convert to bytes
        self.active_log_path = self.log_dir / active_log_name
        self.audit_log_path = self.log_dir / "audit.jsonl"

        logger.info(f"ImmutableTransactionLogger initialized: {self.log_dir}")

    def log_transaction(self, event_type: str, data: Dict[str, Any]) -> str:
        """Log a transaction immutably.

        Args:
            event_type: Type of transaction (TRADE, SIGNAL, DECISION, etc.)
            data: Transaction data (dict)

        Returns:
            Transaction ID (for reference)
        """
        # Create immutable record
        transaction_id = self._generate_id()
        timestamp = datetime.utcnow().isoformat()

        record = {
            "transaction_id": transaction_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "data": data,
            "hash": "",  # Will be calculated
        }

        # Calculate hash for integrity (hash of everything except hash field)
        record_for_hash = {k: v for k, v in record.items() if k != "hash"}
        record["hash"] = self._calculate_hash(
            json.dumps(record_for_hash, sort_keys=True)
        )

        # Write to active log (append-only)
        try:
            with open(self.active_log_path, "a") as f:
                f.write(json.dumps(record) + "\n")

            logger.debug(f"Transaction logged: {event_type} [{transaction_id}]")

            # Check if rotation needed
            self._check_and_rotate()

            return transaction_id

        except Exception as e:
            logger.error(f"CRITICAL: Failed to write immutable log: {e}")
            raise

    def log_audit(self, event: str, details: Dict[str, Any]) -> None:
        """Log audit event (e.g., log rotation, access, deletion attempt).

        Args:
            event: Audit event type
            details: Event details
        """
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "details": details,
        }

        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(audit_record) + "\n")

            logger.info(f"Audit logged: {event}")

        except Exception as e:
            logger.error(f"CRITICAL: Failed to write audit log: {e}")
            raise

    def _check_and_rotate(self) -> None:
        """Check if active log needs rotation and archive if so."""
        try:
            if self.active_log_path.exists():
                size_bytes = self.active_log_path.stat().st_size

                if size_bytes > self.max_log_size:
                    self._rotate_log()

        except Exception as e:
            logger.error(f"Error checking log rotation: {e}")

    def _rotate_log(self) -> None:
        """Archive active log and start new one (append-only rotation)."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_name = f"trades_archive_{timestamp}.jsonl"
            archive_path = self.log_dir / archive_name

            # Move active log to archive (immutable)
            self.active_log_path.rename(archive_path)

            # Make archive read-only
            archive_path.chmod(0o444)

            # Log rotation in audit trail
            self.log_audit(
                "LOG_ROTATION",
                {
                    "archived_as": archive_name,
                    "size_mb": self.active_log_path.stat().st_size / (1024 * 1024)
                    if self.active_log_path.exists()
                    else 0,
                },
            )

            logger.info(f"Log rotated: {archive_name} (now read-only)")

        except Exception as e:
            logger.error(f"CRITICAL: Failed to rotate log: {e}")
            raise

    def verify_integrity(self, log_file: Optional[Path] = None) -> bool:
        """Verify log file integrity by checking all hashes.

        Args:
            log_file: Path to log file (uses active if not specified)

        Returns:
            True if all hashes valid, False otherwise
        """
        target_file = log_file or self.active_log_path

        if not target_file.exists():
            return True

        try:
            with open(target_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        record = json.loads(line)
                        stored_hash = record.get("hash", "")
                        record_for_hash = {
                            k: v for k, v in record.items() if k != "hash"
                        }
                        calculated_hash = self._calculate_hash(
                            json.dumps(record_for_hash, sort_keys=True)
                        )

                        if stored_hash != calculated_hash:
                            logger.error(
                                f"Hash mismatch at line {line_num}: {target_file}"
                            )
                            return False

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON at line {line_num}: {e}")
                        return False

            logger.info(f"Integrity check passed: {target_file}")
            return True

        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            return False

    def prevent_deletion(self) -> None:
        """Make all archived logs read-only to prevent accidental deletion."""
        try:
            for archive_file in self.log_dir.glob("trades_archive_*.jsonl"):
                archive_file.chmod(0o444)
                logger.info(f"Protected (read-only): {archive_file.name}")

        except Exception as e:
            logger.error(f"Failed to protect archives: {e}")

    @staticmethod
    def _generate_id() -> str:
        """Generate unique transaction ID."""
        timestamp = datetime.utcnow().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]

    @staticmethod
    def _calculate_hash(data: str) -> str:
        """Calculate SHA256 hash of data."""
        return hashlib.sha256(data.encode()).hexdigest()

    def get_transaction_count(self) -> int:
        """Get total number of logged transactions."""
        count = 0
        try:
            # Count active log
            if self.active_log_path.exists():
                with open(self.active_log_path, "r") as f:
                    count += sum(1 for _ in f)

            # Count archived logs
            for archive_file in self.log_dir.glob("trades_archive_*.jsonl"):
                with open(archive_file, "r") as f:
                    count += sum(1 for _ in f)

            return count

        except Exception as e:
            logger.error(f"Error counting transactions: {e}")
            return 0

    def get_log_status(self) -> Dict[str, Any]:
        """Get status of immutable log system."""
        return {
            "active_log": str(self.active_log_path),
            "active_log_size_mb": (
                self.active_log_path.stat().st_size / (1024 * 1024)
                if self.active_log_path.exists()
                else 0
            ),
            "archived_logs": len(list(self.log_dir.glob("trades_archive_*.jsonl"))),
            "total_transactions": self.get_transaction_count(),
            "integrity_valid": self.verify_integrity(),
            "max_log_size_mb": self.max_log_size / (1024 * 1024),
            "directory": str(self.log_dir),
        }


# Global instance
_immutable_logger: Optional[ImmutableTransactionLogger] = None


def get_immutable_logger() -> ImmutableTransactionLogger:
    """Get or create global immutable logger."""
    global _immutable_logger
    if _immutable_logger is None:
        _immutable_logger = ImmutableTransactionLogger()
    return _immutable_logger
