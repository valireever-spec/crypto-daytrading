"""Exit signal generation (stop loss, profit target)."""

import logging
from datetime import timezone, datetime
from typing import TYPE_CHECKING, Dict

from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.order_response import validate_order_response
from backend.execution.smart_executor import get_smart_executor
from backend.core.fragility_circuit_breaker import get_fragility_breaker
from backend.core.trading_metrics import get_metrics_collector

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
            # Note: BACKUP may have positions without entry_time (synced state from PRIMARY)
            # This is NOT a failure - just skip incomplete positions
            entry_time = position.get("entry_time")
            if not entry_time:
                logger.debug(
                    f"⏭️ {symbol}: Skipping position without entry_time (expected on BACKUP during sync). "
                    f"Position: {position}"
                )
                continue  # Skip this position, not a failure

            # ✅ BUG FIX #1: Check minimum hold time FIRST (prevents 5-10 second exits)
            hold_time = 0  # Initialize to 0 (safety fallback)
            if entry_time:
                if isinstance(entry_time, str):
                    # Parse ISO format and ensure timezone-aware
                    entry_time = datetime.fromisoformat(entry_time)
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=timezone.utc)
                # Ensure both datetimes are comparable
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                hold_time = (datetime.now(timezone.utc) - entry_time).total_seconds()

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
                    # Alert on forced timeout exit
                    from backend.core.alerting import get_alert_manager
                    alert_mgr = get_alert_manager()
                    engine = get_paper_trading()
                    if engine:
                        account = engine.get_account_state()
                        remaining_cash = account.get("cash", 0.0)
                        entry_price = position["entry_price"]
                        pnl_pct = (current_price - entry_price) / entry_price * 100
                        realized_pnl = position["quantity"] * (current_price - entry_price)
                        await alert_mgr.alert_trade_exit(
                            symbol, realized_pnl, pnl_pct, remaining_cash, hold_time, is_win=(pnl_pct > 0)
                        )
                continue

            current_price = stream_client.price_cache.get(symbol)

            if not current_price:
                logger.debug(f"{symbol}: No current price, skipping profit/stop check")
                continue

            entry_price = position["entry_price"]
            _quantity = position["quantity"]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # DEBUG: Log all P&L values for analysis
            logger.debug(
                f"DEBUG_EXIT_CHECK: {symbol} | Hold: {hold_time:.0f}s | Entry: ${entry_price:.2f} | "
                f"Current: ${current_price:.2f} | P&L: {pnl_pct:.2f}% | "
                f"ProfitTarget: {trader_self.config.exit_profit_target:.1f}% | "
                f"StopLoss: {trader_self.config.exit_stop_loss:.1f}%"
            )

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
    """Execute a sell order to close a position.

    CRITICAL FIX: Closes ALL quantity held for the symbol, not just one position.
    This prevents partial exits that leave remainder positions open and block future entries.
    """
    try:
        engine = get_paper_trading()
        if not engine:
            logger.error("Paper trading engine not initialized")
            return False

        symbol = position["symbol"]

        # CRITICAL FIX: Close ALL quantity held for this symbol, not just this position
        # This prevents the partial closure bug that creates deadlock
        all_positions = engine.get_positions()
        total_quantity = sum(p["quantity"] for p in all_positions if p["symbol"] == symbol)

        if total_quantity <= 0:
            logger.warning(f"Cannot exit {symbol}: no quantity held (position data stale?)")
            return False

        if total_quantity != position["quantity"]:
            logger.warning(
                f"Exit {symbol}: Multiple positions detected. "
                f"Closing ALL {total_quantity:.4f} units (this position: {position['quantity']:.4f})"
            )

        quantity = total_quantity  # Use TOTAL quantity, not just this position

        smart_executor = get_smart_executor()
        if not smart_executor:
            logger.error("Smart executor not initialized")
            return False

        result = await engine.place_order(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            current_price=current_price,
            exit_reason=reason,
        )

        try:
            # Validate response against OrderResponse schema
            validated = validate_order_response(result)

            if validated.status == "FILLED":
                realized_pnl = validated.realized_pnl or 0.0
                realized_pnl_pct = (realized_pnl / (position["entry_price"] * quantity) * 100) if position["entry_price"] > 0 else 0
                hold_time = int((datetime.now(timezone.utc) - datetime.fromisoformat(position.get("entry_time", ""))).total_seconds()) if position.get("entry_time") else 0

                logger.info(
                    f"✅ SOLD {symbol}: {quantity:.4f} @ ${current_price:.2f} - {reason} - "
                    f"P&L: ${realized_pnl:.2f}"
                )

                # Record exit trade for monitoring
                metrics = get_metrics_collector()
                from backend.core.parameter_monitor import get_parameter_monitor

                metrics.record_trade(
                    symbol=symbol,
                    side='SELL',
                    exit_price=current_price,
                    quantity=quantity,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    hold_seconds=hold_time,
                    exit_reason=reason.lower().replace(" ", "_")
                )

                # Record to parameter monitor
                param_monitor = get_parameter_monitor()
                param_monitor.record_exit(
                    symbol=symbol,
                    exit_reason=reason,
                    entry_price=position["entry_price"],
                    exit_price=current_price,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    hold_seconds=hold_time
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
