"""Exit signal generation (stop loss, profit target)."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict

from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.order_response import validate_order_response
from backend.execution.smart_executor import get_smart_executor
from backend.core.fragility_circuit_breaker import get_fragility_breaker

if TYPE_CHECKING:
    from .core import AutonomousTrader

logger = logging.getLogger(__name__)

MIN_HOLD_TIME_SECONDS = 300  # Minimum time position must be held before allowing exit (5 minutes)


async def _check_exits_impl(trader_self: "AutonomousTrader"):
    """Check existing positions for exits (stop loss, profit target)."""
    try:
        engine = get_paper_trading()
        if not engine:
            return

        positions = engine.get_positions()
        if not positions:
            return

        from backend.exchange.binance_stream import get_stream_client

        stream_client = get_stream_client()
        if not stream_client:
            return

        for position in positions:
            symbol = position["symbol"]

            # DEFENSIVE: Validate position has required metadata
            entry_time = position.get("entry_time")
            if not entry_time:
                logger.warning(
                    f"⚠️ {symbol}: Position missing entry_time metadata. "
                    f"Position: {position}. This indicates data corruption upstream."
                )
                # Report to fragility circuit breaker
                breaker = get_fragility_breaker()
                breaker.check_exit_failure(f"Missing entry_time for {symbol}")
                continue  # Skip this position, don't crash

            # ✅ BUG FIX #1: Check minimum hold time FIRST (prevents 5-10 second exits)
            hold_time = 0  # Initialize to 0 (safety fallback)
            if entry_time:
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                hold_time = (datetime.utcnow() - entry_time).total_seconds()

                if hold_time < MIN_HOLD_TIME_SECONDS:
                    logger.info(
                        f"⏳ {symbol}: Position held {hold_time:.1f}s, minimum hold time {MIN_HOLD_TIME_SECONDS}s not yet reached. Skipping exit check."
                    )
                    continue

            # ✅ GUARDRAIL: Force exit positions held >10 minutes (prevent black swan overnight risk)
            MAX_HOLD_TIME_SECONDS = 600  # 10 minutes
            if hold_time > 0 and hold_time >= MAX_HOLD_TIME_SECONDS:
                logger.critical(
                    f"🔴 FORCED EXIT (10-min timeout): {symbol} held {hold_time:.1f}s >= {MAX_HOLD_TIME_SECONDS}s. Closing position."
                )
                current_price = stream_client.price_cache.get(symbol)
                if current_price:
                    await _execute_exit_impl(trader_self, position, current_price, "10-minute timeout")
                continue

            current_price = stream_client.price_cache.get(symbol)

            if not current_price:
                continue

            entry_price = position["entry_price"]
            quantity = position["quantity"]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            if pnl_pct >= trader_self.config.exit_profit_target:
                logger.info(
                    f"✅ PROFIT TARGET HIT {symbol}: {pnl_pct:.2f}% >= "
                    f"{trader_self.config.exit_profit_target:.1f}%"
                )
                await _execute_exit_impl(
                    trader_self, position, current_price, "Profit target"
                )
                # Alert on profit with account status
                from backend.core.alerting import get_alert_manager
                alert_mgr = get_alert_manager()
                engine = get_paper_trading()
                if engine:
                    account = engine.get_account_state()
                    remaining_cash = account.get("cash", 0.0)
                    realized_pnl = position["quantity"] * (current_price - position["entry_price"])
                    await alert_mgr.alert_trade_exit(
                        symbol, realized_pnl, pnl_pct, remaining_cash, hold_time, is_win=True
                    )

            elif pnl_pct <= -trader_self.config.exit_stop_loss:
                logger.warning(
                    f"🛑 STOP LOSS HIT {symbol}: {pnl_pct:.2f}% <= "
                    f"-{trader_self.config.exit_stop_loss:.1f}%"
                )
                await _execute_exit_impl(
                    trader_self, position, current_price, "Stop loss"
                )
                # Alert on stop loss with account status
                from backend.core.alerting import get_alert_manager
                alert_mgr = get_alert_manager()
                engine = get_paper_trading()
                if engine:
                    account = engine.get_account_state()
                    remaining_cash = account.get("cash", 0.0)
                    realized_pnl = position["quantity"] * (current_price - position["entry_price"])
                    await alert_mgr.alert_trade_exit(
                        symbol, realized_pnl, pnl_pct, remaining_cash, hold_time, is_win=False
                    )

    except Exception as e:
        logger.error(f"Error checking exits: {e}", exc_info=True)
        # Report to fragility circuit breaker (Tier 2 safeguard)
        breaker = get_fragility_breaker()
        breaker.check_exit_failure(str(e))


async def _execute_exit_impl(
    trader_self: "AutonomousTrader",
    position: Dict,
    current_price: float,
    reason: str,
) -> bool:
    """Execute a sell order to close a position."""
    try:
        engine = get_paper_trading()
        if not engine:
            logger.error("Paper trading engine not initialized")
            return False

        symbol = position["symbol"]
        quantity = position["quantity"]

        smart_executor = get_smart_executor()
        if not smart_executor:
            logger.error("Smart executor not initialized")
            return False

        result = await engine.place_order(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            current_price=current_price,
        )

        try:
            # Validate response against OrderResponse schema
            validated = validate_order_response(result)

            if validated.status == "FILLED":
                realized_pnl = validated.realized_pnl or 0.0
                logger.info(
                    f"✅ SOLD {symbol}: {quantity:.4f} @ ${current_price:.2f} - {reason} - "
                    f"P&L: ${realized_pnl:.2f}"
                )
                return True
            else:
                logger.warning(
                    f"❌ Sell order failed for {symbol}: {validated.status}"
                )
                return False
        except Exception as e:
            logger.error(f"Invalid order response for {symbol}: {e}")
            return False

    except Exception as e:
        logger.error(
            f"Error executing exit for {position['symbol']}: {e}", exc_info=True
        )
        return False
