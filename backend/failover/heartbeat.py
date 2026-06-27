"""HA Heartbeat Monitor (FR-006)

Detects PRIMARY failure and initiates BACKUP takeover.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Monitor PRIMARY health and trigger failover on failure."""

    def __init__(
        self,
        primary_url: str = "http://127.0.0.1:8001",
        heartbeat_interval: int = 5,
        failure_threshold: int = 3,
    ):
        """Initialize heartbeat monitor.

        Args:
            primary_url: PRIMARY machine API endpoint
            heartbeat_interval: Seconds between health checks
            failure_threshold: How many failures before declaring PRIMARY dead
        """
        self.primary_url = primary_url
        self.heartbeat_interval = heartbeat_interval
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.is_primary_healthy = True
        self.last_check = None
        self._running = False

    async def start(self):
        """Start heartbeat monitoring."""
        self._running = True
        logger.info(
            f"🫀 Heartbeat monitor started (checking PRIMARY every {self.heartbeat_interval}s)"
        )

        while self._running:
            await self.check_primary_health()
            await asyncio.sleep(self.heartbeat_interval)

    async def check_primary_health(self) -> bool:
        """Check if PRIMARY is healthy.

        Returns:
            True if PRIMARY is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.primary_url}/api/paper/account", timeout=3)

            if response.status_code == 200:
                self.consecutive_failures = 0

                if not self.is_primary_healthy:
                    logger.warning("🟢 PRIMARY recovered - back online")
                    self.is_primary_healthy = True
                else:
                    logger.debug(
                        f"✓ PRIMARY healthy (cash: €{response.json().get('cash', 0):.2f})"
                    )

                self.last_check = datetime.utcnow()
                return True
            else:
                self._handle_failure(f"HTTP {response.status_code}")

        except requests.ConnectionError:
            self._handle_failure("Connection refused")
        except requests.Timeout:
            self._handle_failure("Timeout (>3s)")
        except Exception as e:
            self._handle_failure(str(e))

        return False

    def _handle_failure(self, reason: str):
        """Handle PRIMARY health check failure."""
        self.consecutive_failures += 1

        if self.consecutive_failures < self.failure_threshold:
            logger.warning(
                f"⚠️  PRIMARY check failed ({self.consecutive_failures}/{self.failure_threshold}): {reason}"
            )
        elif self.consecutive_failures == self.failure_threshold:
            logger.critical(
                f"🔴 PRIMARY DECLARED DEAD after {self.failure_threshold} failures: {reason}"
            )
            self.is_primary_healthy = False
            self._trigger_failover()
        else:
            logger.error(f"PRIMARY still dead: {reason}")

    def _trigger_failover(self):
        """Trigger BACKUP takeover."""
        logger.critical("🚨 INITIATING FAILOVER TO BACKUP 🚨")
        # TODO: Implement actual failover logic
        # 1. Stop autonomous trader on this instance
        # 2. Send sync request to PRIMARY if reachable
        # 3. Start autonomous trader on BACKUP
        # 4. Alert user

    async def stop(self):
        """Stop heartbeat monitoring."""
        self._running = False
        logger.info("🫀 Heartbeat monitor stopped")

    def is_healthy(self) -> bool:
        """Check if PRIMARY is currently healthy."""
        return self.is_primary_healthy

    def get_status(self) -> dict:
        """Get heartbeat status."""
        return {
            "primary_healthy": self.is_primary_healthy,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "failure_threshold": self.failure_threshold,
        }


# Global heartbeat instance
_heartbeat: Optional[HeartbeatMonitor] = None


def get_heartbeat() -> HeartbeatMonitor:
    """Get or create global heartbeat monitor."""
    global _heartbeat
    if _heartbeat is None:
        _heartbeat = HeartbeatMonitor()
    return _heartbeat


async def start_heartbeat_monitor():
    """Start global heartbeat monitor."""
    monitor = get_heartbeat()
    await monitor.start()
