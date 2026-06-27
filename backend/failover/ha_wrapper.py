"""HA Wrapper: Integrates HeartbeatMonitor with Autonomous Trader

This module wraps the autonomous trader with HA monitoring.
If PRIMARY becomes unhealthy, it stops trading and alerts.
"""

import logging
import asyncio
from backend.failover.heartbeat import HeartbeatMonitor, get_heartbeat

logger = logging.getLogger(__name__)


class HATraderWrapper:
    """Wraps autonomous trader with HA health checks."""

    def __init__(self):
        self.heartbeat = get_heartbeat()
        self._monitor_task = None

    async def start_monitoring(self):
        """Start the heartbeat monitor in background."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self.heartbeat.start())
            logger.info("🫀 HA monitoring started")

    async def check_trading_allowed(self) -> bool:
        """Check if trading should continue.

        Returns:
            True if PRIMARY is healthy, False otherwise
        """
        if not self.heartbeat.is_healthy():
            logger.critical("🚨 PRIMARY UNHEALTHY - Trading paused")
            return False

        return True

    async def stop_monitoring(self):
        """Stop the heartbeat monitor."""
        if self._monitor_task:
            await self.heartbeat.stop()
            await self._monitor_task
            self._monitor_task = None
            logger.info("🫀 HA monitoring stopped")

    def get_health_status(self) -> dict:
        """Get current HA health status."""
        return self.heartbeat.get_status()


# Global wrapper instance
_ha_wrapper: HATraderWrapper = None


def get_ha_wrapper() -> HATraderWrapper:
    """Get or create global HA wrapper."""
    global _ha_wrapper
    if _ha_wrapper is None:
        _ha_wrapper = HATraderWrapper()
    return _ha_wrapper


async def with_ha_check(trading_fn):
    """Decorator to ensure trading only happens if PRIMARY is healthy.

    Usage:
        @with_ha_check
        async def place_orders():
            ...execute trades...
    """
    async def wrapper(*args, **kwargs):
        wrapper_instance = get_ha_wrapper()

        if not await wrapper_instance.check_trading_allowed():
            logger.warning("⚠️ Trade blocked: PRIMARY unhealthy")
            return None

        return await trading_fn(*args, **kwargs)

    return wrapper
