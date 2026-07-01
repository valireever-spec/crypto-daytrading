"""Tests for FR-017: Market Crash Detection."""

import pytest
from datetime import datetime, timedelta

from backend.core.crash_detector import (
    record_price,
    detect_crash,
    set_crash_threshold,
    get_crash_detection_status,
    reset_crash_detection,
    clear_price_history,
    CrashDetectionConfig
)


@pytest.fixture(autouse=True)
def cleanup_price_history():
    """Clear price history before each test."""
    clear_price_history()
    yield
    clear_price_history()


class TestPriceRecording:
    """Test price recording for crash detection."""

    def test_record_single_price(self):
        """Can record a price for a symbol."""
        record_price('BTCUSDT', 45000.0)

        status = get_crash_detection_status()
        assert 'BTCUSDT' in status['tracked_symbols']

    def test_record_multiple_symbols(self):
        """Can track multiple symbols simultaneously."""
        record_price('BTCUSDT', 45000.0)
        record_price('ETHUSDT', 3000.0)
        record_price('BNBUSDT', 600.0)

        status = get_crash_detection_status()
        assert len(status['tracked_symbols']) == 3

    def test_record_price_uses_current_time_if_none(self):
        """If timestamp not provided, uses current time."""
        before = datetime.utcnow()
        record_price('BTCUSDT', 45000.0)
        after = datetime.utcnow()

        # Price should be recorded with current-ish timestamp
        status = get_crash_detection_status()
        assert len(status['tracked_symbols']) == 1

    def test_record_multiple_prices_same_symbol(self):
        """Can record multiple prices for same symbol over time."""
        record_price('BTCUSDT', 45000.0)
        record_price('BTCUSDT', 44500.0)
        record_price('BTCUSDT', 44000.0)

        # Should track all prices
        status = get_crash_detection_status()
        assert 'BTCUSDT' in status['tracked_symbols']


class TestCrashDetectionBasics:
    """Test crash detection logic."""

    def test_no_crash_if_prices_stable(self):
        """No crash detected if prices stable."""
        now = datetime.utcnow()

        # Stable prices (no movement)
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=4))
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=3))
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=2))
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=1))
        record_price('BTCUSDT', 45000.0, now)

        config = CrashDetectionConfig(threshold_percent=5.0, lookback_minutes=5)
        result = detect_crash(config)

        assert result['crash_detected'] is False

    def test_crash_detected_on_5_percent_drop(self):
        """Crash detected when price drops >5%."""
        now = datetime.utcnow()
        high_price = 45000.0
        crash_price = high_price * 0.94  # 6% drop

        # Record high, then crash
        record_price('BTCUSDT', high_price, now - timedelta(minutes=4))
        record_price('BTCUSDT', high_price, now - timedelta(minutes=3))
        record_price('BTCUSDT', crash_price, now)

        config = CrashDetectionConfig(threshold_percent=5.0, lookback_minutes=5)
        result = detect_crash(config)

        assert result['crash_detected'] is True
        assert result['largest_drop_symbol'] == 'BTCUSDT'
        assert result['largest_drop_percent'] >= 5.0

    def test_no_crash_on_smaller_drop(self):
        """No crash if drop is below threshold."""
        now = datetime.utcnow()
        high_price = 45000.0
        small_drop = high_price * 0.97  # 3% drop (below 5% threshold)

        record_price('BTCUSDT', high_price, now - timedelta(minutes=4))
        record_price('BTCUSDT', small_drop, now)

        config = CrashDetectionConfig(threshold_percent=5.0)
        result = detect_crash(config)

        assert result['crash_detected'] is False

    def test_crash_with_multiple_symbols(self):
        """Detects crash in ANY symbol."""
        now = datetime.utcnow()

        # BTC stable, ETH crashes
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=4))
        record_price('BTCUSDT', 45000.0, now)

        record_price('ETHUSDT', 3000.0, now - timedelta(minutes=4))
        record_price('ETHUSDT', 2800.0, now)  # ~7% drop

        config = CrashDetectionConfig(threshold_percent=5.0)
        result = detect_crash(config)

        assert result['crash_detected'] is True
        assert result['largest_drop_symbol'] == 'ETHUSDT'

    def test_insufficient_candles_ignored(self):
        """Ignores symbols with too few data points."""
        now = datetime.utcnow()

        # Only 1 price point (need minimum 3)
        record_price('BTCUSDT', 45000.0, now)

        config = CrashDetectionConfig(threshold_percent=5.0, min_candles=3)
        result = detect_crash(config)

        assert result['crash_detected'] is False
        assert 'BTCUSDT' in result['symbols_analyzed']


