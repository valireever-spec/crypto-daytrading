"""Intelligent Circuit Breaker v2: Graceful Degradation & Recovery

Implements:
- Graceful degradation (warn → throttle → halt)
- Automatic recovery (no manual intervention needed)
- Per-stream failure tracking
- Configurable thresholds
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"          # All systems normal, trading allowed
    DEGRADED = "DEGRADED"      # Some systems warning, throttle trading
    OPEN = "OPEN"              # Critical systems down, trading halted


class CircuitBreakerV2:
    """Intelligent circuit breaker with graceful degradation."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recover_timeout: int = 30,
        degraded_threshold: int = 1,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Failures before OPEN state
            recover_timeout: Seconds before allowing recovery attempt
            degraded_threshold: Failures before DEGRADED state
        """
        self.failure_threshold = failure_threshold
        self.recover_timeout = recover_timeout
        self.degraded_threshold = degraded_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.degraded_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None

        # Per-component tracking
        self.component_failures: Dict[str, int] = {}
        self.component_last_failure: Dict[str, float] = {}

    def record_failure(self, component: str = "default", severity: str = "error") -> None:
        """Record a failure.

        Args:
            component: Component name (e.g., "websocket", "rest_api", "database")
            severity: "warning" or "error"
        """
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Track per-component
        self.component_failures[component] = self.component_failures.get(component, 0) + 1
        self.component_last_failure[component] = time.time()

        logger.warning(f"⚠️  Failure recorded: {component} ({severity}) — Total: {self.failure_count}")

        # State transitions
        if self.failure_count >= self.failure_threshold:
            self._open_circuit()
        elif self.failure_count >= self.degraded_threshold:
            self._degrade_circuit()

    def record_success(self, component: str = "default") -> None:
        """Record a success."""
        # Reset counts on success
        self.failure_count = max(0, self.failure_count - 1)
        self.degraded_count = max(0, self.degraded_count - 1)
        self.component_failures[component] = max(0, self.component_failures.get(component, 0) - 1)

        logger.debug(f"✅ Success: {component} — Failures now: {self.failure_count}")

        # Try to recover
        if self.state == CircuitState.OPEN and self.failure_count == 0:
            self._close_circuit()
        elif self.state == CircuitState.DEGRADED and self.failure_count == 0:
            self._close_circuit()

    def _open_circuit(self) -> None:
        """Transition to OPEN state (halt trading)."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
            logger.critical(
                f"🔴 CIRCUIT BREAKER OPEN: {self.failure_count} failures. "
                f"Trading halted. Recovery in {self.recover_timeout}s."
            )

    def _degrade_circuit(self) -> None:
        """Transition to DEGRADED state (throttle trading)."""
        if self.state == CircuitState.CLOSED:
            self.state = CircuitState.DEGRADED
            self.degraded_count = self.failure_count
            logger.warning(
                f"🟡 CIRCUIT BREAKER DEGRADED: {self.failure_count} failures. "
                f"Trading throttled."
            )

    def _close_circuit(self) -> None:
        """Transition to CLOSED state (resume normal operation)."""
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.degraded_count = 0
            logger.info("🟢 CIRCUIT BREAKER CLOSED: All systems normal, resuming trading.")

    def check_auto_recovery(self) -> bool:
        """Check if circuit should automatically recover (for OPEN state)."""
        if self.state != CircuitState.OPEN:
            return False

        if not self.opened_at:
            return False

        elapsed = time.time() - self.opened_at
        if elapsed > self.recover_timeout:
            logger.info(
                f"🔄 Auto-recovery timeout reached ({elapsed:.0f}s > {self.recover_timeout}s), "
                f"attempting to close circuit..."
            )
            # Don't auto-close yet, just allow retry
            return True

        return False

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.DEGRADED:
            # Allow trading but with throttling (every 2nd attempt)
            return (self.failure_count % 2) == 0
        elif self.state == CircuitState.OPEN:
            # Check if recovery is possible
            if self.check_auto_recovery():
                self._close_circuit()
                return True
            return False

        return False

    def get_status(self) -> Dict:
        """Get circuit breaker status."""
        elapsed = None
        if self.opened_at:
            elapsed = time.time() - self.opened_at

        return {
            "state": self.state.value,
            "trading_allowed": self.is_trading_allowed(),
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
            "degraded_count": self.degraded_count,
            "components": self.component_failures,
            "opened_at": datetime.fromtimestamp(self.opened_at).isoformat() if self.opened_at else None,
            "elapsed_seconds": elapsed,
            "auto_recovery_timeout": self.recover_timeout,
        }

    def get_throttle_percentage(self) -> int:
        """Get throttle percentage when DEGRADED (0-100).

        Returns:
            Percentage of trades to reject (0=allow all, 50=reject half, 100=reject all)
        """
        if self.state == CircuitState.DEGRADED:
            # Throttle more as failures increase
            return min(50, self.failure_count * 25)
        elif self.state == CircuitState.OPEN:
            return 100
        return 0


# Global instance
_breaker: Optional[CircuitBreakerV2] = None


def get_circuit_breaker() -> CircuitBreakerV2:
    """Get or create global circuit breaker."""
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreakerV2()
    return _breaker


def init_circuit_breaker(
    failure_threshold: int = 3,
    recover_timeout: int = 30,
) -> CircuitBreakerV2:
    """Initialize global circuit breaker."""
    global _breaker
    _breaker = CircuitBreakerV2(
        failure_threshold=failure_threshold,
        recover_timeout=recover_timeout,
    )
    return _breaker
