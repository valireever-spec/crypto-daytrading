"""HA Heartbeat monitoring and sending for multi-LAN failover detection.

When PRIMARY is on a different network (behind ISP router), explicit heartbeat
signals are more reliable than HTTP checks through an SSH tunnel that dies with PRIMARY.

Architecture:
- PRIMARY sends heartbeat every 5 seconds to BACKUP
- BACKUP listens for heartbeat, tracks missed beats
- 3 consecutive misses (>15 seconds) → PRIMARY down → Failover
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global instances (set during lifecycle)
_heartbeat_monitor: Optional["HeartbeatMonitor"] = None
_heartbeat_sender: Optional["HeartbeatSender"] = None


def init_heartbeat_monitor(check_interval: int = 5, failure_threshold: int = 3) -> "HeartbeatMonitor":
    """Initialize global heartbeat monitor (BACKUP)."""
    global _heartbeat_monitor
    _heartbeat_monitor = HeartbeatMonitor(check_interval, failure_threshold)
    return _heartbeat_monitor


def get_heartbeat_monitor() -> Optional["HeartbeatMonitor"]:
    """Get global heartbeat monitor instance."""
    return _heartbeat_monitor


def init_heartbeat_sender(backup_url: str, interval: int = 5) -> "HeartbeatSender":
    """Initialize global heartbeat sender (PRIMARY)."""
    global _heartbeat_sender
    _heartbeat_sender = HeartbeatSender(backup_url, interval)
    return _heartbeat_sender


def get_heartbeat_sender() -> Optional["HeartbeatSender"]:
    """Get global heartbeat sender instance."""
    return _heartbeat_sender


class HeartbeatMonitor:
    """Monitor PRIMARY heartbeat on BACKUP machine.

    Triggers failover if no heartbeat for >15 seconds (3 consecutive misses).
    """

    def __init__(self, check_interval: int = 5, failure_threshold: int = 3):
        """
        Args:
            check_interval: Seconds between heartbeat checks (should match sender interval)
            failure_threshold: Number of missed beats before failover (threshold * interval = timeout)
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.missed_count = 0
        self.last_heartbeat_time: Optional[datetime] = None
        self.primary_failed = False

    def on_heartbeat_received(self, data: Dict[str, Any]) -> None:
        """Call when heartbeat received from PRIMARY."""
        self.missed_count = 0
        self.last_heartbeat_time = datetime.utcnow()

        timestamp = data.get("timestamp", "unknown")
        machine_id = data.get("machine_id", "unknown")
        cash = data.get("state", {}).get("cash", 0)
        positions = len(data.get("state", {}).get("positions", []))

        logger.debug(
            f"💓 Heartbeat from PRIMARY: {machine_id} @ {timestamp} "
            f"(cash=€{cash:.2f}, positions={positions})"
        )

        if self.primary_failed:
            logger.critical("✅ PRIMARY RECOVERED - Heartbeat detected after failure")
            self.primary_failed = False

    def check_timeout(self) -> bool:
        """Check if PRIMARY heartbeat has timed out.

        Returns:
            True if PRIMARY has failed (no heartbeat for threshold seconds)
        """
        if self.last_heartbeat_time is None:
            # Never received heartbeat yet
            return False

        elapsed_seconds = (datetime.utcnow() - self.last_heartbeat_time).total_seconds()
        threshold_seconds = self.check_interval * self.failure_threshold

        if elapsed_seconds > self.check_interval:
            self.missed_count += 1
            miss_duration = elapsed_seconds

            if self.missed_count == 1:
                logger.warning(
                    f"⚠️  Heartbeat miss #{self.missed_count}: "
                    f"No signal for {miss_duration:.1f}s (threshold: {threshold_seconds}s)"
                )
            elif self.missed_count < self.failure_threshold:
                logger.warning(
                    f"⚠️  Heartbeat miss #{self.missed_count}: "
                    f"No signal for {miss_duration:.1f}s (threshold: {threshold_seconds}s)"
                )
            elif self.missed_count >= self.failure_threshold and not self.primary_failed:
                logger.critical(
                    f"🚨 PRIMARY FAILURE DETECTED: No heartbeat for {miss_duration:.1f}s "
                    f"({self.missed_count} misses @ {self.check_interval}s interval)"
                )
                self.primary_failed = True
                return True

        return self.primary_failed

    def get_status(self) -> Dict[str, Any]:
        """Get current heartbeat monitor status."""
        elapsed = 0
        if self.last_heartbeat_time:
            elapsed = (datetime.utcnow() - self.last_heartbeat_time).total_seconds()

        return {
            "last_heartbeat": self.last_heartbeat_time.isoformat() if self.last_heartbeat_time else None,
            "seconds_since": elapsed,
            "missed_count": self.missed_count,
            "threshold": self.failure_threshold,
            "primary_failed": self.primary_failed,
            "status": "FAILURE DETECTED" if self.primary_failed else "MONITORING",
        }


