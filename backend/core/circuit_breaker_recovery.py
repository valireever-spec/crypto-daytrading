"""Circuit breaker state persistence and manual recovery.

Skill #5: Persist CB state to disk; enable manual reset without restart.

Benefits:
- Can reset CB without full restart (5 min vs 2+ hours downtime)
- Audit trail: every CB trip logged (reason, timestamp, duration)
- Faster recovery: reset endpoint + monitoring dashboard
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class CircuitBreakerRecovery:
    """Manage CB state persistence and recovery."""

    def __init__(self, state_file: str = "data/circuit_breaker_state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file = self.state_file.parent / "circuit_breaker_history.jsonl"

        # In-memory state
        self.current_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.trip_reason = None
        self.trip_timestamp = None
        self.trip_count = 0
        self.last_recovery_time = None

    def log_trip(self, reason: str, failure_count: int = 0) -> None:
        """Log a CB trip with reason and metadata."""
        self.current_state = "OPEN"
        self.trip_reason = reason
        self.trip_timestamp = datetime.utcnow()
        self.trip_count += 1

        # Persist to disk
        state_data = {
            "state": self.current_state,
            "reason": reason,
            "trip_count": self.trip_count,
            "trip_timestamp": self.trip_timestamp.isoformat(),
            "failure_count": failure_count,
        }

        try:
            with open(self.state_file, "w") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist CB state: {e}")

        # Append to history log
        try:
            history_entry = {
                "timestamp": self.trip_timestamp.isoformat(),
                "state": "OPEN",
                "reason": reason,
                "trip_count": self.trip_count,
                "failure_count": failure_count,
            }
            with open(self.history_file, "a") as f:
                f.write(json.dumps(history_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write CB history: {e}")

        logger.critical(
            f"🔴 CIRCUIT BREAKER TRIPPED (#{self.trip_count}): {reason}"
        )

    def log_recovery(self) -> None:
        """Log a CB recovery (closed again)."""
        if self.trip_timestamp:
            recovery_duration = (datetime.utcnow() - self.trip_timestamp).total_seconds()
        else:
            recovery_duration = 0

        self.current_state = "CLOSED"
        self.last_recovery_time = datetime.utcnow()

        # Persist to disk
        state_data = {
            "state": self.current_state,
            "reason": None,
            "trip_count": self.trip_count,
            "recovery_timestamp": self.last_recovery_time.isoformat(),
            "recovery_duration_seconds": recovery_duration,
        }

        try:
            with open(self.state_file, "w") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist CB state: {e}")

        # Append to history
        try:
            history_entry = {
                "timestamp": self.last_recovery_time.isoformat(),
                "state": "CLOSED",
                "reason": "Automatic recovery",
                "recovery_duration_seconds": recovery_duration,
            }
            with open(self.history_file, "a") as f:
                f.write(json.dumps(history_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write CB history: {e}")

        logger.info(
            f"✅ CIRCUIT BREAKER RECOVERED after {recovery_duration:.0f}s"
        )

    def manual_reset(self, reason: str) -> bool:
        """Manually reset CB without restart (admin endpoint).

        Args:
            reason: Why the reset was triggered (e.g., "admin override", "resolved issue")

        Returns:
            True if reset successful, False otherwise
        """
        try:
            if self.current_state != "OPEN":
                logger.warning(
                    f"Cannot reset CB: not in OPEN state (current: {self.current_state})"
                )
                return False

            old_state = self.current_state
            self.current_state = "CLOSED"
            reset_time = datetime.utcnow()

            # Persist reset
            state_data = {
                "state": "CLOSED",
                "reason": None,
                "manually_reset": True,
                "reset_timestamp": reset_time.isoformat(),
                "reset_reason": reason,
                "trip_count": self.trip_count,
            }

            with open(self.state_file, "w") as f:
                json.dump(state_data, f, indent=2)

            # Log to history
            history_entry = {
                "timestamp": reset_time.isoformat(),
                "state": "CLOSED",
                "reason": f"Manual reset: {reason}",
                "manually_reset": True,
            }
            with open(self.history_file, "a") as f:
                f.write(json.dumps(history_entry) + "\n")

            logger.critical(
                f"⚙️  CIRCUIT BREAKER MANUALLY RESET: {old_state} → CLOSED "
                f"(reason: {reason})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to manually reset CB: {e}")
            return False

    def load_from_disk(self) -> None:
        """Load CB state from persistent storage."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    data = json.load(f)

                self.current_state = data.get("state", "CLOSED")
                self.trip_reason = data.get("reason")
                self.trip_count = data.get("trip_count", 0)

                if data.get("trip_timestamp"):
                    self.trip_timestamp = datetime.fromisoformat(
                        data["trip_timestamp"]
                    )

                if data.get("recovery_timestamp"):
                    self.last_recovery_time = datetime.fromisoformat(
                        data["recovery_timestamp"]
                    )

                logger.info(
                    f"CB state loaded from disk: {self.current_state} "
                    f"(trips: {self.trip_count})"
                )
        except Exception as e:
            logger.error(f"Failed to load CB state from disk: {e}")

    def get_stats(self) -> Dict:
        """Get current CB statistics and history."""
        stats = {
            "current_state": self.current_state,
            "trip_count": self.trip_count,
            "trip_reason": self.trip_reason,
            "trip_timestamp": self.trip_timestamp.isoformat() if self.trip_timestamp else None,
            "last_recovery_time": (
                self.last_recovery_time.isoformat()
                if self.last_recovery_time
                else None
            ),
        }

        # Add recent history (last 10 entries)
        recent_history = []
        try:
            if self.history_file.exists():
                lines = self.history_file.read_text().strip().split("\n")
                for line in lines[-10:]:
                    if line:
                        recent_history.append(json.loads(line))
        except Exception as e:
            logger.debug(f"Failed to read history: {e}")

        stats["recent_history"] = recent_history
        return stats

    def is_open(self) -> bool:
        """Check if CB is currently open (trading disabled)."""
        return self.current_state == "OPEN"

    def get_uptime_since_last_trip(self) -> Optional[float]:
        """Get seconds since CB last tripped (or None if currently open)."""
        if self.current_state == "OPEN":
            return None
        if not self.trip_timestamp:
            return None
        return (datetime.utcnow() - self.trip_timestamp).total_seconds()


# Global instance
_cb_recovery: Optional[CircuitBreakerRecovery] = None


def init_circuit_breaker_recovery(
    state_file: str = "data/circuit_breaker_state.json",
) -> CircuitBreakerRecovery:
    """Initialize CB recovery manager."""
    global _cb_recovery
    if _cb_recovery is None:
        _cb_recovery = CircuitBreakerRecovery(state_file)
        _cb_recovery.load_from_disk()  # Load previous state
    return _cb_recovery


def get_circuit_breaker_recovery() -> Optional[CircuitBreakerRecovery]:
    """Get CB recovery manager."""
    return _cb_recovery
