"""Tier 2 Safeguards: Auto-halt trading if fragility points fail.

This is defensive programming - if any critical system fails, HALT trading
immediately rather than cascade to unlimited losses.
"""

import logging
import time
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class FragilityThresholds:
    """Thresholds for auto-halt triggers."""
    exit_check_failures_threshold = 10  # failures in 60 seconds
    ha_sync_failures_threshold = 5      # failures in 60 seconds
    websocket_stale_threshold = 10      # seconds
    sync_divergence_threshold = 300     # 5 minutes - max time BACKUP can be unsynced


class FragilityCircuitBreaker:
    """Monitor fragility points and halt trading if any fail."""

    def __init__(self, thresholds: FragilityThresholds = FragilityThresholds()):
        self.thresholds = thresholds
        self.halted = False
        self.halt_reason = None
        self.halt_time = None

        # Exit check tracking
        self.exit_failures = []  # [(timestamp, error)]

        # HA sync tracking
        self.sync_failures = []  # [(timestamp, error)]
        self.last_sync_success = time.time()  # Track when BACKUP was last successfully synced

        # WebSocket staleness tracking
        self.websocket_stale_since = None

    def check_exit_failure(self, error: str) -> bool:
        """Record exit check failure, halt if threshold exceeded.

        Returns: True if trading should be halted
        """
        now = time.time()
        self.exit_failures.append((now, error))

        # Clean old failures (>60 seconds)
        cutoff = now - 60
        self.exit_failures = [(t, e) for t, e in self.exit_failures if t > cutoff]

        count = len(self.exit_failures)
        if count > self.thresholds.exit_check_failures_threshold:
            self._halt(f"Exit check failures: {count} in 60s (threshold: {self.thresholds.exit_check_failures_threshold})")
            return True

        if count > 5:  # Warn at 5 failures
            logger.warning(f"⚠️ Exit check failures rising: {count} in 60s")

        return self.halted

    def check_sync_failure(self, error: str) -> bool:
        """Record HA sync failure, halt if threshold exceeded.

        Returns: True if trading should be halted
        """
        now = time.time()
        self.sync_failures.append((now, error))

        # Clean old failures (>60 seconds)
        cutoff = now - 60
        self.sync_failures = [(t, e) for t, e in self.sync_failures if t > cutoff]

        count = len(self.sync_failures)
        if count > self.thresholds.ha_sync_failures_threshold:
            self._halt(f"HA sync failures: {count} in 60s (threshold: {self.thresholds.ha_sync_failures_threshold})")
            return True

        if count > 2:  # Warn at 2 failures
            logger.warning(f"⚠️ HA sync failures rising: {count} in 60s")

        return self.halted

    def check_websocket_staleness(self, stale_duration_seconds: int) -> bool:
        """Check WebSocket staleness, halt if exceeds threshold.

        Returns: True if trading should be halted
        """
        if stale_duration_seconds > self.thresholds.websocket_stale_threshold:
            self._halt(f"WebSocket stale for {stale_duration_seconds}s (threshold: {self.thresholds.websocket_stale_threshold}s)")
            return True

        if stale_duration_seconds > 5:  # Warn if stale >5s
            logger.warning(f"⚠️ WebSocket stale for {stale_duration_seconds}s")

        return self.halted

    def record_sync_success(self):
        """Record successful BACKUP sync."""
        self.last_sync_success = time.time()

    def check_sync_divergence(self) -> bool:
        """Check if BACKUP has been unsynced for too long, halt if exceeded.

        Prevents silent divergence: if PRIMARY keeps trading while BACKUP is unsynced
        for >5 minutes, BACKUP state could be 35+ minutes stale (as documented in
        /tmp/HA_SYNC_BUG_ANALYSIS.md). If PRIMARY crashes during divergence, failover
        uses wrong data and causes overleveraging.

        This ensures: if sync is offline >5 minutes, HALT trading rather than
        accumulate silent divergence.

        Returns: True if trading should be halted
        """
        now = time.time()
        divergence_seconds = now - self.last_sync_success

        if divergence_seconds > self.thresholds.sync_divergence_threshold:
            self._halt(f"BACKUP sync offline for {int(divergence_seconds)}s (threshold: {self.thresholds.sync_divergence_threshold}s) - preventing silent divergence")
            return True

        if divergence_seconds > 180:  # Warn at 3 minutes
            logger.warning(f"⚠️ BACKUP sync offline for {int(divergence_seconds)}s (max allowed: {self.thresholds.sync_divergence_threshold}s)")

        return self.halted

    def is_halted(self) -> bool:
        """Check if trading is halted."""
        return self.halted

    def get_halt_reason(self) -> Optional[str]:
        """Get reason for halt if active."""
        if self.halted:
            elapsed = (datetime.now() - self.halt_time).total_seconds()
            return f"{self.halt_reason} [halted {int(elapsed)}s ago]"
        return None

    def _halt(self, reason: str):
        """Halt trading immediately with reason."""
        if not self.halted:
            self.halted = True
            self.halt_reason = reason
            self.halt_time = datetime.now()
            logger.critical(f"🛑 FRAGILITY CIRCUIT BREAKER TRIGGERED: {reason}")

    def reset(self):
        """Manual reset of halt state (requires human intervention)."""
        if self.halted:
            logger.warning(f"🔄 Fragility circuit breaker RESET (was: {self.halt_reason})")
        self.halted = False
        self.halt_reason = None
        self.halt_time = None
        self.exit_failures = []
        self.sync_failures = []
        self.last_sync_success = time.time()  # Reset divergence timer
        self.websocket_stale_since = None


# Global instance
_circuit_breaker: Optional[FragilityCircuitBreaker] = None


def get_fragility_breaker() -> FragilityCircuitBreaker:
    """Get or create global fragility circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = FragilityCircuitBreaker()
        logger.info("🛡️ Fragility Circuit Breaker initialized (Tier 2 Safeguards)")
    return _circuit_breaker


def should_halt_trading() -> tuple[bool, Optional[str]]:
    """Check if trading should be halted and get reason.

    Returns: (should_halt, reason)
    """
    breaker = get_fragility_breaker()
    return breaker.is_halted(), breaker.get_halt_reason()
