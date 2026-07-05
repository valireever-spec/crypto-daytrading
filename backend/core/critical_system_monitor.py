"""Monitor critical system dependencies that would cause cascade failures."""

import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class CriticalSystemMonitor:
    """Monitor exit checks, HA sync, and WebSocket - alert if any fail."""

    def __init__(self):
        self.exit_check_failures = 0
        self.ha_sync_failures = 0
        self.websocket_staleness_warnings = 0
        self.last_alert_time = {}
        self.alert_cooldown = 300  # seconds between same alert

    async def monitor_exit_checks(self, error_count: int):
        """Alert if exit checks are crashing (fragility point #1)."""
        if error_count > 0 and error_count != self.exit_check_failures:
            self.exit_check_failures = error_count
            await self._alert(
                "🔴 CRITICAL: Exit check failures detected",
                f"Exit checks failing {error_count}x - positions may not close",
                severity="CRITICAL"
            )

    async def monitor_ha_sync(self, sync_failure_count: int):
        """Alert if HA sync is failing (fragility point #2)."""
        if sync_failure_count > self.ha_sync_failures + 5:
            self.ha_sync_failures = sync_failure_count
            await self._alert(
                "🔴 CRITICAL: HA sync degradation",
                f"HA sync failures now at {sync_failure_count} - BACKUP state may diverge",
                severity="CRITICAL"
            )

    async def monitor_websocket_health(self, stale_streams: int, health_pct: int):
        """Alert if WebSocket data becomes stale (fragility point #3)."""
        if stale_streams > 0 and health_pct < 70:
            await self._alert(
                "🟠 WARNING: WebSocket quality degraded",
                f"{stale_streams} stale streams, health {health_pct}% - trading on stale prices",
                severity="HIGH"
            )

    async def _alert(self, title: str, message: str, severity: str):
        """Send alert if not in cooldown period."""
        now = time.time()
        last = self.last_alert_time.get(title, 0)

        if now - last > self.alert_cooldown:
            self.last_alert_time[title] = now
            logger.error(f"{severity}: {title} - {message}")
            # Would send to Telegram, Slack here


# Global instance
_monitor: Optional[CriticalSystemMonitor] = None

def get_critical_monitor() -> CriticalSystemMonitor:
    """Get or create global monitor."""
    global _monitor
    if _monitor is None:
        _monitor = CriticalSystemMonitor()
    return _monitor
