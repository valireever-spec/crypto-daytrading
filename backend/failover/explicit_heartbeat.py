"""Explicit HA heartbeat with BACKUP auto-promotion.

Skill #3: Reliable PRIMARY→BACKUP heartbeat every 2s.
If PRIMARY misses 3 heartbeats (6s total), BACKUP auto-promotes to PRIMARY.

This prevents:
- Split-brain (both thinking they're PRIMARY)
- Hung PRIMARY blocking BACKUP recovery
- Implicit detection failures (HTTP checks can time out)
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ExplicitHeartbeatSender:
    """PRIMARY: Send heartbeat to BACKUP every 2 seconds."""

    def __init__(self, backup_url: str, interval: float = 2.0):
        self.backup_url = backup_url
        self.interval = interval
        self.running = False
        self.task = None
        self.heartbeat_count = 0
        self.send_failures = 0
        self.last_send_time = None

    async def start(self) -> None:
        """Start sending heartbeats."""
        if self.running:
            logger.warning("Heartbeat sender already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._send_loop())
        logger.info(
            f"💓 Explicit heartbeat sender started (→ {self.backup_url} every {self.interval}s)"
        )

    async def stop(self) -> None:
        """Stop sending heartbeats."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat sender stopped")

    async def _send_loop(self) -> None:
        """Send heartbeat every N seconds."""
        while self.running:
            try:
                await asyncio.sleep(self.interval)

                heartbeat = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "heartbeat_id": self.heartbeat_count,
                    "machine_id": "primary",
                }

                async with httpx.AsyncClient(timeout=1.0) as client:
                    try:
                        resp = await client.post(
                            f"{self.backup_url}/api/ha/explicit-heartbeat",
                            json=heartbeat,
                        )
                        if resp.status_code == 200:
                            self.last_send_time = time.time()
                            self.send_failures = 0
                            logger.debug(f"💓 Heartbeat #{self.heartbeat_count} sent")
                            self.heartbeat_count += 1
                        else:
                            self.send_failures += 1
                            logger.warning(
                                f"⚠️  Heartbeat failed ({resp.status_code}): "
                                f"{self.send_failures} failures"
                            )
                    except httpx.TimeoutException:
                        self.send_failures += 1
                        logger.debug(f"Heartbeat timeout ({self.send_failures} failures)")
                    except Exception as e:
                        self.send_failures += 1
                        logger.debug(f"Heartbeat send error: {e}")

            except asyncio.CancelledError:
                logger.info("Heartbeat sender cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat send loop error: {e}")


class ExplicitHeartbeatMonitor:
    """BACKUP: Monitor heartbeats from PRIMARY.

    If PRIMARY misses 3 consecutive heartbeats (>6 seconds), auto-promote BACKUP to PRIMARY.
    """

    def __init__(self, check_interval: float = 1.0, failure_threshold: int = 3):
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.running = False
        self.task = None

        # Heartbeat state
        self.last_heartbeat_time = None
        self.last_heartbeat_id = None
        self.consecutive_misses = 0
        self.heartbeats_received = 0
        self.promoted = False

    async def start(self) -> None:
        """Start monitoring heartbeats."""
        if self.running:
            logger.warning("Heartbeat monitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"💓 Explicit heartbeat monitor started "
            f"({self.failure_threshold} misses = {self.failure_threshold * self.check_interval}s timeout)"
        )

    async def stop(self) -> None:
        """Stop monitoring heartbeats."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat monitor stopped")

    def record_heartbeat(self, heartbeat_id: int) -> None:
        """Called when heartbeat is received from PRIMARY."""
        self.last_heartbeat_time = time.time()
        self.last_heartbeat_id = heartbeat_id
        self.consecutive_misses = 0
        self.heartbeats_received += 1
        logger.debug(f"💓 Heartbeat #{heartbeat_id} received (total: {self.heartbeats_received})")

    async def _monitor_loop(self) -> None:
        """Check for heartbeat timeout every N seconds."""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)

                if self.last_heartbeat_time is None:
                    # No heartbeat yet
                    self.consecutive_misses += 1
                    if self.consecutive_misses == 1:
                        logger.info("⏳ Waiting for first heartbeat from PRIMARY...")
                    continue

                # Check if heartbeat is stale
                time_since_heartbeat = time.time() - self.last_heartbeat_time
                if time_since_heartbeat > self.check_interval * 1.5:  # Allow 1.5x interval jitter
                    self.consecutive_misses += 1
                    if self.consecutive_misses == 1:
                        logger.warning(
                            f"⚠️  Heartbeat stale ({time_since_heartbeat:.1f}s), "
                            f"miss #{self.consecutive_misses}"
                        )
                    elif self.consecutive_misses % self.failure_threshold == 0:
                        logger.warning(
                            f"⚠️  {self.consecutive_misses} consecutive misses "
                            f"({time_since_heartbeat:.1f}s stale)"
                        )
                else:
                    if self.consecutive_misses > 0:
                        logger.info(
                            f"✅ Heartbeat recovered after {self.consecutive_misses} misses"
                        )
                    self.consecutive_misses = 0

                # Trigger promotion if threshold exceeded
                if self.consecutive_misses >= self.failure_threshold and not self.promoted:
                    logger.critical(
                        f"🚨 PRIMARY FAILURE DETECTED: "
                        f"{self.consecutive_misses} consecutive heartbeat misses "
                        f"({self.failure_threshold * self.check_interval}s timeout) - "
                        "Triggering BACKUP promotion"
                    )
                    self.promoted = True
                    # Signal to app that promotion should happen (caller handles it)
                    # Return True to indicate failover should occur
                    return

            except asyncio.CancelledError:
                logger.info("Heartbeat monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

    def is_primary_failed(self) -> bool:
        """Check if PRIMARY has failed based on heartbeat."""
        if self.consecutive_misses >= self.failure_threshold:
            return True
        return False

    def get_stats(self) -> dict:
        """Get heartbeat statistics."""
        return {
            "heartbeats_received": self.heartbeats_received,
            "consecutive_misses": self.consecutive_misses,
            "last_heartbeat_age_seconds": (
                time.time() - self.last_heartbeat_time
                if self.last_heartbeat_time
                else None
            ),
            "promoted": self.promoted,
        }


# Global instances
_heartbeat_sender: Optional[ExplicitHeartbeatSender] = None
_heartbeat_monitor: Optional[ExplicitHeartbeatMonitor] = None


def init_explicit_heartbeat_sender(backup_url: str) -> ExplicitHeartbeatSender:
    """Initialize PRIMARY heartbeat sender."""
    global _heartbeat_sender
    if _heartbeat_sender is None:
        _heartbeat_sender = ExplicitHeartbeatSender(backup_url)
    return _heartbeat_sender


def get_explicit_heartbeat_sender() -> Optional[ExplicitHeartbeatSender]:
    """Get PRIMARY heartbeat sender."""
    return _heartbeat_sender


def init_explicit_heartbeat_monitor() -> ExplicitHeartbeatMonitor:
    """Initialize BACKUP heartbeat monitor."""
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        _heartbeat_monitor = ExplicitHeartbeatMonitor()
    return _heartbeat_monitor


def get_explicit_heartbeat_monitor() -> Optional[ExplicitHeartbeatMonitor]:
    """Get BACKUP heartbeat monitor."""
    return _heartbeat_monitor
