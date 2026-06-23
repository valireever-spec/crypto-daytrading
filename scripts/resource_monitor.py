#!/usr/bin/env python3
"""Monitor system resources and stop Sentinel Bot if thresholds exceeded."""

import psutil
import subprocess
import logging
import time
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
log_dir = Path("/home/trader/crypto-daytrading/logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "resource_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Resource thresholds (when to stop Sentinel Bot)
THRESHOLDS = {
    "cpu_percent": 85,           # CPU usage > 85%
    "memory_percent": 85,        # RAM usage > 85%
    "disk_percent": 90,          # Disk usage > 90%
    "memory_mb": 200,            # Less than 200MB available
}

# Service names
BACKUP_TRADER_SERVICE = "backup-trader"
FAILOVER_MONITOR_SERVICE = "failover-monitor"


class ResourceMonitor:
    def __init__(self):
        self.service_stopped = False
        self.stop_reason = None
        self.check_interval = 10  # Check every 10 seconds

    def get_system_stats(self) -> dict:
        """Get current system resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3),
                "disk_total_gb": disk.total / (1024**3),
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return None

    def check_thresholds(self, stats: dict) -> tuple[bool, str]:
        """Check if any threshold is exceeded.

        Returns:
            (exceeded: bool, reason: str)
        """
        if not stats:
            return False, ""

        # Check CPU
        if stats["cpu_percent"] > THRESHOLDS["cpu_percent"]:
            return True, f"CPU usage critical: {stats['cpu_percent']:.1f}% (threshold: {THRESHOLDS['cpu_percent']}%)"

        # Check RAM
        if stats["memory_percent"] > THRESHOLDS["memory_percent"]:
            return True, f"RAM usage critical: {stats['memory_percent']:.1f}% (threshold: {THRESHOLDS['memory_percent']}%)"

        if stats["memory_available_mb"] < THRESHOLDS["memory_mb"]:
            return True, f"RAM available critical: {stats['memory_available_mb']:.0f}MB (threshold: {THRESHOLDS['memory_mb']}MB)"

        # Check Disk
        if stats["disk_percent"] > THRESHOLDS["disk_percent"]:
            return True, f"Disk usage critical: {stats['disk_percent']:.1f}% (threshold: {THRESHOLDS['disk_percent']}%)"

        return False, ""

    def stop_sentinel_bot(self, reason: str):
        """Stop the Sentinel Bot service."""
        logger.critical(f"🚨 STOPPING SENTINEL BOT: {reason}")

        try:
            # Stop backup trader
            logger.info("Stopping backup trader service...")
            result = subprocess.run(
                ["sudo", "systemctl", "stop", BACKUP_TRADER_SERVICE],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.warning(f"✅ {BACKUP_TRADER_SERVICE} stopped")
            else:
                logger.error(f"❌ Failed to stop {BACKUP_TRADER_SERVICE}: {result.stderr}")

            # Stop failover monitor
            logger.info("Stopping failover monitor service...")
            result = subprocess.run(
                ["sudo", "systemctl", "stop", FAILOVER_MONITOR_SERVICE],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.warning(f"✅ {FAILOVER_MONITOR_SERVICE} stopped")
            else:
                logger.error(f"❌ Failed to stop {FAILOVER_MONITOR_SERVICE}: {result.stderr}")

            self.service_stopped = True
            self.stop_reason = reason

            # Send alert
            self._send_alert(reason)

        except Exception as e:
            logger.error(f"Error stopping services: {e}")

    def restart_sentinel_bot(self):
        """Restart the Sentinel Bot service after resources recover."""
        logger.info("🚀 Resources recovered - restarting Sentinel Bot...")

        try:
            # Start failover monitor
            logger.info("Starting failover monitor service...")
            result = subprocess.run(
                ["sudo", "systemctl", "start", FAILOVER_MONITOR_SERVICE],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"✅ {FAILOVER_MONITOR_SERVICE} started")
            else:
                logger.error(f"❌ Failed to start {FAILOVER_MONITOR_SERVICE}: {result.stderr}")

            # Start backup trader
            logger.info("Starting backup trader service...")
            result = subprocess.run(
                ["sudo", "systemctl", "start", BACKUP_TRADER_SERVICE],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                logger.info(f"✅ {BACKUP_TRADER_SERVICE} started")
            else:
                logger.error(f"❌ Failed to start {BACKUP_TRADER_SERVICE}: {result.stderr}")

            self.service_stopped = False
            self.stop_reason = None

        except Exception as e:
            logger.error(f"Error restarting services: {e}")

    def _send_alert(self, reason: str):
        """Send alert notification."""
        timestamp = datetime.now().isoformat()
        message = f"ALERT: Sentinel Bot stopped at {timestamp}\nReason: {reason}"
        logger.critical(message)

        # TODO: Send email/Slack notification
        # For now, just log it

    def log_stats(self, stats: dict):
        """Log current resource stats."""
        logger.info(
            f"Resources: CPU={stats['cpu_percent']:.1f}% | "
            f"RAM={stats['memory_percent']:.1f}% ({stats['memory_available_mb']:.0f}MB free) | "
            f"Disk={stats['disk_percent']:.1f}%"
        )

    def run(self):
        """Main monitoring loop."""
        logger.info("🔍 Resource monitor started")
        logger.info(f"CPU threshold: {THRESHOLDS['cpu_percent']}%")
        logger.info(f"RAM threshold: {THRESHOLDS['memory_percent']}% or <{THRESHOLDS['memory_mb']}MB")
        logger.info(f"Disk threshold: {THRESHOLDS['disk_percent']}%")
        logger.info(f"Check interval: {self.check_interval}s")

        while True:
            try:
                stats = self.get_system_stats()

                if not stats:
                    logger.error("Could not get system stats, retrying...")
                    time.sleep(self.check_interval)
                    continue

                # Check if thresholds exceeded
                exceeded, reason = self.check_thresholds(stats)

                if exceeded:
                    if not self.service_stopped:
                        # Thresholds exceeded and service is running
                        self.stop_sentinel_bot(reason)
                    else:
                        # Already stopped, just log the condition
                        logger.warning(reason)
                else:
                    # Resources are OK
                    if self.service_stopped:
                        # Service was stopped but resources recovered
                        self.restart_sentinel_bot()
                    else:
                        # Service is running and resources are good
                        self.log_stats(stats)

                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Resource monitor stopped by user")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}")
                time.sleep(self.check_interval)


if __name__ == "__main__":
    monitor = ResourceMonitor()
    monitor.run()
