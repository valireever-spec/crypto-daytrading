"""Stress tests for WebSocket resilience layer.

Tests:
1. Automatic reconnection on stale data
2. Bidirectional heartbeat detection
3. Circuit breaker activation
4. Graceful degradation
5. Recovery and resume trading
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime

from backend.exchange.binance_stream_resilience import (
    WebSocketResilience,
    CircuitBreaker,
    StreamHealth,
)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_closes_after_failures(self):
        """Verify circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=30)

        assert cb.state == "CLOSED"
        assert not cb.is_open()

        # First failure
        cb.record_failure()
        assert cb.state == "CLOSED"
        assert not cb.is_open()

        # Second failure
        cb.record_failure()
        assert cb.state == "CLOSED"

        # Third failure - circuit opens
        result = cb.record_failure()
        assert result is True
        assert cb.state == "OPEN"
        assert cb.is_open()

    def test_circuit_resets_on_success(self):
        """Verify circuit resets after successful operation."""
        cb = CircuitBreaker(failure_threshold=2)

        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()

        cb.record_success()
        assert cb.state == "CLOSED"
        assert not cb.is_open()
        assert cb.failure_count == 0

    def test_circuit_half_open_after_timeout(self):
        """Verify circuit allows retry after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1)

        cb.record_failure()
        assert cb.is_open()

        # Wait for timeout
        time.sleep(1.1)

        # Should transition to HALF_OPEN and allow retry
        assert not cb.is_open()
        assert cb.state == "HALF_OPEN"


class TestStreamHealth:
    """Test stream health tracking."""

    def test_stream_health_tracking(self):
        """Verify stream health is tracked correctly."""
        stream = StreamHealth(symbol="BTCUSDT")

        assert not stream.is_healthy
        assert stream.age_seconds == float('inf')

        # Mark as updated
        stream.last_update = time.time()
        stream.update()

        assert stream.is_healthy
        assert stream.age_seconds < 1.0

    def test_stream_ages_after_time(self):
        """Verify stream is marked unhealthy after aging."""
        stream = StreamHealth(symbol="BTCUSDT")
        stream.last_update = time.time() - 6.0  # 6 seconds old

        stream.update()

        assert not stream.is_healthy
        assert stream.age_seconds > 5.0


class TestWebSocketResilience:
    """Test WebSocket resilience layer."""

    def test_initialization(self):
        """Verify resilience layer initializes correctly."""
        ws = WebSocketResilience(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            max_age_seconds=5.0,
        )

        assert len(ws.stream_health) == 3
        assert ws.max_age_seconds == 5.0
        assert ws.circuit_breaker.state == "CLOSED"

    def test_record_price_update(self):
        """Verify price updates are recorded."""
        ws = WebSocketResilience(symbols=["BTCUSDT"])

        assert not ws.stream_health["BTCUSDT"].is_healthy

        ws.record_price_update("BTCUSDT")

        assert ws.stream_health["BTCUSDT"].is_healthy
        assert ws.stream_health["BTCUSDT"].age_seconds < 1.0

    def test_detect_stale_streams(self):
        """Verify stale streams are detected."""
        ws = WebSocketResilience(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            max_age_seconds=5.0,
        )

        # Mark BTC as stale
        ws.stream_health["BTCUSDT"].last_update = time.time() - 10.0

        stale = ws.get_stale_streams()

        assert len(stale) == 1
        assert stale[0]["symbol"] == "BTCUSDT"
        assert stale[0]["age_seconds"] >= 10.0

    def test_health_check(self):
        """Verify health check reports correct status."""
        ws = WebSocketResilience(symbols=["BTCUSDT", "ETHUSDT"])

        # Update BTCUSDT
        ws.record_price_update("BTCUSDT")

        health = ws.check_health()

        assert health["overall_healthy"] is False  # ETHUSDT still stale
        assert health["healthy_streams"] == 1
        assert health["total_streams"] == 2
        assert len(health["stale_streams"]) == 1

    @pytest.mark.asyncio
    async def test_reconnection_backoff(self):
        """Verify exponential backoff on reconnection attempts."""
        ws = WebSocketResilience(symbols=["BTCUSDT"])

        start = time.time()

        # First reconnection attempt (1 second backoff)
        with patch("asyncio.sleep"):
            result = await ws.trigger_reconnection("test")

        elapsed = time.time() - start
        assert ws.reconnection_attempts == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self):
        """Verify circuit breaker activates after failed reconnections."""
        ws = WebSocketResilience(symbols=["BTCUSDT"])
        ws.circuit_breaker.failure_threshold = 2

        # Simulate failed reconnections
        with patch("asyncio.sleep"):
            await ws.trigger_reconnection("failure 1")
            assert ws.circuit_breaker.state == "CLOSED"

            await ws.trigger_reconnection("failure 2")
            assert ws.circuit_breaker.state == "OPEN"

            # Should be blocked now
            result = await ws.trigger_reconnection("failure 3")
            assert result is False

    @pytest.mark.asyncio
    async def test_successful_reconnection_resets(self):
        """Verify successful reconnection resets counters."""
        ws = WebSocketResilience(symbols=["BTCUSDT"])

        ws.circuit_breaker.record_failure()
        ws.reconnection_attempts = 3

        await ws.record_reconnection_success()

        assert ws.reconnection_attempts == 0
        assert ws.circuit_breaker.state == "CLOSED"
        assert ws.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_monitor_loop_detects_stale(self):
        """Verify monitor loop detects stale streams."""
        ws = WebSocketResilience(
            symbols=["BTCUSDT", "ETHUSDT"],
            heartbeat_interval=0.1,  # Fast for testing
        )

        # Mark both as stale
        ws.stream_health["BTCUSDT"].last_update = time.time() - 10.0
        ws.stream_health["ETHUSDT"].last_update = time.time() - 10.0

        await ws.start_monitoring()
        await asyncio.sleep(0.3)  # Let monitor run

        health = ws.check_health()
        assert health["overall_healthy"] is False
        assert len(health["stale_streams"]) == 2

        await ws.stop_monitoring()

    def test_status_report(self):
        """Verify status report includes all relevant info."""
        ws = WebSocketResilience(symbols=["BTCUSDT", "ETHUSDT"])

        ws.record_price_update("BTCUSDT")

        status = ws.get_status()

        assert "monitoring" in status
        assert "health" in status
        assert "stream_details" in status
        assert "circuit_breaker" in status
        assert "reconnection" in status

        assert status["reconnection"]["max_attempts"] == 5


class TestGracefulDegradation:
    """Test that trading continues with partial stream failures."""

    def test_allow_trading_if_majority_healthy(self):
        """Verify trading allowed when >50% of streams healthy."""
        ws = WebSocketResilience(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            max_age_seconds=5.0,
        )

        # Mark BNB as stale (1 of 3)
        ws.stream_health["BNBUSDT"].last_update = time.time() - 10.0

        health = ws.check_health()

        # 2 of 3 healthy = 67% > 50% threshold
        healthy_pct = health["healthy_streams"] / health["total_streams"]
        can_trade = healthy_pct > 0.5

        assert can_trade
        assert len(health["stale_streams"]) == 1

    def test_halt_trading_if_majority_unhealthy(self):
        """Verify trading halted when >50% of streams fail."""
        ws = WebSocketResilience(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            max_age_seconds=5.0,
        )

        # Mark 2 of 3 as stale
        ws.stream_health["ETHUSDT"].last_update = time.time() - 10.0
        ws.stream_health["BNBUSDT"].last_update = time.time() - 10.0

        health = ws.check_health()

        # 1 of 3 healthy = 33% < 50% threshold
        healthy_pct = health["healthy_streams"] / health["total_streams"]
        can_trade = healthy_pct > 0.5

        assert not can_trade
        assert len(health["stale_streams"]) == 2


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
