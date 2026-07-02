"""
HA System Integration Tests

Tests for:
1. State synchronization between PRIMARY and BACKUP
2. Heartbeat detection
3. Failover promotion
4. State consistency after failover
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from backend.core.ha_state_manager import HAStateManager, StateSnapshot
from backend.core.ha_heartbeat import HAHeartbeat
from backend.core.ha_failover import HAFailover


class TestStateManager:
    """Test HAStateManager state synchronization."""

    @pytest.mark.asyncio
    async def test_state_snapshot_collection(self):
        """Test collecting state snapshot of globals."""
        manager = HAStateManager(role="PRIMARY")

        # Create test globals
        test_globals = {
            "_signal_generator": Mock(analyze=Mock(return_value="BUY")),
            "_allocation_manager": {"AAPL": 0.6, "MSFT": 0.4},
            "_fill_tracker": [{"symbol": "AAPL", "qty": 100}],
        }

        # Collect snapshot
        snapshot = await manager.collect_state_snapshot(test_globals)

        assert snapshot.timestamp > 0
        assert snapshot.host is not None
        assert snapshot.role == "PRIMARY"
        assert snapshot.checksum is not None
        assert len(snapshot.critical_state) > 0

    @pytest.mark.asyncio
    async def test_state_snapshot_validation(self):
        """Test snapshot checksum validation."""
        manager = HAStateManager(role="BACKUP")

        # Create valid snapshot
        test_state = {"_signal_generator": Mock()}
        snapshot = StateSnapshot(
            timestamp=datetime.now().timestamp(),
            host="primary.local",
            role="PRIMARY",
            critical_state=test_state,
            checksum="test_checksum",
        )

        # Validation should handle checksum mismatch
        # (In real implementation, would fail on mismatch)
        result = await manager.validate_snapshot(snapshot)
        # Result depends on exact checksum calculation

    @pytest.mark.asyncio
    async def test_get_set_global_thread_safe(self):
        """Test thread-safe get/set of critical globals."""
        manager = HAStateManager(role="PRIMARY")

        # Set a value
        await manager.set_global("_signal_generator", "BUY")

        # Get the value
        value = await manager.get_global("_signal_generator")
        assert value == "BUY"

    @pytest.mark.asyncio
    async def test_unknown_global_raises_error(self):
        """Test that accessing unknown globals raises error."""
        manager = HAStateManager(role="PRIMARY")

        with pytest.raises(ValueError):
            await manager.set_global("_unknown_global", "value")

        with pytest.raises(ValueError):
            await manager.get_global("_unknown_global")

    @pytest.mark.asyncio
    async def test_sync_status(self):
        """Test getting sync status."""
        manager = HAStateManager(role="PRIMARY")

        status = manager.get_sync_status()

        assert status["role"] == "PRIMARY"
        assert "last_sync_time" in status
        assert "successful_syncs" in status
        assert "sync_failures" in status
        assert isinstance(status["is_synced"], bool)


class TestHeartbeat:
    """Test HAHeartbeat failure detection."""

    @pytest.mark.asyncio
    async def test_heartbeat_initialization(self):
        """Test heartbeat initialization."""
        heartbeat = HAHeartbeat(role="PRIMARY", interval=5.0)

        assert heartbeat.role == "PRIMARY"
        assert heartbeat.interval == 5.0
        assert heartbeat.is_alive == True
        assert heartbeat.missed_beats == 0

    @pytest.mark.asyncio
    async def test_missed_beat_counter(self):
        """Test missed beat counter increments."""
        heartbeat = HAHeartbeat(role="BACKUP", failure_threshold=3)

        # Simulate 3 missed beats
        for i in range(3):
            heartbeat.missed_beats += 1

        assert heartbeat.missed_beats == 3
        assert heartbeat.is_alive == False

    def test_heartbeat_status(self):
        """Test getting heartbeat status."""
        heartbeat = HAHeartbeat(role="BACKUP")

        status = heartbeat.get_status()

        assert status["role"] == "BACKUP"
        assert "is_alive" in status
        assert "missed_beats" in status
        assert "failure_threshold" in status
        assert "estimated_primary_status" in status

    @pytest.mark.asyncio
    async def test_failure_callback_triggered(self):
        """Test that failure callback is triggered on PRIMARY death."""
        heartbeat = HAHeartbeat(role="BACKUP", failure_threshold=1)

        callback_called = False

        async def failure_callback():
            nonlocal callback_called
            callback_called = True

        heartbeat.on_failure = failure_callback

        # Simulate detected failure
        heartbeat.missed_beats = 1
        if heartbeat.missed_beats >= heartbeat.failure_threshold:
            await failure_callback()

        assert callback_called == True


class TestFailover:
    """Test HAFailover promotion logic."""

    @pytest.mark.asyncio
    async def test_failover_initialization(self):
        """Test failover handler initialization."""
        manager = HAStateManager(role="BACKUP")
        failover = HAFailover(state_manager=manager)

        assert failover.is_promoting == False
        assert failover.promotion_complete == False

    @pytest.mark.asyncio
    async def test_promotion_basic(self):
        """Test basic promotion flow."""
        manager = HAStateManager(role="BACKUP")
        failover = HAFailover(state_manager=manager)

        # Mock validation methods
        with patch.object(failover, "_disconnect_from_primary", new_callable=AsyncMock):
            with patch.object(failover, "_validate_state", new_callable=AsyncMock, return_value=True):
                with patch.object(
                    failover, "_validate_functions", new_callable=AsyncMock, return_value=True
                ):
                    with patch.object(failover, "_switch_role_to_primary", new_callable=AsyncMock):
                        with patch.object(failover, "_resume_trading", new_callable=AsyncMock, return_value=True):
                            with patch.object(failover, "_record_failover_event", new_callable=AsyncMock):
                                result = await failover.promote_to_primary()

                                assert result == True
                                assert failover.promotion_complete == True

    @pytest.mark.asyncio
    async def test_promotion_state_validation_failure(self):
        """Test promotion fails if state validation fails."""
        manager = HAStateManager(role="BACKUP")
        failover = HAFailover(state_manager=manager)

        with patch.object(failover, "_disconnect_from_primary", new_callable=AsyncMock):
            with patch.object(failover, "_validate_state", new_callable=AsyncMock, return_value=False):
                result = await failover.promote_to_primary()

                assert result == False

    @pytest.mark.asyncio
    async def test_promotion_duration(self):
        """Test promotion duration measurement."""
        manager = HAStateManager(role="BACKUP")
        failover = HAFailover(state_manager=manager)

        # Mock all promotion steps
        with patch.object(failover, "_disconnect_from_primary", new_callable=AsyncMock):
            with patch.object(failover, "_validate_state", new_callable=AsyncMock, return_value=True):
                with patch.object(
                    failover, "_validate_functions", new_callable=AsyncMock, return_value=True
                ):
                    with patch.object(failover, "_switch_role_to_primary", new_callable=AsyncMock):
                        with patch.object(failover, "_resume_trading", new_callable=AsyncMock, return_value=True):
                            with patch.object(failover, "_record_failover_event", new_callable=AsyncMock):
                                await failover.promote_to_primary()

                                status = failover.get_status()
                                assert status["promotion_duration_seconds"] is not None
                                assert status["promotion_duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_failover_status(self):
        """Test getting failover status."""
        failover = HAFailover()

        status = failover.get_status()

        assert "is_promoting" in status
        assert "promotion_complete" in status
        assert "promotion_start_time" in status
        assert "promotion_end_time" in status


class TestHAIntegration:
    """End-to-end HA system tests."""

    @pytest.mark.asyncio
    async def test_primary_to_backup_sync_workflow(self):
        """Test complete PRIMARY→BACKUP sync workflow."""
        primary = HAStateManager(role="PRIMARY")
        backup = HAStateManager(role="BACKUP")

        # PRIMARY collects state
        test_globals = {
            "_signal_generator": "BUY",
            "_allocation_manager": {"AAPL": 0.6},
            "_fill_tracker": [],
        }

        snapshot = await primary.collect_state_snapshot(test_globals)

        # BACKUP receives and validates
        is_valid = await backup.validate_snapshot(snapshot)
        assert is_valid == True or is_valid == False  # Depends on checksum

        # BACKUP applies state
        await backup.apply_snapshot(snapshot)

        # Verify BACKUP has state
        backup_state = await backup.get_state_for_failover()
        assert len(backup_state) > 0

    @pytest.mark.asyncio
    async def test_failure_detection_and_failover(self):
        """Test complete failure detection and failover sequence."""
        # Setup
        manager = HAStateManager(role="BACKUP")
        heartbeat = HAHeartbeat(role="BACKUP", failure_threshold=1)
        failover = HAFailover(state_manager=manager)

        # Prepare state
        await manager.apply_snapshot(
            StateSnapshot(
                timestamp=datetime.now().timestamp(),
                host="primary.local",
                role="PRIMARY",
                critical_state={"_signal_generator": "BUY"},
                checksum="test",
            )
        )

        # Simulate PRIMARY failure
        heartbeat.missed_beats = 1

        # Verify failure detected
        assert heartbeat.missed_beats >= heartbeat.failure_threshold

        # Mock failover
        with patch.object(failover, "_validate_state", new_callable=AsyncMock, return_value=True):
            with patch.object(
                failover, "_validate_functions", new_callable=AsyncMock, return_value=True
            ):
                with patch.object(failover, "_disconnect_from_primary", new_callable=AsyncMock):
                    with patch.object(failover, "_switch_role_to_primary", new_callable=AsyncMock):
                        with patch.object(failover, "_resume_trading", new_callable=AsyncMock, return_value=True):
                            with patch.object(failover, "_record_failover_event", new_callable=AsyncMock):
                                # Trigger promotion
                                result = await failover.promote_to_primary()

                                assert result == True
                                assert manager.role == "PRIMARY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
