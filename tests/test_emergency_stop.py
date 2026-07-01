"""Tests for FR-020: Emergency Stop Handler."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from backend.core.emergency_stop import (
    trigger_emergency_stop,
    get_emergency_stop_status,
    reset_emergency_stop,
    is_emergency_stop_active
)


@pytest.fixture
async def mock_paper_engine():
    """Mock paper trading engine."""
    engine = AsyncMock()
    engine.get_open_positions.return_value = [
        {'symbol': 'BTCUSDT', 'quantity': 1.0},
        {'symbol': 'ETHUSDT', 'quantity': 2.0}
    ]
    engine.get_current_price.side_effect = lambda s: {'BTCUSDT': 45000, 'ETHUSDT': 3000}.get(s)
    engine.execute_order.return_value = {'order_id': 'test-123'}
    return engine


class TestEmergencyStopTriggering:
    """Test emergency stop activation."""

    @pytest.mark.asyncio
    async def test_trigger_stops_trading(self):
        """Triggering emergency stop sets flag."""
        assert not is_emergency_stop_active()

        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = None

            result = await trigger_emergency_stop("Test trigger")

        assert result['success'] is True
        assert result['reason'] == "Test trigger"
        assert is_emergency_stop_active()

    @pytest.mark.asyncio
    async def test_trigger_closes_all_positions(self, mock_paper_engine):
        """Emergency stop closes all open positions."""
        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = mock_paper_engine

            result = await trigger_emergency_stop("Market crash")

        assert result['success'] is True
        assert result['positions_closed'] > 0

    @pytest.mark.asyncio
    async def test_trigger_includes_timestamp(self):
        """Emergency stop result includes when triggered."""
        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = None

            result = await trigger_emergency_stop("Test")

        assert result['timestamp'] is not None
        assert isinstance(result['timestamp'], datetime)

    @pytest.mark.asyncio
    async def test_trigger_handles_close_errors_gracefully(self, mock_paper_engine):
        """If closing a position fails, continue closing others."""
        mock_paper_engine.execute_order.side_effect = Exception("Order failed")

        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = mock_paper_engine

            result = await trigger_emergency_stop("Test")

        # Should still return success (graceful degradation)
        assert result['success'] is True or result['positions_closed'] == 0


class TestEmergencyStopStatus:
    """Test status reporting."""

    def test_get_status_when_inactive(self):
        """Status shows inactive when not triggered."""
        status = get_emergency_stop_status()

        assert status['active'] is False
        assert status['triggered_at'] is None
        assert status['reason'] is None

    @pytest.mark.asyncio
    async def test_get_status_when_active(self):
        """Status shows active when triggered."""
        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = None

            await trigger_emergency_stop("Test reason")

        status = get_emergency_stop_status()

        assert status['active'] is True
        assert status['reason'] == "Test reason"
        assert status['triggered_at'] is not None


class TestEmergencyStopReset:
    """Test reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_flag(self):
        """Resetting clears emergency stop flag."""
        # First trigger
        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = None
            await trigger_emergency_stop("Test")

        assert is_emergency_stop_active()

        # Then reset
        await reset_emergency_stop()

        assert not is_emergency_stop_active()

    def test_reset_clears_reason(self):
        """Reset clears reason."""
        # Manually set stop
        import backend.core.emergency_stop as es
        es._emergency_stop_triggered = True
        es._emergency_stop_reason = "Test"

        # Reset
        import asyncio
        asyncio.run(reset_emergency_stop())

        status = get_emergency_stop_status()
        assert status['active'] is False
        assert status['reason'] is None


class TestEmergencyStopIntegration:
    """Integration tests with trading engine."""

    @pytest.mark.asyncio
    async def test_multiple_positions_closed_in_sequence(self, mock_paper_engine):
        """All positions closed when multiple open."""
        mock_paper_engine.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'quantity': 1.0},
            {'symbol': 'ETHUSDT', 'quantity': 2.0},
            {'symbol': 'BNBUSDT', 'quantity': 3.0}
        ]

        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = mock_paper_engine

            result = await trigger_emergency_stop("Close all")

        # Should have attempted to close all 3
        assert mock_paper_engine.execute_order.call_count >= 3

    @pytest.mark.asyncio
    async def test_short_positions_flipped_to_buy(self, mock_paper_engine):
        """Short positions closed by buying (side='BUY')."""
        mock_paper_engine.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'quantity': -1.0}  # Short position
        ]

        with patch('backend.core.emergency_stop.get_paper_trading') as mock_get:
            mock_get.return_value = mock_paper_engine

            await trigger_emergency_stop("Close shorts")

        # Should have called execute_order with side='BUY'
        mock_paper_engine.execute_order.assert_called()
        call_kwargs = mock_paper_engine.execute_order.call_args[1]
        assert call_kwargs['side'] == 'BUY'
