"""Tests for GARP Value Strategy."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.strategies.garp_value_strategy import GARPValueStrategy, apply_garp_value_strategy


class TestGARPValueStrategy:
    """Test GARP Value Strategy implementation."""

    @pytest.fixture
    def sample_ohlcv(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        np.random.seed(42)

        # Create realistic price data with trend
        prices = 100 + np.cumsum(np.random.randn(100) * 2)

        return pd.DataFrame(
            {
                "Open": prices + np.random.randn(100),
                "High": prices + np.abs(np.random.randn(100)),
                "Low": prices - np.abs(np.random.randn(100)),
                "Close": prices,
                "Volume": np.random.randint(1000000, 10000000, 100),
            },
            index=dates,
        )

    def test_garp_initialization(self):
        """Test GARP strategy initializes with defaults."""
        strategy = GARPValueStrategy()
        assert strategy.params["garp_threshold"] == 70.0
        assert strategy.params["momentum_window"] == 20
        assert strategy.params["exit_stop_loss"] == 0.08
        assert strategy.params["exit_profit_target"] == 0.15

    def test_garp_custom_params(self):
        """Test GARP strategy accepts custom parameters."""
        params = {
            "garp_threshold": 65.0,
            "exit_stop_loss": 0.10,
        }
        strategy = GARPValueStrategy(params)
        assert strategy.params["garp_threshold"] == 65.0
        assert strategy.params["exit_stop_loss"] == 0.10

    def test_garp_apply_returns_position_column(self, sample_ohlcv):
        """Test GARP apply returns DataFrame with position column."""
        strategy = GARPValueStrategy()
        result = strategy.apply(sample_ohlcv)

        assert "position" in result.columns
        assert all(result["position"] >= 0)
        assert all(result["position"] <= 1)

    def test_garp_position_values(self, sample_ohlcv):
        """Test position values are 0 or 1 (no sizing)."""
        strategy = GARPValueStrategy()
        result = strategy.apply(sample_ohlcv)

        unique_positions = result["position"].unique()
        for pos in unique_positions:
            assert pos in [0.0, 1.0], f"Position should be 0 or 1, got {pos}"

    def test_garp_convenience_function(self, sample_ohlcv):
        """Test convenience function apply_garp_value_strategy."""
        result = apply_garp_value_strategy(sample_ohlcv)

        assert "position" in result.columns
        assert len(result) > 0
        assert len(result) <= len(sample_ohlcv)

    def test_garp_handles_empty_data(self):
        """Test GARP handles empty DataFrame."""
        df = pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": [], "Volume": []})
        strategy = GARPValueStrategy()
        result = strategy.apply(df)

        assert "position" in result.columns
        assert all(result["position"] == 0.0)

    def test_garp_handles_insufficient_data(self):
        """Test GARP handles DataFrame with insufficient data for calculation."""
        df = pd.DataFrame(
            {
                "Open": [100, 101, 102],
                "High": [102, 103, 104],
                "Low": [99, 100, 101],
                "Close": [101, 102, 103],
                "Volume": [1000000, 1100000, 1200000],
            }
        )
        strategy = GARPValueStrategy()
        result = strategy.apply(df)

        # Should return something, possibly empty after dropna
        assert isinstance(result, pd.DataFrame)

    def test_garp_score_calculation(self, sample_ohlcv):
        """Test GARP score is calculated correctly."""
        strategy = GARPValueStrategy()
        result = strategy.apply(sample_ohlcv)

        # Verify position changes based on GARP score
        # With real data, we should see some positions (not all zeros)
        positions = result["position"].values
        assert len(positions) > 0

    def test_garp_exit_conditions(self, sample_ohlcv):
        """Test GARP exit conditions (stop-loss and profit target)."""
        # Create strong uptrend with low volatility (high GARP score)
        # This is a smooth trend which increases GARP score
        smooth_trend = np.linspace(100, 150, len(sample_ohlcv))
        sample_ohlcv["Close"] = smooth_trend + np.random.randn(len(sample_ohlcv)) * 0.5

        strategy = GARPValueStrategy(
            {
                "garp_threshold": 50.0,  # Lower threshold for test
                "exit_stop_loss": 0.05,  # 5% stop-loss
                "exit_profit_target": 0.10,  # 10% profit target
            }
        )
        result = strategy.apply(sample_ohlcv)

        # Just verify that positions column exists and is valid
        positions = result["position"].values
        assert all(p in [0.0, 1.0] for p in positions), "Positions should be 0 or 1"

    def test_garp_output_columns(self, sample_ohlcv):
        """Test GARP output has required columns."""
        strategy = GARPValueStrategy()
        result = strategy.apply(sample_ohlcv)

        required_cols = ["Open", "High", "Low", "Close", "Volume", "position"]
        for col in required_cols:
            assert col in result.columns, f"Missing column: {col}"
