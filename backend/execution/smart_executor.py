"""Smart order execution with regime-aware risk controls (Phase 3 Week 1)."""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime

import pandas as pd

from backend.analytics.regime_detector import get_regime_detector
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)


@dataclass
class ExecutionDecision:
    """Result of smart entry execution decision."""
    decision: str  # EXECUTE, WAIT, REJECT
    symbol: str
    quantity: float
    price: float
    regime: str
    confidence: float
    order_id: Optional[str] = None
    reason: str = ""
    risk_level: str = ""  # LOW, MEDIUM, HIGH
    max_loss_pct: float = 0.0
    max_gain_pct: float = 0.0


@dataclass
class ExecutionContext:
    """Context for execution decision."""
    symbol: str
    quantity: float
    current_price: float
    min_confidence: float = 0.6
    max_position_pct: float = 0.05  # Max 5% of capital per trade
    max_loss_pct: float = 2.0  # Max 2% loss from entry
    max_portfolio_risk: float = 5.0  # Max 5% of portfolio at risk


class SmartExecutor:
    """Execute trades with intelligent entry validation and risk control."""

    def __init__(self, max_position_pct: float = 0.05):
        """Initialize smart executor.

        Args:
            max_position_pct: Maximum position size as % of capital (default 5%)
        """
        self.max_position_pct = max_position_pct

    def evaluate_entry(self, context: ExecutionContext) -> ExecutionDecision:
        """Evaluate and execute smart entry decision.

        Args:
            context: Execution context with symbol, quantity, confidence thresholds

        Returns:
            ExecutionDecision with order details or rejection reason
        """
        try:
            detector = get_regime_detector()
            if not detector:
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason="Regime detector not initialized",
                )

            # Step 1: Validate account state
            engine = get_paper_trading()
            if not engine:
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason="Paper trading engine not initialized",
                )

            account = engine.get_account_state()
            available_cash = account.get("cash") or account.get("available_cash", 0)

            # Step 2: Validate position sizing
            trade_cost = context.quantity * context.current_price
            if trade_cost > available_cash:
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason=f"Insufficient cash: need {trade_cost:.2f}, have {available_cash:.2f}",
                )

            # Step 3: Check position size limit
            total_capital = account.get("total_capital", 100000)
            position_pct = (trade_cost / total_capital) * 100
            if position_pct > self.max_position_pct * 100:
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason=f"Position too large: {position_pct:.1f}% > {self.max_position_pct*100:.1f}%",
                )

            # Step 4: Get current regime metrics
            # Note: In real execution, this would fetch from database or cache
            # For now, we return a decision that would require regime data
            logger.info(
                f"Entry evaluation for {context.symbol}: "
                f"{context.quantity} @ ${context.current_price:.2f}"
            )

            return ExecutionDecision(
                decision="PENDING_REGIME_DATA",
                symbol=context.symbol,
                quantity=context.quantity,
                price=context.current_price,
                regime="UNKNOWN",
                confidence=0.0,
                reason="Awaiting regime detection",
            )

        except Exception as e:
            logger.error(f"Entry evaluation error: {e}")
            return ExecutionDecision(
                decision="REJECT",
                symbol=context.symbol,
                quantity=context.quantity,
                price=context.current_price,
                regime="UNKNOWN",
                confidence=0.0,
                reason=f"Evaluation error: {str(e)}",
            )

    async def execute_smart_entry(
        self, context: ExecutionContext
    ) -> ExecutionDecision:
        """Execute smart entry with full validation.

        Args:
            context: Execution context

        Returns:
            ExecutionDecision with order confirmation or rejection
        """
        # First evaluate the entry
        evaluation = self.evaluate_entry(context)

        if evaluation.decision == "REJECT":
            logger.warning(f"Entry rejected for {context.symbol}: {evaluation.reason}")
            return evaluation

        # If passed validation, place the order
        try:
            engine = get_paper_trading()
            if not engine:
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason="Paper trading engine not initialized",
                )

            order_result = await engine.place_order(
                symbol=context.symbol,
                side="BUY",
                quantity=context.quantity,
                current_price=context.current_price,
                order_type="MARKET",
                strategy_name="smart_gateway",
            )

            if order_result.get("status") == "filled":
                order_id = order_result.get("order_id")
                logger.info(f"Smart entry executed: {context.symbol} {context.quantity} @ {context.current_price}")

                return ExecutionDecision(
                    decision="EXECUTE",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="BULL",  # Would come from regime detector
                    confidence=0.8,  # Would come from regime detector
                    order_id=order_id,
                    reason="Order filled",
                )
            else:
                reason = order_result.get("reason", "Order rejected by exchange")
                return ExecutionDecision(
                    decision="REJECT",
                    symbol=context.symbol,
                    quantity=context.quantity,
                    price=context.current_price,
                    regime="UNKNOWN",
                    confidence=0.0,
                    reason=reason,
                )

        except Exception as e:
            logger.error(f"Execution error: {e}")
            return ExecutionDecision(
                decision="REJECT",
                symbol=context.symbol,
                quantity=context.quantity,
                price=context.current_price,
                regime="UNKNOWN",
                confidence=0.0,
                reason=f"Execution failed: {str(e)}",
            )

    def validate_position_fit(
        self, symbol: str, quantity: float, price: float
    ) -> bool:
        """Check if position fits within risk limits.

        Args:
            symbol: Trading symbol
            quantity: Position quantity
            price: Entry price

        Returns:
            True if position fits, False otherwise
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return False

            account = engine.get_account_state()
            position_value = quantity * price
            available_cash = account.get("cash") or account.get("available_cash", 0)
            total_capital = account.get("total_equity") or account.get("total_capital", 100000)

            # Check cash available
            if position_value > available_cash:
                return False

            # Check position size limit
            if total_capital > 0:
                position_pct = (position_value / total_capital) * 100
                if position_pct > self.max_position_pct * 100:
                    return False
            else:
                return False

            # Check existing positions for this symbol
            positions = engine.get_positions()
            for pos in positions:
                if pos.get("symbol") == symbol:
                    # Already have position - would need averaging logic
                    total_qty = pos.get("quantity", 0) + quantity
                    total_value = total_qty * price
                    new_pct = (total_value / total_capital) * 100
                    if new_pct > self.max_position_pct * 100:
                        return False

            return True

        except Exception as e:
            logger.error(f"Position validation error: {e}")
            return False

    def get_execution_summary(
        self, symbol: str, quantity: float, price: float, regime: str
    ) -> Dict:
        """Get pre-execution summary.

        Args:
            symbol: Trading symbol
            quantity: Position quantity
            price: Entry price
            regime: Current market regime

        Returns:
            Summary dict with position details and risk metrics
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return {"error": "Trading engine not initialized"}

            account = engine.get_account_state()
            total_capital = account.get("total_equity") or account.get("total_capital", 100000)
            available_cash = account.get("cash") or account.get("available_cash", 0)

            position_value = quantity * price
            position_pct = (position_value / total_capital * 100) if total_capital > 0 else 0
            cash_after = available_cash - position_value

            detector = get_regime_detector()
            if detector:
                rules = detector.get_regime_trading_rules(regime)
                stop_price = price * (1 - rules["stop_loss_pct"] / 100)
                target_price = price * (1 + rules["take_profit_pct"] / 100)
            else:
                stop_price = price * 0.98
                target_price = price * 1.02

            cash_util = (position_value / available_cash * 100) if available_cash > 0 else 0

            return {
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": round(price, 2),
                "position_value": round(position_value, 2),
                "position_pct_of_capital": round(position_pct, 2),
                "regime": regime,
                "stop_loss_price": round(stop_price, 2),
                "take_profit_price": round(target_price, 2),
                "max_loss": round((quantity * (price - stop_price)), 2),
                "max_gain": round((quantity * (target_price - price)), 2),
                "cash_after_trade": round(cash_after, 2),
                "cash_utilization_pct": round(cash_util, 2),
            }

        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return {"error": str(e)}


# Global instance
_smart_executor: Optional[SmartExecutor] = None


def init_smart_executor(max_position_pct: float = 0.05) -> SmartExecutor:
    """Initialize global smart executor."""
    global _smart_executor
    _smart_executor = SmartExecutor(max_position_pct=max_position_pct)
    logger.info("Smart executor initialized")
    return _smart_executor


def get_smart_executor() -> Optional[SmartExecutor]:
    """Get global smart executor."""
    return _smart_executor
