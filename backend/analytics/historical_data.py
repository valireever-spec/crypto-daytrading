"""Historical OHLCV data service for backtesting (Phase 2 Week 6)."""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """Fetch and manage historical OHLCV data."""

    def __init__(self):
        """Initialize historical data service."""
        self.cache: dict = {}
        self.cache_ttl = 3600  # 1 hour

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch historical OHLCV data.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT', 'BTC-USD')
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Interval ('1m', '5m', '1h', '1d', '1wk', '1mo')

        Returns:
            DataFrame with OHLCV data or None if fetch fails
        """
        try:
            # Normalize symbol for yfinance
            yf_symbol = self._normalize_symbol(symbol)

            # Check cache first (avoid expensive yfinance calls)
            # Use only date (not time) so multiple calls on same day hit cache
            cache_key = f"{yf_symbol}_{start_date.date()}_{end_date.date()}_{interval}"
            if cache_key in self.cache:
                cached_entry = self.cache[cache_key]
                age = (datetime.now() - cached_entry["time"]).total_seconds()
                if age < self.cache_ttl:
                    logger.info(
                        f"✓ Cache hit: {yf_symbol} ({age:.0f}s old, next refresh in {self.cache_ttl - age:.0f}s)"
                    )
                    return cached_entry["data"]
                else:
                    del self.cache[cache_key]  # Expired, remove from cache

            logger.info(
                f"Fetching {yf_symbol} data from {start_date.date()} to {end_date.date()}"
            )

            # Fetch data
            ticker = yf.download(
                yf_symbol,
                start=start_date,
                end=end_date,
                interval=interval,
                progress=False,
            )

            if ticker is None or ticker.empty:
                logger.warning(f"No data returned for {yf_symbol}")
                return None

            # Standardize column names
            ticker = self._standardize_columns(ticker)

            # Remove any NaN values
            ticker = ticker.dropna()

            if ticker.empty:
                logger.warning(f"No valid OHLCV data for {yf_symbol}")
                return None

            # Store in cache for future calls
            self.cache[cache_key] = {"data": ticker, "time": datetime.now()}

            logger.info(f"Fetched {len(ticker)} candles for {yf_symbol}")
            return ticker

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None

    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> dict:
        """Fetch historical data for multiple symbols.

        Args:
            symbols: List of trading symbols
            start_date: Start date
            end_date: End date
            interval: Data interval

        Returns:
            Dict mapping symbol -> DataFrame
        """
        results = {}

        for symbol in symbols:
            data = self.fetch_ohlcv(symbol, start_date, end_date, interval)
            if data is not None:
                results[symbol] = data

        logger.info(f"Fetched data for {len(results)}/{len(symbols)} symbols")
        return results

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Latest price or None if unavailable
        """
        try:
            yf_symbol = self._normalize_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d")

            if data is None or data.empty:
                return None

            return float(data["Close"].iloc[-1])

        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol}: {e}")
            return None

    def get_data_range(self, symbol: str) -> Optional[tuple]:
        """Get available data date range for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (start_date, end_date) or None if unavailable
        """
        try:
            # Fetch 10 years of daily data
            start_date = datetime.utcnow() - timedelta(days=3650)
            data = self.fetch_ohlcv(
                symbol, start_date, datetime.utcnow(), interval="1d"
            )

            if data is None or data.empty:
                return None

            return (data.index[0], data.index[-1])

        except Exception as e:
            logger.error(f"Error getting data range for {symbol}: {e}")
            return None

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for yfinance.

        Args:
            symbol: Trading symbol

        Returns:
            Normalized symbol
        """
        # Handle common crypto symbols
        if symbol.upper() == "BTCUSDT":
            return "BTC-USD"
        elif symbol.upper() == "ETHUSDT":
            return "ETH-USD"
        elif symbol.upper() == "BNBUSDT":
            return "BNB-USD"

        # Return as-is for stock symbols
        return symbol

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize DataFrame column names.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with standardized columns
        """
        # Rename columns to standard format
        rename_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "Open": "Open",
            "High": "High",
            "Low": "Low",
            "Close": "Close",
            "Volume": "Volume",
        }

        df = df.rename(columns=rename_map)

        # Ensure required columns exist
        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}")

        return df


# Global instance
_historical_service: Optional[HistoricalDataService] = None


def init_historical_service() -> HistoricalDataService:
    """Initialize global historical data service."""
    global _historical_service
    _historical_service = HistoricalDataService()
    logger.info("Historical data service initialized")
    return _historical_service


def get_historical_service() -> Optional[HistoricalDataService]:
    """Get global historical data service."""
    return _historical_service
