"""WebSocket Staleness Detection & Auto-Reconnect Skill.

Monitors price feed staleness and triggers automatic reconnection before
circuit breaker activates. Prevents cascading failures from transient
WebSocket outages.
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StreamHealth:
    """Tracks health of a single WebSocket stream."""
    symbol: str
    last_update_time: float  # epoch seconds
    staleness_secs: float = 0
    reconnect_attempts: int = 0
    last_reconnect_attempt: Optional[float] = None
    is_healthy: bool = True

    def update_staleness(self):
        self.staleness_secs = time.time() - self.last_update_time


class WebSocketStalenessMonitor:
    """Monitors WebSocket price feed staleness and triggers auto-reconnect."""

    # Tunable thresholds (seconds)
    WARN_THRESHOLD = 10.0      # Log warning, start tracking
    CRITICAL_THRESHOLD = 30.0  # Attempt reconnect (increased for low-volume periods)
    BREAKER_THRESHOLD = 60.0   # Let circuit breaker handle it
    MAX_RECONNECT_ATTEMPTS = 3
    BACKOFF_BASE = 2.0  # exponential backoff: 2s, 4s, 8s

    def __init__(self, ws_manager):
        """
        Args:
            ws_manager: WebSocket manager instance (must have reconnect() method)
        """
        self.ws_manager = ws_manager
        self.streams: Dict[str, StreamHealth] = {}
        self.metrics = {
            'staleness_warnings': 0,
            'reconnect_attempts': 0,
            'reconnect_successes': 0,
            'reconnect_failures': 0,
        }

    async def start_monitoring(self, symbols: list):
        """Start background monitor loop."""
        for symbol in symbols:
            self.streams[symbol] = StreamHealth(symbol, time.time())

        logger.info(f"🔍 Starting WebSocket staleness monitor for {len(symbols)} streams: {', '.join(symbols)}")
        await self._monitor_loop()

    async def _monitor_loop(self):
        """Background task: check staleness every 1 second."""
        while True:
            try:
                await self._check_all_streams()
                await asyncio.sleep(1)  # Check every second
            except asyncio.CancelledError:
                logger.info("WebSocket staleness monitor stopped")
                break
            except Exception as e:
                logger.error(f"Staleness monitor error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _check_all_streams(self):
        """Check staleness of all streams, trigger recovery if needed."""
        for symbol, stream in self.streams.items():
            stream.update_staleness()

            # WARN level: log but don't intervene yet
            if stream.staleness_secs > self.WARN_THRESHOLD and not stream.is_healthy:
                logger.warning(
                    f"⚠️  [{symbol}] Price stale: {stream.staleness_secs:.1f}s, "
                    f"reconnect attempts: {stream.reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS}"
                )
                self.metrics['staleness_warnings'] += 1

            # CRITICAL level: attempt recovery
            if stream.staleness_secs > self.CRITICAL_THRESHOLD and stream.is_healthy:
                logger.error(
                    f"🚨 [{symbol}] CRITICAL staleness: {stream.staleness_secs:.1f}s > {self.CRITICAL_THRESHOLD}s, "
                    f"triggering reconnect"
                )
                stream.is_healthy = False  # Mark as unhealthy to start recovery
                await self._attempt_reconnect(symbol, stream)

    async def _attempt_reconnect(self, symbol: str, stream: StreamHealth):
        """Attempt to reconnect a specific stream with backoff."""
        while stream.reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            # Calculate backoff: 2^attempt * base (2s, 4s, 8s)
            backoff_secs = self.BACKOFF_BASE ** stream.reconnect_attempts

            logger.info(
                f"🔄 [{symbol}] Reconnect attempt {stream.reconnect_attempts + 1}/"
                f"{self.MAX_RECONNECT_ATTEMPTS}, waiting {backoff_secs}s"
            )

            await asyncio.sleep(backoff_secs)
            stream.reconnect_attempts += 1
            stream.last_reconnect_attempt = time.time()
            self.metrics['reconnect_attempts'] += 1

            try:
                # Call the WebSocket manager's reconnect method
                await self.ws_manager.reconnect(symbol)

                logger.info(f"✅ [{symbol}] Reconnect successful after {stream.reconnect_attempts} attempts")

                # Reset on success
                stream.is_healthy = True
                stream.reconnect_attempts = 0
                stream.last_update_time = time.time()
                self.metrics['reconnect_successes'] += 1
                return

            except Exception as e:
                logger.warning(f"⚠️  [{symbol}] Reconnect attempt {stream.reconnect_attempts} failed: {e}")

        # Exhausted retries: circuit breaker will handle it
        logger.critical(
            f"❌ [{symbol}] WebSocket unrecoverable after {self.MAX_RECONNECT_ATTEMPTS} attempts, "
            f"deferring to circuit breaker"
        )
        self.metrics['reconnect_failures'] += 1

    def on_price_update(self, symbol: str):
        """Call this whenever a price update arrives for a symbol."""
        if symbol in self.streams:
            self.streams[symbol].last_update_time = time.time()
            self.streams[symbol].is_healthy = True  # Mark healthy again

    def get_status(self) -> Dict:
        """Return current health status (for dashboards/logs)."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'streams': {
                symbol: {
                    'staleness_secs': round(stream.staleness_secs, 2),
                    'is_healthy': stream.is_healthy,
                    'reconnect_attempts': stream.reconnect_attempts,
                    'last_update': datetime.fromtimestamp(stream.last_update_time).isoformat(),
                }
                for symbol, stream in self.streams.items()
            },
            'metrics': self.metrics,
        }
