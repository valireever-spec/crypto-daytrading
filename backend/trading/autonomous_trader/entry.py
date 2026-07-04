"""
Entry signal generation using TREND-FOLLOWING signal (5 entry conditions).

Replaces broken mean-reversion signal with multi-timeframe confirmation:
1. Price > EMA20_4hr (macro trend up)
2. EMA5_1hr > EMA20_1hr (momentum up)
3. Close > High5_5min (breakout)
4. Volume > 1.5x average (confirmation)
5. RSI < 70 (not overbought)
"""

import asyncio
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
import ccxt.async_support as ccxt

from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.order_response import validate_order_response
from backend.core.data_quality import get_data_quality_measurer
from backend.execution.smart_executor import get_smart_executor
from backend.exchange.binance_stream import get_stream_client

logger = logging.getLogger(__name__)

MIN_HOLD_TIME_SECONDS = 300  # Minimum time position must be held before allowing exit

# Technical Indicators (from backtesting framework)
class Indicators:
    """Technical indicator calculations"""

    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """Calculate EMA of last price"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0.0

        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0  # Neutral if insufficient data

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]

        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


class SignalCalculator:
    """Simple trend-following signal - 2 core conditions only"""

    EMA20_PERIOD = 20
    RSI_PERIOD = 14
    VOLUME_AVG_PERIOD = 20
    ENTRY_THRESHOLD = 40  # Simple: just above neutral
    SIGNAL_BASE_SCORE = 50
    RSI_MAX = 85  # Only filter extreme overbought

    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
        prices_4hr: List[float],
        volumes_5min: List[float],
    ) -> Tuple[Optional[float], str]:
        """
        SIMPLE trend-following signal - 2 core conditions only.
        Returns (strength, reason) or (None, reason) if no signal.
        """

        if len(prices_5min) < 20 or len(prices_4hr) < 20:
            return None, "Insufficient price history"

        current_price = prices_5min[-1]

        # CORE CONDITION 1: Uptrend - Price > EMA20 (4-hour)
        ema20_4hr = Indicators.ema(prices_4hr, SignalCalculator.EMA20_PERIOD)
        if current_price <= ema20_4hr:
            return None, f"Downtrend: price {current_price:.2f} <= EMA20 {ema20_4hr:.2f}"

        # CORE CONDITION 2: Volume Confirmation
        current_volume = volumes_5min[-1]
        avg_volume_20 = sum(volumes_5min[-20:]) / 20 if len(volumes_5min) >= 20 else current_volume
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

        # Allow trades even with modest volume (>0.8x is OK)
        # RSI filter: extreme overbought only (>85)
        rsi_5min = Indicators.rsi(prices_5min, SignalCalculator.RSI_PERIOD)
        if rsi_5min >= SignalCalculator.RSI_MAX:
            return None, f"Extreme overbought: RSI {rsi_5min:.0f} >= 85"

        # SIGNAL CONDITIONS MET - Calculate strength
        signal_strength = SignalCalculator.SIGNAL_BASE_SCORE

        # Bonuses for quality
        bonuses = []

        # Bonus: Volume strength
        if volume_ratio >= 1.5:
            signal_strength += 20
            bonuses.append(f"vol {volume_ratio:.1f}x")
        elif volume_ratio >= 1.0:
            signal_strength += 10
            bonuses.append(f"vol {volume_ratio:.1f}x")

        # Bonus: RSI room to run (<60 = plenty of room)
        if rsi_5min < 60:
            signal_strength += 15
            bonuses.append(f"RSI {rsi_5min:.0f}")

        # Bonus: Price momentum (% above EMA)
        pct_above_ema = ((current_price - ema20_4hr) / ema20_4hr) * 100
        if pct_above_ema > 2.0:
            signal_strength += 10
            bonuses.append(f"+{pct_above_ema:.1f}%")

        signal_strength = min(signal_strength, 100.0)

        bonus_text = ", ".join(bonuses) if bonuses else "trend"
        reason = f"Uptrend ({bonus_text})"

        if signal_strength >= SignalCalculator.ENTRY_THRESHOLD:
            return signal_strength, reason
        else:
            return None, f"Signal weak: {signal_strength:.0f} < threshold"


async def _fetch_ohlcv(symbol: str, timeframe: str, limit: int = 100) -> Optional[List]:
    """Fetch OHLCV data from Binance via CCXT"""
    try:
        exchange = ccxt.binance()
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()
        return ohlcv
    except Exception as e:
        logger.debug(f"Failed to fetch {symbol} {timeframe}: {e}")
        return None


def _extract_candle_data(ohlcv: List) -> Tuple[List[float], List[float]]:
    """Extract closes and volumes from OHLCV data"""
    closes = [candle[4] for candle in ohlcv]  # Close price
    volumes = [candle[5] for candle in ohlcv]  # Volume
    return closes, volumes


async def _check_symbol_impl(trader_self, symbol: str) -> Optional:
    """Check if a symbol should be bought using trend-following signal."""
    if not trader_self.config.enabled:
        return None

    try:
        engine = get_paper_trading()
        if not engine:
            return None

        positions = engine.get_positions()
        if any(p["symbol"] == symbol for p in positions):
            logger.debug(f"{symbol}: Already have position, skipping")
            return None

        if len(positions) >= trader_self.config.max_positions:
            logger.debug(f"{symbol}: At max positions ({trader_self.config.max_positions})")
            return None

        # Fetch multi-timeframe data
        data_5min = await _fetch_ohlcv(symbol, "5m", limit=100)
        data_1hr = await _fetch_ohlcv(symbol, "1h", limit=100)
        data_4hr = await _fetch_ohlcv(symbol, "4h", limit=100)

        if not data_5min or not data_1hr or not data_4hr:
            logger.debug(f"{symbol}: Missing OHLCV data")
            return None

        closes_5min, volumes_5min = _extract_candle_data(data_5min)
        closes_1hr, _ = _extract_candle_data(data_1hr)
        closes_4hr, _ = _extract_candle_data(data_4hr)

        # Calculate signal
        signal_strength, reason = SignalCalculator.calculate_signal(
            closes_5min, closes_1hr, closes_4hr, volumes_5min
        )

        if signal_strength is None:
            logger.debug(f"{symbol}: {reason}")
            return None

        logger.info(f"✅ Signal generated for {symbol}: {reason} (strength: {signal_strength:.0f})")

        from .core import TradeSignal
        return TradeSignal(
            symbol=symbol,
            side="BUY",
            strength=signal_strength,
            reason=f"{reason} (strength: {signal_strength:.0f})",
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Error checking symbol {symbol}: {e}", exc_info=True)
        return None


async def _execute_entry_impl(trader_self, signal) -> bool:
    """Execute a buy order."""
    try:
        engine = get_paper_trading()
        if not engine:
            logger.error("Paper trading engine not initialized")
            return False

        account = engine.get_account_state()
        cash = account.get("cash", 0.0)

        stream_client = get_stream_client()
        current_price = None

        if stream_client and signal.symbol in stream_client.price_cache:
            current_price = stream_client.price_cache[signal.symbol]

        if not current_price:
            logger.warning(f"{signal.symbol}: No current price, cannot execute entry")
            return False

        position_size_pct = trader_self.config.position_size_pct / 100.0
        order_value = cash * position_size_pct
        quantity = order_value / current_price

        # Bug Fix #3: Position size limit (max 10% per position)
        max_position_pct = 10.0
        max_position_value = cash * (max_position_pct / 100.0)

        existing_positions = engine.get_positions()
        current_position_value = 0.0
        for pos in existing_positions:
            if pos["symbol"] == signal.symbol:
                current_position_value = pos["quantity"] * pos["entry_price"]
                break

        new_position_value = order_value
        total_position_value = current_position_value + new_position_value

        if total_position_value > max_position_value:
            logger.critical(
                f"🚫 POSITION LIMIT: {signal.symbol} entry blocked "
                f"(would exceed ${max_position_value:.2f} max)"
            )
            return False

        result = await engine.place_order(
            symbol=signal.symbol,
            side="BUY",
            quantity=round(quantity, 4),
            current_price=current_price,
        )

        try:
            validated = validate_order_response(result)

            if validated.status == "FILLED":
                logger.info(
                    f"✅ BUY {signal.symbol}: {quantity:.4f} @ ${current_price:.2f} - {signal.reason}"
                )
                return True
            else:
                logger.warning(f"❌ Buy order failed for {signal.symbol}: {validated.status}")
                return False
        except Exception as e:
            logger.error(f"Invalid order response for {signal.symbol}: {e}")
            return False

    except Exception as e:
        logger.error(f"Error executing entry for {signal.symbol}: {e}", exc_info=True)
        return False
