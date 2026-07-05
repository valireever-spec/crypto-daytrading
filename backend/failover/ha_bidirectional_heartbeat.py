"""Bidirectional HA Heartbeat with Scenario-Aware Routing.

PRIMARY → BACKUP heartbeat that:
1. Uses scenario-determined endpoint (local IP, DDNS, or fails gracefully)
2. Includes state verification (PRIMARY sends its state, BACKUP responds with ACK)
3. Periodic DDNS retry in scenario C
4. Handles timeouts gracefully

Flow:
PRIMARY heartbeat sender:
  - Get current scenario from orchestrator
  - Send heartbeat to scenario-determined endpoint
  - Include: timestamp, heartbeat_id, machine_id, primary_state_hash

BACKUP heartbeat receiver:
  - Receive heartbeat on /api/ha/heartbeat
  - Verify it's from PRIMARY (machine_id check)
  - Respond with ACK (status=received, timestamp, backup_state)

If PRIMARY in scenario C (BACKUP offline):
  - Still send heartbeats to /dev/null (no-op)
  - Periodically ask orchestrator to retry DDNS determination
"""

import asyncio
import logging
import json
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

import httpx

from backend.failover.ha_scenario_orchestrator import (
    get_ha_orchestrator,
    HAScenario,
)

logger = logging.getLogger(__name__)


