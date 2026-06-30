#!/usr/bin/env python3
"""Monitor primary trader and trigger failover if needed."""

import requests
import subprocess
import time
import logging
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
log_dir = Path.home() / "crypto-daytrading" / "logs"
log_dir.mkdir(exist_ok=True, parents=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "failover_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration from command line
PRIMARY_HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.30.137"
PRIMARY_PORT = sys.argv[2] if len(sys.argv) > 2 else "8001"
PRIMARY_URL = f"http://{PRIMARY_HOST}:{PRIMARY_PORT}"

HEALTH_CHECK_INTERVAL = 10
FAILOVER_THRESHOLD = 3


class FailoverMonitor:
    def __init__(self):
        self.failure_count = 0
        self.is_failed_over = False

    def check_primary_health(self) -> bool:
        """Check if primary is healthy."""
        try:
            r = requests.get(f"{PRIMARY_URL}/api/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Primary health check failed: {e}")
            return False

    def trigger_failover(self):
        """Activate backup trader."""
        logger.critical("🚨 FAILOVER TRIGGERED - Primary is down!")

        try:
            # Method 1: Try systemd service (if configured)
            try:
                subprocess.run(
                    ["sudo", "systemctl", "restart", "backup-trader"],
                    check=True,
                    timeout=30
                )
                self.is_failed_over = True
                logger.critical("✅ Backup trader activated via systemd")
                return
            except Exception as e:
                logger.warning(f"Systemd activation failed: {e}")

            # Method 2: Activate via SSH to remote backup machine
            logger.info("Attempting SSH activation of backup trader...")
            ssh_cmd = [
                "ssh",
                "-i", "/home/vali/.ssh/openhab_claude",
                "-p", "2347",
                "claude@192.168.3.25",
                "cd /home/claude/crypto-daytrading && "
                "/home/claude/venv/bin/python -m uvicorn backend.api.main:app "
                "--host 0.0.0.0 --port 8002 > /tmp/backup-trader.log 2>&1 &"
            ]
            subprocess.run(ssh_cmd, check=True, timeout=30)
            self.is_failed_over = True
            logger.critical("✅ Backup trader activated via SSH (192.168.3.25:8002)")
        except Exception as e:
            logger.error(f"Failover activation failed (both methods): {e}")

    def run(self):
        """Main monitoring loop."""
        logger.info("Failover monitor started")
        logger.info(f"Monitoring primary at: {PRIMARY_URL}")
        logger.info(f"Health check interval: {HEALTH_CHECK_INTERVAL}s")
        logger.info(f"Failover threshold: {FAILOVER_THRESHOLD} missed checks")

        while True:
            try:
                if self.check_primary_health():
                    # Primary is healthy
                    self.failure_count = 0
                    if not self.is_failed_over:
                        logger.info("Primary healthy - backup in standby")
                else:
                    # Primary is down
                    self.failure_count += 1
                    logger.warning(f"Primary check #{self.failure_count} failed")

                    if self.failure_count >= FAILOVER_THRESHOLD:
                        self.trigger_failover()

                time.sleep(HEALTH_CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Failover monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)


if __name__ == "__main__":
    monitor = FailoverMonitor()
    monitor.run()
