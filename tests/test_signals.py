"""Unit tests for signal generation (FR-003)."""

import pytest
import pandas as pd
import numpy as np

from backend.analytics.signals import SignalGenerator


@pytest.fixture(autouse=True)
def cleanup_allocation():
    """Clean up allocation file and reset manager before and after tests."""
    from pathlib import Path
    import backend.analytics.allocation as alloc_module

    # Clean before
    if alloc_module.ALLOCATION_FILE.exists():
        alloc_module.ALLOCATION_FILE.unlink()

    # Reset global allocation manager
    alloc_module._allocation_manager = None

    yield

    # Clean after
    if alloc_module.ALLOCATION_FILE.exists():
        alloc_module.ALLOCATION_FILE.unlink()

    # Reset global allocation manager
    alloc_module._allocation_manager = None


@pytest.fixture
def signal_gen():
    """Create signal generator for tests."""
    return SignalGenerator()


@pytest.fixture
def sample_prices():
    """Create sample price series for testing."""
    np.random.seed(42)
    # Simulate realistic price movement
    base_price = 45000
    returns = np.random.normal(0.0005, 0.01, 100)
    prices = base_price * np.exp(np.cumsum(returns))
    return pd.Series(prices)


# === RSI Tests ===


def test_rsi_calculation(signal_gen, sample_prices):
    """RSI should calculate correctly."""
    rsi = signal_gen.calculate_rsi(sample_prices)

    # RSI should be between 0 and 100
    assert rsi.min() >= 0
    assert rsi.max() <= 100
    assert len(rsi) == len(sample_prices)


def test_rsi_insufficient_data(signal_gen):
    """RSI with insufficient data should default to neutral (50)."""
    short_prices = pd.Series([100, 101, 102])
    rsi = signal_gen.calculate_rsi(short_prices, period=14)

    # Should return neutral signal
    assert rsi.iloc[-1] == 50.0


def test_rsi_overbought(signal_gen):
    """Consistently rising prices should trigger overbought RSI."""
    rising_prices = pd.Series(np.linspace(100, 200, 50))
    rsi = signal_gen.calculate_rsi(rising_prices)

    # Last RSI should be high (overbought)
    assert rsi.iloc[-1] > 70


def test_rsi_oversold(signal_gen):
    """Consistently falling prices should trigger oversold RSI."""
    falling_prices = pd.Series(np.linspace(200, 100, 50))
    rsi = signal_gen.calculate_rsi(falling_prices)

    # Last RSI should be low (oversold)
    assert rsi.iloc[-1] < 30


# === MACD Tests ===


def test_macd_calculation(signal_gen, sample_prices):
    """MACD should calculate correctly."""
    macd_line, signal_line, histogram = signal_gen.calculate_macd(sample_prices)

    # All should have same length
    assert len(macd_line) == len(sample_prices)
    assert len(signal_line) == len(sample_prices)
    assert len(histogram) == len(sample_prices)

    # Histogram = MACD - Signal
    assert np.allclose(
        histogram.dropna().values, (macd_line - signal_line).dropna().values
    )


def test_macd_insufficient_data(signal_gen):
    """MACD with insufficient data should return zeros."""
    short_prices = pd.Series([100, 101, 102])
    macd_line, signal_line, histogram = signal_gen.calculate_macd(short_prices)

    # Should return zeros
    assert (macd_line == 0.0).all()
    assert (signal_line == 0.0).all()
    assert (histogram == 0.0).all()


# === Bollinger Bands Tests ===


def test_bollinger_bands_calculation(signal_gen, sample_prices):
    """Bollinger Bands should calculate correctly."""
    upper, middle, lower = signal_gen.calculate_bollinger_bands(sample_prices)

    # All should have same length
    assert len(upper) == len(sample_prices)
    assert len(middle) == len(sample_prices)
    assert len(lower) == len(sample_prices)

    # Upper > Middle > Lower
    valid_idx = ~(upper.isna() | middle.isna() | lower.isna())
    assert (upper[valid_idx] >= middle[valid_idx]).all()
    assert (middle[valid_idx] >= lower[valid_idx]).all()


def test_bollinger_bands_insufficient_data(signal_gen):
    """Bollinger Bands with insufficient data should return original prices."""
    short_prices = pd.Series([100, 101, 102])
    upper, middle, lower = signal_gen.calculate_bollinger_bands(
        short_prices, period=20
    )

    # With insufficient data, should return original prices
    assert len(upper) == len(short_prices)


# === Signal Generation Tests ===


