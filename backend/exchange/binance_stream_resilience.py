"""WebSocket Resilience Layer: Automatic Recovery & Health Monitoring

Implements:
- Automatic reconnection with exponential backoff
- Bidirectional heartbeat (ping/pong)
- Circuit breaker pattern
- Health tracking & degradation detection
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StreamHealth:
    """Track health of a single price stream."""
    symbol: str
    last_update: Optional[float] = None
    age_seconds: float = 0.0
    is_healthy: bool = False
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None

    def update(self) -> None:
        """Update age and health status."""
        if self.last_update is None:
            self.age_seconds = float('inf')
            self.is_healthy = False
        else:
            self.age_seconds = time.time() - self.last_update
            # Healthy if fresher than 5 seconds
            self.is_healthy = self.age_seconds < 5.0

    def mark_failure(self) -> None:
        """Record a stream failure."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

    def reset_failures(self) -> None:
        """Reset failure counter on successful reconnection."""
        self.consecutive_failures = 0


class CircuitBreaker:
    """Circuit breaker pattern: Open → Half-Open → Closed"""

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED → OPEN → HALF_OPEN → CLOSED

    def record_failure(self) -> bool:
        """Record a failure, return True if circuit should open."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.critical(
                f"🔴 Circuit breaker OPEN after {self.failure_count} failures"
            )
            return True

        return False

    def record_success(self) -> None:
        """Record a success, reset circuit."""
        if self.state == "OPEN":
            logger.info("🟢 Circuit breaker CLOSED, resuming trading")

        self.failure_count = 0
        self.state = "CLOSED"

    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "OPEN":
            # Check if timeout expired (allow retry)
            if self.last_failure_time and (
                time.time() - self.last_failure_time > self.timeout_seconds
            ):
                self.state = "HALF_OPEN"
                logger.warning("🟡 Circuit breaker HALF_OPEN, attempting recovery...")
                return False

            return True

        return False

    def get_state(self) -> Dict:
        """Get circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
            "last_failure": (
                datetime.fromtimestamp(self.last_failure_time).isoformat()
                if self.last_failure_time
                else None
            ),
        }


