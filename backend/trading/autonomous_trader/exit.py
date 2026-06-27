"""Exit signal generation (stop loss, profit target)."""

import logging
from typing import TYPE_CHECKING, Dict

from backend.exchange.paper_trading import get_paper_trading
from backend.execution.smart_executor import get_smart_executor

if TYPE_CHECKING:
    from .core import AutonomousTrader

logger = logging.getLogger(__name__)


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
                # Alert on profit target
                from backend.core.alerting import get_alert_manager
                alert_mgr = get_alert_manager()
                await alert_mgr.alert_profit_target_hit(symbol, pnl_pct)

            elif pnl_pct <= -trader_self.config.exit_stop_loss:
                logger.warning(
                    f"🛑 STOP LOSS HIT {symbol}: {pnl_pct:.2f}% <= "
                    f"-{trader_self.config.exit_stop_loss:.1f}%"
                )
                await _execute_exit_impl(
                    trader_self, position, current_price, "Stop loss"
                )
                # Alert on stop loss
                from backend.core.alerting import get_alert_manager
                alert_mgr = get_alert_manager()
                await alert_mgr.alert_stop_loss_hit(symbol, pnl_pct)

    except Exception as e:
        logger.error(f"Error checking exits: {e}", exc_info=True)


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

        if result.get("success"):
            realized_pnl = result.get("realized_pnl", 0.0)
            logger.info(
                f"✅ SOLD {symbol}: {quantity:.4f} @ ${current_price:.2f} - {reason} - "
                f"P&L: ${realized_pnl:.2f}"
            )
            return True
        else:
            logger.warning(
                f"❌ Sell order failed for {symbol}: {result.get('error')}"
            )
            return False

    except Exception as e:
        logger.error(
            f"Error executing exit for {position['symbol']}: {e}", exc_info=True
        )
        return False
