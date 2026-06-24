"""
Phase 327: Constrained Rebalancing Engine

Portfolio rebalancing with constraint enforcement and scenario stress testing.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd

from backend.analytics.constraint_manager import get_constraint_manager

logger = logging.getLogger(__name__)


@dataclass
class DriftAnalysis:
    """Portfolio drift analysis."""
    total_drift_pct: float
    current_allocation: Dict[str, float]
    target_allocation: Dict[str, float]
    drift_per_symbol: Dict[str, float]
    requires_rebalancing: bool
    drift_threshold_pct: float


@dataclass
class RebalancingPlan:
    """Rebalancing execution plan."""
    trades: List[Tuple[str, str, float]]  # (symbol, side, amount_pct)
    total_cost_pct: float
    estimated_slippage_pct: float
    tax_impact_pct: float
    feasible: bool
    constraint_violations: List[str]
    estimated_execution_time_min: float


@dataclass
class StressResult:
    """Rebalancing stress test result."""
    scenario_name: str
    rebalancing_pct: float
    final_allocation: Dict[str, float]
    constraint_violations: List[str]
    feasible_under_stress: bool


class RebalancingEngine:
    """Manage portfolio rebalancing with constraints."""

    def __init__(self, drift_threshold_pct: float = 5.0):
        """
        Initialize rebalancing engine.

        Parameters:
        -----------
        drift_threshold_pct : float
            Trigger rebalancing when any position drifts beyond this threshold
        """
        self.drift_threshold_pct = drift_threshold_pct
        self.rebalancing_history: List[RebalancingPlan] = []

    def analyze_drift(
        self,
        current_allocation: Dict[str, float],
        target_allocation: Dict[str, float],
    ) -> DriftAnalysis:
        """
        Analyze portfolio drift from target.

        Parameters:
        -----------
        current_allocation : dict
            {symbol: current weight %}
        target_allocation : dict
            {symbol: target weight %}

        Returns:
        --------
        DriftAnalysis with drift metrics
        """
        drift_per_symbol = {}
        max_drift = 0.0

        # Guard: validate input data
        for sym, val in list(current_allocation.items()) + list(target_allocation.items()):
            if not isinstance(val, (int, float)) or np.isnan(val) or np.isinf(val):
                logger.warning(f"Invalid allocation value for {sym}: {val}, replacing with 0")
                if sym in current_allocation:
                    current_allocation[sym] = 0.0
                if sym in target_allocation:
                    target_allocation[sym] = 0.0

        for symbol in set(list(current_allocation.keys()) + list(target_allocation.keys())):
            current = current_allocation.get(symbol, 0.0)
            target = target_allocation.get(symbol, 0.0)
            drift = abs(current - target)
            drift_per_symbol[symbol] = drift
            max_drift = max(max_drift, drift)

        requires_rebalancing = max_drift >= self.drift_threshold_pct

        return DriftAnalysis(
            total_drift_pct=max_drift,
            current_allocation=current_allocation.copy(),
            target_allocation=target_allocation.copy(),
            drift_per_symbol=drift_per_symbol,
            requires_rebalancing=requires_rebalancing,
            drift_threshold_pct=self.drift_threshold_pct,
        )

    def generate_rebalancing_plan(
        self,
        current_allocation: Dict[str, float],
        target_allocation: Dict[str, float],
        portfolio_value_eur: float,
        constraints: Optional[List[Dict]] = None,
        execution_cost_bps: float = 10.0,
        tax_rate_pct: float = 27.0,
    ) -> RebalancingPlan:
        """
        Generate rebalancing trade plan.

        Parameters:
        -----------
        current_allocation : dict
            {symbol: current weight %}
        target_allocation : dict
            {symbol: target weight %}
        portfolio_value_eur : float
            Total portfolio value in EUR
        constraints : list
            Constraint violation checks
        execution_cost_bps : float
            Execution cost in basis points
        tax_rate_pct : float
            Tax rate (%)

        Returns:
        --------
        RebalancingPlan with trades and costs
        """
        trades: List[Tuple[str, str, float]] = []
        constraint_violations: List[str] = []

        # Calculate trades needed
        for symbol in set(list(current_allocation.keys()) + list(target_allocation.keys())):
            current = current_allocation.get(symbol, 0.0)
            target = target_allocation.get(symbol, 0.0)
            delta = target - current

            if abs(delta) > 0.01:  # Ignore tiny differences
                side = "BUY" if delta > 0 else "SELL"
                trades.append((symbol, side, abs(delta)))

        if not trades:
            return RebalancingPlan(
                trades=[],
                total_cost_pct=0.0,
                estimated_slippage_pct=0.0,
                tax_impact_pct=0.0,
                feasible=True,
                constraint_violations=[],
                estimated_execution_time_min=0.0,
            )

        # Calculate costs
        total_trades_pct = sum(pct for _, _, pct in trades)
        execution_cost = (total_trades_pct * execution_cost_bps) / 10000

        # Tax on realized gains (simplified: assume 50% gains on sells)
        sell_volume = sum(pct for _, side, pct in trades if side == "SELL")
        tax_impact = (sell_volume * 0.5 * tax_rate_pct) / 100

        # Estimate execution time (1% per 2 minutes)
        estimated_execution_time = (total_trades_pct / 1.0) * 2.0

        # Check constraints (FIXED: now actually validates)
        final_allocation = target_allocation.copy()
        manager = get_constraint_manager()
        is_valid, violations = manager.validate_allocation(final_allocation)
        constraint_violations = violations

        feasible = len(constraint_violations) == 0

        return RebalancingPlan(
            trades=trades,
            total_cost_pct=execution_cost,
            estimated_slippage_pct=(total_trades_pct * 0.05) / 100,  # 0.05% slippage per %
            tax_impact_pct=tax_impact,
            feasible=feasible,
            constraint_violations=constraint_violations,
            estimated_execution_time_min=estimated_execution_time,
        )

    def break_into_tranches(
        self,
        plan: RebalancingPlan,
        max_tranche_pct: float = 2.0,
        tranche_interval_min: float = 5.0,
    ) -> List[RebalancingPlan]:
        """
        Break large rebalancing into smaller tranches.

        Parameters:
        -----------
        plan : RebalancingPlan
            Full rebalancing plan
        max_tranche_pct : float
            Maximum % per tranche
        tranche_interval_min : float
            Minutes between tranches

        Returns:
        --------
        List of smaller rebalancing plans
        """
        if not plan.trades:
            return [plan]

        total_volume = sum(pct for _, _, pct in plan.trades)

        if total_volume <= max_tranche_pct:
            return [plan]

        # Split proportionally
        num_tranches = int(np.ceil(total_volume / max_tranche_pct))
        tranches = []

        for i in range(num_tranches):
            tranche_trades = [
                (symbol, side, pct / num_tranches)
                for symbol, side, pct in plan.trades
            ]

            tranche = RebalancingPlan(
                trades=tranche_trades,
                total_cost_pct=plan.total_cost_pct / num_tranches,
                estimated_slippage_pct=plan.estimated_slippage_pct / num_tranches,
                tax_impact_pct=plan.tax_impact_pct / num_tranches,
                feasible=plan.feasible,
                constraint_violations=plan.constraint_violations,
                estimated_execution_time_min=tranche_interval_min,
            )
            tranches.append(tranche)

        logger.info(f"Split rebalancing into {num_tranches} tranches of {max_tranche_pct}% each")
        return tranches

    def estimate_cost_breakdown(
        self,
        plan: RebalancingPlan,
    ) -> Dict[str, float]:
        """
        Estimate cost breakdown for rebalancing.

        Parameters:
        -----------
        plan : RebalancingPlan
            Rebalancing plan

        Returns:
        --------
        Cost breakdown (execution, slippage, tax, total)
        """
        total_cost = (
            plan.total_cost_pct +
            plan.estimated_slippage_pct +
            plan.tax_impact_pct
        )

        return {
            "execution_cost_pct": plan.total_cost_pct,
            "slippage_cost_pct": plan.estimated_slippage_pct,
            "tax_cost_pct": plan.tax_impact_pct,
            "total_cost_pct": total_cost,
            "net_benefit_pct": 0.0,  # Placeholder: benefit minus cost
        }

    def validate_rebalancing_feasibility(
        self,
        plan: RebalancingPlan,
        current_cash_pct: float = 2.0,
    ) -> Tuple[bool, List[str]]:
        """
        Validate rebalancing plan feasibility.

        Parameters:
        -----------
        plan : RebalancingPlan
            Plan to validate
        current_cash_pct : float
            Current cash position (%)

        Returns:
        --------
        (is_feasible, list of issues)
        """
        issues = plan.constraint_violations.copy()

        # Check if enough cash for buys
        total_buy = sum(pct for _, side, pct in plan.trades if side == "BUY")
        if total_buy > current_cash_pct:
            issues.append(f"Insufficient cash: need {total_buy:.1f}%, have {current_cash_pct:.1f}%")

        # Check estimated execution time
        if plan.estimated_execution_time_min > 60:
            issues.append(f"Long execution time: {plan.estimated_execution_time_min:.0f} minutes")

        return len(issues) == 0, issues

    def record_rebalancing(self, plan: RebalancingPlan) -> None:
        """Record completed rebalancing in history."""
        self.rebalancing_history.append(plan)
        logger.info(f"Recorded rebalancing: {len(plan.trades)} trades, cost {plan.total_cost_pct:.2f}%")

    def get_rebalancing_history(self, limit: int = 10) -> List[RebalancingPlan]:
        """Get recent rebalancing history."""
        return self.rebalancing_history[-limit:]


# Global instance
_rebalancing_engine: RebalancingEngine = None


def get_rebalancing_engine() -> RebalancingEngine:
    """Get or create rebalancing engine."""
    global _rebalancing_engine
    if _rebalancing_engine is None:
        _rebalancing_engine = RebalancingEngine()
    return _rebalancing_engine
