"""Integration tests for autonomous trading system with GARP integration."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.trading.autonomous_trader import (
    AutonomousTrader,
    TradingConfig,
    TradeSignal,
)


class TestAutonomousTrader:
    """Test autonomous trading system."""

    @pytest.fixture
    def trading_config(self):
        """Create test trading config."""
        return TradingConfig(
            enabled=True,
            entry_threshold=60.0,
            exit_profit_target=0.03,
            exit_stop_loss=0.02,
            position_size_pct=0.10,
            max_positions=5,
            symbols=['BTCUSDT', 'ETHUSDT', 'EQ_AAPL', 'EQ_MSFT'],
        )

    def test_trader_initialization(self, trading_config):
        """Test trader initializes with config."""
        trader = AutonomousTrader(trading_config)
        assert trader.running is False
        assert trader.config.enabled is True
        assert trader.config.entry_threshold == 60.0
        assert 'EQ_AAPL' in trader.config.symbols

    def test_trader_status(self, trading_config):
        """Test trader status reporting."""
        trader = AutonomousTrader(trading_config)
        status = trader.get_status()

        assert status['enabled'] is True
        assert status['running'] is False
        assert status['total_trades'] == 0
        assert status['config']['entry_threshold'] == 60.0

    def test_config_symbols(self):
        """Test config symbol defaults and overrides."""
        # Test defaults
        config = TradingConfig()
        assert len(config.symbols) == 6
        assert 'BTCUSDT' in config.symbols
        assert 'EQ_AAPL' in config.symbols

        # Test custom symbols
        custom_symbols = ['BTC', 'ETH', 'EQ_TSLA']
        config = TradingConfig(symbols=custom_symbols)
        assert config.symbols == custom_symbols

    @pytest.mark.asyncio
    async def test_calculate_signal_crypto(self, trading_config):
        """Test signal calculation for crypto symbols."""
        trader = AutonomousTrader(trading_config)

        # Mock historical data fetch
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        ohlcv = pd.DataFrame(
            {
                "Open": np.random.randn(100).cumsum() + 100,
                "High": np.random.randn(100).cumsum() + 102,
                "Low": np.random.randn(100).cumsum() + 98,
                "Close": np.random.randn(100).cumsum() + 100,
                "Volume": np.random.randint(1000000, 10000000, 100),
            },
            index=dates,
        )

        with patch('backend.analytics.historical_data.get_historical_service') as mock_hist:
            mock_service = MagicMock()
            mock_service.fetch_ohlcv = MagicMock(return_value=ohlcv)
            mock_hist.return_value = mock_service

            signal = await trader._calculate_signal('BTCUSDT')
            assert 0 <= signal <= 100
            assert isinstance(signal, float)

    @pytest.mark.asyncio
    async def test_calculate_signal_stock_with_garp(self, trading_config):
        """Test signal calculation for stocks with GARP blending."""
        trader = AutonomousTrader(trading_config)

        # Mock historical data with strong uptrend (high GARP score)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        close_prices = np.linspace(100, 150, 100)  # Strong uptrend
        ohlcv = pd.DataFrame(
            {
                "Open": close_prices - 0.5,
                "High": close_prices + 0.5,
                "Low": close_prices - 1.0,
                "Close": close_prices,
                "Volume": np.full(100, 1000000),
            },
            index=dates,
        )

        with patch('backend.analytics.historical_data.get_historical_service') as mock_hist:
            mock_service = MagicMock()
            mock_service.fetch_ohlcv = MagicMock(return_value=ohlcv)
            mock_hist.return_value = mock_service

            signal = await trader._calculate_signal('EQ_AAPL')
            assert 0 <= signal <= 100
            # With strong uptrend, GARP should contribute significantly
            # 70% GARP (likely high) + 30% technical should result in decent score
            assert isinstance(signal, float)

    @pytest.mark.asyncio
    async def test_check_symbol_with_position(self, trading_config):
        """Test that trader doesn't re-signal already open positions."""
        trader = AutonomousTrader(trading_config)

        # Mock paper trading with existing position
        mock_engine = AsyncMock()
        mock_engine.get_positions = MagicMock(return_value=[
            {'symbol': 'BTCUSDT', 'quantity': 1.0, 'entry_price': 100}
        ])

        with patch('backend.trading.autonomous_trader.get_paper_trading') as mock_pt:
            mock_pt.return_value = mock_engine

            signal = await trader._check_symbol('BTCUSDT')
            assert signal is None  # Should skip because position exists

    def test_trade_signal_creation(self):
        """Test TradeSignal creation."""
        signal = TradeSignal(
            symbol='BTCUSDT',
            side='BUY',
            strength=75.0,
            reason='Strong GARP signal',
            timestamp=datetime.utcnow()
        )

        assert signal.symbol == 'BTCUSDT'
        assert signal.side == 'BUY'
        assert signal.strength == 75.0
        assert 'GARP' in signal.reason

    @pytest.mark.asyncio
    async def test_get_current_prices(self, trading_config):
        """Test price fetching from WebSocket."""
        trader = AutonomousTrader(trading_config)

        mock_prices = {
            'BTCUSDT': 48500.0,
            'ETHUSDT': 2800.0,
            'EQ_AAPL': 195.50,
            'EQ_MSFT': 425.30,
        }

        with patch('backend.exchange.binance_stream.get_stream_client') as mock_stream:
            mock_client = MagicMock()
            mock_client.get_prices = MagicMock(return_value=mock_prices)
            mock_stream.return_value = mock_client

            prices = await trader._get_current_prices()
            assert prices == mock_prices
            assert prices['BTCUSDT'] == 48500.0
            assert prices['EQ_AAPL'] == 195.50

    @pytest.mark.asyncio
    async def test_get_current_prices_empty(self, trading_config):
        """Test price fetching handles WebSocket not ready."""
        trader = AutonomousTrader(trading_config)

        with patch('backend.exchange.binance_stream.get_stream_client') as mock_stream:
            mock_stream.return_value = None

            prices = await trader._get_current_prices()
            assert prices == {}

    def test_config_symbol_configuration(self):
        """Test that config properly initializes symbols."""
        config = TradingConfig()
        assert 'BTCUSDT' in config.symbols
        assert 'ETHUSDT' in config.symbols
        assert 'EQ_AAPL' in config.symbols
        assert 'EQ_MSFT' in config.symbols
        assert 'EQ_TSLA' in config.symbols
