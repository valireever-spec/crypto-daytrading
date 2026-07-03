"""Periodic monitoring logger for baseline metrics.

Logs key health metrics every 60 seconds so they're visible in systemd journal
and can be tracked over 24+ hour periods for baseline validation.

Logs:
- Process health (sockets, threads, memory, CPU)
- WebSocket status
- Circuit breaker state
- Trading status (cash, P&L, positions)
- Explicit heartbeat stats (BACKUP only)
- HA status (PRIMARY/BACKUP role)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class MonitoringLogger:
    """Log monitoring metrics at regular intervals."""

    def __init__(self, interval: float = 60.0):
        """
        Args:
            interval: Log metrics every N seconds (default 60s)
        """
        self.interval = interval
        self.running = False
        self.task = None

    async def start(self) -> None:
        """Start periodic monitoring logger."""
        if self.running:
            logger.warning("Monitoring logger already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._log_loop())
        logger.info(f"📊 Monitoring logger started (every {self.interval}s)")

    async def stop(self) -> None:
        """Stop monitoring logger."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring logger stopped")

    async def _log_loop(self) -> None:
        """Periodically log monitoring data."""
        while self.running:
            try:
                await asyncio.sleep(self.interval)
                await self._log_metrics()

            except asyncio.CancelledError:
                logger.debug("Monitoring logger cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring logger error: {e}")

    async def _log_metrics(self) -> None:
        """Gather and log all monitoring metrics."""
        try:
            metrics = await self._gather_metrics()
            self._log_structured(metrics)
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")

    async def _gather_metrics(self) -> dict:
        """Gather all monitoring metrics."""
        from backend.core.process_health_monitor import get_process_health_monitor
        from backend.core.circuit_breaker_recovery import get_circuit_breaker_recovery
        from backend.exchange.paper_trading import get_paper_trading
        from backend.failover.explicit_heartbeat import get_explicit_heartbeat_monitor
        from backend.core import constants

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "machine_id": constants.MACHINE_ID,
            "is_primary": constants.IS_PRIMARY,
        }

        # Process health
        process_monitor = get_process_health_monitor()
        if process_monitor:
            stats = process_monitor.get_stats()
            metrics["process"] = {
                "sockets": stats.get("sockets", {}).get("current"),
                "threads": stats.get("threads", {}).get("current"),
                "memory_percent": stats.get("memory", {}).get("percent"),
                "cpu_percent": stats.get("cpu", {}).get("percent"),
                "restarts_last_hour": stats.get("restarts_last_hour"),
            }

        # Circuit breaker
        cb_recovery = get_circuit_breaker_recovery()
        if cb_recovery:
            metrics["circuit_breaker"] = {
                "state": cb_recovery.current_state,
                "trip_count": cb_recovery.trip_count,
            }

        # Trading status
        engine = get_paper_trading()
        if engine:
            positions = engine.get_positions()
            metrics["trading"] = {
                "mode": "PAPER",
                "cash": round(engine.cash, 2),
                "total_pnl": round(engine.total_pnl, 2),
                "positions_count": len(positions),
            }

        # Explicit heartbeat monitor (BACKUP only)
        if not constants.IS_PRIMARY:
            heartbeat_monitor = get_explicit_heartbeat_monitor()
            if heartbeat_monitor:
                hb_stats = heartbeat_monitor.get_stats()
                metrics["heartbeat"] = {
                    "heartbeats_received": hb_stats.get("heartbeats_received"),
                    "consecutive_misses": hb_stats.get("consecutive_misses"),
                    "promoted": hb_stats.get("promoted"),
                }

        return metrics

    def _log_structured(self, metrics: dict) -> None:
        """Log metrics as structured JSON."""
        log_entry = {
            "timestamp": metrics["timestamp"],
            "level": "INFO",
            "logger": "backend.core.monitoring_logger",
            "message": f"📊 Baseline metrics: {metrics['machine_id'].upper()}",
            "event": "BASELINE_METRICS",
            "metrics": metrics,
        }

        # Log as JSON so it's easy to parse
        logger.info(json.dumps(log_entry))


# Global instance
_monitoring_logger: Optional[MonitoringLogger] = None


def init_monitoring_logger(interval: float = 60.0) -> MonitoringLogger:
    """Initialize monitoring logger."""
    global _monitoring_logger
    if _monitoring_logger is None:
        _monitoring_logger = MonitoringLogger(interval=interval)
    return _monitoring_logger


def get_monitoring_logger() -> Optional[MonitoringLogger]:
    """Get monitoring logger."""
    return _monitoring_logger
