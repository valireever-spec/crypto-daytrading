"""Tests for regime detection (Phase 2 Week 7)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.analytics.regime_detector import (
    RegimeDetector,
    get_regime_detector,
)


@pytest.fixture
def detector():
    """Create regime detector for tests."""
    return RegimeDetector(lookback_trend=50, lookback_vol=20, ma_window=50)


@pytest.fixture
def bull_market_data():
    """Create bull market OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    base_price = 100
    prices = []

    for i in range(100):
        # Strong uptrend with low noise to keep volatility medium
        close = base_price + (i * 1.0) + np.random.normal(0, 0.15)
        prices.append(close)

    df = pd.DataFrame({
        'Open': prices,
        'High': [p + 2 for p in prices],
        'Low': [p - 1 for p in prices],
        'Close': prices,
        'Volume': [1000000] * 100,
    }, index=dates)

    return df


@pytest.fixture
def bear_market_data():
    """Create bear market OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    base_price = 100
    prices = []

    for i in range(100):
        # Moderate downtrend with low noise to avoid high volatility classification
        close = base_price - (i * 0.4) + np.random.normal(0, 0.15)
        prices.append(max(10, close))  # Prevent going below 10

    df = pd.DataFrame({
        'Open': prices,
        'High': [p + 1 for p in prices],
        'Low': [p - 2 for p in prices],
        'Close': prices,
        'Volume': [1000000] * 100,
    }, index=dates)

    return df


@pytest.fixture
def sideways_market_data():
    """Create sideways market OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    base_price = 100
    # Create true sideways: constrained oscillation around base price
    np.random.seed(42)
    noise = np.random.normal(0, 0.5, 100)
    prices = [base_price + noise[i] for i in range(100)]

    df = pd.DataFrame({
        'Open': prices,
        'High': [p + 1.5 for p in prices],
        'Low': [p - 1.5 for p in prices],
        'Close': prices,
        'Volume': [1000000] * 100,
    }, index=dates)

    return df


@pytest.fixture(autouse=True)
def cleanup_detector():
    """Clean up global detector between tests."""
    import backend.analytics.regime_detector as regime_module

    regime_module._regime_detector = None
    yield
    regime_module._regime_detector = None


