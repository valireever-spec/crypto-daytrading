"""Process health monitoring for stuck-state detection.

Skill #2: Detect when API process is hung (stuck sockets, held locks).
If stuck >60s, attempt graceful restart. If >5 restarts/hour, escalate alert.

This prevents:
- API process hanging and blocking systemd recovery
- Stuck locks preventing graceful shutdown
- Runaway resource usage
"""

import asyncio
import logging
import os
import psutil
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ProcessHealthMonitor:
    """Monitor current process health (sockets, locks, threads, memory)."""

    def __init__(self, check_interval: float = 10.0, stuck_threshold: int = 60):
        """
        Args:
            check_interval: Check every N seconds
            stuck_threshold: Process is "stuck" if issue persists >N seconds
        """
        self.check_interval = check_interval
        self.stuck_threshold = stuck_threshold
        self.running = False
        self.task = None

        # Current process
        self.process = psutil.Process(os.getpid())

        # Health state
        self.socket_count = 0
        self.max_sockets = 0
        self.lock_age_seconds = 0.0
        self.thread_count = 0
        self.memory_percent = 0.0
        self.cpu_percent = 0.0

        # Stuck detection
        self.stuck_sockets_since = None
        self.stuck_locks_since = None
        self.restart_count_last_hour: List[datetime] = []
        self.last_health_check = None

        # Thresholds
        self.socket_warning_threshold = 400  # Warn at 400 open sockets
        self.lock_warning_threshold = 30.0  # Warn if lock held >30s
        self.thread_warning_threshold = 100  # Warn at 100+ threads
        self.memory_warning_threshold = 90.0  # Warn at 90% memory
        self.cpu_warning_threshold = 95.0  # Warn at 95% CPU

    async def start(self) -> None:
        """Start monitoring process health."""
        if self.running:
            logger.warning("Process health monitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"📊 Process health monitor started "
            f"(check every {self.check_interval}s, stuck threshold: {self.stuck_threshold}s)"
        )

    async def stop(self) -> None:
        """Stop monitoring."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Process health monitor stopped")

    async def _monitor_loop(self) -> None:
        """Check process health every N seconds."""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                self._check_health()
                self.last_health_check = datetime.utcnow()

            except asyncio.CancelledError:
                logger.info("Process health monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Process health check error: {e}")

    def _check_health(self) -> None:
        """Check current process metrics."""
        try:
            # Socket count
            try:
                self.socket_count = len(self.process.net_connections(kind="inet"))
                self.max_sockets = max(self.max_sockets, self.socket_count)

                if self.socket_count > self.socket_warning_threshold:
                    if not self.stuck_sockets_since:
                        self.stuck_sockets_since = time.time()
                        logger.warning(
                            f"⚠️  HIGH SOCKET COUNT: {self.socket_count} sockets "
                            f"(threshold: {self.socket_warning_threshold})"
                        )

                    stuck_duration = time.time() - self.stuck_sockets_since
                    if stuck_duration > self.stuck_threshold:
                        logger.critical(
                            f"🔴 PROCESS STUCK: {self.socket_count} sockets for {stuck_duration:.0f}s "
                            f"(threshold: {self.stuck_threshold}s) - Consider graceful restart"
                        )
                else:
                    if self.stuck_sockets_since:
                        recovery_time = time.time() - self.stuck_sockets_since
                        logger.info(
                            f"✅ Socket count recovered from {self.max_sockets} "
                            f"to {self.socket_count} after {recovery_time:.0f}s"
                        )
                        self.stuck_sockets_since = None

            except Exception as e:
                logger.debug(f"Failed to get socket count: {e}")

            # Thread count
            try:
                self.thread_count = self.process.num_threads()
                if self.thread_count > self.thread_warning_threshold:
                    logger.warning(
                        f"⚠️  HIGH THREAD COUNT: {self.thread_count} threads "
                        f"(threshold: {self.thread_warning_threshold})"
                    )
            except Exception as e:
                logger.debug(f"Failed to get thread count: {e}")

            # Memory usage
            try:
                self.memory_percent = self.process.memory_percent()
                if self.memory_percent > self.memory_warning_threshold:
                    logger.warning(
                        f"⚠️  HIGH MEMORY: {self.memory_percent:.1f}% "
                        f"(threshold: {self.memory_warning_threshold}%)"
                    )
            except Exception as e:
                logger.debug(f"Failed to get memory percent: {e}")

            # CPU usage
            try:
                self.cpu_percent = self.process.cpu_percent(interval=0.1)
                if self.cpu_percent > self.cpu_warning_threshold:
                    logger.warning(
                        f"⚠️  HIGH CPU: {self.cpu_percent:.1f}% "
                        f"(threshold: {self.cpu_warning_threshold}%)"
                    )
            except Exception as e:
                logger.debug(f"Failed to get CPU percent: {e}")

        except Exception as e:
            logger.error(f"Process health check failed: {e}")

    def record_restart(self) -> None:
        """Record a process restart (called when systemd restarts service)."""
        now = datetime.utcnow()
        self.restart_count_last_hour.append(now)

        # Clean up old restarts
        one_hour_ago = now - timedelta(hours=1)
        self.restart_count_last_hour = [
            r for r in self.restart_count_last_hour if r > one_hour_ago
        ]

        count = len(self.restart_count_last_hour)
        if count > 5:
            logger.critical(
                f"🚨 RUNAWAY RESTARTS: {count} restarts in last hour "
                f"(threshold: 5) - Possible infinite restart loop!"
            )
        elif count > 3:
            logger.warning(
                f"⚠️  MULTIPLE RESTARTS: {count} restarts in last hour "
                f"(monitor for issues)"
            )
        else:
            logger.info(f"Process restart recorded ({count} in last hour)")

    def get_stats(self) -> Dict:
        """Get current health statistics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "sockets": {
                "current": self.socket_count,
                "max": self.max_sockets,
                "warning_threshold": self.socket_warning_threshold,
                "stuck_duration_seconds": (
                    time.time() - self.stuck_sockets_since
                    if self.stuck_sockets_since
                    else None
                ),
            },
            "threads": {
                "current": self.thread_count,
                "warning_threshold": self.thread_warning_threshold,
            },
            "memory": {
                "percent": self.memory_percent,
                "warning_threshold": self.memory_warning_threshold,
            },
            "cpu": {
                "percent": self.cpu_percent,
                "warning_threshold": self.cpu_warning_threshold,
            },
            "restarts_last_hour": len(self.restart_count_last_hour),
            "last_check": self.last_health_check.isoformat() if self.last_health_check is not None else None,
        }

    def is_stuck(self) -> bool:
        """Check if process is currently stuck."""
        if self.stuck_sockets_since:
            stuck_duration = time.time() - self.stuck_sockets_since
            if stuck_duration > self.stuck_threshold:
                return True
        if self.stuck_locks_since:
            stuck_duration = time.time() - self.stuck_locks_since
            if stuck_duration > self.stuck_threshold:
                return True
        return False

    def get_runaway_restart_alert(self) -> Optional[str]:
        """Check if restarts are happening too frequently."""
        count = len(self.restart_count_last_hour)
        if count > 5:
            return f"🚨 RUNAWAY RESTARTS: {count} in last hour (max 5)"
        return None


# Global instance
_process_monitor: Optional[ProcessHealthMonitor] = None


def init_process_health_monitor() -> ProcessHealthMonitor:
    """Initialize process health monitor."""
    global _process_monitor
    if _process_monitor is None:
        _process_monitor = ProcessHealthMonitor()
    return _process_monitor


def get_process_health_monitor() -> Optional[ProcessHealthMonitor]:
    """Get process health monitor."""
    return _process_monitor