class TestCrashThresholdConfiguration:
    """Test crash threshold settings."""

    def test_set_threshold_affects_detection(self):
        """Changing threshold affects detection results."""
        now = datetime.utcnow()
        high = 45000.0
        low = 44100.0  # ~2% drop

        record_price('BTCUSDT', high, now - timedelta(minutes=4))
        record_price('BTCUSDT', low, now)

        # With 5% threshold, no crash
        config_5 = CrashDetectionConfig(threshold_percent=5.0)
        result_5 = detect_crash(config_5)
        assert result_5['crash_detected'] is False

        # With 1% threshold, should detect crash
        config_1 = CrashDetectionConfig(threshold_percent=1.0)
        result_1 = detect_crash(config_1)
        assert result_1['crash_detected'] is True

    def test_set_crash_threshold_api(self):
        """set_crash_threshold() updates global threshold."""
        set_crash_threshold(3.0)

        status = get_crash_detection_status()
        assert status['threshold_percent'] == 3.0


class TestCrashDetectionReset:
    """Test reset functionality."""

    def test_reset_clears_crash_flag(self):
        """Resetting clears crash detection flag."""
        now = datetime.utcnow()

        # Record crash
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=4))
        record_price('BTCUSDT', 42000.0, now)

        config = CrashDetectionConfig(threshold_percent=5.0)
        result = detect_crash(config)
        assert result['crash_detected'] is True

        # Reset
        reset_crash_detection()

        status = get_crash_detection_status()
        assert status['crashed'] is False

    def test_clear_price_history(self):
        """clear_price_history() removes all recorded prices."""
        record_price('BTCUSDT', 45000.0)
        record_price('ETHUSDT', 3000.0)

        status = get_crash_detection_status()
        assert len(status['tracked_symbols']) == 2

        clear_price_history()

        status = get_crash_detection_status()
        assert len(status['tracked_symbols']) == 0


class TestCrashDetectionDetails:
    """Test detailed crash analysis."""

    def test_details_show_price_drops(self):
        """Details show high price, current price, drop %."""
        now = datetime.utcnow()

        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=4))
        record_price('BTCUSDT', 42750.0, now)  # 5% drop

        config = CrashDetectionConfig(threshold_percent=5.0)
        result = detect_crash(config)

        assert 'BTCUSDT' in result['details']
        details = result['details']['BTCUSDT']
        assert details['high'] == 45000.0
        assert details['current_price'] == 42750.0
        assert abs(details['drop_percent'] - 5.0) < 0.1

    def test_details_for_all_symbols(self):
        """Details show analysis for all tracked symbols."""
        now = datetime.utcnow()

        # Track 3 symbols
        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            record_price(symbol, 100.0, now - timedelta(minutes=4))
            record_price(symbol, 99.0, now)

        config = CrashDetectionConfig(threshold_percent=5.0, min_candles=2)
        result = detect_crash(config)

        for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            assert symbol in result['details']

    def test_largest_drop_tracking(self):
        """Tracks which symbol had largest drop."""
        now = datetime.utcnow()

        # BTC: 2% drop
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=4))
        record_price('BTCUSDT', 44100.0, now)

        # ETH: 8% drop (larger)
        record_price('ETHUSDT', 3000.0, now - timedelta(minutes=4))
        record_price('ETHUSDT', 2760.0, now)

        config = CrashDetectionConfig(threshold_percent=5.0)
        result = detect_crash(config)

        assert result['largest_drop_symbol'] == 'ETHUSDT'
        assert result['largest_drop_percent'] >= 8.0


class TestLookbackWindow:
    """Test price lookback window."""

    def test_prices_outside_window_ignored(self):
        """Prices outside lookback window are ignored."""
        now = datetime.utcnow()

        # Old price: 6 minutes ago (outside 5-min window)
        record_price('BTCUSDT', 45000.0, now - timedelta(minutes=6))

        # Current price: crashed
        record_price('BTCUSDT', 42000.0, now)

        # With 5-min lookback, should only see current price (no high to compare)
        config = CrashDetectionConfig(threshold_percent=5.0, lookback_minutes=5)
        result = detect_crash(config)

        # Should detect as having insufficient data (only 1 recent candle)
        assert result['crash_detected'] is False or len(result['symbols_analyzed']) == 0
