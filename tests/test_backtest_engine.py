"""Tests for historical backtesting engine (Phase 2 Week 6)."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

from backend.analytics.backtest_engine import BacktestEngine, BacktestMetrics, BacktestTrade


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    data = {
        'Open': np.linspace(100, 110, 100),
        'High': np.linspace(102, 112, 100),
        'Low': np.linspace(99, 109, 100),
        'Close': np.linspace(101, 111, 100),
        'Volume': np.ones(100) * 1000000,
    }
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture
def engine():
    """Create backtest engine for tests."""
    return BacktestEngine(initial_capital=10000.0, slippage_pct=0.1)


class TestBacktestEngine:
    """Test BacktestEngine class."""

    def test_init(self, engine):
        """Initialize backtest engine."""
        assert engine.initial_capital == 10000.0
        assert engine.slippage_pct == 0.1

    def test_empty_ohlcv(self, engine):
        """Handle empty OHLCV data."""
        empty_df = pd.DataFrame()
        result = engine.backtest_strategy(
            empty_df,
            lambda df: 0.5,
            "BTCUSDT",
            "test"
        )

        assert result.total_trades == 0
        assert result.ending_capital == 10000.0

    def test_missing_columns(self, engine, sample_ohlcv):
        """Handle missing OHLCV columns."""
        bad_df = sample_ohlcv.drop(columns=['Close'])

        with pytest.raises(ValueError):
            engine.backtest_strategy(
                bad_df,
                lambda df: 0.5,
                "BTCUSDT",
                "test"
            )

    def test_simple_strategy(self, engine, sample_ohlcv):
        """Test simple always-long strategy."""
        # Always hold 50% of capital
        def always_long(df):
            return 0.5

        result = engine.backtest_strategy(
            sample_ohlcv,
            always_long,
            "BTCUSDT",
            "test"
        )

        assert result.total_trades >= 0
        assert result.ending_capital > 0
        assert result.win_rate_pct >= 0
        assert result.win_rate_pct <= 100

    def test_alternating_strategy(self, engine, sample_ohlcv):
        """Test strategy that alternates position."""
        def alternating(df):
            if len(df) < 10:
                return 0.0
            # Switch every 20 bars
            return 0.5 if (len(df) // 20) % 2 == 0 else 0.0

        result = engine.backtest_strategy(
            sample_ohlcv,
            alternating,
            "BTCUSDT",
            "test"
        )

        assert result.total_trades >= 1
        assert result.strategy_name == "test"
        assert result.symbol == "BTCUSDT"

    def test_metrics_calculation(self, engine):
        """Test metrics calculation from trades."""
        # Create synthetic trades
        trades = [
            BacktestTrade(
                entry_date=datetime(2024, 1, 1),
                exit_date=datetime(2024, 1, 5),
                symbol="BTC",
                entry_price=100,
                exit_price=110,
                quantity=1.0,
                pnl=10,
                pnl_pct=10.0,
                holding_days=4
            ),
            BacktestTrade(
                entry_date=datetime(2024, 1, 6),
                exit_date=datetime(2024, 1, 10),
                symbol="BTC",
                entry_price=110,
                exit_price=105,
                quantity=1.0,
                pnl=-5,
                pnl_pct=-4.5,
                holding_days=4
            ),
        ]

        metrics = engine._calculate_metrics(
            trades=trades,
            symbol="BTCUSDT",
            strategy_name="test",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
        )

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate_pct == 50.0
        assert metrics.total_pnl == 5.0
        assert metrics.expectancy == 2.5

    def test_profit_factor(self, engine):
        """Test profit factor calculation."""
        trades = [
            BacktestTrade(datetime(2024, 1, 1), datetime(2024, 1, 2), "BTC", 100, 120, 1, 20, 20, 1),
            BacktestTrade(datetime(2024, 1, 3), datetime(2024, 1, 4), "BTC", 120, 110, 1, -10, -8, 1),
        ]

        metrics = engine._calculate_metrics(
            trades, "BTCUSDT", "test",
            datetime(2024, 1, 1), datetime(2024, 1, 4)
        )

        # avg_win=20, avg_loss=-10
        # gross_profit = 20 * 1 = 20
        # gross_loss = 10 * 1 = 10
        # profit_factor = 20 / 10 = 2.0
        assert metrics.profit_factor == pytest.approx(2.0)

    def test_win_rate_calculation(self, engine):
        """Test win rate calculation."""
        trades = [
            BacktestTrade(datetime(2024, 1, 1), datetime(2024, 1, 2), "BTC", 100, 110, 1, 10, 10, 1),
            BacktestTrade(datetime(2024, 1, 3), datetime(2024, 1, 4), "BTC", 110, 105, 1, -5, -5, 1),
            BacktestTrade(datetime(2024, 1, 5), datetime(2024, 1, 6), "BTC", 105, 115, 1, 10, 10, 1),
        ]

        metrics = engine._calculate_metrics(
            trades, "BTCUSDT", "test",
            datetime(2024, 1, 1), datetime(2024, 1, 6)
        )

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate_pct == pytest.approx(66.7, abs=0.1)

    def test_sharpe_ratio(self, engine):
        """Test Sharpe ratio calculation."""
        pnls = [100, -50, 100, -30, 150]
        sharpe = engine._calculate_sharpe_ratio(pnls)

        # Should be a valid number
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)
        assert not np.isinf(sharpe)

    def test_sortino_ratio(self, engine):
        """Test Sortino ratio calculation."""
        pnls = [100, -50, 100, -30, 150]
        sortino = engine._calculate_sortino_ratio(pnls)

        assert isinstance(sortino, float)
        # With losses present, should calculate properly
        assert not np.isnan(sortino)

    def test_max_drawdown(self, engine):
        """Test maximum drawdown calculation."""
        pnls = [100, 50, -80, 100, -50]
        max_dd = engine._calculate_max_drawdown(pnls)

        # Should be negative (drawdown)
        assert max_dd < 0
        assert isinstance(max_dd, float)

    def test_recovery_factor(self, engine):
        """Test recovery factor calculation."""
        metrics = BacktestMetrics(
            strategy_name="test",
            symbol="BTC",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            total_pnl_pct=50.0,
            max_drawdown_pct=-20.0,
        )

        recovery = engine._calculate_recovery_factor(metrics)
        assert recovery == pytest.approx(2.5)

    def test_empty_trades(self, engine):
        """Handle empty trades list."""
        metrics = engine._calculate_metrics(
            trades=[],
            symbol="BTCUSDT",
            strategy_name="test",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.ending_capital == 10000.0

    def test_consecutive_losses(self, engine):
        """Test consecutive loss tracking."""
        trades = [
            BacktestTrade(datetime(2024, 1, 1), datetime(2024, 1, 2), "BTC", 100, 105, 1, 5, 5, 1),
            BacktestTrade(datetime(2024, 1, 3), datetime(2024, 1, 4), "BTC", 105, 100, 1, -5, -5, 1),
            BacktestTrade(datetime(2024, 1, 5), datetime(2024, 1, 6), "BTC", 100, 95, 1, -5, -5, 1),
            BacktestTrade(datetime(2024, 1, 7), datetime(2024, 1, 8), "BTC", 95, 90, 1, -5, -5, 1),
        ]

        metrics = engine._calculate_metrics(
            trades, "BTCUSDT", "test",
            datetime(2024, 1, 1), datetime(2024, 1, 8)
        )

        assert metrics.max_consecutive_losses == 3

    def test_holding_period(self, engine):
        """Test average holding period calculation."""
        trades = [
            BacktestTrade(datetime(2024, 1, 1), datetime(2024, 1, 6), "BTC", 100, 110, 1, 10, 10, 5),
            BacktestTrade(datetime(2024, 1, 7), datetime(2024, 1, 17), "BTC", 110, 120, 1, 10, 10, 10),
        ]

        metrics = engine._calculate_metrics(
            trades, "BTCUSDT", "test",
            datetime(2024, 1, 1), datetime(2024, 1, 17)
        )

        assert metrics.avg_holding_days == pytest.approx(7.5)


class TestBacktestTrade:
    """Test BacktestTrade dataclass."""

    def test_trade_creation(self):
        """Create a trade."""
        trade = BacktestTrade(
            entry_date=datetime(2024, 1, 1),
            exit_date=datetime(2024, 1, 5),
            symbol="BTCUSDT",
            entry_price=100.0,
            exit_price=110.0,
            quantity=1.0,
            pnl=10.0,
            pnl_pct=10.0,
            holding_days=4
        )

        assert trade.symbol == "BTCUSDT"
        assert trade.pnl == 10.0
        assert trade.holding_days == 4


class TestBacktestMetrics:
    """Test BacktestMetrics dataclass."""

    def test_metrics_creation(self):
        """Create backtest metrics."""
        metrics = BacktestMetrics(
            strategy_name="momentum",
            symbol="BTCUSDT",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            total_trades=50,
            winning_trades=30,
            win_rate_pct=60.0,
        )

        assert metrics.strategy_name == "momentum"
        assert metrics.symbol == "BTCUSDT"
        assert metrics.total_trades == 50
        assert metrics.win_rate_pct == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
