"""Entry signal generation and execution."""

import asyncio
import logging
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.order_response import validate_order_response
from backend.core.data_quality import get_data_quality_measurer
from backend.analytics.signal_explainer import get_signal_explainer
from backend.analytics.regime_detector import get_regime_detector
from backend.strategies.garp_value_strategy import apply_garp_value_strategy
from backend.execution.smart_executor import get_smart_executor
from backend.core.data_validator import get_price_validator

if TYPE_CHECKING:
    from .core import AutonomousTrader, TradeSignal

logger = logging.getLogger(__name__)

_signal_thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="signal_calc")


async def _check_symbol_impl(trader_self: "AutonomousTrader", symbol: str) -> Optional["TradeSignal"]:
    """Check if a symbol should be bought."""
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

        signal = await _calculate_signal_impl(trader_self, symbol)

        if signal is None:
            return None

        signal_strength, reason = signal
        threshold = await _get_adaptive_entry_threshold_impl(trader_self, symbol)

        if signal_strength < threshold:
            logger.debug(
                f"{symbol}: Signal too weak ({signal_strength:.0f} < {threshold:.0f}): {reason}"
            )
            return None

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


async def _calculate_signal_impl(trader_self: "AutonomousTrader", symbol: str) -> Optional[tuple]:
    """Calculate signal using real Binance data (mean reversion + momentum)."""
    try:
        from backend.exchange.binance_stream import get_stream_client

        stream_client = get_stream_client()
        if not stream_client:
            return None

        # Get recent price data for momentum calculation
        price_history = stream_client.price_history.get(symbol, [])
        if len(price_history) < 5:
            logger.debug(f"{symbol}: Insufficient price history ({len(price_history)} < 5)")
            return None

        # Calculate momentum: compare recent prices
        prices = [p["price"] for p in price_history[-10:]]  # Last 10 samples
        momentum_pct = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0

        # Calculate volatility (simple: recent price range as % of mean)
        recent_prices = prices[-5:]
        price_mean = sum(recent_prices) / len(recent_prices)
        price_range = max(recent_prices) - min(recent_prices)
        volatility_pct = (price_range / price_mean) * 100 if price_mean != 0 else 0

        # Mean reversion signal: buy when price is below moving average
        sma_5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else prices[-1]
        current_price = prices[-1]
        distance_from_ma_pct = ((current_price - sma_5) / sma_5) * 100 if sma_5 != 0 else 0

        # Calculate signal strength (0-100)
        # High signal: price below MA (mean reversion) + moderate volatility
        signal_strength = 0.0

        if distance_from_ma_pct < -0.5:
            # Price is below 5-min MA - mean reversion opportunity
            signal_strength += 40
            reason = f"Mean reversion: price {distance_from_ma_pct:.2f}% below MA5"

            # Boost if momentum is positive (recovering)
            if momentum_pct > 0:
                signal_strength += 20
                reason += f", momentum +{momentum_pct:.2f}%"

            # Reduce if volatility too high (avoid noise)
            if volatility_pct > 2.0:
                signal_strength -= 10
                reason += f", high volatility {volatility_pct:.2f}%"

        else:
            # Price not in mean reversion zone, use weak momentum signal
            if momentum_pct > 0.1:
                signal_strength = 35 + (momentum_pct * 5)  # Scale 0-35 + momentum
                reason = f"Weak momentum: +{momentum_pct:.2f}%"
            else:
                reason = f"No signal: price above MA, momentum {momentum_pct:.2f}%"

        # Cap at 100
        signal_strength = min(signal_strength, 100.0)
        entry_threshold = trader_self.config.entry_threshold

        # Return signal if above threshold
        if signal_strength >= entry_threshold:
            logger.debug(f"{symbol}: {reason} (signal {signal_strength:.0f} >= threshold {entry_threshold})")
            return signal_strength, reason
        else:
            logger.debug(f"{symbol}: {reason} (signal {signal_strength:.0f} < threshold {entry_threshold})")
            return None

    except Exception as e:
        logger.error(f"Error calculating signal for {symbol}: {e}", exc_info=True)
        return None


async def _execute_entry_impl(trader_self: "AutonomousTrader", signal: "TradeSignal") -> bool:
    """Execute a buy order."""
    try:
        engine = get_paper_trading()
        if not engine:
            logger.error("Paper trading engine not initialized")
            return False

        account = engine.get_account_state()
        cash = account.get("cash", 0.0)

        from backend.exchange.binance_stream import get_stream_client
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

        # ✅ BUG FIX #3: Check position size limit (prevent unbounded accumulation)
        # Max 10% of account per single position (prevents -$5,419 overexposure)
        max_position_pct = 10.0
        max_position_value = cash * (max_position_pct / 100.0)

        # Check existing position for this symbol
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
                f"🚫 POSITION LIMIT ENFORCED: {signal.symbol} entry blocked\n"
                f"   Current position: ${current_position_value:.2f}\n"
                f"   New order would add: ${new_position_value:.2f}\n"
                f"   Total would be: ${total_position_value:.2f}\n"
                f"   Maximum allowed: ${max_position_value:.2f} ({max_position_pct}% of ${cash:.2f})"
            )
            return False

        from . import validation
        is_valid, reason = await validation._validate_risk_before_order_impl(
            trader_self, signal.symbol, "BUY", quantity, current_price
        )

        if not is_valid:
            logger.warning(f"{signal.symbol}: Risk validation failed: {reason}")
            return False

        smart_executor = get_smart_executor()
        if not smart_executor:
            logger.error("Smart executor not initialized")
            return False

        result = await engine.place_order(
            symbol=signal.symbol,
            side="BUY",
            quantity=round(quantity, 4),
            current_price=current_price,
        )

        try:
            # Validate response against OrderResponse schema
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


async def _get_adaptive_entry_threshold_impl(trader_self: "AutonomousTrader", symbol: str) -> float:
    """Get adaptive entry threshold based on market conditions."""
    try:
        base_threshold = trader_self.config.entry_threshold
        return base_threshold

    except Exception as e:
        logger.error(f"Error calculating adaptive threshold: {e}", exc_info=True)
        return trader_self.config.entry_threshold
