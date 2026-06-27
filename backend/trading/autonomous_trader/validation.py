"""Validation and health checks."""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

from backend.exchange.paper_trading import get_paper_trading
from backend.core.data_quality import get_data_quality_measurer
from backend.analytics.historical_data import get_historical_service
from backend.analytics.regime_detector import get_regime_detector
from backend.exchange.binance_stream import get_stream_client

logger = logging.getLogger(__name__)


async def _get_current_prices_impl(trader_self) -> Dict[str, float]:
    """Get current market prices from WebSocket stream."""
    try:
        stream_client = get_stream_client()
        if not stream_client or not stream_client.is_connected:
            return {}

        prices = {}
        for symbol in trader_self.config.symbols:
            if symbol in stream_client.price_cache:
                prices[symbol] = stream_client.price_cache[symbol]

        return prices

    except Exception as e:
        logger.error(f"Error getting current prices: {e}", exc_info=True)
        return {}


async def _measure_data_quality_impl(trader_self, prices: Dict[str, float]):
    """Measure overall data quality score."""
    try:
        measurer = get_data_quality_measurer()
        if not measurer:
            return None

        data_quality = measurer.measure(
            prices=prices,
            symbols=trader_self.config.symbols,
            data_provider="binance_stream",
        )

        return data_quality

    except Exception as e:
        logger.error(f"Error measuring data quality: {e}", exc_info=True)
        return None


async def _check_daily_loss_limit_impl(trader_self) -> bool:
    """Check if daily loss limit has been exceeded."""
    try:
        engine = get_paper_trading()
        if not engine:
            return False

        account = engine.get_account_state()
        daily_pnl = account.get("daily_pnl", 0.0)
        total_equity = account.get("total_equity", 1000.0)

        if total_equity <= 0:
            return False

        daily_loss_pct = abs(daily_pnl) / total_equity * 100

        if daily_pnl < 0 and daily_loss_pct >= trader_self.config.max_daily_loss_pct:
            logger.critical(
                f"🛑 DAILY LOSS LIMIT EXCEEDED: "
                f"${abs(daily_pnl):.2f} ({daily_loss_pct:.2f}%) >= "
                f"{trader_self.config.max_daily_loss_pct:.1f}% limit"
            )
            return True

        if daily_pnl < 0 and daily_loss_pct >= (
            trader_self.config.max_daily_loss_pct * 0.8
        ):
            logger.warning(
                f"⚠️  Approaching daily loss limit: "
                f"${abs(daily_pnl):.2f} ({daily_loss_pct:.2f}%) "
                f"(limit: {trader_self.config.max_daily_loss_pct:.1f}%)"
            )

        return False

    except Exception as e:
        logger.error(f"Error checking daily loss limit: {e}", exc_info=True)
        return False


async def _validate_risk_before_order_impl(
    trader_self, symbol: str, side: str, quantity: float, current_price: float
) -> tuple:
    """Pre-order risk validation."""
    try:
        engine = get_paper_trading()
        if not engine:
            return False, "Paper trading engine unavailable"

        account = engine.get_account_state()
        daily_pnl = account.get("daily_pnl", 0.0)
        total_equity = account.get("total_equity", 1000.0)
        cash = account.get("cash", 1000.0)

        if total_equity <= 0:
            return False, "Invalid account equity"

        daily_loss_pct = abs(daily_pnl) / total_equity * 100
        if daily_pnl < 0 and daily_loss_pct >= trader_self.config.max_daily_loss_pct:
            return (
                False,
                f"Daily loss limit already exceeded: ${abs(daily_pnl):.2f}",
            )

        if side == "BUY":
            order_cost = quantity * current_price
            if order_cost > cash:
                return (
                    False,
                    f"Insufficient cash: need ${order_cost:.2f}, have ${cash:.2f}",
                )

            worst_case_loss = order_cost * 0.02 + (order_cost * 0.001)
            projected_daily_pnl = daily_pnl - worst_case_loss
            projected_loss_pct = abs(projected_daily_pnl) / total_equity * 100

            if projected_loss_pct > trader_self.config.max_daily_loss_pct:
                return (
                    False,
                    f"Order would exceed daily limit: worst-case loss ${worst_case_loss:.2f} → "
                    f"${abs(projected_daily_pnl):.2f} ({projected_loss_pct:.1f}%)",
                )

        logger.debug(
            f"RISK_VALIDATION_PASSED: {side} {quantity} {symbol} @ ${current_price:.2f}"
        )

        return True, "OK"

    except Exception as e:
        logger.error(f"Error validating risk: {e}", exc_info=True)
        return False, f"Validation error: {str(e)}"
