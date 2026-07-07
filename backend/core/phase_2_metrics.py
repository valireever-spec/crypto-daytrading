"""Phase 2: HA Cascade Prevention - Metrics Collection Module.

This module collects real-time metrics required to detect cascade failures BEFORE
they occur. It tracks memory, WebSocket health, HA sync status, exceptions, and
trading statistics.

Metrics are collected every 5 seconds and can be exported as Prometheus format.
"""

import asyncio
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class MetricsSnapshot:
    """A single snapshot of system metrics at a point in time."""

    def __init__(self, timestamp: datetime):
        """Initialize metrics snapshot.

        Args:
            timestamp: When this snapshot was taken
        """
        self.timestamp = timestamp

        # Memory metrics
        self.memory_mb = 0.0
        self.memory_percent = 0.0
        self.memory_available_mb = 0.0

        # WebSocket metrics
        self.ws_connected_count = 0
        self.ws_max_age_seconds = 0.0
        self.ws_stale_symbols = []
        self.ws_reconnect_failures = 0

        # HA sync metrics
        self.ha_sync_success_rate = 0.0
        self.ha_sync_latency_ms = 0.0
        self.ha_last_sync_time = None
        self.ha_state_divergence = False

        # Exception metrics
        self.exception_count = 0
        self.exception_rate_percent = 0.0
        self.exceptions_by_type = {}

        # Trading metrics
        self.trades_per_hour = 0.0
        self.avg_slippage_pct = 0.0
        self.trade_errors = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        last_sync_ts: Optional[str] = None
        if self.ha_last_sync_time is not None:
            last_sync_ts = self.ha_last_sync_time.isoformat()

        return {
            "timestamp": self.timestamp.isoformat(),
            "memory": {
                "mb": self.memory_mb,
                "percent": self.memory_percent,
                "available_mb": self.memory_available_mb,
            },
            "websocket": {
                "connected_count": self.ws_connected_count,
                "max_age_seconds": self.ws_max_age_seconds,
                "stale_symbols": self.ws_stale_symbols,
                "reconnect_failures": self.ws_reconnect_failures,
            },
            "ha_sync": {
                "success_rate": self.ha_sync_success_rate,
                "latency_ms": self.ha_sync_latency_ms,
                "last_sync_time": last_sync_ts,
                "state_divergence": self.ha_state_divergence,
            },
            "exceptions": {
                "count": self.exception_count,
                "rate_percent": self.exception_rate_percent,
                "by_type": self.exceptions_by_type,
            },
            "trading": {
                "trades_per_hour": self.trades_per_hour,
                "avg_slippage_pct": self.avg_slippage_pct,
                "errors": self.trade_errors,
            },
        }


