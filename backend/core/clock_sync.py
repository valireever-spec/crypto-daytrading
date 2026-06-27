"""Clock Synchronization: Detect and alert on time drift"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ClockSyncMonitor:
    """Monitor system clock vs Binance time."""

    def __init__(self, max_drift_seconds: int = 5):
        self.max_drift_seconds = max_drift_seconds
        self.last_binance_time: Optional[float] = None
        self.is_synced = False

    async def sync_with_binance(self, binance_timestamp_ms: int) -> Dict:
        """Check clock sync with Binance.

        Args:
            binance_timestamp_ms: Binance server time in milliseconds

        Returns:
            {"synced": bool, "drift_seconds": float, "action": ""}
        """
        binance_time = binance_timestamp_ms / 1000.0
        local_time = time.time()
        drift = abs(local_time - binance_time)

        self.last_binance_time = binance_time
        self.is_synced = drift < self.max_drift_seconds

        action = ""
        if drift > self.max_drift_seconds:
            action = "ALERT: Clock drift detected"
            logger.critical(
                f"🚨 CLOCK DRIFT: {drift:.1f}s (limit: {self.max_drift_seconds}s)"
            )
        elif drift > self.max_drift_seconds * 0.5:
            action = "WARNING: Clock drift increasing"
            logger.warning(f"⚠️  Clock drift: {drift:.1f}s")
        else:
            logger.debug(f"✅ Clock synced: {drift:.1f}s drift")

        return {
            "synced": self.is_synced,
            "drift_seconds": drift,
            "max_drift": self.max_drift_seconds,
            "action": action,
            "local_time": local_time,
            "binance_time": binance_time,
        }

    def get_status(self) -> Dict:
        """Get clock sync status."""
        return {
            "synced": self.is_synced,
            "last_check": self.last_binance_time,
        }


# Global instance
_clock_sync_monitor: Optional[ClockSyncMonitor] = None


def get_clock_sync_monitor() -> ClockSyncMonitor:
    global _clock_sync_monitor
    if _clock_sync_monitor is None:
        _clock_sync_monitor = ClockSyncMonitor()
    return _clock_sync_monitor