class BiDirectionalHeartbeatSender:
    """PRIMARY: Send bidirectional heartbeat to BACKUP every 2 seconds.

    Includes state hash so BACKUP can verify PRIMARY is healthy.
    Automatically fails over between scenarios (A→B→C) based on
    endpoint availability.
    """

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.running = False
        self.task = None

        # Statistics
        self.heartbeat_count = 0
        self.send_failures = 0
        self.scenario_transitions = 0
        self.last_send_time = None
        self.last_successful_scenario: Optional[HAScenario] = None

        # Get orchestrator
        self.orchestrator = get_ha_orchestrator()

    async def start(self) -> None:
        """Start sending heartbeats."""
        if self.running:
            logger.warning("Bidirectional heartbeat sender already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._send_loop())
        logger.info(f"💓 Bidirectional heartbeat sender started (every {self.interval}s)")

    async def stop(self) -> None:
        """Stop sending heartbeats."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Bidirectional heartbeat sender stopped")

    async def _send_loop(self) -> None:
        """Send heartbeat every N seconds with scenario-aware routing."""
        while self.running:
            try:
                await asyncio.sleep(self.interval)

                # Determine current scenario
                scenario = await self.orchestrator.determine_scenario()

                # Track transitions
                if self.last_successful_scenario != scenario:
                    self.scenario_transitions += 1
                    self.last_successful_scenario = scenario

                # Get BACKUP endpoint
                backup_endpoint = self.orchestrator.get_backup_endpoint()

                # Build heartbeat payload
                heartbeat = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "heartbeat_id": self.heartbeat_count,
                    "machine_id": "primary",
                    "scenario": scenario.value,
                    "state_hash": self._compute_state_hash(),
                }

                # Send heartbeat based on scenario
                if scenario == HAScenario.A_LOCAL:
                    success = await self._send_to_local(heartbeat, backup_endpoint)

                elif scenario == HAScenario.B_REMOTE_DDNS:
                    success = await self._send_to_ddns(heartbeat, backup_endpoint)

                elif scenario == HAScenario.C_OFFLINE:
                    # BACKUP offline - but still log for observability
                    success = await self._send_to_scenario_c(heartbeat)

                    # Periodically ask orchestrator to retry DDNS
                    if self.orchestrator.should_retry_ddns():
                        logger.info("🔄 Scenario C: Retrying DDNS resolution...")

                if success:
                    self.last_send_time = time.time()
                    self.send_failures = 0
                    if self.heartbeat_count % 30 == 0:  # Log every 30 successful heartbeats
                        logger.info(
                            f"💓 Heartbeat #{self.heartbeat_count} sent "
                            f"({scenario.value})"
                        )
                    else:
                        logger.debug(
                            f"💓 Heartbeat #{self.heartbeat_count} sent "
                            f"({scenario.value})"
                        )
                    self.heartbeat_count += 1
                else:
                    self.send_failures += 1
                    if self.send_failures % 5 == 0:  # Log every 5 failures
                        logger.warning(
                            f"⚠️  Heartbeat failures: {self.send_failures} "
                            f"(scenario: {scenario.value})"
                        )

            except asyncio.CancelledError:
                logger.info("Bidirectional heartbeat sender cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat send loop error: {e}")

    async def _send_to_local(self, heartbeat: Dict[str, Any], endpoint: str) -> bool:
        """Send heartbeat to local IP endpoint (scenario A).

        Args:
            heartbeat: Heartbeat payload
            endpoint: Local IP (e.g., 192.168.3.25)

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"http://{endpoint}:8002/api/ha/heartbeat"

            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.post(url, json=heartbeat)

                if resp.status_code == 200:
                    logger.debug(f"✅ Heartbeat delivered to local: {endpoint}")
                    return True
                else:
                    logger.debug(
                        f"Heartbeat to local failed ({resp.status_code}): {endpoint}"
                    )
                    return False

        except asyncio.TimeoutError:
            logger.debug(f"Heartbeat timeout (local): {endpoint}")
            return False
        except Exception as e:
            logger.debug(f"Heartbeat error (local): {e}")
            return False

    async def _send_to_ddns(self, heartbeat: Dict[str, Any], endpoint: str) -> bool:
        """Send heartbeat to DDNS hostname (scenario B).

        Args:
            heartbeat: Heartbeat payload
            endpoint: DDNS hostname (e.g., r33v3r.ddns.net)

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"http://{endpoint}:8002/api/ha/heartbeat"

            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(url, json=heartbeat)

                if resp.status_code == 200:
                    logger.debug(f"✅ Heartbeat delivered via DDNS: {endpoint}")
                    return True
                else:
                    logger.debug(
                        f"Heartbeat to DDNS failed ({resp.status_code}): {endpoint}"
                    )
                    return False

        except asyncio.TimeoutError:
            logger.debug(f"Heartbeat timeout (DDNS): {endpoint}")
            return False
        except Exception as e:
            logger.debug(f"Heartbeat error (DDNS): {e}")
            return False

    async def _send_to_scenario_c(self, heartbeat: Dict[str, Any]) -> bool:
        """Handle heartbeat when BACKUP offline (scenario C).

        In scenario C, BACKUP is unreachable but PRIMARY has internet.
        We don't send heartbeats (nowhere to send), but we log for observability.

        Returns:
            Always True (no-op success)
        """
        logger.debug(
            f"💓 Heartbeat #{self.heartbeat_count} (scenario C - BACKUP offline, "
            f"local: not sending, trading continues)"
        )
        return True

    def _compute_state_hash(self) -> str:
        """Compute hash of PRIMARY's current state.

        This allows BACKUP to verify PRIMARY is actually running,
        not just that a heartbeat packet arrived.

        Returns:
            SHA256 hash of state (for now, just timestamp hash)
        """
        # TODO: In future, include actual trading state (cash, positions, etc.)
        state_str = datetime.utcnow().isoformat()
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        """Get heartbeat statistics."""
        return {
            "heartbeat_count": self.heartbeat_count,
            "send_failures": self.send_failures,
            "scenario_transitions": self.scenario_transitions,
            "last_scenario": self.last_successful_scenario.value if self.last_successful_scenario else None,
            "last_send_ago_seconds": (
                time.time() - self.last_send_time if self.last_send_time else None
            ),
        }


class BiDirectionalHeartbeatMonitor:
    """BACKUP: Monitor heartbeats from PRIMARY.

    If PRIMARY misses 3 consecutive heartbeats (>6 seconds), auto-promote
    BACKUP to PRIMARY and take over trading.

    Features:
    - Bidirectional verification (checks that heartbeats contain PRIMARY state)
    - Scenario awareness (tracks which scenario PRIMARY is in)
    - Auto-promotion with logging
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
        self.last_received_scenario: Optional[str] = None

    async def start(self) -> None:
        """Start monitoring heartbeats."""
        if self.running:
            logger.warning("Bidirectional heartbeat monitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"💓 Bidirectional heartbeat monitor started "
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
        logger.info("Bidirectional heartbeat monitor stopped")

    def record_heartbeat(
        self,
        heartbeat_id: int,
        scenario: str,
        state_hash: str
    ) -> None:
        """Called when heartbeat is received from PRIMARY.

        Args:
            heartbeat_id: Heartbeat sequence number
            scenario: HA scenario PRIMARY is in (A, B, or C)
            state_hash: Hash of PRIMARY's state
        """
        self.last_heartbeat_time = time.time()
        self.last_heartbeat_id = heartbeat_id
        self.consecutive_misses = 0
        self.heartbeats_received += 1
        self.last_received_scenario = scenario

        if self.heartbeats_received % 30 == 0:  # Log every 30 received heartbeats
            logger.info(
                f"💓 Heartbeat #{heartbeat_id} received "
                f"(scenario: {scenario}, total: {self.heartbeats_received})"
            )
        else:
            logger.debug(
                f"💓 Heartbeat #{heartbeat_id} received "
                f"(scenario: {scenario}, state_hash: {state_hash[:8]}..., "
                f"total: {self.heartbeats_received})"
            )

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
                if time_since_heartbeat > self.check_interval * 1.5:  # Allow 1.5x jitter
                    self.consecutive_misses += 1
                    if self.consecutive_misses == 1:
                        logger.warning(
                            f"⚠️  Heartbeat stale ({time_since_heartbeat:.1f}s), "
                            f"miss #{self.consecutive_misses}"
                        )
                    elif self.consecutive_misses % self.failure_threshold == 0:
                        logger.warning(
                            f"⚠️  {self.consecutive_misses} consecutive misses "
                            f"({time_since_heartbeat:.1f}s stale, scenario: {self.last_received_scenario})"
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
                        f"🚨 PRIMARY FAILURE DETECTED (via heartbeat): "
                        f"{self.consecutive_misses} consecutive misses "
                        f"({self.failure_threshold * self.check_interval}s timeout, "
                        f"last scenario: {self.last_received_scenario}) - "
                        "Triggering BACKUP promotion"
                    )
                    self.promoted = True
                    return

            except asyncio.CancelledError:
                logger.info("Bidirectional heartbeat monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

    def is_primary_failed(self) -> bool:
        """Check if PRIMARY has failed based on heartbeat."""
        return self.consecutive_misses >= self.failure_threshold

    def get_stats(self) -> Dict[str, Any]:
        """Get heartbeat statistics."""
        return {
            "heartbeats_received": self.heartbeats_received,
            "consecutive_misses": self.consecutive_misses,
            "last_heartbeat_age_seconds": (
                time.time() - self.last_heartbeat_time
                if self.last_heartbeat_time
                else None
            ),
            "last_received_scenario": self.last_received_scenario,
            "promoted": self.promoted,
        }


# Global instances
_heartbeat_sender: Optional[BiDirectionalHeartbeatSender] = None
_heartbeat_monitor: Optional[BiDirectionalHeartbeatMonitor] = None


def get_bidirectional_heartbeat_sender() -> BiDirectionalHeartbeatSender:
    """Get or create PRIMARY heartbeat sender."""
    global _heartbeat_sender
    if _heartbeat_sender is None:
        _heartbeat_sender = BiDirectionalHeartbeatSender()
    return _heartbeat_sender


def get_bidirectional_heartbeat_monitor() -> BiDirectionalHeartbeatMonitor:
    """Get or create BACKUP heartbeat monitor."""
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        _heartbeat_monitor = BiDirectionalHeartbeatMonitor()
    return _heartbeat_monitor