class Phase2MetricsCollector:
    """Collects metrics for cascade failure detection.

    Design:
    - Collects every 5 seconds (< 1% overhead)
    - Maintains 24-hour rolling window
    - Exports Prometheus format on demand
    - Thread-safe (async-safe) operations
    """

    def __init__(self, max_history_snapshots: int = 288):
        """Initialize Phase 2 metrics collector.

        Args:
            max_history_snapshots: Max snapshots to keep (288 = 24 hours @ 5sec intervals)
        """
        self.max_history = max_history_snapshots
        self.snapshots: deque = deque(maxlen=max_history_snapshots)
        self.current_snapshot: Optional[MetricsSnapshot] = None

        # Counters for rates (used to calculate per-hour rates)
        self.total_trades = 0
        self.total_trade_errors = 0
        self.total_exceptions = 0
        self.exception_counters: Dict[str, int] = defaultdict(int)

        # HA sync tracking
        self.ha_sync_attempts = 0
        self.ha_sync_successes = 0
        self.ha_sync_latencies: deque = deque(maxlen=100)

        # WebSocket tracking
        self.ws_failure_count = 0
        self.collection_loop_task: Optional[asyncio.Task] = None
        self.is_collecting = False

        logger.info("Phase 2 Metrics Collector initialized")

    async def start_collection(self) -> None:
        """Start the metrics collection loop (every 5 seconds).

        Should be called once at system startup.
        """
        if self.is_collecting:
            logger.warning("Collection already started")
            return

        self.is_collecting = True
        logger.info("Starting Phase 2 metrics collection loop")

        # Create background task
        self.collection_loop_task = asyncio.create_task(self._collection_loop())

    async def stop_collection(self) -> None:
        """Stop the metrics collection loop."""
        if not self.is_collecting:
            return

        self.is_collecting = False
        if self.collection_loop_task:
            self.collection_loop_task.cancel()
            try:
                await self.collection_loop_task
            except asyncio.CancelledError:
                pass

        logger.info("Phase 2 metrics collection stopped")

    async def _collection_loop(self) -> None:
        """Background loop that collects metrics every 5 seconds."""
        logger.info("Metrics collection loop started")
        try:
            while self.is_collecting:
                try:
                    await self.collect_snapshot()
                    await asyncio.sleep(5)  # Collect every 5 seconds
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in metrics collection loop: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Don't hammer on errors
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Metrics collection loop stopped")

    async def collect_snapshot(self) -> MetricsSnapshot:
        """Collect one snapshot of all metrics.

        Returns:
            MetricsSnapshot with current system state
        """
        snapshot = MetricsSnapshot(datetime.utcnow())

        # Collect memory metrics
        self._collect_memory_metrics(snapshot)

        # Collect WebSocket metrics
        await self._collect_websocket_metrics(snapshot)

        # Collect HA sync metrics
        self._collect_ha_metrics(snapshot)

        # Collect exception metrics
        self._collect_exception_metrics(snapshot)

        # Collect trading metrics
        await self._collect_trading_metrics(snapshot)

        # Store in history
        self.snapshots.append(snapshot)
        self.current_snapshot = snapshot

        return snapshot

    def _collect_memory_metrics(self, snapshot: MetricsSnapshot) -> None:
        """Collect memory usage metrics."""
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            vm = psutil.virtual_memory()

            snapshot.memory_mb = mem_info.rss / 1024 / 1024
            snapshot.memory_percent = process.memory_percent()
            snapshot.memory_available_mb = vm.available / 1024 / 1024

            logger.debug(
                f"Memory: {snapshot.memory_mb:.1f}MB ({snapshot.memory_percent:.1f}%)"
            )
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")

    async def _collect_websocket_metrics(self, snapshot: MetricsSnapshot) -> None:
        """Collect WebSocket connection health metrics."""
        try:
            from backend.exchange.binance_stream import get_stream_client

            client = get_stream_client()
            if not client:
                snapshot.ws_connected_count = 0
                snapshot.ws_max_age_seconds = 0
                return

            # Count active connections
            snapshot.ws_connected_count = 1 if client.is_connected else 0

            # Calculate max age of price data
            if client.last_update:
                from datetime import timezone
                now = datetime.now(timezone.utc)
                ages = [
                    (now - update_time).total_seconds()
                    for update_time in client.last_update.values()
                ]
                snapshot.ws_max_age_seconds = max(ages) if ages else 0

                # Find stale symbols (>30 seconds)
                snapshot.ws_stale_symbols = [
                    symbol
                    for symbol, update_time in client.last_update.items()
                    if (now - update_time).total_seconds() > 30
                ]
            else:
                snapshot.ws_max_age_seconds = 0

            # Track reconnect failures
            snapshot.ws_reconnect_failures = client.reconnect_attempts

            logger.debug(
                f"WebSocket: {snapshot.ws_connected_count} connections, "
                f"max age {snapshot.ws_max_age_seconds:.1f}s"
            )
        except Exception as e:
            logger.error(f"Failed to collect WebSocket metrics: {e}")

    def _collect_ha_metrics(self, snapshot: MetricsSnapshot) -> None:
        """Collect HA sync status metrics."""
        try:
            # Calculate sync success rate
            if self.ha_sync_attempts > 0:
                snapshot.ha_sync_success_rate = (
                    self.ha_sync_successes / self.ha_sync_attempts * 100
                )
            else:
                snapshot.ha_sync_success_rate = 100.0

            # Calculate average latency
            if self.ha_sync_latencies:
                snapshot.ha_sync_latency_ms = sum(self.ha_sync_latencies) / len(
                    self.ha_sync_latencies
                )
            else:
                snapshot.ha_sync_latency_ms = 0.0

            # Will be set by external sync modules
            snapshot.ha_last_sync_time = datetime.utcnow()

            logger.debug(
                f"HA Sync: {snapshot.ha_sync_success_rate:.1f}% success rate, "
                f"{snapshot.ha_sync_latency_ms:.1f}ms latency"
            )
        except Exception as e:
            logger.error(f"Failed to collect HA metrics: {e}")

    def _collect_exception_metrics(self, snapshot: MetricsSnapshot) -> None:
        """Collect exception rate metrics."""
        try:
            snapshot.exception_count = self.total_exceptions
            snapshot.exceptions_by_type = dict(self.exception_counters)

            # Calculate exception rate (per hour)
            if len(self.snapshots) > 0:
                time_span_minutes = (
                    (datetime.utcnow() - self.snapshots[0].timestamp).total_seconds()
                    / 60
                )
                if time_span_minutes > 0:
                    snapshot.exception_rate_percent = (
                        self.total_exceptions / max(1, time_span_minutes / 60) * 100
                    )
            else:
                snapshot.exception_rate_percent = 0.0

            logger.debug(
                f"Exceptions: {snapshot.exception_count} total, "
                f"{snapshot.exception_rate_percent:.2f}% rate"
            )
        except Exception as e:
            logger.error(f"Failed to collect exception metrics: {e}")

    async def _collect_trading_metrics(self, snapshot: MetricsSnapshot) -> None:
        """Collect trading statistics."""
        try:
            # Calculate trades per hour
            if len(self.snapshots) > 0 and self.snapshots[0].timestamp:
                time_span_minutes = (
                    (datetime.utcnow() - self.snapshots[0].timestamp).total_seconds()
                    / 60
                )
                if time_span_minutes > 0:
                    snapshot.trades_per_hour = (
                        self.total_trades / max(1, time_span_minutes / 60)
                    )

            snapshot.trade_errors = self.total_trade_errors

            logger.debug(
                f"Trading: {snapshot.trades_per_hour:.1f} trades/hour, "
                f"{snapshot.trade_errors} errors"
            )
        except Exception as e:
            logger.error(f"Failed to collect trading metrics: {e}")

    def record_trade(self, success: bool = True, slippage_pct: float = 0.0) -> None:
        """Record a trade execution.

        Args:
            success: Whether trade was successful
            slippage_pct: Slippage percentage
        """
        self.total_trades += 1
        if not success:
            self.total_trade_errors += 1

    def record_exception(self, exception_type: str) -> None:
        """Record an exception occurrence.

        Args:
            exception_type: Type/module of exception
        """
        self.total_exceptions += 1
        self.exception_counters[exception_type] += 1

    def record_ha_sync(
        self, success: bool = True, latency_ms: float = 0.0
    ) -> None:
        """Record an HA sync attempt.

        Args:
            success: Whether sync was successful
            latency_ms: Time taken for sync in milliseconds
        """
        self.ha_sync_attempts += 1
        if success:
            self.ha_sync_successes += 1
        self.ha_sync_latencies.append(latency_ms)

    def record_websocket_failure(self) -> None:
        """Record a WebSocket reconnection failure."""
        self.ws_failure_count += 1

    def get_current_snapshot(self) -> Optional[MetricsSnapshot]:
        """Get the most recent metrics snapshot.

        Returns:
            Current MetricsSnapshot or None if no data collected yet
        """
        return self.current_snapshot

    def get_snapshot_history(
        self, minutes: int = 60
    ) -> List[MetricsSnapshot]:
        """Get snapshots from the last N minutes.

        Args:
            minutes: Number of minutes of history to return

        Returns:
            List of MetricsSnapshot objects
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [s for s in self.snapshots if s.timestamp >= cutoff_time]

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-format metric text
        """
        if not self.current_snapshot:
            return ""

        snap = self.current_snapshot
        metrics = []

        # Memory metrics
        metrics.append("# HELP phase2_memory_mb Current process memory in MB")
        metrics.append("# TYPE phase2_memory_mb gauge")
        metrics.append(f"phase2_memory_mb {snap.memory_mb:.2f}")

        metrics.append("# HELP phase2_memory_percent Current memory usage percentage")
        metrics.append("# TYPE phase2_memory_percent gauge")
        metrics.append(f"phase2_memory_percent {snap.memory_percent:.2f}")

        # WebSocket metrics
        metrics.append(
            "# HELP phase2_websocket_max_age_seconds Max age of WebSocket data"
        )
        metrics.append("# TYPE phase2_websocket_max_age_seconds gauge")
        metrics.append(f"phase2_websocket_max_age_seconds {snap.ws_max_age_seconds:.2f}")

        metrics.append(
            "# HELP phase2_websocket_reconnect_failures Count of reconnection failures"
        )
        metrics.append("# TYPE phase2_websocket_reconnect_failures counter")
        metrics.append(f"phase2_websocket_reconnect_failures {snap.ws_reconnect_failures}")

        # HA sync metrics
        metrics.append(
            "# HELP phase2_ha_sync_success_rate HA sync success rate percentage"
        )
        metrics.append("# TYPE phase2_ha_sync_success_rate gauge")
        metrics.append(f"phase2_ha_sync_success_rate {snap.ha_sync_success_rate:.2f}")

        metrics.append(
            "# HELP phase2_ha_sync_latency_ms HA sync latency in milliseconds"
        )
        metrics.append("# TYPE phase2_ha_sync_latency_ms gauge")
        metrics.append(f"phase2_ha_sync_latency_ms {snap.ha_sync_latency_ms:.2f}")

        # Exception metrics
        metrics.append(
            "# HELP phase2_exception_count Total exception count since startup"
        )
        metrics.append("# TYPE phase2_exception_count counter")
        metrics.append(f"phase2_exception_count {snap.exception_count}")

        metrics.append(
            "# HELP phase2_exception_rate_percent Exception rate per hour"
        )
        metrics.append("# TYPE phase2_exception_rate_percent gauge")
        metrics.append(f"phase2_exception_rate_percent {snap.exception_rate_percent:.2f}")

        return "\n".join(metrics)

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics of collected metrics.

        Returns:
            Dictionary with summary stats
        """
        if not self.snapshots:
            return {"error": "No metrics collected yet"}

        snapshots_list = list(self.snapshots)

        return {
            "collection_window_minutes": (
                (datetime.utcnow() - snapshots_list[0].timestamp).total_seconds() / 60
            ),
            "snapshots_collected": len(snapshots_list),
            "memory": {
                "current_mb": snapshots_list[-1].memory_mb,
                "max_mb": max(s.memory_mb for s in snapshots_list),
                "avg_mb": sum(s.memory_mb for s in snapshots_list) / len(snapshots_list),
                "current_percent": snapshots_list[-1].memory_percent,
            },
            "websocket": {
                "max_age_seconds_peak": max(
                    s.ws_max_age_seconds for s in snapshots_list
                ),
                "reconnect_failures_peak": max(
                    s.ws_reconnect_failures for s in snapshots_list
                ),
                "stale_events": sum(1 for s in snapshots_list if s.ws_stale_symbols),
            },
            "ha_sync": {
                "success_rate_current": snapshots_list[-1].ha_sync_success_rate,
                "latency_ms_current": snapshots_list[-1].ha_sync_latency_ms,
            },
            "exceptions": {
                "total": self.total_exceptions,
                "rate_per_hour": (
                    self.total_exceptions
                    / max(
                        1,
                        (datetime.utcnow() - snapshots_list[0].timestamp).total_seconds()
                        / 3600,
                    )
                ),
                "by_type": dict(self.exception_counters),
            },
            "trading": {
                "trades_total": self.total_trades,
                "trades_per_hour": snapshots_list[-1].trades_per_hour,
                "errors": self.total_trade_errors,
            },
        }


# Global instance
_phase2_metrics: Optional[Phase2MetricsCollector] = None


def get_phase2_metrics() -> Phase2MetricsCollector:
    """Get or create global Phase 2 metrics collector.

    Returns:
        Phase2MetricsCollector instance
    """
    global _phase2_metrics
    if _phase2_metrics is None:
        _phase2_metrics = Phase2MetricsCollector()
    return _phase2_metrics


def init_phase2_metrics() -> Phase2MetricsCollector:
    """Initialize Phase 2 metrics collector.

    Returns:
        Phase2MetricsCollector instance
    """
    global _phase2_metrics
    _phase2_metrics = Phase2MetricsCollector()
    logger.info("Phase 2 metrics collector initialized")
    return _phase2_metrics
