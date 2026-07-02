"""
HA Heartbeat Monitor: Detects PRIMARY failure and triggers failover.

PRIMARY sends heartbeat every 5 seconds.
BACKUP monitors for 3 missed beats = 15 seconds = triggers failover.
"""

import asyncio
import logging
import time
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class HAHeartbeat:
    """
    Dual-machine heartbeat mechanism.

    PRIMARY:  Sends heartbeat every 5 seconds
    BACKUP:   Monitors heartbeat, detects failure after 15 seconds
    """

    def __init__(
        self,
        role: str = "PRIMARY",
        interval: float = 5.0,
        timeout: float = 6.0,  # Allow 1 extra second
        failure_threshold: int = 3,  # 3 missed beats
        primary_port: int = 9998,
        backup_port: int = 9999
    ):
        """
        Initialize heartbeat monitor.

        Args:
            role: "PRIMARY" or "BACKUP"
            interval: Heartbeat interval (seconds) - PRIMARY sends
            timeout: Read timeout per beat - BACKUP waits
            failure_threshold: Consecutive missed beats to trigger failover
            primary_port: PRIMARY's heartbeat server port
            backup_port: BACKUP's heartbeat server port
        """
        self.role = role
        self.interval = interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.primary_port = primary_port
        self.backup_port = backup_port

        # Heartbeat state
        self.last_heartbeat_time: Optional[float] = None
        self.missed_beats = 0
        self.is_alive = True
        self.is_running = False

        # Callbacks
        self.on_failure: Optional[Callable] = None
        self.on_recovery: Optional[Callable] = None

        logger.info(
            f"HAHeartbeat initialized: role={role}, interval={interval}s, "
            f"timeout={timeout}s, failure_threshold={failure_threshold}"
        )

    async def start_heartbeat_sender(self) -> None:
        """
        PRIMARY: Send heartbeat to BACKUP every 5 seconds.
        """
        if self.role != "PRIMARY":
            logger.error("Only PRIMARY can send heartbeat")
            return

        self.is_running = True
        logger.info("PRIMARY heartbeat sender started")

        try:
            while self.is_running:
                try:
                    # Create heartbeat packet
                    heartbeat_data = {
                        "role": "PRIMARY",
                        "timestamp": time.time(),
                        "is_alive": True
                    }

                    # Send to BACKUP
                    try:
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection("localhost", self.backup_port),
                            timeout=2.0
                        )
                        writer.write(str(heartbeat_data).encode())
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                        logger.debug(f"Heartbeat sent to BACKUP at {heartbeat_data['timestamp']}")
                    except asyncio.TimeoutError:
                        logger.warning("BACKUP connection timeout (network issue?)")
                    except Exception as e:
                        logger.warning(f"Failed to send heartbeat to BACKUP: {e}")

                    # Wait before next heartbeat
                    await asyncio.sleep(self.interval)

                except Exception as e:
                    logger.error(f"Heartbeat sender error: {e}")
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("PRIMARY heartbeat sender stopped")
        finally:
            self.is_running = False

    async def start_heartbeat_monitor(self, on_failure: Optional[Callable] = None) -> None:
        """
        BACKUP: Monitor PRIMARY heartbeat and trigger failover on failure.

        Args:
            on_failure: Callback to invoke on PRIMARY failure
        """
        if self.role != "BACKUP":
            logger.error("Only BACKUP can monitor heartbeat")
            return

        self.on_failure = on_failure
        self.is_running = True
        self.missed_beats = 0
        logger.info("BACKUP heartbeat monitor started")

        try:
            while self.is_running:
                try:
                    # Wait for heartbeat from PRIMARY with timeout
                    await asyncio.wait_for(
                        self._wait_for_heartbeat(),
                        timeout=self.timeout
                    )
                    # Heartbeat received
                    self.missed_beats = 0
                    self.is_alive = True
                    logger.debug("Heartbeat received from PRIMARY")

                except asyncio.TimeoutError:
                    # Heartbeat missed
                    self.missed_beats += 1
                    logger.warning(
                        f"Heartbeat missed from PRIMARY ({self.missed_beats}/{self.failure_threshold})"
                    )

                    # Check if PRIMARY is dead (too many missed beats)
                    if self.missed_beats >= self.failure_threshold:
                        self.is_alive = False
                        logger.critical(
                            f"PRIMARY failure detected: {self.missed_beats} missed beats "
                            f"({self.missed_beats * self.interval:.1f}s)"
                        )

                        # Trigger failover callback
                        if self.on_failure:
                            try:
                                if asyncio.iscoroutinefunction(self.on_failure):
                                    await self.on_failure()
                                else:
                                    self.on_failure()
                            except Exception as e:
                                logger.error(f"Failover callback failed: {e}")

                        # Stop monitoring (failover takes over)
                        break

                except Exception as e:
                    logger.error(f"Heartbeat monitor error: {e}")
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("BACKUP heartbeat monitor stopped")
        finally:
            self.is_running = False

    async def _wait_for_heartbeat(self) -> None:
        """
        BACKUP: Internal method to wait for heartbeat.
        Actual implementation would listen on a socket/stream.
        """
        # This is a placeholder - real implementation would listen on BACKUP_PORT
        await asyncio.sleep(0.1)

    async def stop(self) -> None:
        """Stop heartbeat sender/monitor."""
        self.is_running = False
        logger.info(f"HAHeartbeat stopped ({self.role})")

    def get_status(self) -> dict:
        """
        Get heartbeat status.

        Returns:
            Status dict with heartbeat metrics
        """
        time_since_beat = (
            time.time() - self.last_heartbeat_time
            if self.last_heartbeat_time
            else None
        )

        return {
            "role": self.role,
            "is_alive": self.is_alive,
            "is_running": self.is_running,
            "missed_beats": self.missed_beats,
            "failure_threshold": self.failure_threshold,
            "time_since_last_beat_seconds": time_since_beat,
            "estimated_primary_status": "ALIVE" if self.is_alive else "DEAD",
        }