class HeartbeatSender:
    """Send heartbeat from PRIMARY to BACKUP every 5 seconds.

    Provides explicit proof that PRIMARY is alive and tunnel is healthy.
    """

    def __init__(self, backup_url: str, interval: int = 5):
        """
        Args:
            backup_url: BACKUP API URL (e.g., "http://192.168.3.25:8002")
            interval: Seconds between heartbeats
        """
        self.backup_url = backup_url
        self.interval = interval
        self.sent_count = 0
        self.failed_count = 0

    async def send_heartbeat(self) -> bool:
        """Send single heartbeat to BACKUP.

        Returns:
            True if successful, False if failed
        """
        import httpx
        from backend.exchange.paper_trading import get_paper_trading

        try:
            engine = get_paper_trading()
            if not engine:
                logger.warning("Paper trading engine not ready for heartbeat")
                return False

            # Get current state
            state = {
                "machine_id": os.getenv("MACHINE_ID", "main"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "state": {
                    "cash": engine.cash,
                    "total_pnl": engine.total_pnl,
                    "positions": engine.get_positions(),
                    "active_positions": len([p for p in engine.get_positions() if p.get("status") == "open"]),
                    "trades_today": len([t for t in engine.get_trades() if t.get("timestamp", "").startswith(datetime.utcnow().strftime("%Y-%m-%d"))]),
                }
            }

            # Send to BACKUP
            async with httpx.AsyncClient(timeout=3) as client:
                endpoint = f"{self.backup_url}/api/ha/heartbeat"
                response = await client.post(endpoint, json=state)

                if response.status_code == 200:
                    self.sent_count += 1
                    logger.debug(
                        f"💓 Heartbeat sent to BACKUP: "
                        f"cash=€{state['state']['cash']:.2f}, "
                        f"positions={state['state']['active_positions']}"
                    )
                    return True
                else:
                    self.failed_count += 1
                    logger.warning(
                        f"❌ Heartbeat failed: HTTP {response.status_code} from {self.backup_url}"
                    )
                    return False

        except asyncio.TimeoutError:
            self.failed_count += 1
            logger.warning(f"⏱️  Heartbeat timeout (network issue or BACKUP unreachable)")
            return False
        except Exception as e:
            self.failed_count += 1
            logger.warning(f"❌ Heartbeat error: {e}")
            return False

    async def start(self) -> None:
        """Start sending heartbeats every `interval` seconds."""
        logger.info(
            f"📤 PRIMARY heartbeat sender started (→ {self.backup_url} every {self.interval}s)"
        )

        while True:
            try:
                await self.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat send error: {e}")

            await asyncio.sleep(self.interval)

    def get_status(self) -> Dict[str, Any]:
        """Get heartbeat sender statistics."""
        success_rate = 0
        if self.sent_count + self.failed_count > 0:
            success_rate = self.sent_count / (self.sent_count + self.failed_count) * 100

        return {
            "sent": self.sent_count,
            "failed": self.failed_count,
            "success_rate": f"{success_rate:.1f}%",
            "backup_url": self.backup_url,
            "interval": self.interval,
        }
