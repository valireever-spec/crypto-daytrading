"""Stop-loss management: Cut losses even if it breaks the 365-day rule."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class StopLossLevel:
    """Stop-loss trigger level."""
    symbol: str
    entry_price: float
    stop_loss_pct: float  # e.g., 2.0 for 2% stop
    take_profit_pct: float  # e.g., 10.0 for 10% target


class StopLossManager:
    """Manage stop-loss orders and protect capital."""

    def __init__(self, default_stop_loss_pct: float = 2.0):
        """Initialize stop-loss manager.

        Args:
            default_stop_loss_pct: Default stop-loss percentage (e.g., 2.0 = 2%)
        """
        self.default_stop_loss_pct = default_stop_loss_pct
        self.stops: Dict[str, StopLossLevel] = {}

    def set_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_pct: float,
        take_profit_pct: float = 10.0,
    ) -> Dict:
        """Set stop-loss and take-profit levels for a position.

        Args:
            symbol: Stock/crypto symbol
            entry_price: Entry price
            stop_loss_pct: Stop-loss percentage (e.g., 2.0)
            take_profit_pct: Take-profit percentage (default 10%)

        Returns:
            Configured stop-loss details
        """
        stop = StopLossLevel(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        self.stops[symbol] = stop

        stop_price = entry_price * (1 - stop_loss_pct / 100)
        profit_price = entry_price * (1 + take_profit_pct / 100)

        return {
            "symbol": symbol,
            "entry_price": round(entry_price, 2),
            "stop_loss_price": round(stop_price, 2),
            "stop_loss_pct": stop_loss_pct,
            "take_profit_price": round(profit_price, 2),
            "take_profit_pct": take_profit_pct,
        }

    def check_stop_loss_hit(
        self,
        symbol: str,
        current_price: float,
        current_gain_pct: float,
        days_held: int,
    ) -> Dict:
        """Check if stop-loss or take-profit has been hit.

        Args:
            symbol: Position symbol
            current_price: Current market price
            current_gain_pct: Current P&L as percentage
            days_held: Days the position has been held

        Returns:
            Analysis of whether to act
        """
        if symbol not in self.stops:
            return {"triggered": False, "action": "NONE"}

        stop = self.stops[symbol]
        stop_price = stop.entry_price * (1 - stop.stop_loss_pct / 100)
        profit_price = stop.entry_price * (1 + stop.take_profit_pct / 100)

        # Check stop-loss FIRST (capital protection)
        if current_price <= stop_price:
            return {
                "triggered": True,
                "action": "SELL_STOP_LOSS",
                "reason": f"Stop-loss hit at €{current_price:.2f} (threshold: €{stop_price:.2f})",
                "current_loss_pct": round(current_gain_pct, 2),
                "message": "🛑 CUT LOSSES! Sell immediately to protect capital.",
                "importance": "CRITICAL",
            }

        # Check take-profit (if long-term, capture tax-free gains)
        if current_price >= profit_price and days_held >= 365:
            return {
                "triggered": True,
                "action": "SELL_PROFIT_LONGTERM",
                "reason": f"Take-profit hit at €{current_price:.2f} + {days_held} days held",
                "current_gain_pct": round(current_gain_pct, 2),
                "message": "✅ TAKE PROFIT: You've hit target + crossed 365-day tax threshold (0% tax)!",
                "importance": "RECOMMENDED",
            }

        # Check take-profit (if short-term, consider taxes)
        if current_price >= profit_price and days_held < 365:
            days_remaining = 365 - days_held
            return {
                "triggered": True,
                "action": "SELL_PROFIT_SHORTTERM",
                "reason": f"Take-profit hit at €{current_price:.2f} (only {days_held} days held, {days_remaining} more to tax-free)",
                "current_gain_pct": round(current_gain_pct, 2),
                "days_to_long_term": days_remaining,
                "message": (
                    f"⚠️ DECISION: Take profit now (pay 42% tax) or hold {days_remaining} "
                    "days more for 0% tax? Both are valid!"
                ),
                "importance": "DECISION_NEEDED",
            }

        return {"triggered": False, "action": "NONE"}

    def get_emergency_exit_scenarios(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        days_held: int,
        jurisdiction: str = "DE",
    ) -> Dict:
        """Calculate exit scenarios if you MUST sell now (emergency, margin call, etc).

        Args:
            symbol: Position symbol
            entry_price: Entry price
            current_price: Current market price
            days_held: Days held
            jurisdiction: Tax jurisdiction

        Returns:
            Different exit scenarios with tax implications
        """
        cost_basis = entry_price
        current_value = current_price
        gain = current_value - cost_basis
        gain_pct = (gain / cost_basis * 100) if cost_basis > 0 else 0

        # Tax calculation for Germany
        if jurisdiction == "DE":
            if days_held >= 365:
                tax = 0
                tax_status = "TAX_FREE (long-term)"
            else:
                tax = gain * 0.42 * 1.055  # 42% + 5.5% solidarity
                tax_status = f"TAXABLE (42%) - {365 - days_held} days until tax-free"
        else:
            # Simplified for other jurisdictions
            tax = gain * 0.3
            tax_status = "Estimated 30% tax"

        net_proceeds = gain - tax

        scenarios = {
            "symbol": symbol,
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2),
            "gain_loss": round(gain, 2),
            "gain_loss_pct": round(gain_pct, 2),
            "days_held": days_held,
            "days_to_tax_free": max(0, 365 - days_held),
        }

        # Scenario 1: Forced exit now
        scenarios["scenario_exit_now"] = {
            "action": "SELL NOW",
            "reason": "Emergency, margin call, rebalancing",
            "proceeds": round(current_value, 2),
            "tax_owed": round(tax, 2),
            "tax_status": tax_status,
            "net_to_pocket": round(current_value - tax, 2),
        }

        # Scenario 2: If you COULD wait (not in emergency)
        if days_held < 365:
            gain_tax_free = gain  # Would pay 0% tax if waited
            scenarios["scenario_wait"] = {
                "action": "HOLD & WAIT",
                "days_remaining": 365 - days_held,
                "tax_at_long_term": 0,
                "net_if_hold_and_sell": round(current_value, 2),
                "additional_profit_vs_now": round(gain_tax_free - (current_value - tax), 2),
            }

        return scenarios


def get_stop_loss_recommendation(
    position_loss_pct: float,
    days_held: int,
    jurisdiction: str = "DE",
) -> Dict:
    """Quick recommendation: hold or sell?

    Args:
        position_loss_pct: Current loss as percentage (e.g., -5.0)
        days_held: Days held
        jurisdiction: Tax jurisdiction

    Returns:
        Recommendation
    """
    # Rule 1: ALWAYS cut large losses (>5%)
    if position_loss_pct <= -5.0:
        return {
            "action": "SELL",
            "reason": "Large loss detected - cut losses immediately",
            "message": "🛑 Don't hope for recovery - sell now and lock losses for tax deduction",
        }

    # Rule 2: Cut moderate losses if short-term
    if position_loss_pct <= -2.0 and days_held < 180:
        return {
            "action": "SELL",
            "reason": "Moderate loss + short holding period - exit and redeploy",
            "message": "⚠️ Small loss + fresh position = better to reset position",
        }

    # Rule 3: Small losses are OK to hold
    if position_loss_pct > -2.0:
        return {
            "action": "HOLD",
            "reason": "Small loss - hold for recovery or long-term tax benefit",
            "message": "📊 Loss <2% - hold until you reach profit or 365 days",
        }

    return {"action": "EVALUATE"}
