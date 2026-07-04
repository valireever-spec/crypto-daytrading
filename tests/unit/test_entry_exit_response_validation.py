"""Unit tests for entry/exit response validation.

These tests verify that entry.py and exit.py correctly handle place_order() responses.
They catch interface mismatches like the bug where code checked for "success" 
when place_order() returns "status".
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from backend.exchange.order_response import OrderResponse, validate_order_response
from backend.trading.autonomous_trader.entry import _execute_entry_impl
from backend.trading.autonomous_trader.exit import _execute_exit_impl


class TestOrderResponseValidation:
    """Test response schema validation."""

    def test_valid_filled_response(self):
        """Test validation of valid FILLED response."""
        response_dict = {
            "status": "FILLED",
            "order_id": "uuid-123",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 45000.50,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:30:49Z",
        }
        
        validated = validate_order_response(response_dict)
        assert validated.status == "FILLED"
        assert validated.order_id == "uuid-123"
        assert validated.symbol == "BTCUSDT"

    def test_response_missing_required_field(self):
        """Test that validation fails when required field is missing."""
        response_dict = {
            "order_id": "uuid-123",
            "symbol": "BTCUSDT",
            # Missing "status" - should fail validation
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 45000.50,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:30:49Z",
        }
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            validate_order_response(response_dict)

    def test_response_invalid_status_value(self):
        """Test that validation fails with invalid status."""
        response_dict = {
            "status": "INVALID_STATUS",  # Not in Literal["FILLED", "REJECTED", ...]
            "order_id": "uuid-123",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 45000.50,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:30:49Z",
        }
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            validate_order_response(response_dict)


@pytest.mark.asyncio
class TestEntryResponseHandling:
    """Test entry execution with mocked place_order responses."""

    async def test_entry_success_with_filled_response(self):
        """Test entry correctly detects FILLED status."""
        # Mock dependencies
        mock_signal = MagicMock()
        mock_signal.symbol = "BTCUSDT"
        mock_signal.reason = "momentum_signal"
        
        mock_trader = MagicMock()
        mock_trader.config.position_size_pct = 2.5
        
        mock_engine = AsyncMock()
        mock_engine.place_order = AsyncMock(return_value={
            "status": "FILLED",
            "order_id": "uuid-123",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 45000.50,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:30:49Z",
        })
        
        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', 
                   return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client') as mock_stream:
                mock_stream.return_value.price_cache = {"BTCUSDT": 45000.50}
                
                # Execute entry
                result = await _execute_entry_impl(mock_trader, mock_signal)
        
        # Entry should succeed (response status = FILLED)
        assert result is True

    async def test_entry_failure_with_rejected_response(self):
        """Test entry correctly detects REJECTED status."""
        mock_signal = MagicMock()
        mock_signal.symbol = "BTCUSDT"
        mock_signal.reason = "momentum_signal"
        
        mock_trader = MagicMock()
        mock_trader.config.position_size_pct = 2.5
        
        mock_engine = AsyncMock()
        mock_engine.place_order = AsyncMock(return_value={
            "status": "REJECTED",
            "order_id": "uuid-456",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 0.0,
            "fee": 0.0,
            "timestamp": "2026-07-04T10:30:49Z",
            "error": "Insufficient balance",
        })
        
        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', 
                   return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client') as mock_stream:
                mock_stream.return_value.price_cache = {"BTCUSDT": 45000.50}
                
                # Execute entry
                result = await _execute_entry_impl(mock_trader, mock_signal)
        
        # Entry should fail (response status = REJECTED)
        assert result is False

    async def test_entry_fails_on_malformed_response(self):
        """Test entry fails gracefully if response missing required keys.
        
        This would catch bugs like checking for "success" when response has "status".
        """
        mock_signal = MagicMock()
        mock_signal.symbol = "BTCUSDT"
        mock_signal.reason = "momentum_signal"
        
        mock_trader = MagicMock()
        mock_trader.config.position_size_pct = 2.5
        
        mock_engine = AsyncMock()
        # Malformed response - missing "status" key (the old bug!)
        mock_engine.place_order = AsyncMock(return_value={
            "order_id": "uuid-789",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.001,
            "fill_price": 45000.50,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:30:49Z",
            # Missing "status" - the validation will catch this!
        })
        
        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', 
                   return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client') as mock_stream:
                mock_stream.return_value.price_cache = {"BTCUSDT": 45000.50}
                
                # Execute entry
                result = await _execute_entry_impl(mock_trader, mock_signal)
        
        # Entry should fail (validation error on malformed response)
        assert result is False


@pytest.mark.asyncio
class TestExitResponseHandling:
    """Test exit execution with mocked place_order responses."""

    async def test_exit_success_with_filled_response(self):
        """Test exit correctly detects FILLED status with P&L."""
        mock_trader = MagicMock()
        mock_trader.config.exit_profit_target = 2.0
        
        mock_engine = AsyncMock()
        mock_engine.place_order = AsyncMock(return_value={
            "status": "FILLED",
            "order_id": "uuid-exit-1",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "quantity": 0.001,
            "fill_price": 46000.00,
            "fee": 0.01,
            "timestamp": "2026-07-04T10:31:00Z",
            "realized_pnl": 999.99,  # Profitable exit
        })
        
        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', 
                   return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client') as mock_stream:
                mock_stream.return_value.price_cache = {"BTCUSDT": 46000.00}
                
                # Execute exit
                result = await _execute_exit_impl(
                    mock_trader, 
                    "BTCUSDT", 
                    0.001, 
                    45000.50,
                    "profit_target"
                )
        
        # Exit should succeed
        assert result is True

    async def test_exit_failure_with_rejected_response(self):
        """Test exit correctly detects REJECTED status."""
        mock_trader = MagicMock()
        mock_trader.config.exit_profit_target = 2.0
        
        mock_engine = AsyncMock()
        mock_engine.place_order = AsyncMock(return_value={
            "status": "REJECTED",
            "order_id": "uuid-exit-2",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "quantity": 0.001,
            "fill_price": 0.0,
            "fee": 0.0,
            "timestamp": "2026-07-04T10:31:00Z",
            "error": "Market closed",
        })
        
        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', 
                   return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client') as mock_stream:
                mock_stream.return_value.price_cache = {"BTCUSDT": 46000.00}
                
                # Execute exit
                result = await _execute_exit_impl(
                    mock_trader, 
                    "BTCUSDT", 
                    0.001, 
                    45000.50,
                    "stop_loss"
                )
        
        # Exit should fail
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
