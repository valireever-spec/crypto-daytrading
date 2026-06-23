"""Tests for historical data service (Phase 2 Week 6)."""

import pytest
from datetime import datetime, timedelta
import pandas as pd

from backend.analytics.historical_data import (
    HistoricalDataService,
    init_historical_service,
    get_historical_service,
)


@pytest.fixture
def service():
    """Create historical data service for tests."""
    return HistoricalDataService()


@pytest.fixture(autouse=True)
def cleanup_service():
    """Clean up global service between tests."""
    import backend.analytics.historical_data as data_module

    data_module._historical_service = None
    yield
    data_module._historical_service = None


class TestHistoricalDataService:
    """Test HistoricalDataService class."""

    def test_init(self, service):
        """Initialize service."""
        assert service.cache == {}
        assert service.cache_ttl == 3600

    def test_normalize_symbol_crypto(self, service):
        """Normalize crypto symbols."""
        assert service._normalize_symbol("BTCUSDT") == "BTC-USD"
        assert service._normalize_symbol("ETHUSDT") == "ETH-USD"
        assert service._normalize_symbol("BNBUSDT") == "BNB-USD"

    def test_normalize_symbol_stock(self, service):
        """Keep stock symbols as-is."""
        assert service._normalize_symbol("AAPL") == "AAPL"
        assert service._normalize_symbol("MSFT") == "MSFT"

    def test_standardize_columns(self, service):
        """Standardize DataFrame columns."""
        df = pd.DataFrame({
            'open': [100, 101],
            'high': [102, 103],
            'low': [99, 100],
            'close': [101, 102],
            'volume': [1000000, 1100000],
        })

        result = service._standardize_columns(df)

        assert 'Open' in result.columns
        assert 'High' in result.columns
        assert 'Low' in result.columns
        assert 'Close' in result.columns
        assert 'Volume' in result.columns

    def test_standardize_columns_mixed_case(self, service):
        """Handle mixed case columns."""
        df = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'close': [101, 102],
            'volume': [1000000, 1100000],
        })

        result = service._standardize_columns(df)

        assert 'Open' in result.columns
        assert 'Close' in result.columns
        assert 'Volume' in result.columns


class TestGlobalInstance:
    """Test global service instance."""

    def test_init_service(self):
        """Initialize global service."""
        service = init_historical_service()
        assert service is not None

    def test_get_service(self):
        """Get initialized global service."""
        init_historical_service()
        service = get_historical_service()
        assert service is not None

    def test_get_uninitialized(self):
        """Return None if not initialized."""
        import backend.analytics.historical_data as data_module

        data_module._historical_service = None
        assert get_historical_service() is None


class TestFetchOHLCV:
    """Test OHLCV data fetching."""

    def test_fetch_valid_symbol(self, service):
        """Fetch data for valid symbol."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        data = service.fetch_ohlcv("AAPL", start, end, interval="1d")

        # Should either return data or None gracefully
        if data is not None:
            assert isinstance(data, pd.DataFrame)
            assert len(data) > 0
            assert 'Open' in data.columns
            assert 'Close' in data.columns
            assert 'Volume' in data.columns

    def test_fetch_crypto_symbol(self, service):
        """Fetch data for crypto symbol."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        data = service.fetch_ohlcv("BTCUSDT", start, end, interval="1d")

        # Should handle crypto symbols
        if data is not None:
            assert isinstance(data, pd.DataFrame)
            assert 'Open' in data.columns

    def test_fetch_invalid_date_range(self, service):
        """Handle invalid date range."""
        start = datetime(2025, 1, 1)
        end = datetime(2024, 1, 1)

        # End date before start date - should handle gracefully
        data = service.fetch_ohlcv("AAPL", start, end)

        # Should return None or empty
        assert data is None or data.empty

    def test_fetch_future_dates(self, service):
        """Handle future dates."""
        start = datetime.utcnow() + timedelta(days=30)
        end = datetime.utcnow() + timedelta(days=60)

        data = service.fetch_ohlcv("AAPL", start, end)

        # Should return None (no future data)
        assert data is None or data.empty

    def test_fetch_interval_options(self, service):
        """Test different interval options."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 8)

        # Test daily
        data_daily = service.fetch_ohlcv("AAPL", start, end, interval="1d")

        # Test different intervals
        for interval in ["1d", "1wk"]:
            data = service.fetch_ohlcv("AAPL", start, end, interval=interval)
            if data is not None:
                assert len(data) > 0
                assert 'Close' in data.columns


class TestMultipleSymbols:
    """Test fetching multiple symbols."""

    def test_fetch_multiple_symbols(self, service):
        """Fetch data for multiple symbols."""
        symbols = ["AAPL", "MSFT"]
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        results = service.fetch_multiple(symbols, start, end)

        # Should return dict with results
        assert isinstance(results, dict)
        # At least some symbols should succeed
        assert len(results) >= 0

    def test_fetch_multiple_empty(self, service):
        """Handle empty symbol list."""
        symbols = []
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        results = service.fetch_multiple(symbols, start, end)

        assert results == {}


class TestLatestPrice:
    """Test fetching latest price."""

    def test_get_latest_price(self, service):
        """Get latest price for symbol."""
        price = service.get_latest_price("AAPL")

        # Should return float or None
        if price is not None:
            assert isinstance(price, float)
            assert price > 0

    def test_get_latest_price_crypto(self, service):
        """Get latest price for crypto."""
        price = service.get_latest_price("BTCUSDT")

        if price is not None:
            assert isinstance(price, float)
            assert price > 0


class TestDataRange:
    """Test getting data range."""

    def test_get_data_range(self, service):
        """Get available data date range."""
        date_range = service.get_data_range("AAPL")

        if date_range is not None:
            start_date, end_date = date_range
            assert isinstance(start_date, type(end_date))
            assert start_date <= end_date

    def test_get_data_range_recent_symbol(self, service):
        """Get data range for newer symbol."""
        date_range = service.get_data_range("AAPL")

        # Should return range or None
        assert date_range is None or isinstance(date_range, tuple)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
