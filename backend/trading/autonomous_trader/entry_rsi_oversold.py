"""RSI Oversold Mean Reversion Strategy - Simple & Proven

Entry Logic:
1. Wait for RSI < 30 on 1-hour timeframe (oversold = weak, ready to bounce)
2. Enter when 5-min RSI starts recovering (mean reversion)
3. Exit at RSI > 70 on 1h (overbought, take profit) or -0.5% stop

This replaces the complex Bollinger Band + regime detection.
Simpler = easier to debug + fewer false signals.
"""

import logging
from typing import Optional, Tuple, List
from datetime import datetime

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


class RSIOversoldStrategy:
    """RSI Oversold mean reversion - simple & proven"""

    # Entry thresholds (aggressive: any 5m dip)
    RSI_OVERSOLD_1H = 70      # No 1h filter (trade any market)
    RSI_RECOVERY_5M = 20      # 5m RSI between 20-40 = dip zone
    RSI_MAX_5M = 40           # Don't enter if 5m already hot

    # Exit thresholds
    RSI_OVERBOUGHT_1H = 70    # Sell when 5m RSI > 40 (recovered)
    
    # Risk
    STOP_LOSS_PCT = 0.5       # -0.5% stop loss
    PROFIT_TARGET_PCT = 2.0   # +2.0% profit target
    
    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
    ) -> Tuple[Optional[float], str]:
        """Generate entry signal based on RSI oversold on 1h + recovery on 5m"""
        
        if len(prices_5min) < 30 or len(prices_1hr) < 30:
            return None, "Insufficient price history"
        
        # Calculate RSI on both timeframes
        rsi_1h = TechnicalIndicators.rsi(prices_1hr)
        rsi_5m = TechnicalIndicators.rsi(prices_5min)

        current_price = prices_5min[-1]

        # TREND FILTER: Allow neutral/weak markets (1h RSI > 30)
        # Prevents entry only in severe downtrends (RSI < 30), allows ranging/consolidation
        if rsi_1h < 30:
            return None, f"1h RSI {rsi_1h:.0f} too weak (severe downtrend, need > 30)"

        # Entry: 5m RSI dipped (< 40) and starting to recover (> 20)
        # Only triggered when market is already in uptrend (1h RSI > 50)
        if rsi_5m >= RSIOversoldStrategy.RSI_MAX_5M:
            return None, f"5m RSI {rsi_5m:.0f} too hot (need < {RSIOversoldStrategy.RSI_MAX_5M})"

        if rsi_5m < RSIOversoldStrategy.RSI_RECOVERY_5M:
            return None, f"5m RSI {rsi_5m:.0f} still falling (wait for recovery > {RSIOversoldStrategy.RSI_RECOVERY_5M})"

        # ALL CHECKS PASSED - Buy dips IN UPTRENDS
        strength = 50 + (40 - rsi_5m)  # Strength increases as 5m RSI dips lower
        strength = min(100, max(0, strength))

        reason = (
            f"UPTREND DIP: 1h RSI {rsi_1h:.0f} strong, 5m RSI {rsi_5m:.0f} dipped, "
            f"buying weakness in uptrend"
        )
        
        logger.info(f"✅ RSI oversold signal: {reason} (strength: {strength:.0f})")
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

        signal_strength, reason = RSIOversoldStrategy.calculate_signal(
            closes_5min, closes_1hr
        )

        if signal_strength is None:
            logger.info(f"⚠️  {symbol}: {reason}")
            return None

        logger.info(f"✅ Signal generated for {symbol}: {reason} (strength: {signal_strength:.0f})")

        # Record metrics
        from backend.core.trading_metrics import get_metrics_collector
        from backend.core.parameter_monitor import get_parameter_monitor

        metrics = get_metrics_collector()
        param_monitor = get_parameter_monitor()

        rsi_1h = TechnicalIndicators.rsi(closes_1hr)
        rsi_5m = TechnicalIndicators.rsi(closes_5min)

        metrics.record_signal(
            symbol=symbol,
            regime="oversold",
            entry_reason=reason,
            filters_passed={'rsi_1h_oversold': rsi_1h < 30, 'rsi_5m_recovering': rsi_5m >= 20},
            rsi_5m=rsi_5m,
            rsi_1h=rsi_1h,
            bb_width_pct=0,  # Not used in this strategy
            macd_histogram=0,  # Not used in this strategy
            volume_ratio=1.0,  # Not used in this strategy
            signal_strength=signal_strength,
            decision='ENTER'
        )

        # Record to parameter monitor
        param_monitor.record_signal(
            symbol=symbol,
            regime="oversold",
            rsi_1h=rsi_1h,
            rsi_5m=rsi_5m,
            trend_filter_passed=(rsi_1h > 50),
            signal_strength=signal_strength,
            entry_reason=reason
        )

        # Track entry reason
        param_monitor.record_entry_reason(reason)

        from .core import TradeSignal
        return TradeSignal(
            symbol=symbol,
            side="BUY",
            strength=signal_strength,
            reason=f"{reason} (strength: {signal_strength:.0f})",
            timestamp=datetime.utcnow(),
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
