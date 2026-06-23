"""Tests for regime detection (Phase 2 Week 7)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.analytics.regime_detector import (
    RegimeDetector,
    RegimeMetrics,
    init_regime_detector,
    get_regime_detector,
)


@pytest.fixture
def detector():
    """Create regime detector for tests."""
    return RegimeDetector(lookback_periods=60)


@pytest.fixture
def bull_market_data():
    """Create bull market OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    base_price = 100
    prices = []

    for i in range(100):
        # Strong uptrend
        close = base_price + (i * 0.5) + np.random.normal(0, 0.5)
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
        # Strong downtrend
        close = base_price - (i * 0.5) + np.random.normal(0, 0.5)
        prices.append(close)

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
    prices = [base_price + np.random.normal(0, 1) for _ in range(100)]

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
        assert detector.lookback_periods == 60

    def test_detect_bull_regime(self, detector, bull_market_data):
        """Detect bull market regime."""
        metrics = detector.detect_regime(bull_market_data)

        assert metrics.regime == "BULL"
        assert metrics.confidence > 0.5
        assert metrics.trend_strength > 0  # Uptrend

    def test_detect_bear_regime(self, detector, bear_market_data):
        """Detect bear market regime."""
        metrics = detector.detect_regime(bear_market_data)

        assert metrics.regime == "BEAR"
        assert metrics.confidence > 0.5
        assert metrics.trend_strength < 0  # Downtrend

    def test_detect_sideways_regime(self, detector, sideways_market_data):
        """Detect sideways market regime."""
        metrics = detector.detect_regime(sideways_market_data)

        assert metrics.regime in ["SIDEWAYS", "VOLATILE"]
        assert metrics.confidence > 0

    def test_rsi_calculation(self, detector, bull_market_data):
        """Calculate RSI indicator."""
        rsi = detector._calculate_rsi(bull_market_data["Close"])

        assert len(rsi) == len(bull_market_data)
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_atr_calculation(self, detector, bull_market_data):
        """Calculate ATR indicator."""
        atr = detector._calculate_atr(bull_market_data)

        assert len(atr) == len(bull_market_data)
        assert (atr >= 0).all()

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

        assert metrics.regime == "SIDEWAYS"
        assert metrics.confidence == 0.0

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

        assert metrics.regime == "SIDEWAYS"
        assert metrics.confidence == 0.0

    def test_metrics_structure(self, detector, bull_market_data):
        """Verify metrics structure."""
        metrics = detector.detect_regime(bull_market_data)

        assert isinstance(metrics, RegimeMetrics)
        assert isinstance(metrics.regime, str)
        assert 0 <= metrics.confidence <= 1
        assert metrics.volatility_pct >= 0
        assert -1 <= metrics.trend_strength <= 1
        assert metrics.support_level > 0
        assert metrics.resistance_level > 0
        assert 0 <= metrics.rsi <= 100

    def test_regime_impact_analysis(self, detector):
        """Analyze regime impact on strategies."""
        strategy_returns = {
            "momentum": [0.01, 0.02, -0.01],
            "reversion": [-0.01, 0.01, 0.02],
            "grid": [0.005, 0.005, 0.005],
        }

        adjustments = detector.analyze_regime_impact("BULL", strategy_returns)

        assert "momentum" in adjustments
        assert "reversion" in adjustments
        assert "grid" in adjustments
        assert adjustments["momentum"] > adjustments["reversion"]

    def test_strategy_adjustment_bull(self, detector):
        """Test strategy adjustment for bull market."""
        adj_mom = detector._get_strategy_adjustment("momentum", "BULL")
        adj_rev = detector._get_strategy_adjustment("reversion", "BULL")

        assert adj_mom > 1.0  # Momentum should do better
        assert adj_rev < 1.0  # Reversion should do worse

    def test_strategy_adjustment_bear(self, detector):
        """Test strategy adjustment for bear market."""
        adj_mom = detector._get_strategy_adjustment("momentum", "BEAR")
        adj_rev = detector._get_strategy_adjustment("reversion", "BEAR")

        assert adj_mom < 1.0  # Momentum should do worse
        assert adj_rev > 1.0  # Reversion should do better

    def test_strategy_adjustment_sideways(self, detector):
        """Test strategy adjustment for sideways market."""
        adj_grid = detector._get_strategy_adjustment("grid", "SIDEWAYS")
        adj_rev = detector._get_strategy_adjustment("reversion", "SIDEWAYS")
        adj_mom = detector._get_strategy_adjustment("momentum", "SIDEWAYS")

        # Both grid and reversion do well in sideways, better than momentum
        assert adj_grid > adj_mom
        assert adj_rev > adj_mom

    def test_trading_rules_bull(self, detector):
        """Get trading rules for bull market."""
        rules = detector.get_regime_trading_rules("BULL")

        assert rules["position_size_multiplier"] > 1.0
        assert "momentum" in rules["recommended_strategies"]
        assert rules["stop_loss_pct"] > 0
        assert rules["take_profit_pct"] > 0

    def test_trading_rules_bear(self, detector):
        """Get trading rules for bear market."""
        rules = detector.get_regime_trading_rules("BEAR")

        assert rules["position_size_multiplier"] < 1.0
        assert "reversion" in rules["recommended_strategies"]

    def test_trading_rules_sideways(self, detector):
        """Get trading rules for sideways market."""
        rules = detector.get_regime_trading_rules("SIDEWAYS")

        assert rules["position_size_multiplier"] == 1.0
        assert "grid" in rules["recommended_strategies"]

    def test_trading_rules_volatile(self, detector):
        """Get trading rules for volatile market."""
        rules = detector.get_regime_trading_rules("VOLATILE")

        assert rules["position_size_multiplier"] < 1.0
        assert len(rules["recommended_strategies"]) == 0


class TestGlobalInstance:
    """Test global regime detector instance."""

    def test_init_detector(self):
        """Initialize global detector."""
        detector = init_regime_detector()
        assert detector is not None

    def test_get_detector(self):
        """Get initialized global detector."""
        init_regime_detector()
        detector = get_regime_detector()
        assert detector is not None

    def test_get_uninitialized(self):
        """Return None if not initialized."""
        import backend.analytics.regime_detector as regime_module

        regime_module._regime_detector = None
        assert get_regime_detector() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
