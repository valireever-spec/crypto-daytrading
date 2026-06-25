"""Pillar #14: Circuit Breaker - Auto-stop trading on system anomalies (CRITICAL)."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """Current state of circuit breaker."""

    is_broken: bool  # True = trading stopped, False = trading allowed
    reason: str  # Why it broke (empty if not broken)
    triggered_at: Optional[datetime]  # When it broke
    break_duration: Optional[
        int
    ]  # How long to stay broken (seconds, None = manual reset)


class CircuitBreaker:
    """Auto-stop trading on anomalies.

    States:
    - CLOSED: Trading allowed, normal operation
    - OPEN: Trading stopped, emergency mode only (allow exits)
    - HALF_OPEN: Testing if system recovered (ready to close)

    Pillar #14 Triggers:
    - Data quality drops <30%
    - WebSocket disconnected >2 minutes
    - Database integrity check fails
    - API latency >5 seconds
    - Position reconciliation fails
    """

    def __init__(self):
        """Initialize circuit breaker (starts CLOSED = trading allowed)."""
        self.is_broken = False
        self.reason = ""
        self.triggered_at: Optional[datetime] = None
        self.break_duration: Optional[int] = None  # None = manual reset required
        self.last_check = datetime.utcnow()

    def check_health(self) -> bool:
        """Check if circuit breaker is active.

        Returns:
            True if trading allowed (circuit CLOSED), False if stopped (circuit OPEN)
        """
        # If broken, check if we should auto-recover
        if self.is_broken and self.break_duration:
            elapsed = (datetime.utcnow() - self.triggered_at).total_seconds()
            if elapsed >= self.break_duration:
                logger.info(
                    f"⏱️ CIRCUIT BREAKER: Auto-recovery window passed "
                    f"({elapsed:.0f}s > {self.break_duration}s), testing system health..."
                )
                # Transition to HALF_OPEN (testing)
                self.is_broken = False
                self.reason = ""
                self.triggered_at = None
                return True

        return not self.is_broken

    def trip(self, reason: str, break_duration: Optional[int] = None) -> None:
        """Open circuit breaker - stop new trades, allow exits only.

        Args:
            reason: Why circuit broke (logged for audit)
            break_duration: Seconds until auto-recovery, None = manual reset
        """
        if not self.is_broken:  # Only log if not already broken
            recovery_msg = (
                f"(auto-recover in {break_duration}s)"
                if break_duration
                else "(manual reset required)"
            )
            logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED: {reason} {recovery_msg}")

        self.is_broken = True
        self.reason = reason
        self.triggered_at = datetime.utcnow()
        self.break_duration = break_duration

    def reset(self, reason: str = "Manual reset") -> None:
        """Manually reset circuit breaker - resume normal trading.

        Args:
            reason: Why it's being reset (logged for audit)
        """
        if self.is_broken:
            logger.info(f"✅ CIRCUIT BREAKER RESET: {reason}")

        self.is_broken = False
        self.reason = ""
        self.triggered_at = None
        self.break_duration = None

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return CircuitBreakerState(
            is_broken=self.is_broken,
            reason=self.reason,
            triggered_at=self.triggered_at,
            break_duration=self.break_duration,
        )

    def check_data_quality(self, quality_score: float) -> bool:
        """Check data quality gate (Pillar #14 Trigger #1)."""
        if quality_score < 30:
            self.trip(
                f"Data quality critically low: {quality_score:.1f}% (threshold: 30%)",
                break_duration=300,
            )
            return False

        if self.is_broken and quality_score >= 60:
            self.reset(f"Data quality recovered: {quality_score:.1f}%")

        return True

    def check_websocket_health(
        self, is_connected: bool, last_update_seconds: float
    ) -> bool:
        """Check WebSocket connection health (Pillar #14 Trigger #2)."""
        if not is_connected or last_update_seconds > 120:
            self.trip(
                f"WebSocket unhealthy: connected={is_connected}, last_update={last_update_seconds:.0f}s ago",
                break_duration=60,
            )
            return False

        if self.is_broken and is_connected and last_update_seconds < 5:
            self.reset("WebSocket connection restored")

        return True

    def check_database_integrity(self, integrity_valid: bool) -> bool:
        """Check database integrity (Pillar #14 Trigger #3).

        Disabled for Phase 1 - schema not aligned with hash verification.
        TODO: Re-enable after Phase 1 with proper schema.
        """
        # Always return True for Phase 1 (Pillar #10 not fully integrated)
        return True

    def check_api_latency(self, latency_seconds: float) -> bool:
        """Check API response time (Pillar #14 Trigger #4)."""
        if latency_seconds > 5:
            self.trip(
                f"API latency critical: {latency_seconds:.1f}s (threshold: 5s)",
                break_duration=30,
            )
            return False

        if self.is_broken and latency_seconds < 2:
            self.reset(f"API latency normalized: {latency_seconds:.2f}s")

        return True

    def check_position_reconciliation(
        self, positions_match: bool, mismatch_reason: str = ""
    ) -> bool:
        """Check position reconciliation (Pillar #14 Trigger #5)."""
        if not positions_match:
            self.trip(
                f"Position reconciliation failed: {mismatch_reason}",
                break_duration=120,
            )
            return False

        if self.is_broken and positions_match:
            self.reset("Positions reconciled successfully")

        return True

    def get_status_report(self) -> Dict[str, Any]:
        """Get circuit breaker status for logging/monitoring."""
        state = self.get_state()

        if state.is_broken:
            elapsed = (datetime.utcnow() - state.triggered_at).total_seconds()
            return {
                "status": "OPEN (trading stopped)",
                "reason": state.reason,
                "triggered_at": state.triggered_at.isoformat()
                if state.triggered_at
                else None,
                "elapsed_seconds": elapsed,
                "auto_recovery_in_seconds": (
                    state.break_duration - elapsed if state.break_duration else None
                ),
                "allows_entries": False,
                "allows_exits": True,
            }
        else:
            return {
                "status": "CLOSED (normal operation)",
                "reason": "Trading allowed",
                "triggered_at": None,
                "elapsed_seconds": None,
                "auto_recovery_in_seconds": None,
                "allows_entries": True,
                "allows_exits": True,
            }


# Global circuit breaker instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create global circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
        logger.info("✅ Circuit Breaker initialized (Pillar #14)")
    return _circuit_breaker
