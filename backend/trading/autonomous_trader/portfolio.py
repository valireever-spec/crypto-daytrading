"""Portfolio-level decisions and rebalancing."""

import logging
from typing import Dict, Any, List, TYPE_CHECKING
from datetime import datetime, timedelta

from backend.exchange.paper_trading import get_paper_trading
from backend.analytics.historical_data import get_historical_service
from backend.analytics.regime_detector import get_regime_detector
from backend.trading.portfolio_decision_coordinator import (
    get_portfolio_decision_coordinator,
)

if TYPE_CHECKING:
    from .core import AutonomousTrader

logger = logging.getLogger(__name__)


async def _check_portfolio_decisions_impl(trader_self: "AutonomousTrader"):
    """Check and execute portfolio-level regime decisions."""
    try:
        engine = get_paper_trading()
        if not engine:
            return

        positions = engine.get_positions()
        prices = await _get_prices_for_portfolio(trader_self)
        account = engine.get_account_state()
        portfolio_value = account.get("total_equity", 0)

        if not positions or not prices or portfolio_value <= 0:
            return

        symbol_regimes = await _fetch_all_regimes_impl(
            [p["symbol"] for p in positions]
        )

        if not symbol_regimes:
            return

        coordinator = get_portfolio_decision_coordinator()
        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=symbol_regimes,
            current_positions=positions,
            portfolio_value=portfolio_value,
            target_allocation=_get_target_allocation_impl(trader_self),
            current_prices=prices,
        )

        for decision in decisions:
            if decision.urgency >= 8:
                await _execute_portfolio_decision_impl(trader_self, decision, prices)
            elif decision.urgency >= 6:
                logger.info(
                    f"📋 Queued portfolio decision: {decision.decision_type} "
                    f"(urgency {decision.urgency}/10)"
                )
            else:
                logger.debug(
                    f"📋 Portfolio decision: {decision.decision_type} "
                    f"(urgency {decision.urgency}/10)"
                )

    except Exception as e:
        logger.error(f"Error checking portfolio decisions: {e}", exc_info=True)


async def _fetch_all_regimes_impl(symbols: List[str]) -> Dict[str, Any]:
    """Fetch regime info for all symbols."""
    try:
        hist_service = get_historical_service()
        regime_detector = get_regime_detector()
        regimes = {}

        if not hist_service:
            return regimes

        end = datetime.utcnow()
        start = end - timedelta(days=90)

        for symbol in symbols:
            try:
                ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
                if ohlcv is not None and len(ohlcv) >= 200:
                    regime_info = regime_detector.detect_regime(ohlcv)
                    regimes[symbol] = regime_info
            except Exception as e:
                logger.debug(f"Could not fetch regime for {symbol}: {e}")

        return regimes

    except Exception as e:
        logger.error(f"Error fetching regimes: {e}")
        return {}


def _get_target_allocation_impl(trader_self: "AutonomousTrader") -> Dict[str, float]:
    """Get target allocation (equal weight)."""
    if not trader_self.config.symbols:
        return {}

    equal_weight = 100.0 / len(trader_self.config.symbols)
    return {symbol: equal_weight for symbol in trader_self.config.symbols}


async def _execute_portfolio_decision_impl(
    trader_self: "AutonomousTrader",
    decision: Any,
    current_prices: Dict[str, float],
) -> bool:
    """Execute a portfolio-level decision."""
    try:
        engine = get_paper_trading()
        if not engine:
            logger.error("Paper trading engine not initialized")
            return False

        logger.info(f"🚀 Executing portfolio decision: {decision.decision_type}")
        logger.info(f"   Targets: {decision.target_symbols}")
        logger.info(f"   Actions: {decision.actions}")
        logger.info(f"   Rationale: {decision.rationale}")

        executed_count = 0

        for symbol, action in decision.actions.items():
            if action == "SELL":
                positions = engine.get_positions()
                pos = next((p for p in positions if p["symbol"] == symbol), None)

                if pos:
                    result = await engine.place_order(
                        symbol=symbol,
                        side="SELL",
                        quantity=pos["quantity"],
                        current_price=current_prices.get(symbol, pos["entry_price"]),
                    )

                    if result["success"]:
                        executed_count += 1
                        logger.info(f"✅ Sold {pos['quantity']} {symbol}")

        logger.info(
            f"Portfolio decision executed: {executed_count}/{len(decision.actions)} actions"
        )
        return True

    except Exception as e:
        logger.error(f"Error executing portfolio decision: {e}", exc_info=True)
        return False


async def _get_prices_for_portfolio(trader_self: "AutonomousTrader") -> Dict[str, float]:
    """Get current prices for portfolio analysis."""
    from backend.exchange.binance_stream import get_stream_client

    stream_client = get_stream_client()
    if not stream_client or not stream_client.is_connected:
        return {}

    prices = {}
    for symbol in trader_self.config.symbols:
        if symbol in stream_client.price_cache:
            prices[symbol] = stream_client.price_cache[symbol]

    return prices
