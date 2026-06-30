"""HA Wrapper: Integrates HeartbeatMonitor with Autonomous Trader

This module wraps the autonomous trader with HA monitoring.
Phase 2 Hardening: Includes split-brain detection & prevention
"""

import logging
import asyncio
import os
from backend.failover.heartbeat import get_heartbeat
from backend.core.split_brain_prevention import SplitBrainPrevention

logger = logging.getLogger(__name__)


class HATraderWrapper:
    """Wraps autonomous trader with HA health checks + split-brain prevention."""

    def __init__(self):
        self.heartbeat = get_heartbeat()
        self._monitor_task = None

        # Initialize split-brain prevention
        machine_id = os.getenv("MACHINE_ID", "main")
        primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
        backup_url = os.getenv("BACKUP_API_URL", "http://192.168.3.25:8002")
        self.split_brain_prevention = SplitBrainPrevention(
            machine_id=machine_id,
            primary_url=primary_url,
            backup_url=backup_url
        )
        self._split_brain_monitor_task = None

    async def start_monitoring(self):
        """Start the heartbeat monitor and split-brain detection in background."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self.heartbeat.start())
            self._split_brain_monitor_task = asyncio.create_task(self._monitor_split_brain())
            logger.info("🫀 HA monitoring started (with split-brain detection)")

    async def _monitor_split_brain(self):
        """Continuously monitor for split-brain conditions."""
        split_brain_counter = 0
        while True:
            try:
                health = await self.split_brain_prevention.check_mutual_health()

                if health["split_brain"]:
                    split_brain_counter += 1
                    if split_brain_counter >= 3:
                        # Confirmed split-brain after 3 consecutive checks
                        logger.critical("🚨 SPLIT-BRAIN CONFIRMED - Resolving...")
                        await self.split_brain_prevention.resolve_split_brain()
                else:
                    split_brain_counter = 0

                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Split-brain monitor error: {e}")
                await asyncio.sleep(5)

    async def check_trading_allowed(self) -> bool:
        """Check if trading should continue.

        Returns:
            True if:
            - PRIMARY is healthy, OR
            - BACKUP is healthy AND PRIMARY is dead AND no split-brain

            False if:
            - Split-brain detected (both healthy but can't coordinate)
            - Both dead
        """
        # Check split-brain status
        health = await self.split_brain_prevention.check_mutual_health()

        if health["split_brain"]:
            logger.critical("🚨 SPLIT-BRAIN DETECTED - Halting trades to prevent duplication")
            return False

        # Allow trading based on machine role and health
        can_trade = self.split_brain_prevention.can_trade()

        if not can_trade:
            logger.warning("❌ This machine cannot trade (PRIMARY is healthy or split-brain detected)")

        return can_trade

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
