"""Entry signal generation and execution."""

import asyncio
import logging
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from backend.exchange.paper_trading import get_paper_trading
from backend.core.data_quality import get_data_quality_measurer
from backend.analytics.signal_explainer import get_signal_explainer
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
    """Calculate signal using GARP value strategy."""
    try:
        signal_explainer = get_signal_explainer()
        garp_result = apply_garp_value_strategy(symbol)

        if garp_result is None:
            return None

        garp_score, garp_reason = garp_result

        if signal_explainer:
            explanation = signal_explainer.explain_signal(symbol, garp_score, garp_reason)
            logger.debug(f"{symbol}: GARP explanation: {explanation}")

        return garp_score, garp_reason

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

        from . import validation
        is_valid, reason = await validation._validate_risk_before_order_impl(
            trader_self, signal.symbol, "BUY", 1.0, current_price
        )

        if not is_valid:
            logger.warning(f"{signal.symbol}: Risk validation failed: {reason}")
            return False

        position_size_pct = trader_self.config.position_size_pct / 100.0
        order_value = cash * position_size_pct
        quantity = order_value / current_price

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

        if result.get("success"):
            logger.info(
                f"✅ BUY {signal.symbol}: {quantity:.4f} @ ${current_price:.2f} - {signal.reason}"
            )
            return True
        else:
            logger.warning(f"❌ Buy order failed for {signal.symbol}: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Error executing entry for {signal.symbol}: {e}", exc_info=True)
        return False


async def _get_adaptive_entry_threshold_impl(trader_self: "AutonomousTrader", symbol: str) -> float:
    """Get adaptive entry threshold based on market conditions."""
    try:
        validator = get_price_validator()
        if not validator:
            return trader_self.config.entry_threshold

        base_threshold = trader_self.config.entry_threshold

        measurer = get_data_quality_measurer()
        if measurer:
            quality_score = measurer.overall_score
            if quality_score < 70:
                adjustment = (100 - quality_score) * 0.5
                return base_threshold + adjustment

        return base_threshold

    except Exception as e:
        logger.error(f"Error calculating adaptive threshold: {e}", exc_info=True)
        return trader_self.config.entry_threshold