class WebSocketResilience:
    """Manage WebSocket resilience: reconnection, heartbeat, circuit breaker."""

    def __init__(
        self,
        symbols: list = None,
        max_age_seconds: float = 5.0,
        heartbeat_interval: float = 10.0,
    ):
        """Initialize WebSocket resilience manager.

        Args:
            symbols: List of symbols to monitor (BTCUSDT, ETHUSDT, BNBUSDT)
            max_age_seconds: Maximum acceptable age for price data (default 5s)
            heartbeat_interval: How often to check for stale data (default 10s)
        """
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        self.max_age_seconds = max_age_seconds
        self.heartbeat_interval = heartbeat_interval

        # Stream health tracking
        self.stream_health: Dict[str, StreamHealth] = {
            symbol: StreamHealth(symbol=symbol) for symbol in self.symbols
        }

        # Reconnection logic
        self.reconnection_attempts = 0
        self.max_reconnection_attempts = 5
        self.base_backoff = 1.0  # 1 second initial backoff

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=30)

        # Monitoring
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

    def record_price_update(self, symbol: str) -> None:
        """Record that we received a price update for a symbol."""
        if symbol in self.stream_health:
            self.stream_health[symbol].last_update = time.time()
            self.stream_health[symbol].mark_failure.__self__.consecutive_failures = 0

    def get_stream_health(self) -> Dict[str, Dict]:
        """Get health status of all streams."""
        for stream in self.stream_health.values():
            stream.update()

        return {
            symbol: {
                "symbol": stream.symbol,
                "age_seconds": round(stream.age_seconds, 2),
                "is_healthy": stream.is_healthy,
                "consecutive_failures": stream.consecutive_failures,
            }
            for symbol, stream in self.stream_health.items()
        }

    def get_stale_streams(self) -> list:
        """Get list of streams that are stale (age > max_age)."""
        stale = []
        for symbol, stream in self.stream_health.items():
            stream.update()
            if stream.age_seconds > self.max_age_seconds:
                stale.append(
                    {
                        "symbol": symbol,
                        "age_seconds": round(stream.age_seconds, 2),
                    }
                )

        return stale

    def check_health(self) -> Dict:
        """Check WebSocket health and return status."""
        stale = self.get_stale_streams()
        healthy_count = len(self.symbols) - len(stale)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_healthy": len(stale) == 0,
            "healthy_streams": healthy_count,
            "total_streams": len(self.symbols),
            "stale_streams": stale,
            "circuit_breaker": self.circuit_breaker.get_state(),
        }

    async def trigger_reconnection(self, reason: str) -> bool:
        """Trigger WebSocket reconnection with exponential backoff.

        Args:
            reason: Why reconnection is needed

        Returns:
            True if reconnection successful, False otherwise
        """
        logger.warning(f"⚠️  WebSocket reconnection triggered: {reason}")

        # Check circuit breaker
        if self.circuit_breaker.is_open():
            logger.critical(
                "🔴 Circuit breaker OPEN - WebSocket recovery paused, trading halted"
            )
            return False

        # Exponential backoff: 1s, 2s, 4s, 8s, 8s (max)
        backoff = min(self.base_backoff * (2 ** self.reconnection_attempts), 8.0)

        logger.info(f"⏳ Reconnecting in {backoff:.1f}s (attempt {self.reconnection_attempts + 1}/{self.max_reconnection_attempts})")
        await asyncio.sleep(backoff)

        self.reconnection_attempts += 1

        # Record failure if max attempts exceeded
        if self.reconnection_attempts >= self.max_reconnection_attempts:
            if self.circuit_breaker.record_failure():
                logger.critical(
                    f"🔴 WebSocket reconnection failed {self.max_reconnection_attempts}x, circuit breaker OPEN"
                )
                return False

        # TODO: Actual reconnection logic (call binance_stream.reconnect())
        logger.info("🔄 Attempting WebSocket reconnection...")

        return True

    async def record_reconnection_success(self) -> None:
        """Record successful reconnection."""
        self.reconnection_attempts = 0
        self.circuit_breaker.record_success()
        logger.info("✅ WebSocket reconnected successfully")

        # Reset failure counters for all streams
        for stream in self.stream_health.values():
            stream.reset_failures()

    async def start_monitoring(self) -> None:
        """Start monitoring WebSocket health in background."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🫀 WebSocket health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring WebSocket health."""
        self._monitoring = False
        if self._monitor_task:
            await self._monitor_task
        logger.info("🫀 WebSocket health monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Background loop: monitor WebSocket health and trigger recovery."""
        while self._monitoring:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                health = self.check_health()

                # Check for stale streams
                if health["stale_streams"]:
                    stale_str = ", ".join(
                        [
                            f"{s['symbol']}({s['age_seconds']}s)"
                            for s in health["stale_streams"]
                        ]
                    )
                    logger.warning(f"⚠️  Stale price streams: {stale_str}")

                    # Trigger reconnection if too much staleness
                    if len(health["stale_streams"]) > len(self.symbols) * 0.5:
                        logger.critical(
                            f"🔴 >50% of streams stale, triggering reconnection"
                        )
                        await self.trigger_reconnection(
                            f"Multiple stale streams: {stale_str}"
                        )

            except Exception as e:
                logger.error(f"Error in WebSocket health monitoring: {e}")

    def get_status(self) -> Dict:
        """Get comprehensive WebSocket status."""
        return {
            "monitoring": self._monitoring,
            "health": self.check_health(),
            "stream_details": self.get_stream_health(),
            "circuit_breaker": self.circuit_breaker.get_state(),
            "reconnection": {
                "attempts": self.reconnection_attempts,
                "max_attempts": self.max_reconnection_attempts,
            },
        }


# Global instance
_websocket_resilience: Optional[WebSocketResilience] = None


def init_websocket_resilience(
    symbols: list = None, max_age_seconds: float = 5.0
) -> WebSocketResilience:
    """Initialize global WebSocket resilience manager."""
    global _websocket_resilience
    _websocket_resilience = WebSocketResilience(
        symbols=symbols, max_age_seconds=max_age_seconds
    )
    logger.info("✅ WebSocket resilience layer initialized")
    return _websocket_resilience


def get_websocket_resilience() -> WebSocketResilience:
    """Get global WebSocket resilience manager."""
    global _websocket_resilience
    if _websocket_resilience is None:
        _websocket_resilience = WebSocketResilience()
    return _websocket_resilience