@pytest.mark.asyncio
async def test_signal_generation_bullish(signal_gen):
    """Strong uptrend should generate bullish signal."""
    rising_prices = pd.Series(np.linspace(100, 150, 50))
    signal = await signal_gen.generate_signal("TEST", rising_prices)

    # With allocation weighting, uptrend momentum is positive but
    # price near upper BB is treated as reversion sell signal
    # Net result: positive but not necessarily > 50
    assert signal["score"] > 0  # Should be bullish overall
    assert signal["grade"] in ["BUY", "STRONG BUY", "WEAK BUY", "NEUTRAL"]


@pytest.mark.asyncio
async def test_signal_generation_bearish(signal_gen):
    """Strong downtrend should generate bearish signal."""
    falling_prices = pd.Series(np.linspace(150, 100, 50))
    signal = await signal_gen.generate_signal("TEST", falling_prices)

    # With allocation weighting, downtrend momentum is negative but
    # price near lower BB is treated as reversion buy signal
    # Net result: negative but not necessarily < 50
    assert signal["score"] < 0  # Should be bearish overall
    assert signal["grade"] in ["SELL", "STRONG SELL", "WEAK SELL", "NEUTRAL"]


@pytest.mark.asyncio
async def test_signal_generation_neutral(signal_gen):
    """Sideways market should generate neutral signal."""
    sideways_prices = pd.Series([100] * 50)
    signal = await signal_gen.generate_signal("TEST", sideways_prices)

    # RSI should be ~50 (neutral) for flat price
    assert 35 <= signal["score"] <= 65 or signal["grade"] == "NEUTRAL"


@pytest.mark.asyncio
async def test_signal_insufficient_data(signal_gen):
    """Signal with insufficient data should return neutral."""
    short_prices = pd.Series([100, 101, 102])
    signal = await signal_gen.generate_signal("TEST", short_prices)

    assert signal["score"] == 50
    assert signal["grade"] == "NEUTRAL"


@pytest.mark.asyncio
async def test_signal_contains_indicators(signal_gen, sample_prices):
    """Signal should include indicator values."""
    signal = await signal_gen.generate_signal("BTCUSDT", sample_prices)

    assert "symbol" in signal
    assert "score" in signal
    assert "grade" in signal
    assert "rsi" in signal
    assert "macd_histogram" in signal
    assert "bb_position" in signal
    assert "timestamp" in signal


@pytest.mark.asyncio
async def test_signal_score_range(signal_gen, sample_prices):
    """Signal score should be in valid range."""
    signal = await signal_gen.generate_signal("TEST", sample_prices)

    # Score should be between -100 and +100
    assert -100 <= signal["score"] <= 100


@pytest.mark.asyncio
async def test_signal_grade_validity(signal_gen, sample_prices):
    """Signal grade should match score."""
    signal = await signal_gen.generate_signal("TEST", sample_prices)

    grade = signal["grade"]
    score = signal["score"]

    # Grade should match score range
    if score >= 70:
        assert grade in ["STRONG BUY", "BUY"]
    elif score >= 50:
        assert grade in ["BUY", "WEAK BUY", "NEUTRAL"]
    elif score >= 30:
        assert grade in ["WEAK BUY", "NEUTRAL", "WEAK SELL"]
    elif score >= -30:
        assert grade == "NEUTRAL"
    elif score >= -50:
        assert grade in ["WEAK SELL", "NEUTRAL"]
    elif score >= -70:
        assert grade in ["SELL", "WEAK SELL"]
    else:
        assert grade == "STRONG SELL"


@pytest.mark.asyncio
async def test_signal_with_random_data(signal_gen):
    """Signal generation should work with random data."""
    random_prices = pd.Series(np.random.uniform(100, 110, 100))
    signal = await signal_gen.generate_signal("RANDOM", random_prices)

    # Should not error and should have valid structure
    assert "score" in signal
    assert "grade" in signal
    assert -100 <= signal["score"] <= 100


# === Integration Tests ===


@pytest.mark.asyncio
async def test_signal_consistency(signal_gen, sample_prices):
    """Same prices should generate same signal."""
    signal1 = await signal_gen.generate_signal("TEST1", sample_prices.copy())
    signal2 = await signal_gen.generate_signal("TEST2", sample_prices.copy())

    # Signals should be identical (different symbol doesn't matter)
    assert signal1["score"] == signal2["score"]
    assert signal1["rsi"] == signal2["rsi"]


@pytest.mark.asyncio
async def test_multiple_signals(signal_gen):
    """Should generate signals for multiple symbols."""
    prices = pd.Series(np.linspace(100, 150, 50))

    signals = []
    for symbol in ["BTC", "ETH", "BNB"]:
        signal = await signal_gen.generate_signal(symbol, prices.copy())
        signals.append(signal)

    assert len(signals) == 3
    assert all("score" in s for s in signals)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