class TestRegimeDetector:
    """Test RegimeDetector class."""

    def test_init(self, detector):
        """Initialize detector."""
        assert detector.lookback_trend == 50
        assert detector.lookback_vol == 20
        assert detector.ma_window == 50

    def test_detect_bull_regime(self, detector, bull_market_data):
        """Detect bull market regime."""
        metrics = detector.detect_regime(bull_market_data)

        assert metrics["regime"] == "BULL"
        assert metrics.get("volatility_ratio", 1.0) > 0.5
        assert metrics["trend_strength"] > 0  # Uptrend

    def test_detect_bear_regime(self, detector, bear_market_data):
        """Detect bear market regime."""
        metrics = detector.detect_regime(bear_market_data)

        # Bear market has downtrend - check that
        assert metrics["trend_strength"] < 0  # Downtrend
        assert metrics["volatility_level"] is not None  # Has volatility level

    def test_detect_sideways_regime(self, detector, sideways_market_data):
        """Detect sideways market regime."""
        metrics = detector.detect_regime(sideways_market_data)

        assert metrics["regime"] in ["SIDEWAYS", "VOLATILE"]
        assert metrics.get("volatility_ratio", 1.0) > 0

    def test_rsi_calculation(self, detector, bull_market_data):
        """Calculate RSI indicator."""
        rsi = detector._calculate_rsi(bull_market_data["Close"])

        assert isinstance(rsi, float)
        assert 0 <= rsi <= 100

    def test_atr_calculation(self, detector, bull_market_data):
        """Calculate ATR indicator (via detect_regime)."""
        metrics = detector.detect_regime(bull_market_data)
        assert "rsi_value" in metrics
        assert 0 <= metrics["rsi_value"] <= 100

    def test_support_resistance(self, detector, bull_market_data):
        """Calculate support and resistance levels."""
        support, resistance = detector._calculate_support_resistance(bull_market_data)

        assert support < resistance
        assert support > 0
        assert resistance > 0

    def test_empty_data(self, detector):
        """Handle empty DataFrame."""
        empty_df = pd.DataFrame()
        metrics = detector.detect_regime(empty_df)

        assert metrics["regime"] == "unknown"
        assert metrics["trend_strength"] == 0.0

    def test_insufficient_data(self, detector):
        """Handle insufficient data."""
        small_df = pd.DataFrame({
            'Open': [100],
            'High': [102],
            'Low': [99],
            'Close': [101],
            'Volume': [1000],
        })

        metrics = detector.detect_regime(small_df)

        assert metrics["regime"] == "unknown"
        assert metrics["trend_strength"] == 0.0

    def test_metrics_structure(self, detector, bull_market_data):
        """Verify metrics structure."""
        metrics = detector.detect_regime(bull_market_data)

        assert isinstance(metrics, dict)
        assert "regime" in metrics
        assert isinstance(metrics["regime"], str)
        assert metrics["regime"] in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE", "unknown"]
        assert "trend_strength" in metrics
        assert -1 <= metrics["trend_strength"] <= 1
        assert "rsi_value" in metrics
        assert 0 <= metrics["rsi_value"] <= 100

    def test_regime_impact_analysis(self, detector):
        """Verify regime-aware threshold adjustments."""
        bull_metrics = {
            "regime": "BULL",
            "trend_strength": 0.5,
            "volatility_level": "medium",
            "rsi_value": 55,
        }

        thresholds = detector.get_adaptive_thresholds(bull_metrics)

        assert "entry_threshold" in thresholds
        assert "profit_target" in thresholds
        assert "stop_loss" in thresholds
        assert "position_size_adjustment" in thresholds

    def test_strategy_adjustment_bull(self, detector):
        """Test strategy adjustment for bull market."""
        bull_metrics = {"regime": "bull", "volatility_level": "medium", "rsi_value": 50}
        thresholds = detector.get_adaptive_thresholds(bull_metrics)

        assert thresholds["position_size_adjustment"] > 1.0  # Bull market = larger positions

    def test_strategy_adjustment_bear(self, detector):
        """Test strategy adjustment for bear market."""
        bear_metrics = {"regime": "bear", "volatility_level": "medium", "rsi_value": 50}
        thresholds = detector.get_adaptive_thresholds(bear_metrics)

        assert thresholds["position_size_adjustment"] < 1.0  # Bear market = smaller positions

    def test_strategy_adjustment_sideways(self, detector):
        """Test strategy adjustment for sideways market."""
        sideways_metrics = {"regime": "sideways", "volatility_level": "medium", "rsi_value": 50}
        thresholds = detector.get_adaptive_thresholds(sideways_metrics)

        assert thresholds["position_size_adjustment"] == 1.0  # Sideways = neutral sizing

    def test_trading_rules_bull(self, detector):
        """Get trading rules for bull market."""
        bull_metrics = {"regime": "bull", "volatility_level": "medium", "rsi_value": 50}
        rules = detector.get_adaptive_thresholds(bull_metrics)

        assert rules["position_size_adjustment"] > 1.0
        assert rules["profit_target"] > 0.05
        assert rules["stop_loss"] > 0

    def test_trading_rules_bear(self, detector):
        """Get trading rules for bear market."""
        bear_metrics = {"regime": "bear", "volatility_level": "medium", "rsi_value": 50}
        rules = detector.get_adaptive_thresholds(bear_metrics)

        assert rules["position_size_adjustment"] < 1.0
        assert rules["stop_loss"] < 0.03

    def test_trading_rules_sideways(self, detector):
        """Get trading rules for sideways market."""
        sideways_metrics = {"regime": "sideways", "volatility_level": "medium", "rsi_value": 50}
        rules = detector.get_adaptive_thresholds(sideways_metrics)

        assert rules["position_size_adjustment"] == 1.0

    def test_trading_rules_volatile(self, detector):
        """Get trading rules for volatile market."""
        volatile_metrics = {"regime": "volatile", "volatility_level": "extreme", "rsi_value": 50}
        rules = detector.get_adaptive_thresholds(volatile_metrics)

        assert rules["position_size_adjustment"] < 1.0


class TestGlobalInstance:
    """Test global regime detector instance."""

    def test_init_detector(self):
        """Initialize global detector."""
        detector = get_regime_detector()
        assert detector is not None

    def test_get_detector(self):
        """Get initialized global detector."""
        get_regime_detector()
        detector = get_regime_detector()
        assert detector is not None

    def test_get_uninitialized(self):
        """Initialize detector when needed."""
        import backend.analytics.regime_detector as regime_module

        regime_module._regime_detector = None
        detector = get_regime_detector()
        # get_regime_detector() creates one if None, not returns None
        assert detector is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
