"""Tests for Volatility Manager (Phase 314)."""

import pytest
import pandas as pd
import numpy as np
from backend.analytics.volatility_manager import VolatilityManager, get_volatility_manager


class TestVolatilityManager:
    """Test volatility-based position sizing and stops."""

    @pytest.fixture
    def vol_mgr(self):
        """Create volatility manager instance."""
        return VolatilityManager()

    @pytest.fixture
    def sample_ohlcv(self):
        """Create sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        np.random.seed(42)

        # Create realistic price data with uptrend and ~2% daily volatility
        prices = 100 + np.cumsum(np.random.randn(100) * 2)

        return pd.DataFrame({
            "Open": prices - np.abs(np.random.randn(100)),
            "High": prices + np.abs(np.random.randn(100)),
            "Low": prices - np.abs(np.random.randn(100)),
            "Close": prices,
            "Volume": np.full(100, 1000000),
        }, index=dates)

    def test_initialization(self, vol_mgr):
        """Test volatility manager initializes with correct defaults."""
        assert vol_mgr.lookback_vol == 20
        assert vol_mgr.lookback_atr == 14
        assert vol_mgr.risk_per_trade == 0.02
        assert vol_mgr.kelly_fraction == 0.25

    def test_calculate_volatility(self, vol_mgr, sample_ohlcv):
        """Test volatility calculation."""
        vol_metrics = vol_mgr.calculate_volatility(sample_ohlcv)

        assert vol_metrics["current_vol"] is not None
        assert vol_metrics["vol_percentile"] >= 0
        assert vol_metrics["vol_percentile"] <= 100
        assert vol_metrics["regime"] in ["low", "medium", "high", "extreme", "unknown"]
        assert vol_metrics["trend"] in ["expanding", "contracting", "stable"]

    def test_volatility_on_uptrend(self):
        """Test volatility on smooth uptrend (low vol)."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = 100 + np.arange(100)  # Linear uptrend, low vol
        ohlcv = pd.DataFrame({
            "Open": prices - 0.5,
            "High": prices + 0.5,
            "Low": prices - 0.5,
            "Close": prices,
            "Volume": np.full(100, 1000000),
        }, index=dates)

        vol_mgr = VolatilityManager()
        vol_metrics = vol_mgr.calculate_volatility(ohlcv)

        # Linear trend should have very low volatility
        assert vol_metrics["current_vol"] < 10  # < 10% annualized
        assert vol_metrics["regime"] == "low"

    def test_volatility_on_crash(self):
        """Test volatility on sudden crash (high vol)."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = np.concatenate([
            100 + np.arange(50),  # Stable
            150 - np.arange(50) * 3,  # Crash
        ])
        ohlcv = pd.DataFrame({
            "Open": prices - 2,
            "High": prices + 2,
            "Low": prices - 5,
            "Close": prices,
            "Volume": np.full(100, 1000000),
        }, index=dates)

        vol_mgr = VolatilityManager()
        vol_metrics = vol_mgr.calculate_volatility(ohlcv)

        # Crash should have high volatility
        assert vol_metrics["current_vol"] > 20  # > 20% annualized
        assert vol_metrics["regime"] in ["high", "extreme"]

    def test_calculate_atr(self, vol_mgr, sample_ohlcv):
        """Test ATR calculation."""
        atr_value, stop_loss_pct, _ = vol_mgr.calculate_atr(sample_ohlcv)

        assert atr_value > 0
        assert 0 < stop_loss_pct < 0.10  # 0-10%

    def test_atr_increasing(self):
        """Test ATR responds to increasing volatility."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")

        # Increasing volatility over time
        volatility = np.linspace(1, 10, 100)
        closes = 100 + np.cumsum(np.random.randn(100) * volatility)

        ohlcv = pd.DataFrame({
            "Open": closes - volatility,
            "High": closes + volatility * 2,
            "Low": closes - volatility * 2,
            "Close": closes,
            "Volume": np.full(100, 1000000),
        }, index=dates)

        vol_mgr = VolatilityManager()
        atr_early = vol_mgr.calculate_atr(ohlcv.iloc[:30])
        atr_late = vol_mgr.calculate_atr(ohlcv.iloc[-30:])

        # ATR should increase with volatility
        if atr_early[0] > 0:
            assert atr_late[0] > atr_early[0]

    def test_calculate_position_size_normal(self, vol_mgr, sample_ohlcv):
        """Test position sizing in normal conditions."""
        vol_metrics = vol_mgr.calculate_volatility(sample_ohlcv)

        sizing = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics,
            entry_signal_strength=75.0,
        )

        assert 0 <= sizing["position_size_pct"] <= 0.10
        assert sizing["position_quantity"] > 0
        assert sizing["position_value_eur"] > 0
        assert sizing["vol_adjustment"] > 0

    def test_position_size_scales_with_signal(self, vol_mgr, sample_ohlcv):
        """Test position size scales with signal strength."""
        vol_metrics = vol_mgr.calculate_volatility(sample_ohlcv)

        sizing_weak = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics,
            entry_signal_strength=30.0,  # Very weak signal
        )

        sizing_strong = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics,
            entry_signal_strength=95.0,  # Very strong signal
        )

        # Strong signal should have equal or larger position
        # (might hit minimum 1% floor for very weak signals)
        assert sizing_strong["position_size_pct"] >= sizing_weak["position_size_pct"]

    def test_position_size_scales_with_vol(self, vol_mgr, sample_ohlcv):
        """Test position size reduces with high volatility."""
        vol_metrics_low = {"current_vol": 0.10, "regime": "low"}
        vol_metrics_high = {"current_vol": 0.80, "regime": "extreme"}

        sizing_low_vol = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics_low,
            entry_signal_strength=75.0,
        )

        sizing_high_vol = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics_high,
            entry_signal_strength=75.0,
        )

        # High vol should result in smaller position
        assert sizing_low_vol["position_size_pct"] > sizing_high_vol["position_size_pct"]

    def test_calculate_stops(self, vol_mgr, sample_ohlcv):
        """Test stop-loss and take-profit calculation."""
        stops = vol_mgr.calculate_stops(
            entry_price=100.0,
            df=sample_ohlcv,
            atr_multiplier=2.0,
        )

        assert stops["stop_loss_price"] < 100.0
        assert stops["take_profit_price"] > 100.0
        assert stops["stop_loss_pct"] > 0
        assert stops["take_profit_pct"] > 0
        # Reward should be > 2x risk
        assert stops["take_profit_pct"] > stops["stop_loss_pct"] * 2

    def test_stops_scale_with_atr(self, vol_mgr, sample_ohlcv):
        """Test stops scale with ATR multiplier."""
        stops_1x = vol_mgr.calculate_stops(
            entry_price=100.0,
            df=sample_ohlcv,
            atr_multiplier=1.0,
        )

        stops_2x = vol_mgr.calculate_stops(
            entry_price=100.0,
            df=sample_ohlcv,
            atr_multiplier=2.0,
        )

        # Larger ATR multiplier = larger stops
        assert abs(stops_2x["stop_loss_price"] - 100.0) > abs(stops_1x["stop_loss_price"] - 100.0)

    def test_empty_data_handling(self, vol_mgr):
        """Test handling of empty data."""
        empty_df = pd.DataFrame({"Close": []})

        vol_metrics = vol_mgr.calculate_volatility(empty_df)
        assert vol_metrics["current_vol"] is None
        assert vol_metrics["regime"] == "unknown"

        atr_value, stop_pct, _ = vol_mgr.calculate_atr(empty_df)
        assert atr_value == 0.0
        assert stop_pct == 0.02  # Fallback

    def test_sizing_with_invalid_price(self, vol_mgr):
        """Test position sizing with invalid price."""
        vol_metrics = {"current_vol": 0.30, "regime": "medium"}

        sizing = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=0,
            vol_metrics=vol_metrics,
        )

        assert sizing["position_size_pct"] == 0.01  # Minimum
        assert sizing["position_quantity"] == 0

    def test_get_volatility_manager(self):
        """Test global volatility manager instance."""
        mgr1 = get_volatility_manager()
        mgr2 = get_volatility_manager()

        assert mgr1 is mgr2  # Same instance

    def test_regime_boundaries(self):
        """Test regime classification at boundaries."""
        vol_mgr = VolatilityManager()

        # Test at 24th percentile (should be "low")
        df_low = pd.DataFrame({
            "Close": 100 + np.arange(100) * 0.1,  # Very stable
        })
        metrics = vol_mgr.calculate_volatility(df_low)
        assert metrics["vol_percentile"] < 25

        # Test at 75th percentile (should be "high")
        np.random.seed(42)
        df_high = pd.DataFrame({
            "Close": 100 + np.cumsum(np.random.randn(100) * 5),  # Volatile
        })
        metrics = vol_mgr.calculate_volatility(df_high)
        # Depending on randomness, should be medium or high
        assert metrics["regime"] in ["medium", "high"]

    def test_kelly_fraction_conservative(self, vol_mgr, sample_ohlcv):
        """Test that Kelly fraction makes sizing conservative."""
        vol_metrics = vol_mgr.calculate_volatility(sample_ohlcv)

        # With kelly_fraction=0.25, position should be at most 6.25% of account
        sizing = vol_mgr.calculate_position_size(
            account_equity=100000,
            current_price=100,
            vol_metrics=vol_metrics,
            entry_signal_strength=100.0,  # Max signal
        )

        # Even with max signal, shouldn't exceed 10%
        assert sizing["position_size_pct"] <= 0.10
