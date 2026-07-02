"""Unit tests for Circuit Breaker v2 with graceful degradation."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from backend.core.circuit_breaker_v2 import CircuitBreakerV2, CircuitBreakerState


def test_circuit_breaker_initialization():
    """Test CircuitBreaker v2 initialization."""
    cb = CircuitBreakerV2(failure_threshold=5, recover_timeout=20)
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0
    assert cb.failure_threshold == 5
    assert cb.recover_timeout == 20
    assert cb.trading_allowed == True


def test_circuit_breaker_failure_count():
    """Test recording failures."""
    cb = CircuitBreakerV2(failure_threshold=3)
    assert cb.failure_count == 0

    cb.record_failure("component1")
    assert cb.failure_count == 1

    cb.record_failure("component2")
    assert cb.failure_count == 2


def test_circuit_breaker_closed_to_degraded():
    """Test transition from CLOSED to DEGRADED state."""
    cb = CircuitBreakerV2(failure_threshold=3)
    assert cb.state == CircuitBreakerState.CLOSED

    # Record failures
    cb.record_failure("api")
    cb.record_failure("websocket")

    # At 2 failures, should still be CLOSED
    assert cb.state == CircuitBreakerState.CLOSED

    # At threshold, should move to DEGRADED
    cb.record_failure("database")
    assert cb.state == CircuitBreakerState.DEGRADED
    assert cb.trading_allowed == True  # Still trading but at reduced capacity


def test_circuit_breaker_degraded_to_open():
    """Test transition from DEGRADED to OPEN state."""
    cb = CircuitBreakerV2(failure_threshold=3)

    # Record failures to reach DEGRADED
    cb.record_failure("api")
    cb.record_failure("websocket")
    cb.record_failure("database")
    assert cb.state == CircuitBreakerState.DEGRADED

    # More failures move to OPEN
    cb.record_failure("execution")
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.trading_allowed == False


def test_circuit_breaker_auto_recovery():
    """Test automatic recovery after timeout."""
    cb = CircuitBreakerV2(failure_threshold=3, recover_timeout=1)

    # Move to OPEN state
    cb.record_failure("api")
    cb.record_failure("websocket")
    cb.record_failure("database")
    cb.record_failure("execution")
    assert cb.state == CircuitBreakerState.OPEN

    # Wait for recovery timeout
    import time
    time.sleep(1.5)

    # Manual check to see if recovery triggered
    cb.check_recovery()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0


def test_circuit_breaker_trading_allowed_degraded():
    """Test trading is allowed in DEGRADED state (with reduced capacity)."""
    cb = CircuitBreakerV2(failure_threshold=3)

    # Move to DEGRADED
    cb.record_failure("api")
    cb.record_failure("websocket")
    cb.record_failure("database")

    assert cb.state == CircuitBreakerState.DEGRADED
    assert cb.trading_allowed == True
    assert cb.get_degradation_level() == 0.5  # 50% capacity


def test_circuit_breaker_trading_blocked_open():
    """Test trading is blocked in OPEN state."""
    cb = CircuitBreakerV2(failure_threshold=3)

    # Move to OPEN
    for i in range(4):
        cb.record_failure(f"component{i}")

    assert cb.state == CircuitBreakerState.OPEN
    assert cb.trading_allowed == False


def test_circuit_breaker_per_component_failures():
    """Test tracking failures per component."""
    cb = CircuitBreakerV2(failure_threshold=10)

    cb.record_failure("websocket")
    cb.record_failure("websocket")
    cb.record_failure("api")
    cb.record_failure("database")

    assert cb.get_component_failures("websocket") == 2
    assert cb.get_component_failures("api") == 1
    assert cb.get_component_failures("database") == 1


def test_circuit_breaker_health_status():
    """Test getting health status."""
    cb = CircuitBreakerV2(failure_threshold=5)

    health = cb.get_health()
    assert health["state"] == "CLOSED"
    assert health["trading_allowed"] == True
    assert health["failure_count"] == 0

    # Move to DEGRADED
    for i in range(5):
        cb.record_failure(f"component{i}")

    health = cb.get_health()
    assert health["state"] == "DEGRADED"
    assert health["degradation_level"] == 0.5


def test_circuit_breaker_reset():
    """Test manual reset of circuit breaker."""
    cb = CircuitBreakerV2(failure_threshold=3)

    # Move to OPEN
    for i in range(4):
        cb.record_failure(f"component{i}")

    assert cb.state == CircuitBreakerState.OPEN

    # Reset
    cb.reset()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0
    assert cb.trading_allowed == True


def test_circuit_breaker_degradation_levels():
    """Test different degradation levels."""
    cb = CircuitBreakerV2(failure_threshold=10)

    # CLOSED: 0% degradation
    assert cb.get_degradation_level() == 0.0

    # At threshold: 50% degradation
    for i in range(10):
        cb.record_failure(f"component{i}")
    assert cb.state == CircuitBreakerState.DEGRADED
    assert cb.get_degradation_level() == 0.5

    # OPEN: 100% degradation
    cb.record_failure("final")
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.get_degradation_level() == 1.0


def test_circuit_breaker_failure_tracking():
    """Test detailed failure tracking."""
    cb = CircuitBreakerV2(failure_threshold=5)

    failures = []
    cb.record_failure("websocket")
    failures = cb.get_failures_log()
    assert len(failures) == 1
    assert failures[0]["component"] == "websocket"


def test_circuit_breaker_opened_at_timestamp():
    """Test tracking when circuit breaker opened."""
    cb = CircuitBreakerV2(failure_threshold=3)

    # Move to OPEN
    for i in range(4):
        cb.record_failure(f"component{i}")

    assert cb.state == CircuitBreakerState.OPEN
    assert cb.opened_at is not None
    assert isinstance(cb.opened_at, datetime)
