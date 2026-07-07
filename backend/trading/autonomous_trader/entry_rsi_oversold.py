"""RSI Oversold Mean Reversion Strategy with Phase 2 Confluence

Entry Logic (Phase 1):
1. Wait for 1h RSI > 40 (uptrend requirement)
2. Enter when 5m RSI dips to 30-65 range (mean reversion)
3. Exit at +2.0% profit or -0.5% stop loss

Phase 2 Confluence Filters (NEW):
1. MACD histogram > 0 (confirm uptrend with moving average crossover)
2. Volume > 20-period average (confirm conviction with volume)
3. Both gates required for high-confidence entries

This improves signal quality and reduces false breakouts.
"""

import logging
from typing import Optional, Tuple, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Simple technical indicators"""
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
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
    
    @staticmethod
    def sma(prices: List[float], period: int) -> float:
        """Calculate SMA"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0.0
        return sum(prices[-period:]) / period

    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """Calculate EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return TechnicalIndicators.sma(prices, len(prices))

        multiplier = 2.0 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = price * multiplier + ema * (1 - multiplier)
        return ema

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """Calculate MACD (fast EMA - slow EMA, signal line, histogram)"""
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0

        # Calculate EMAs
        fast_ema = TechnicalIndicators.ema(prices, fast)
        slow_ema = TechnicalIndicators.ema(prices, slow)
        macd_line = fast_ema - slow_ema

        # For signal line, we need to calculate EMA of MACD over recent values
        # Simplified: use last 9 MACD values or just return current MACD as signal
        signal_line = macd_line * 0.8  # Simplified signal (normally EMA of MACD line)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram


class RSIOversoldStrategy:
    """RSI Oversold mean reversion - simple & proven"""

    # Entry thresholds (very strong uptrend market: RSI 60-65)
    RSI_OVERSOLD_1H = 70      # No 1h filter (trade any market)
    RSI_RECOVERY_5M = 30      # 5m RSI above 30 = recovery zone
    RSI_MAX_5M = 65           # Allow entries up to RSI 65 (catch strong uptrend rallies)

    # Exit thresholds
    RSI_OVERBOUGHT_1H = 70    # Sell when 5m RSI > 40 (recovered)
    
    # Risk
    STOP_LOSS_PCT = 0.5       # -0.5% stop loss
    PROFIT_TARGET_PCT = 2.0   # +2.0% profit target
    
    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
        volumes_5min: Optional[List[float]] = None,
    ) -> Tuple[Optional[float], str]:
        """Generate entry signal with Phase 2 confluence filters (MACD + volume)"""

        if len(prices_5min) < 30 or len(prices_1hr) < 30:
            return None, "Insufficient price history"

        # Calculate RSI on both timeframes
        rsi_1h = TechnicalIndicators.rsi(prices_1hr)
        rsi_5m = TechnicalIndicators.rsi(prices_5min)

        current_price = prices_5min[-1]

        # TREND FILTER: Require uptrend confirmation (1h RSI > 40)
        if rsi_1h < 40:
            return None, f"1h RSI {rsi_1h:.0f} too weak (need strong uptrend, > 40)"

        # Entry: 5m RSI pullback (30-65) in uptrend
        if rsi_5m >= RSIOversoldStrategy.RSI_MAX_5M:
            return None, f"5m RSI {rsi_5m:.0f} too hot (need < {RSIOversoldStrategy.RSI_MAX_5M})"

        if rsi_5m < RSIOversoldStrategy.RSI_RECOVERY_5M:
            return None, f"5m RSI {rsi_5m:.0f} still falling (wait for recovery > {RSIOversoldStrategy.RSI_RECOVERY_5M})"

        # PHASE 2: MACD confirmation (uptrend consensus)
        macd_line, _, macd_histogram = TechnicalIndicators.macd(prices_1hr, fast=12, slow=26, signal=9)
        if macd_histogram <= 0:
            return None, f"MACD histogram {macd_histogram:.4f} < 0 (wait for uptrend confirmation)"

        # PHASE 2: Volume confirmation (conviction check)
        if volumes_5min and len(volumes_5min) >= 20:
            avg_volume = TechnicalIndicators.sma(volumes_5min, 20)
            current_volume = volumes_5min[-1]
            if current_volume < avg_volume:
                return None, f"Volume {current_volume:.0f} < avg {avg_volume:.0f} (need conviction confirmation)"

        # ALL CHECKS PASSED - Buy dips IN UPTRENDS with MACD + VOLUME confirmation
        strength = 50 + (40 - rsi_5m)  # Strength increases as 5m RSI dips lower
        strength = min(100, max(0, strength))

        reason = (
            f"UPTREND DIP + CONFLUENCE: 1h RSI {rsi_1h:.0f} strong, 5m RSI {rsi_5m:.0f} dipped, "
            f"MACD {macd_histogram:.4f} + Volume confirmed"
        )

        logger.info(f"✅ Phase 2 signal: {reason} (strength: {strength:.0f})")
        return strength, reason


async def _check_symbol_impl(trader_self, symbol: str) -> Optional:
    """Check if symbol should be bought using RSI oversold strategy."""
    if not trader_self.config.enabled:
        return None

    try:
        from backend.exchange.paper_trading import get_paper_trading

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

        # Fetch OHLCV data
        import time
        import ccxt.async_support as ccxt

        try:
            exchange = ccxt.binance()
            data_5min = await exchange.fetch_ohlcv(symbol, "5m", limit=100)
            data_1hr = await exchange.fetch_ohlcv(symbol, "1h", limit=100)
            await exchange.close()
        except Exception as e:
            logger.info(f"⚠️  {symbol}: Failed to fetch OHLCV: {str(e)[:80]}")
            return None

        if not data_5min or not data_1hr:
            logger.info(f"⚠️  {symbol}: Missing OHLCV data (5m: {len(data_5min) if data_5min else 0}, 1h: {len(data_1hr) if data_1hr else 0})")
            return None

        closes_5min = [c[4] for c in data_5min]
        closes_1hr = [c[4] for c in data_1hr]
        # Extract volumes: Binance OHLCV format [timestamp, open, high, low, close, volume, quote_asset_volume, ...]
        # Use quote_asset_volume (index 7) if available, fall back to volume (index 5)
        try:
            volumes_5min = [c[7] for c in data_5min] if (data_5min and len(data_5min[0]) > 7) else [c[5] for c in data_5min]
        except (IndexError, TypeError):
            volumes_5min = [c[5] for c in data_5min] if data_5min else []

        signal_strength, reason = RSIOversoldStrategy.calculate_signal(
            closes_5min, closes_1hr, volumes_5min
        )

        if signal_strength is None:
            logger.info(f"⚠️  {symbol}: {reason}")
            return None

        logger.info(f"✅ Signal generated for {symbol}: {reason} (strength: {signal_strength:.0f})")

        # Skip metrics recording (causing timezone errors) - focus on core execution
        # Metrics can be recorded after we confirm trades execute

        from .core import TradeSignal
        return TradeSignal(
            symbol=symbol,
            side="BUY",
            strength=signal_strength,
            reason=f"{reason} (strength: {signal_strength:.0f})",
            timestamp=None,  # Let TradeSignal use current time
        )

    except Exception as e:
        logger.error(f"Error checking {symbol}: {e}")
        return None


async def _execute_entry_impl(trader_self, signal) -> bool:
    """Execute a buy order for RSI dip signal."""
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.exchange.binance_stream import get_stream_client
        from backend.exchange.order_response import validate_order_response
        from backend.core.alerting import get_alert_manager

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

                # Record trade execution for monitoring
                metrics = get_metrics_collector()
                metrics.record_trade(
                    symbol=signal.symbol,
                    side='BUY',
                    entry_price=current_price,
                    quantity=quantity,
                )

                alert_mgr = get_alert_manager()
                new_account = engine.get_account_state()
                new_cash = new_account.get("cash", 0.0)

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
