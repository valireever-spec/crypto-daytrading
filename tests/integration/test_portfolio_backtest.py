"""Integration tests for Portfolio Backtest Engine (Phase 319)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.backtesting.portfolio_backtest_engine import (
    PortfolioBacktestEngine,
    BacktestMetrics,
    get_portfolio_backtest_engine,
)
from backend.analytics.backtest_validators import (
    BacktestValidator,
    get_backtest_validator,
)


class TestPortfolioBacktestEngine:
    """Test portfolio backtesting engine."""

    @pytest.fixture
    def engine(self):
        """Create backtest engine."""
        return PortfolioBacktestEngine()

    @pytest.fixture
    def sample_price_history(self):
        """Create sample price history with bull/bear regimes."""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")

        # BTCUSDT: bull then bear
        btc_prices = list(50000 + np.arange(126) * 100) + list(62600 - np.arange(126) * 100)
        btc_df = pd.DataFrame({
            'Open': btc_prices,
            'High': [p * 1.01 for p in btc_prices],
            'Low': [p * 0.99 for p in btc_prices],
            'Close': btc_prices,
            'Volume': np.full(252, 1000000),
        }, index=dates)

        # EQ_AAPL: steady bull
        aapl_prices = list(150 + np.arange(252) * 0.5)
        aapl_df = pd.DataFrame({
            'Open': aapl_prices,
            'High': [p * 1.005 for p in aapl_prices],
            'Low': [p * 0.995 for p in aapl_prices],
            'Close': aapl_prices,
            'Volume': np.full(252, 10000000),
        }, index=dates)

        return {
            'BTCUSDT': btc_df,
            'EQ_AAPL': aapl_df,
        }

    @pytest.fixture
    def sample_regime_history(self):
        """Create sample regime history."""
        btc_regimes = [
            (datetime(2024, 1, 1), 'bull'),
            (datetime(2024, 5, 10), 'bear'),
        ]

        aapl_regimes = [
            (datetime(2024, 1, 1), 'bull'),
            (datetime(2024, 12, 31), 'bull'),
        ]

        return {
            'BTCUSDT': btc_regimes,
            'EQ_AAPL': aapl_regimes,
        }

    def test_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.trades == []
        assert engine.equity_curve == []
        assert engine.portfolio_values == {}

    def test_backtest_regime_exits_basic(self, engine, sample_price_history, sample_regime_history):
        """Test basic regime exit backtesting."""
        metrics, trades = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have metrics
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_trades >= 0

    def test_backtest_metrics_return_calculation(self, engine, sample_price_history, sample_regime_history):
        """Test that metrics calculate returns correctly."""
        metrics, _ = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have return metrics
        assert hasattr(metrics, 'total_return_pct')
        assert hasattr(metrics, 'annualized_return_pct')
        assert hasattr(metrics, 'max_drawdown_pct')

    def test_backtest_metrics_trade_statistics(self, engine, sample_price_history, sample_regime_history):
        """Test that metrics include trade statistics."""
        metrics, trades = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have trade stats
        assert metrics.total_trades >= 0
        assert metrics.winning_trades >= 0
        assert metrics.losing_trades >= 0
        assert metrics.win_rate_pct >= 0

    def test_backtest_equity_curve(self, engine, sample_price_history, sample_regime_history):
        """Test that equity curve is generated."""
        engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have equity curve
        assert len(engine.equity_curve) > 0
        assert all(isinstance(date, datetime) for date, _ in engine.equity_curve)
        assert all(isinstance(value, (int, float)) for _, value in engine.equity_curve)

    def test_backtest_sharpe_ratio_calculation(self, engine, sample_price_history, sample_regime_history):
        """Test Sharpe ratio calculation."""
        metrics, _ = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have Sharpe ratio
        assert hasattr(metrics, 'sharpe_ratio')
        assert isinstance(metrics.sharpe_ratio, (int, float))

    def test_backtest_profit_factor(self, engine, sample_price_history, sample_regime_history):
        """Test profit factor calculation."""
        metrics, _ = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Should have profit factor
        assert hasattr(metrics, 'profit_factor')
        assert isinstance(metrics.profit_factor, (int, float))

    def test_backtest_sector_rotations(self, engine, sample_price_history, sample_regime_history):
        """Test sector rotation backtesting."""
        symbol_sectors = {
            'BTCUSDT': 'cryptocurrency',
            'EQ_AAPL': 'technology',
        }

        metrics, trades = engine.backtest_sector_rotations(
            symbol_price_history=sample_price_history,
            symbol_sectors=symbol_sectors,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.10,
        )

        # Should have metrics
        assert isinstance(metrics, BacktestMetrics)

    def test_backtest_rebalancing(self, engine, sample_price_history):
        """Test rebalancing backtesting."""
        target_allocation = {
            'BTCUSDT': 50,
            'EQ_AAPL': 50,
        }

        metrics, trades = engine.backtest_rebalancing(
            symbol_price_history=sample_price_history,
            target_allocation=target_allocation,
            initial_capital=100000,
            rebalance_frequency_days=30,
        )

        # Should have metrics
        assert isinstance(metrics, BacktestMetrics)

    def test_backtest_summary_generation(self, engine, sample_price_history, sample_regime_history):
        """Test summary generation."""
        metrics, _ = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        summary = engine.get_summary(metrics)

        # Summary should contain key metrics
        assert "Return" in summary
        assert "Drawdown" in summary
        assert "Win Rate" in summary

    def test_global_instance(self):
        """Test global engine instance."""
        eng1 = get_portfolio_backtest_engine()
        eng2 = get_portfolio_backtest_engine()

        assert eng1 is eng2

    def test_metrics_bounds(self, engine, sample_price_history, sample_regime_history):
        """Test that metrics are within reasonable bounds."""
        metrics, _ = engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Win rate should be 0-100%
        assert 0 <= metrics.win_rate_pct <= 100

        # Drawdown should be negative or zero
        assert metrics.max_drawdown_pct <= 0

    def test_trade_records(self, engine, sample_price_history, sample_regime_history):
        """Test that trades are recorded correctly."""
        engine.backtest_regime_exits(
            symbol_price_history=sample_price_history,
            regime_history=sample_regime_history,
            initial_capital=100000,
            position_size_pct=0.05,
        )

        # Each trade should have complete data
        for trade in engine.trades:
            assert trade.symbol is not None
            assert trade.entry_price > 0
            assert trade.entry_date is not None
            assert trade.quantity > 0
            assert trade.pnl is not None


class TestBacktestValidator:
    """Test backtest validators."""

    @pytest.fixture
    def validator(self):
        """Create backtest validator."""
        return BacktestValidator()

    @pytest.fixture
    def sample_regimes(self):
        """Create sample actual regimes."""
        return {
            'BTCUSDT': [
                (datetime(2024, 1, 1), 'bull'),
                (datetime(2024, 6, 1), 'bear'),
                (datetime(2024, 9, 1), 'bull'),
            ],
            'EQ_AAPL': [
                (datetime(2024, 1, 1), 'bull'),
                (datetime(2024, 12, 31), 'bull'),
            ],
        }

    @pytest.fixture
    def sample_price_history(self):
        """Create sample price history."""
        dates = pd.date_range(start="2024-01-01", periods=365, freq="D")

        btc_prices = list(50000 + np.arange(183) * 100) + list(68300 - np.arange(182) * 100)
        aapl_prices = list(150 + np.arange(365) * 0.3)

        return {
            'BTCUSDT': pd.DataFrame({
                'Close': btc_prices,
            }, index=dates),
            'EQ_AAPL': pd.DataFrame({
                'Close': aapl_prices,
            }, index=dates),
        }

    def test_initialization(self, validator):
        """Test validator initializes."""
        assert validator is not None

    def test_regime_accuracy_validation(self, validator, sample_regimes, sample_price_history):
        """Test regime accuracy validation."""
        detected_regimes = sample_regimes  # Assume perfect detection for test

        accuracy = validator.validate_regime_accuracy(
            actual_regimes=sample_regimes,
            detected_regimes=detected_regimes,
            symbol_price_history=sample_price_history,
        )

        # Should have accuracy metrics
        assert hasattr(accuracy, 'accuracy_pct')
        assert hasattr(accuracy, 'bull_accuracy_pct')
        assert hasattr(accuracy, 'bear_accuracy_pct')

    def test_regime_accuracy_bounds(self, validator, sample_regimes, sample_price_history):
        """Test that accuracy is within bounds."""
        accuracy = validator.validate_regime_accuracy(
            actual_regimes=sample_regimes,
            detected_regimes=sample_regimes,
            symbol_price_history=sample_price_history,
        )

        # Accuracy should be 0-100%
        assert 0 <= accuracy.accuracy_pct <= 100
        assert 0 <= accuracy.bull_accuracy_pct <= 100
        assert 0 <= accuracy.bear_accuracy_pct <= 100

    def test_exit_profitability_validation(self, validator, sample_price_history):
        """Test exit profitability validation."""
        exit_decisions = [
            {
                'symbol': 'BTCUSDT',
                'date': datetime(2024, 6, 1),
                'price': 60000,
                'entry_date': datetime(2024, 1, 1),
            },
        ]

        profitability = validator.validate_exit_profitability(
            exit_decisions=exit_decisions,
            symbol_price_history=sample_price_history,
        )

        # Should have profitability metrics
        assert hasattr(profitability, 'win_rate_pct')
        assert hasattr(profitability, 'avg_days_held')
        assert hasattr(profitability, 'opportunity_cost')

    def test_rotation_performance_validation(self, validator):
        """Test rotation performance validation."""
        rotation_decisions = [
            {
                'from_sector': 'technology',
                'to_sector': 'healthcare',
                'date': datetime(2024, 6, 1),
            },
        ]

        # Create mock sector price histories
        dates = pd.date_range(start="2024-01-01", periods=365, freq="D")
        sector_prices = {}

        for sector in ['technology', 'healthcare']:
            prices = 100 + np.arange(365)
            sector_prices[sector] = pd.DataFrame({
                'Close': prices,
            }, index=dates)

        performance = validator.validate_rotation_performance(
            rotation_decisions=rotation_decisions,
            sector_price_history=sector_prices,
            benchmark_returns=5.0,
        )

        # Should have performance metrics
        assert hasattr(performance, 'win_rate_pct')
        assert hasattr(performance, 'avg_outperformance_pct')

    def test_validation_summary(self, validator, sample_regimes, sample_price_history):
        """Test validation summary generation."""
        accuracy = validator.validate_regime_accuracy(
            actual_regimes=sample_regimes,
            detected_regimes=sample_regimes,
            symbol_price_history=sample_price_history,
        )

        summary = validator.get_validation_summary(regime_accuracy=accuracy)

        # Summary should contain key info
        assert "Accuracy" in summary
        assert "%" in summary

    def test_global_instance(self):
        """Test global validator instance."""
        val1 = get_backtest_validator()
        val2 = get_backtest_validator()

        assert val1 is val2

    def test_false_positive_detection(self, validator):
        """Test detection of false positive exits."""
        # Detect bear regime but market was actually bull
        actual_regimes = {
            'BTCUSDT': [(datetime(2024, 1, 1), 'bull')],
        }

        detected_regimes = {
            'BTCUSDT': [(datetime(2024, 1, 1), 'bear')],
        }

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = 50000 + np.arange(100) * 100  # Uptrend = bull

        price_history = {
            'BTCUSDT': pd.DataFrame({'Close': prices}, index=dates),
        }

        accuracy = validator.validate_regime_accuracy(
            actual_regimes=actual_regimes,
            detected_regimes=detected_regimes,
            symbol_price_history=price_history,
        )

        # Should detect false positives
        assert accuracy.false_positive_exits > 0

    def test_opportunity_cost_calculation(self, validator):
        """Test opportunity cost calculation in exits."""
        exit_decisions = [
            {
                'symbol': 'BTCUSDT',
                'date': datetime(2024, 1, 15),
                'price': 51500,
                'entry_date': datetime(2024, 1, 1),
            },
        ]

        dates = pd.date_range(start="2024-01-01", periods=60, freq="D")
        prices = 50000 + np.arange(60) * 100  # Strong uptrend

        price_history = {
            'BTCUSDT': pd.DataFrame({'Close': prices}, index=dates),
        }

        profitability = validator.validate_exit_profitability(
            exit_decisions=exit_decisions,
            symbol_price_history=price_history,
        )

        # Should have opportunity cost (missed gains)
        assert profitability.opportunity_cost > 0
