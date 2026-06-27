"""Stress test for HA heartbeat monitor - simulate PRIMARY failure during trading."""

import asyncio
import pytest
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import requests

from backend.failover.heartbeat import HeartbeatMonitor, get_heartbeat
from backend.failover.ha_wrapper import HATraderWrapper, get_ha_wrapper
from backend.core.alerting import get_alert_manager


logger = logging.getLogger(__name__)


class TestHAHeartbeatStress:
    """Stress tests for HA failover scenarios."""

    @pytest.mark.asyncio
    async def test_primary_failure_detection_time(self):
        """
        SCENARIO: PRIMARY stops responding during active trading
        GOAL: Verify failover is detected within acceptable time (<20 seconds)
        """
        monitor = HeartbeatMonitor(
            primary_url="http://127.0.0.1:8001",
            heartbeat_interval=2,  # 2-second checks for testing
            failure_threshold=2,   # Fail after 2 consecutive failures = 4 seconds
        )

        start_time = datetime.utcnow()
        failure_detected = False

        # Mock requests.get to fail after 4 seconds
        call_count = [0]

        def mock_health_check(*args, **kwargs):
            call_count[0] += 1
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            if elapsed < 4:
                # Healthy for first 4 seconds
                response = Mock()
                response.status_code = 200
                response.json.return_value = {"cash": 1000, "positions": []}
                return response
            else:
                # Fail after 4 seconds
                raise requests.ConnectionError("Connection refused")

        with patch("backend.failover.heartbeat.requests.get", side_effect=mock_health_check):
            # Run monitor loop for 15 seconds
            monitor._running = True
            monitor_task = asyncio.create_task(monitor.start())

            try:
                for i in range(15):
                    await asyncio.sleep(1)
                    if not monitor.is_healthy():
                        failure_detected = True
                        failure_time = datetime.utcnow()
                        break

            finally:
                monitor._running = False
                try:
                    await asyncio.wait_for(monitor_task, timeout=1)
                except asyncio.TimeoutError:
                    monitor_task.cancel()

        # Verify failover was detected
        assert failure_detected, "Failure was not detected"
        detection_delay = (failure_time - start_time).total_seconds()
        assert detection_delay < 15, f"Failure detection took {detection_delay}s (>15s)"
        logger.info(f"✅ PRIMARY failure detected in {detection_delay:.1f}s")

    @pytest.mark.asyncio
    async def test_primary_recovery_reversion(self):
        """
        SCENARIO: PRIMARY comes back online after failure
        GOAL: Verify system reverts to healthy once PRIMARY recovers
        """
        monitor = HeartbeatMonitor(
            primary_url="http://127.0.0.1:8001",
            heartbeat_interval=1,
            failure_threshold=2,
        )

        start_time = datetime.utcnow()
        health_transitions = []

        call_count = [0]

        def mock_health_check(*args, **kwargs):
            call_count[0] += 1
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            if elapsed < 3:  # Healthy first
                response = Mock()
                response.status_code = 200
                response.json.return_value = {"cash": 1000}
                return response
            elif elapsed < 8:  # Fails 3-8 seconds
                raise requests.ConnectionError("Connection refused")
            else:  # Recovers after 8 seconds
                response = Mock()
                response.status_code = 200
                response.json.return_value = {"cash": 1000}
                return response

        with patch("backend.failover.heartbeat.requests.get", side_effect=mock_health_check):
            monitor._running = True
            monitor_task = asyncio.create_task(monitor.start())

            try:
                prev_health = True
                for i in range(15):
                    await asyncio.sleep(1)
                    current_health = monitor.is_healthy()

                    if current_health != prev_health:
                        health_transitions.append((datetime.utcnow(), current_health))
                        logger.info(f"Health transition: {current_health}")
                        prev_health = current_health

                    if len(health_transitions) >= 2:  # healthy → unhealthy → healthy
                        break

            finally:
                monitor._running = False
                try:
                    await asyncio.wait_for(monitor_task, timeout=1)
                except asyncio.TimeoutError:
                    monitor_task.cancel()

        # Verify state transitions: healthy → unhealthy → healthy
        assert len(health_transitions) >= 2, f"Expected 2+ state changes, got {len(health_transitions)}"
        states = [state for _, state in health_transitions]
        assert states[0] == False, f"Should fail (unhealthy), got {states[0]}"
        assert states[1] == True, f"Should recover (healthy), got {states[1]}"
        logger.info(f"✅ Failover + recovery completed: {states}")

    @pytest.mark.asyncio
    async def test_multiple_rapid_failovers(self):
        """
        SCENARIO: PRIMARY flaps multiple times (unstable network)
        GOAL: Verify system handles rapid failovers gracefully
        """
        monitor = HeartbeatMonitor(
            primary_url="http://127.0.0.1:8001",
            heartbeat_interval=1,
            failure_threshold=1,  # Quick failover
        )

        health_changes = []
        call_count = [0]

        def mock_health_check(*args, **kwargs):
            call_count[0] += 1
            # Flap every 2 calls: healthy → fail → healthy → fail, etc.
            if (call_count[0] // 2) % 2 == 0:
                response = Mock()
                response.status_code = 200
                response.json.return_value = {"cash": 1000}
                return response
            else:
                raise requests.ConnectionError("Connection refused")

        with patch("backend.failover.heartbeat.requests.get", side_effect=mock_health_check):
            monitor._running = True
            monitor_task = asyncio.create_task(monitor.start())

            try:
                prev_health = True
                for i in range(20):
                    await asyncio.sleep(1)
                    current_health = monitor.is_healthy()

                    if current_health != prev_health:
                        health_changes.append(current_health)
                        logger.info(f"Health change #{len(health_changes)}: {current_health}")
                        prev_health = current_health

            finally:
                monitor._running = False
                try:
                    await asyncio.wait_for(monitor_task, timeout=1)
                except asyncio.TimeoutError:
                    monitor_task.cancel()

        # Verify system handled multiple failovers gracefully
        assert len(health_changes) >= 2, f"Expected 2+ health changes, got {len(health_changes)}"
        logger.info(f"✅ Handled {len(health_changes)} health state changes gracefully")

    def test_heartbeat_status_format(self):
        """
        SCENARIO: Verify heartbeat status can be queried
        GOAL: Ensure monitoring infrastructure works
        """
        monitor = HeartbeatMonitor(
            primary_url="http://127.0.0.1:8001",
            heartbeat_interval=5,
            failure_threshold=3,
        )

        status = monitor.get_status()

        assert isinstance(status, dict), "Status should be a dict"
        assert "primary_healthy" in status, "Status missing 'primary_healthy'"
        assert "consecutive_failures" in status, "Status missing 'consecutive_failures'"
        assert "failure_threshold" in status, "Status missing 'failure_threshold'"
        logger.info(f"✅ Heartbeat status format valid: {status}")


# Pytest will auto-discover and run these tests
# Run with: pytest tests/acceptance/test_ha_heartbeat_stress.py -v -s
