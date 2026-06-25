"""
Phase 317: Portfolio Rebalancing Engine

Monitor portfolio drift and recommend rebalancing actions per market regime.
Calculates optimal allocation changes and generates execution plan.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RebalancingAction:
    """Single rebalancing trade."""

    symbol: str
    action: str  # BUY or SELL
    current_allocation_pct: float
    target_allocation_pct: float
    adjustment_pct: float  # How much to adjust
    estimated_cost_eur: float
    priority: int  # 1-10 (higher = execute first)
    rationale: str


@dataclass
class RebalancingPlan:
    """Complete rebalancing plan."""

    timestamp: datetime
    total_rebalancing_cost: float  # Total transaction cost estimate
    total_drift: float  # Sum of absolute drifts
    actions: List[RebalancingAction]
    estimated_execution_time_min: float  # Minutes to execute
    improvement_expected: str  # Qualitative (Small / Moderate / Large)
    urgency: int  # 1-10


class PortfolioRebalancingEngine:
    """Manage portfolio drift and rebalancing decisions."""

    def __init__(
        self,
        drift_threshold_pct: float = 5.0,  # Rebalance if any position drifts >5%
        max_rebalancing_cost_pct: float = 0.1,  # Max 0.1% of portfolio for rebalancing
    ):
        """
        Initialize rebalancing engine.

        Parameters:
        -----------
        drift_threshold_pct : float
            Trigger rebalancing if any position drifts more than this (%)
        max_rebalancing_cost_pct : float
            Maximum acceptable cost of rebalancing as % of portfolio value
        """
        self.drift_threshold_pct = drift_threshold_pct
        self.max_rebalancing_cost_pct = max_rebalancing_cost_pct
        self.last_rebalance_timestamp = None

    def analyze_drift(
        self,
        current_positions: Dict[str, Dict],  # symbol → {quantity, price, cost_basis}
        portfolio_value: float,
        target_allocation: Dict[str, float],  # symbol → target % (0-100)
    ) -> Dict[str, float]:
        """
        Analyze how current portfolio drifts from target allocation.

        Returns dict of {symbol: drift_pct} where drift = current - target
        """
        drifts = {}

        for symbol, target_pct in target_allocation.items():
            current_amount = 0
            if symbol in current_positions:
                pos = current_positions[symbol]
                current_amount = pos.get("value_eur", 0)

            current_pct = (
                (current_amount / portfolio_value * 100) if portfolio_value > 0 else 0
            )
            drift = current_pct - target_pct
            drifts[symbol] = drift

        return drifts

    def should_rebalance(
        self,
        drifts: Dict[str, float],
        time_since_last_rebalance_days: float = 0,
    ) -> bool:
        """
        Determine if rebalancing is needed.

        Rebalance if:
          1. Any position drifts >threshold
          2. OR total drift is high (>15%)
          3. AND time since last rebalance >7 days
        """
        if not drifts:
            return False

        max_drift = max(abs(d) for d in drifts.values())
        total_drift = sum(abs(d) for d in drifts.values())

        # Check drift conditions
        drift_condition = (max_drift > self.drift_threshold_pct) or (total_drift > 15)

        # Check time condition (don't rebalance too frequently)
        time_condition = time_since_last_rebalance_days >= 7

        return drift_condition and time_condition

    def generate_rebalancing_plan(
        self,
        current_positions: Dict[str, Dict],  # symbol → {quantity, price, entry_price}
        portfolio_value: float,
        target_allocation: Dict[str, float],  # symbol → target % (0-100)
        transaction_costs_pct: float = 0.002,  # 0.2% transaction cost
        regime: str = "neutral",  # For prioritization
    ) -> Optional[RebalancingPlan]:
        """
        Generate detailed rebalancing plan.

        Parameters:
        -----------
        current_positions : dict
            Current portfolio positions
        portfolio_value : float
            Total portfolio value in EUR
        target_allocation : dict
            Target allocation percentages
        transaction_costs_pct : float
            Cost per transaction (bid-ask spread, fees)
        regime : str
            Market regime for prioritization (bull/bear/sideways/volatile)

        Returns:
        --------
        RebalancingPlan or None if no rebalancing needed
        """
        drifts = self.analyze_drift(
            current_positions, portfolio_value, target_allocation
        )

        if not self.should_rebalance(drifts):
            logger.debug("Portfolio drift within tolerance, no rebalancing needed")
            return None

        # Generate actions
        actions: List[RebalancingAction] = []
        total_cost = 0
        total_drift = sum(abs(d) for d in drifts.values())

        for symbol, target_pct in target_allocation.items():
            drift = drifts.get(symbol, 0)

            # Only generate action if drift exceeds threshold
            if abs(drift) < 0.5:
                continue

            current_pct = (
                (
                    current_positions.get(symbol, {}).get("value_eur", 0)
                    / portfolio_value
                    * 100
                )
                if portfolio_value > 0
                else 0
            )

            if drift > 0:
                # Overweight: SELL
                action_type = "SELL"
                adjustment_pct = min(drift, 5)  # Don't sell more than 5% in one go
            else:
                # Underweight: BUY
                action_type = "BUY"
                adjustment_pct = abs(min(drift, -5))

            # Estimate cost
            target_value = portfolio_value * (target_pct / 100)
            estimated_cost = (
                abs(
                    target_value - current_positions.get(symbol, {}).get("value_eur", 0)
                )
                * transaction_costs_pct
            )

            # Priority: higher in bull (buy dips), higher in bear (raise cash)
            base_priority = int(abs(drift) / 2) + 1  # 1-10
            if regime == "bull" and action_type == "BUY":
                base_priority = min(base_priority + 3, 10)
            elif regime == "bear" and action_type == "SELL":
                base_priority = min(base_priority + 3, 10)

            total_cost += estimated_cost

            actions.append(
                RebalancingAction(
                    symbol=symbol,
                    action=action_type,
                    current_allocation_pct=current_pct,
                    target_allocation_pct=target_pct,
                    adjustment_pct=adjustment_pct,
                    estimated_cost_eur=estimated_cost,
                    priority=base_priority,
                    rationale=f"{action_type} {adjustment_pct:.1f}% to reach {target_pct}% target",
                )
            )

        # Sort actions by priority (higher first)
        actions.sort(key=lambda a: a.priority, reverse=True)

        # Estimate execution time (2 min per action + 5 min overhead)
        execution_time = len(actions) * 2 + 5

        # Determine improvement magnitude
        if total_drift < 5:
            improvement = "Small"
        elif total_drift < 15:
            improvement = "Moderate"
        else:
            improvement = "Large"

        # Calculate urgency (0-10)
        urgency = min(int(total_drift / 2), 10)

        plan = RebalancingPlan(
            timestamp=datetime.utcnow(),
            total_rebalancing_cost=total_cost,
            total_drift=total_drift,
            actions=actions,
            estimated_execution_time_min=execution_time,
            improvement_expected=improvement,
            urgency=urgency,
        )

        return plan

    def get_regime_aware_targets(
        self,
        regime: str,
        base_allocation: Dict[str, float],  # Equal-weight or market-cap allocation
    ) -> Dict[str, float]:
        """
        Adjust allocation targets based on market regime.

        Bull: Overweight growth (tech, crypto)
        Bear: Overweight defensive (utilities, healthcare)
        Sideways: Neutral (equal weight)
        Volatile: Reduce risk assets, increase cash
        """
        if not base_allocation:
            return base_allocation

        if regime == "bull":
            # Overweight growth
            multipliers = {
                "cryptocurrency": 1.3,
                "technology": 1.2,
                "consumer": 1.1,
                "finance": 1.0,
                "healthcare": 0.9,
                "energy": 0.8,
                "utilities": 0.7,
            }
        elif regime == "bear":
            # Overweight defensive
            multipliers = {
                "cryptocurrency": 0.5,
                "technology": 0.7,
                "consumer": 0.8,
                "finance": 1.0,
                "healthcare": 1.3,
                "energy": 1.2,
                "utilities": 1.4,
            }
        elif regime == "volatile":
            # Reduce risk
            multipliers = {
                "cryptocurrency": 0.3,
                "technology": 0.8,
                "consumer": 0.8,
                "finance": 0.9,
                "healthcare": 1.2,
                "energy": 1.0,
                "utilities": 1.2,
            }
        else:  # sideways or unknown
            # Neutral
            multipliers = {k: 1.0 for k in base_allocation.keys()}

        # Apply multipliers and renormalize
        adjusted = {}
        total = 0

        for symbol, target in base_allocation.items():
            sector = self._get_sector(symbol)
            multiplier = multipliers.get(sector, 1.0)
            adjusted[symbol] = target * multiplier
            total += adjusted[symbol]

        # Renormalize to sum to 100%
        if total > 0:
            adjusted = {s: (v / total) * 100 for s, v in adjusted.items()}

        return adjusted

    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol (hardcoded for now)."""
        sector_map = {
            "BTCUSDT": "cryptocurrency",
            "ETHUSDT": "cryptocurrency",
            "BNBUSDT": "cryptocurrency",
            "EQ_AAPL": "technology",
            "EQ_MSFT": "technology",
            "EQ_NVDA": "technology",
            "EQ_TSLA": "technology",
            "EQ_JNJ": "healthcare",
            "EQ_UNH": "healthcare",
            "EQ_JPM": "finance",
            "EQ_BAC": "finance",
            "EQ_XOM": "energy",
            "EQ_CVX": "energy",
            "EQ_NEE": "utilities",
            "EQ_DUK": "utilities",
            "EQ_AMZN": "consumer",
            "EQ_WMT": "consumer",
        }
        return sector_map.get(symbol, "other")

    def estimate_rebalancing_impact(
        self,
        plan: RebalancingPlan,
        portfolio_value: float,
    ) -> Dict[str, Any]:
        """
        Estimate impact of executing rebalancing plan.

        Returns metrics on improvement and cost.
        """
        if not plan or not plan.actions:
            return {}

        # Cost metrics
        cost_pct_of_portfolio = (
            (plan.total_rebalancing_cost / portfolio_value * 100)
            if portfolio_value > 0
            else 0
        )

        # Drift reduction (before/after)
        pre_drift = plan.total_drift
        post_drift = sum(
            abs(a.adjustment_pct / 2) for a in plan.actions
        )  # Rough estimate

        return {
            "cost_eur": plan.total_rebalancing_cost,
            "cost_pct_of_portfolio": cost_pct_of_portfolio,
            "drift_reduction": pre_drift - post_drift,
            "estimated_execution_time_min": plan.estimated_execution_time_min,
            "breakeven_days": self._estimate_breakeven(pre_drift, post_drift),
        }

    def _estimate_breakeven(
        self,
        drift_reduction: float,
        improvement_pct: float,
    ) -> float:
        """Estimate days until rebalancing pays for itself through better positioning."""
        if improvement_pct <= 0:
            return float("inf")

        # Assume improvement reduces risk by 0.5bps per drift percentage point
        annualized_benefit = drift_reduction * 0.005 * 100  # In basis points
        daily_benefit = annualized_benefit / 252
        breakeven = 1.0 / daily_benefit if daily_benefit > 0 else float("inf")

        return min(breakeven, 365)  # Cap at 1 year

    def get_summary(self, plan: Optional[RebalancingPlan]) -> str:
        """Get human-readable summary of rebalancing plan."""
        if not plan:
            return "📊 Portfolio allocation is balanced, no rebalancing needed"

        summary = f"📊 Rebalancing plan (urgency: {plan.urgency}/10):\n"
        summary += f"  • Estimated cost: €{plan.total_rebalancing_cost:.2f}\n"
        summary += f"  • Total drift: {plan.total_drift:.1f}%\n"
        summary += f"  • Expected improvement: {plan.improvement_expected}\n"
        summary += f"  • Actions: {len(plan.actions)} trades\n"

        if plan.actions:
            summary += "  Top actions:\n"
            for action in plan.actions[:3]:
                summary += f"    • {action.action} {action.symbol} "
                summary += f"({action.current_allocation_pct:.1f}% → {action.target_allocation_pct:.1f}%)\n"

        return summary


# Global instance
_rebalancing_engine: PortfolioRebalancingEngine = None


def get_portfolio_rebalancing_engine() -> PortfolioRebalancingEngine:
    """Get or create portfolio rebalancing engine instance."""
    global _rebalancing_engine
    if _rebalancing_engine is None:
        _rebalancing_engine = PortfolioRebalancingEngine()
    return _rebalancing_engine
