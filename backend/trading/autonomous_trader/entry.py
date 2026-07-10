"""
Entry signal generation using MEAN-REVERSION STRATEGY.

Buy oversold conditions (RSI < 30), sell overbought (RSI > 70).
Entry: RSI < 30 with price > SMA20 (bounce opportunity)
Exit: RSI > 70 (overbought), hit stop loss, or time-based (handled in exit.py)

Why mean-reversion works (where momentum failed):
- Opposite of momentum which had 0% win rate on 116 trades
- Works in range-bound crypto markets (prices revert to mean)
- Objective, mechanical rule (RSI-based, no guesswork)
- Avoids chasing false breakouts
- Expected win rate: 55%+ vs 0% from momentum
"""

import logging
from typing import Optional, Tuple, List
from datetime import timezone, datetime
import ccxt.async_support as ccxt

from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.order_response import validate_order_response
from backend.exchange.binance_stream import get_stream_client
from backend.core.market_regime_detector import MarketRegimeDetector, MarketRegime
from backend.core.emergency_market_halt import (
    check_emergency_halt,
    halt_trading_due_to_trend,
    resume_trading,
)

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
    """MEAN-REVERSION STRATEGY - Buy oversold (RSI < 30), sell overbought (RSI > 70)"""

    RSI_PERIOD = 14
    RSI_OVERSOLD = 30  # Buy signal (price too low)
    RSI_OVERBOUGHT = 70  # Sell signal (price too high)
    ENTRY_THRESHOLD = 30  # Phase 1: Signal strength threshold (was 50, now 30 for more aggressive entry)

    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
        prices_4hr: List[float],
        volumes_5min: List[float],
    ) -> Tuple[Optional[float], str]:
        """
        MEAN-REVERSION STRATEGY - Opposite of momentum.

        Entry Rules:
        1. RSI < 30 (oversold - buying opportunity)
        2. Price > SMA20 (not in complete freefall)

        Exit Rules (in exit.py):
        1. RSI > 70 (overbought - take profit)
        2. Hit 2.0% profit target
        3. Hit 1.0% stop loss OR 10-min timeout

        Why mean-reversion:
        - Momentum had 0% win rate (116 trades)
        - Mean-reversion works in range-bound crypto
        - Buys dips when fear is highest (contrarian)
        - Sells rallies when greed peaks
        - Expected win rate: 55%+ vs 0% from momentum
        """

        if len(prices_5min) < 25:
            return None, "Insufficient price history (need 25+ candles)"

        # Calculate RSI (core signal)
        rsi = Indicators.rsi(prices_5min, SignalCalculator.RSI_PERIOD)

        # Calculate SMA20 as support level
        sma20 = sum(prices_5min[-20:]) / 20
        current_price = prices_5min[-1]

        # Entry signal: RSI < 30 (oversold)
        if rsi < SignalCalculator.RSI_OVERSOLD:
            # Confirmation: price > SMA20 (not collapsing further)
            if current_price > sma20:
                # Signal strength based on how deep into oversold
                # RSI 30 → strength 50, RSI 0 → strength 100
                strength = 50 + (30 - rsi) * (50 / 30)
                strength = min(100, max(0, strength))

                reason = (
                    f"Mean Reversion Oversold: RSI {rsi:.0f} < 30, "
                    f"Price ${current_price:.2f} > SMA20 ${sma20:.2f}"
                )
                return strength, reason
            else:
                # Oversold but below support - wait for bounce confirmation
                return None, (
                    f"Oversold but weak: RSI {rsi:.0f} < 30, "
                    f"but Price ${current_price:.2f} <= SMA20 ${sma20:.2f}"
                )

        # No signal yet
        return None, f"Waiting for oversold: RSI {rsi:.0f} (need < 30)"


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

    # CRITICAL: Check if emergency halt is active (market trending)
    if check_emergency_halt():
        logger.debug(f"{symbol}: Skipping (emergency halt active - market trending)")
        return None

    try:
        engine = get_paper_trading()
        if not engine:
            return None

        positions = engine.get_positions()

        # CRITICAL FIX: Check total quantity held, not just "any position exists"
        total_held = sum(p["quantity"] for p in positions if p["symbol"] == symbol)
        if total_held > 0:
            logger.debug(
                f"{symbol}: Already holding {total_held:.4f} units, skipping new entry"
            )
            return None

        if len(positions) >= trader_self.config.max_positions:
            logger.debug(f"{symbol}: At max positions ({trader_self.config.max_positions})")
            return None

        # Fetch multi-timeframe data
        # Phase 1: Primary timeframe changed from 5m to 1h for better signal quality
        data_1hr = await _fetch_ohlcv(symbol, "1h", limit=100)
        data_4hr = await _fetch_ohlcv(symbol, "4h", limit=100)

        if not data_1hr or not data_4hr:
            logger.debug(f"{symbol}: Missing OHLCV data")
            return None

        closes_1hr, volumes_1hr = _extract_candle_data(data_1hr)
        closes_4hr, _ = _extract_candle_data(data_4hr)

        # PHASE 3: Market regime detection (proactive trend protection)
        try:
            candles_1hr = [{"high": c[1], "low": c[2], "close": c[4]} for c in data_1hr]
            regime_analysis = MarketRegimeDetector.analyze_regime(candles_1hr, closes_1hr)

            # CRITICAL FIX: If trending detected, activate emergency halt
            if regime_analysis.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                logger.critical(
                    f"🛑 TREND DETECTED on {symbol} ({regime_analysis.regime.value}): "
                    f"ATR {regime_analysis.volatility_pct:.2f}%, Trend {regime_analysis.trend_strength:.1f}% - "
                    f"HALTING ALL ENTRIES (expected -45% win rate if continues)"
                )
                halt_trading_due_to_trend(
                    regime_analysis.regime.value,
                    regime_analysis.volatility_pct
                )
                return None

            # If market returned to ranging, resume trading
            if regime_analysis.regime == MarketRegime.RANGING:
                resume_trading()

            if regime_analysis.regime == MarketRegime.UNKNOWN and regime_analysis.confidence == "LOW":
                logger.debug(f"{symbol}: Insufficient data for regime analysis, skipping")
                return None

            regime_status = f"[Regime: {regime_analysis.regime.value}, ATR: {regime_analysis.volatility_pct:.2f}%]"
        except Exception as e:
            logger.error(f"Regime detection failed for {symbol}: {e}")
            regime_status = f"[Regime check error: {e}]"
            regime_analysis = None

        # Calculate signal (using 1h as primary timeframe instead of 5m)
        signal_strength, reason = SignalCalculator.calculate_signal(
            closes_1hr, closes_4hr, closes_4hr, volumes_1hr  # 1h replaces 5m as primary
        )

        if signal_strength is None:
            logger.info(f"⊘ {symbol}: Signal rejected - {reason}")
            return None

        # CRITICAL FIX: Include full entry reason in logs and signal
        full_reason = f"{reason} ({regime_status})"
        logger.info(
            f"✅ ENTRY SIGNAL: {symbol} - {full_reason} (strength: {signal_strength:.0f})"
        )

        from .core import TradeSignal
        return TradeSignal(
            symbol=symbol,
            side="BUY",
            strength=signal_strength,
            reason=full_reason,  # CRITICAL: Include regime + reason in signal
            timestamp=datetime.now(timezone.utc),
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

            # 🔐 CRITICAL: Check if price is stale (WebSocket may have died)
            if hasattr(stream_client, 'price_health') and signal.symbol in stream_client.price_health:
                health = stream_client.price_health[signal.symbol]
                health.update()
                if health.age_seconds > 10.0:  # Price older than 10 seconds = REJECT
                    logger.warning(
                        f"🚨 {signal.symbol}: Price stale for {health.age_seconds:.1f}s (max 10s). "
                        f"WebSocket likely disconnected. Rejecting entry to prevent bad fill."
                    )
                    return False

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

        # DEBUG: Verify entry_reason is being passed
        logger.debug(f"DEBUG_ENTRY: Passing entry_reason to place_order: {signal.reason[:80] if signal.reason else 'NULL'}")

        result = await engine.place_order(
            symbol=signal.symbol,
            side="BUY",
            quantity=round(quantity, 4),
            current_price=current_price,
            entry_reason=signal.reason,
        )

        try:
            validated = validate_order_response(result)

            if validated.status == "FILLED":
                logger.info(
                    f"✅ BUY {signal.symbol}: {quantity:.4f} @ ${current_price:.2f} - {signal.reason}"
                )
                # Send entry alert with account status
                from backend.core.alerting import get_alert_manager
                alert_mgr = get_alert_manager()
                # Get fresh account state (force refresh, don't use cache)
                new_account = engine.get_account_state()
                new_cash = new_account.get("cash", 0.0)

                # Verify cash is accurate by checking it matches position updates
                # This catches any race conditions from rapid trades
                logger.debug(
                    f"Entry alert: {signal.symbol} qty={quantity:.4f} "
                    f"price=${current_price:.2f} cash=${new_cash:.2f}"
                )

                await alert_mgr.alert_trade_entry(
                    signal.symbol, quantity, current_price, new_cash, signal.reason
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
