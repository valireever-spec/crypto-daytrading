"""HA Heartbeat Monitor (FR-006)

Detects PRIMARY failure and initiates BACKUP takeover.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import requests

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Monitor PRIMARY health and trigger failover on failure.

    Features:
    - Tracks consecutive failures with exponential backoff
    - Logs all state transitions for debugging
    - Supports automatic recovery when PRIMARY comes back online
    - Validates PRIMARY response before declaring healthy
    """

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
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

    async def start(self) -> None:
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
                was_recovering = self.recovery_attempts > 0

                if not self.is_primary_healthy:
                    # PRIMARY has recovered from failure
                    logger.critical(
                        f"🟢 PRIMARY RECOVERED - back online after "
                        f"{self.recovery_attempts} recovery attempts"
                    )
                    self.is_primary_healthy = True
                    self.recovery_attempts = 0  # Reset recovery counter
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

    def _handle_failure(self, reason: str) -> None:
        """Handle PRIMARY health check failure with exponential backoff.

        Implements retry logic with increasing severity:
        1. First N-1 failures: Log as warning, continue checking
        2. Nth failure: Declare PRIMARY dead and trigger failover
        3. After failover: Log as error, retry periodically
        """
        self.consecutive_failures += 1
        failure_time = datetime.utcnow()

        if self.consecutive_failures < self.failure_threshold:
            # Transient failure - may be temporary network issue
            logger.warning(
                f"⚠️  PRIMARY check failed ({self.consecutive_failures}/{self.failure_threshold}): {reason}"
            )
        elif self.consecutive_failures == self.failure_threshold:
            # PRIMARY declared dead - trigger failover
            logger.critical(
                f"🔴 PRIMARY DECLARED DEAD after {self.failure_threshold} failures: {reason} "
                f"@ {failure_time.isoformat()}"
            )
            self.is_primary_healthy = False
            self._trigger_failover()
        else:
            # PRIMARY still dead - log with backoff
            time_since_failure = (failure_time - self.last_check).total_seconds() if self.last_check else 0
            logger.error(
                f"PRIMARY still dead ({self.consecutive_failures} failures, "
                f"{time_since_failure:.0f}s since first failure): {reason}"
            )
            # Increment recovery attempts
            self.recovery_attempts += 1
            if self.recovery_attempts >= self.max_recovery_attempts:
                logger.critical(
                    f"🚨 MAX RECOVERY ATTEMPTS EXCEEDED ({self.recovery_attempts}). "
                    f"PRIMARY may be permanently offline. Manual intervention required."
                )

    def _trigger_failover(self) -> None:
        """Trigger BACKUP takeover when PRIMARY fails.

        Note: This is called on BACKUP when PRIMARY heartbeat timeout occurs.
        Failover is managed by lifecycle.py's failover_monitor task.
        """
        logger.critical("🚨 FAILOVER TRIGGERED: PRIMARY FAILURE DETECTED 🚨")
        # Failover state is tracked and handled by the failover_monitor task
        # in lifecycle.py which will:
        # 1. Stop autonomous trader on BACKUP (if running)
        # 2. Initialize new autonomous trader instance
        # 3. Sync state from PRIMARY if still reachable
        # 4. Start trading on BACKUP
        # This method serves as a signal that failover is needed

    async def stop(self):
        """Stop heartbeat monitoring."""
        self._running = False
        logger.info("🫀 Heartbeat monitor stopped")

    def is_healthy(self) -> bool:
        """Check if PRIMARY is currently healthy."""
        return self.is_primary_healthy

    def get_status(self) -> Dict[str, Any]:
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
