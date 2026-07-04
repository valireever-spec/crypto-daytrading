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
    """Trend-following signal with 5 entry conditions"""

    EMA5_PERIOD = 5
    EMA20_PERIOD = 20
    RSI_PERIOD = 14
    VOLUME_AVG_PERIOD = 20
    ENTRY_THRESHOLD = 50
    SIGNAL_BASE_SCORE = 50
    RSI_OVERBOUGHT = 70

    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
        prices_4hr: List[float],
        volumes_5min: List[float],
    ) -> Tuple[Optional[float], str]:
        """
        Calculate signal strength (0-100) using 5 entry conditions.
        Returns (strength, reason) or (None, reason) if no signal.
        """

        if len(prices_5min) < 20 or len(prices_1hr) < 20 or len(prices_4hr) < 20:
            return None, "Insufficient price history"

        current_price = prices_5min[-1]

        # Condition 1: Trend Filter (4-hour) - Price > EMA20_4hr
        ema20_4hr = Indicators.ema(prices_4hr, SignalCalculator.EMA20_PERIOD)
        if current_price <= ema20_4hr:
            return None, f"Trend DOWN: price {current_price:.2f} < EMA20_4hr {ema20_4hr:.2f}"

        # Condition 2: Momentum Filter (1-hour) - EMA5 > EMA20
        ema5_1hr = Indicators.ema(prices_1hr, SignalCalculator.EMA5_PERIOD)
        ema20_1hr = Indicators.ema(prices_1hr, SignalCalculator.EMA20_PERIOD)
        if ema5_1hr <= ema20_1hr:
            return None, f"Momentum DOWN: EMA5_1hr {ema5_1hr:.2f} <= EMA20_1hr {ema20_1hr:.2f}"

        # Condition 3: Entry Signal (5-min breakout) - Close > High5
        high5_5min = max(prices_5min[-5:]) if len(prices_5min) >= 5 else prices_5min[-1]
        if current_price <= high5_5min:
            return None, f"No breakout: close {current_price:.2f} <= high5 {high5_5min:.2f}"

        # Condition 4: Volume Confirmation - Volume > 1.5x average
        current_volume = volumes_5min[-1]
        avg_volume_20 = sum(volumes_5min[-20:]) / 20 if len(volumes_5min) >= 20 else current_volume
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
        if volume_ratio < 1.5:
            return None, f"Low volume: {volume_ratio:.2f}x < 1.5x"

        # Condition 5: Overbought Filter (RSI) - RSI < 70
        rsi_5min = Indicators.rsi(prices_5min, SignalCalculator.RSI_PERIOD)
        if rsi_5min >= SignalCalculator.RSI_OVERBOUGHT:
            return None, f"Overbought: RSI {rsi_5min:.0f} >= 70"

        # ALL CONDITIONS MET - Calculate signal strength
        signal_strength = SignalCalculator.SIGNAL_BASE_SCORE
        bonuses = []

        # Bonus 1: Strong momentum
        momentum_distance = ((ema5_1hr - ema20_1hr) / ema20_1hr) * 100 if ema20_1hr > 0 else 0
        if momentum_distance > 0.5:
            signal_strength += 15
            bonuses.append(f"momentum +{momentum_distance:.2f}%")

        # Bonus 2: Volume surge
        if volume_ratio > 2.0:
            signal_strength += 10
            bonuses.append(f"volume {volume_ratio:.1f}x")

        # Bonus 3: RSI room to run
        if rsi_5min < 50:
            signal_strength += 10
            bonuses.append(f"RSI {rsi_5min:.0f}")

        # Bonus 4: 5-min uptrend
        ema5_5min = Indicators.ema(prices_5min, SignalCalculator.EMA5_PERIOD)
        if current_price > ema5_5min:
            signal_strength += 5
            bonuses.append("5-min uptrend")

        signal_strength = min(signal_strength, 100.0)

        bonus_text = ", ".join(bonuses) if bonuses else ""
        reason = f"Breakout w/ {bonus_text}" if bonus_text else "Breakout signal"

        if signal_strength >= SignalCalculator.ENTRY_THRESHOLD:
            return signal_strength, reason
        else:
            return None, f"Signal weak: {signal_strength:.0f} < {SignalCalculator.ENTRY_THRESHOLD}"


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
