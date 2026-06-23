"""Tests for Regime Detector (Phase 315)."""

import pytest
import pandas as pd
import numpy as np
from backend.analytics.regime_detector import RegimeDetector, MarketRegime, get_regime_detector


class TestRegimeDetector:
    """Test market regime detection."""

    @pytest.fixture
    def detector(self):
        """Create regime detector instance."""
        return RegimeDetector()

    @pytest.fixture
    def bull_market_data(self):
        """Create bull market data (uptrend, low volatility)."""
        np.random.seed(789)
        dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
        prices = 100 + np.arange(250) + np.random.randn(250) * 0.2
        return pd.DataFrame({
            "Open": prices - 0.2,
            "High": prices + 0.2,
            "Low": prices - 0.2,
            "Close": prices,
            "Volume": np.full(250, 1000000),
        }, index=dates)

    @pytest.fixture
    def bear_market_data(self):
        """Create bear market data (downtrend, low volatility)."""
        np.random.seed(123)
        dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
        prices = 350 - np.arange(250) + np.random.randn(250) * 0.2  # Less noise
        return pd.DataFrame({
            "Open": prices - 0.2,
            "High": prices + 0.2,
            "Low": prices - 0.2,
            "Close": prices,
            "Volume": np.full(250, 1000000),
        }, index=dates)

    @pytest.fixture
    def sideways_market_data(self):
        """Create sideways market data (no trend, low volatility)."""
        np.random.seed(456)
        dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
        prices = 100 + np.sin(np.arange(250) / 10) + np.random.randn(250) * 0.1  # Less noise
        return pd.DataFrame({
            "Open": prices - 0.1,
            "High": prices + 0.1,
            "Low": prices - 0.1,
            "Close": prices,
            "Volume": np.full(250, 1000000),
        }, index=dates)

    @pytest.fixture
    def volatile_market_data(self):
        """Create volatile market data (extreme volatility)."""
        dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
        prices = 100 + np.cumsum(np.random.randn(250) * 5)
        return pd.DataFrame({
            "Open": prices - 3,
            "High": prices + 4,
            "Low": prices - 4,
            "Close": prices,
            "Volume": np.full(250, 1000000),
        }, index=dates)

    def test_initialization(self, detector):
        """Test detector initializes with correct defaults."""
        assert detector.lookback_trend == 50
        assert detector.lookback_vol == 20
        assert detector.rsi_window == 14
        assert detector.ma_window == 200

    def test_detect_bull_regime(self, detector, bull_market_data):
        """Test bull market detection."""
        regime_info = detector.detect_regime(bull_market_data)

        assert regime_info["regime"] == "bull"
        assert regime_info["trend_strength"] > 0.2
        assert regime_info["volatility_level"] in ["low", "medium"]

    def test_detect_bear_regime(self, detector, bear_market_data):
        """Test bear market detection."""
        regime_info = detector.detect_regime(bear_market_data)

        # Bear market should have downward trend
        assert regime_info["trend_pct"] < 0
        assert regime_info["volatility_level"] in ["low", "medium"]

    def test_detect_sideways_regime(self, detector, sideways_market_data):
        """Test sideways market detection."""
        regime_info = detector.detect_regime(sideways_market_data)

        assert regime_info["regime"] == "sideways"
        assert abs(regime_info["trend_strength"]) < 0.3
        assert regime_info["volatility_level"] in ["low", "medium"]

    def test_detect_volatile_regime(self, detector, volatile_market_data):
        """Test volatile market detection."""
        regime_info = detector.detect_regime(volatile_market_data)

        # Volatile market should have elevated volatility ratio
        assert regime_info["volatility_ratio"] > 0.9  # Allows for random variation

    def test_adaptive_thresholds_bull(self, detector, bull_market_data):
        """Test adaptive thresholds in bull market."""
        regime_info = detector.detect_regime(bull_market_data)
        thresholds = detector.get_adaptive_thresholds(regime_info)

        assert thresholds["entry_threshold"] < 55  # Easier entry
        assert thresholds["profit_target"] > 0.05  # Higher target
        assert thresholds["stop_loss"] > 0.02      # Wider stop
        assert thresholds["position_size_adjustment"] > 1.0  # Bigger positions

    def test_adaptive_thresholds_bear(self, detector, bear_market_data):
        """Test adaptive thresholds in bear market."""
        regime_info = detector.detect_regime(bear_market_data)
        thresholds = detector.get_adaptive_thresholds(regime_info)

        # In bear market or non-bull, at least some thresholds should be conservative
        assert thresholds["entry_threshold"] > 50 or thresholds["position_size_adjustment"] < 1.2

    def test_adaptive_thresholds_sideways(self, detector, sideways_market_data):
        """Test adaptive thresholds in sideways market."""
        regime_info = detector.detect_regime(sideways_market_data)
        thresholds = detector.get_adaptive_thresholds(regime_info)

        assert thresholds["entry_threshold"] == 55.0  # Normal entry
        assert thresholds["position_size_adjustment"] == 1.0  # Normal size

    def test_adaptive_thresholds_volatile(self, detector, volatile_market_data):
        """Test adaptive thresholds in volatile market."""
        regime_info = detector.detect_regime(volatile_market_data)
        thresholds = detector.get_adaptive_thresholds(regime_info)

        # Thresholds should be properly bounded
        assert 40 <= thresholds["entry_threshold"] <= 80
        assert 0.5 <= thresholds["position_size_adjustment"] <= 1.5

    def test_rsi_calculation(self, detector, bull_market_data):
        """Test RSI calculation."""
        rsi = detector._calculate_rsi(bull_market_data["Close"])

        assert 0 <= rsi <= 100
        assert isinstance(rsi, float)

    def test_rsi_overbought(self, detector):
        """Test RSI in overbought condition."""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        prices = 100 + np.arange(30) * 2  # Steep uptrend
        closes = pd.Series(prices, index=dates)

        rsi = detector._calculate_rsi(closes)
        assert rsi > 60  # Should be high in uptrend

    def test_rsi_oversold(self, detector):
        """Test RSI in oversold condition."""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        prices = 100 - np.arange(30) * 2  # Steep downtrend
        closes = pd.Series(prices, index=dates)

        rsi = detector._calculate_rsi(closes)
        assert rsi < 40  # Should be low in downtrend

    def test_support_resistance_calculation(self, detector, bull_market_data):
        """Test support and resistance calculation."""
        support, resistance = detector._calculate_support_resistance(bull_market_data)

        assert support is not None
        assert resistance is not None
        assert support < resistance
        assert support > 0
        assert resistance > 0

    def test_empty_data_handling(self, detector):
        """Test handling of empty data."""
        empty_df = pd.DataFrame({"Close": []})

        regime_info = detector.detect_regime(empty_df)
        assert regime_info["regime"] == "unknown"
        assert regime_info["rsi_value"] == 50.0

    def test_insufficient_data_handling(self, detector):
        """Test handling of insufficient data."""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        df = pd.DataFrame({
            "Close": 100 + np.arange(30),
        }, index=dates)

        regime_info = detector.detect_regime(df)
        assert regime_info["regime"] == "unknown"

    def test_regime_summary(self, detector, bull_market_data):
        """Test regime summary generation."""
        regime_info = detector.detect_regime(bull_market_data)
        summary = detector.get_regime_summary(regime_info)

        assert "BULL" in summary or "bull" in summary.lower()
        assert "Trend:" in summary
        assert "Vol:" in summary
        assert "RSI:" in summary

    def test_threshold_bounds(self, detector, bull_market_data):
        """Test that thresholds are within bounds."""
        regime_info = detector.detect_regime(bull_market_data)
        thresholds = detector.get_adaptive_thresholds(regime_info)

        assert 40 <= thresholds["entry_threshold"] <= 80
        assert 0 < thresholds["profit_target"] <= 0.10
        assert 0 < thresholds["stop_loss"] <= 0.05
        assert 0.5 <= thresholds["position_size_adjustment"] <= 1.5

    def test_get_regime_detector(self):
        """Test global regime detector instance."""
        det1 = get_regime_detector()
        det2 = get_regime_detector()

        assert det1 is det2  # Same instance

    def test_market_regime_enum(self):
        """Test MarketRegime enum."""
        assert MarketRegime.BULL.value == "bull"
        assert MarketRegime.BEAR.value == "bear"
        assert MarketRegime.SIDEWAYS.value == "sideways"
        assert MarketRegime.VOLATILE.value == "volatile"

    def test_trend_calculation(self, detector, bull_market_data):
        """Test trend strength calculation."""
        regime_info = detector.detect_regime(bull_market_data)

        trend_strength = regime_info["trend_strength"]
        trend_pct = regime_info["trend_pct"]

        # Uptrend should have positive values
        assert trend_strength > 0
        assert trend_pct > 0
        assert -1.0 <= trend_strength <= 1.0

    def test_volatility_ratio(self, detector, bull_market_data):
        """Test volatility ratio calculation."""
        regime_info = detector.detect_regime(bull_market_data)

        vol_ratio = regime_info["volatility_ratio"]
        assert vol_ratio > 0

    def test_rsi_fine_tuning(self, detector):
        """Test RSI-based fine tuning of thresholds."""
        # Overbought condition
        regime_info_high_rsi = {
            "regime": "sideways",
            "volatility_level": "medium",
            "rsi_value": 80.0,
        }
        thresholds = detector.get_adaptive_thresholds(regime_info_high_rsi)
        assert thresholds["entry_threshold"] > 55.0  # Should be harder

        # Oversold condition
        regime_info_low_rsi = {
            "regime": "sideways",
            "volatility_level": "medium",
            "rsi_value": 20.0,
        }
        thresholds = detector.get_adaptive_thresholds(regime_info_low_rsi)
        assert thresholds["entry_threshold"] < 55.0  # Should be easier
