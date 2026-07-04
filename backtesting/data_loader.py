"""
Historical data loader for backtesting.
Fetches OHLCV data from Binance.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pathlib import Path

try:
    import ccxt
except ImportError:
    ccxt = None

from .backtest_engine import Candle

logger = logging.getLogger(__name__)


class DataLoader:
    """Load historical OHLCV data from Binance"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.exchange = None
        self.cache_dir = cache_dir or Path("backtest_cache")
        self.cache_dir.mkdir(exist_ok=True)

        if ccxt:
            self.exchange = ccxt.binance({'enableRateLimit': True})
            logger.info("✅ Connected to Binance via CCXT")
        else:
            logger.warning("⚠️  CCXT not installed. Using cached data only.")

    def _get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """Get cache file path for symbol/timeframe"""
        return self.cache_dir / f"{symbol}_{timeframe}.json"

    def _save_cache(self, symbol: str, timeframe: str, data: List[Dict]):
        """Save candles to cache"""
        cache_path = self._get_cache_path(symbol, timeframe)
        with open(cache_path, "w") as f:
            json.dump(data, f)
        logger.info(f"✅ Cached {len(data)} candles: {symbol} {timeframe}")

    def _load_cache(self, symbol: str, timeframe: str) -> Optional[List[Dict]]:
        """Load candles from cache"""
        cache_path = self._get_cache_path(symbol, timeframe)
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(f"✅ Loaded {len(data)} candles from cache: {symbol} {timeframe}")
            return data
        return None

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True,
    ) -> List[Candle]:
        """
        Fetch OHLCV data from Binance.

        Args:
            symbol: e.g. 'BTCUSDT'
            timeframe: e.g. '5m', '1h', '4h'
            start_date: Start datetime
            end_date: End datetime
            use_cache: Use cached data if available

        Returns:
            List of Candle objects
        """

        # Try cache first
        if use_cache:
            cached = self._load_cache(symbol, timeframe)
            if cached:
                candles = self._ohlcv_to_candles(cached)
                # Filter to date range
                candles = [c for c in candles if start_date <= c.timestamp <= end_date]
                return candles

        # Fetch from exchange
        if not self.exchange:
            logger.error("❌ CCXT not available and no cached data")
            return []

        logger.info(f"📥 Fetching {symbol} {timeframe} from {start_date.date()} to {end_date.date()}")

        try:
            all_ohlcv = []
            current_time = int(start_date.timestamp() * 1000)
            end_time = int(end_date.timestamp() * 1000)

            while current_time < end_time:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=current_time, limit=1000)

                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)

                # Move to next batch
                last_timestamp = ohlcv[-1][0]
                current_time = last_timestamp + 1

                logger.info(f"  Fetched {len(ohlcv)} candles, now at {datetime.fromtimestamp(current_time/1000)}")

            # Save to cache
            if all_ohlcv:
                self._save_cache(symbol, timeframe, all_ohlcv)

            # Convert to Candle objects
            candles = self._ohlcv_to_candles(all_ohlcv)

            # Filter to date range
            candles = [c for c in candles if start_date <= c.timestamp <= end_date]

            logger.info(f"✅ Got {len(candles)} candles for {symbol} {timeframe}")
            return candles

        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return []

    @staticmethod
    def _ohlcv_to_candles(ohlcv: List[List]) -> List[Candle]:
        """Convert CCXT OHLCV format to Candle objects"""
        candles = []
        for ohlcv_item in ohlcv:
            timestamp = datetime.fromtimestamp(ohlcv_item[0] / 1000)
            candle = Candle(
                timestamp=timestamp,
                open=ohlcv_item[1],
                high=ohlcv_item[2],
                low=ohlcv_item[3],
                close=ohlcv_item[4],
                volume=ohlcv_item[5],
            )
            candles.append(candle)
        return candles

    def generate_mock_data(self, symbol: str, days: int = 180) -> Dict[str, List[Candle]]:
        """
        Generate realistic mock data for testing.
        Uses sine wave with noise to simulate price movement.
        """
        logger.info(f"📊 Generating {days} days of mock data for {symbol}")

        import random
        import math

        # Starting prices
        start_prices = {
            'BTCUSDT': 62500.0,
            'ETHUSDT': 1785.0,
            'BNBUSDT': 575.0,
        }

        base_price = start_prices.get(symbol, 100.0)
        current_price = base_price

        data_5min = []
        data_1hr = []
        data_4hr = []

        # Generate 5-min candles
        current_time = datetime.utcnow() - timedelta(days=days)
        end_time = datetime.utcnow()

        while current_time < end_time:
            # Realistic price movement
            # Trend: small random walk
            price_change = random.gauss(0, base_price * 0.0005)  # 0.05% std dev
            current_price = current_price * (1 + price_change / current_price)

            # Add some structure (fake momentum)
            days_elapsed = (current_time - (end_time - timedelta(days=days))).days
            trend = math.sin(days_elapsed / 30) * base_price * 0.05  # 5% trend
            current_price = current_price * (1 + trend / current_price * 0.001)

            # Create OHLCV for this candle
            open_price = current_price
            high_price = current_price * (1 + random.uniform(0, 0.005))  # 0-0.5% high
            low_price = current_price * (1 - random.uniform(0, 0.005))   # 0-0.5% low
            close_price = low_price + random.uniform(0, high_price - low_price)
            volume = random.uniform(50, 500)  # BTC or ETH equivalent

            candle_5min = Candle(
                timestamp=current_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )
            data_5min.append(candle_5min)

            current_time += timedelta(minutes=5)

        # Aggregate to 1-hour and 4-hour
        for i in range(0, len(data_5min), 12):  # 12 * 5min = 1 hour
            chunk = data_5min[i:i+12]
            if len(chunk) > 0:
                data_1hr.append(Candle(
                    timestamp=chunk[0].timestamp,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                ))

        for i in range(0, len(data_1hr), 4):  # 4 * 1hour = 4 hours
            chunk = data_1hr[i:i+4]
            if len(chunk) > 0:
                data_4hr.append(Candle(
                    timestamp=chunk[0].timestamp,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                ))

        logger.info(f"✅ Generated {len(data_5min)} 5-min, {len(data_1hr)} 1-hr, {len(data_4hr)} 4-hr candles")

        return {
            '5m': data_5min,
            '1h': data_1hr,
            '4h': data_4hr,
        }
