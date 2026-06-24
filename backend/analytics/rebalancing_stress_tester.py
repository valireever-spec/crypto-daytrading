"""
Phase 327: Rebalancing Stress Tester

Test rebalancing plans under Phase 326 scenarios.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StressTestResult:
    """Result of stress test for rebalancing."""
    scenario_name: str
    allocation_under_stress: Dict[str, float]
    constraint_violations: List[str]
    portfolio_volatility_pct: float
    worst_case_drawdown_pct: float
    recovery_time_days: int
    feasible_under_stress: bool
    recommendation: str


class RebalancingStressTester:
    """Test rebalancing plans under market stress scenarios."""

    def __init__(self):
        """Initialize stress tester."""
        self.test_history: List[StressTestResult] = []

    def stress_test_allocation(
        self,
        target_allocation: Dict[str, float],
        scenario_returns: Dict[str, float],  # symbol -> return %
        scenario_volatilities: Dict[str, float],  # symbol -> volatility %
        scenario_correlations: np.ndarray,  # correlation matrix
        scenario_name: str = "Custom",
        duration_days: int = 252,
    ) -> StressTestResult:
        """
        Stress test allocation under scenario.

        Parameters:
        -----------
        target_allocation : dict
            {symbol: target weight %}
        scenario_returns : dict
            {symbol: expected return %}
        scenario_volatilities : dict
            {symbol: volatility %}
        scenario_correlations : array
            Correlation matrix
        scenario_name : str
            Name of scenario
        duration_days : int
            Time horizon

        Returns:
        --------
        StressTestResult with allocation performance
        """
        symbols = list(target_allocation.keys())
        weights = np.array([target_allocation.get(s, 0) / 100 for s in symbols])

        # Calculate portfolio metrics under scenario
        returns = np.array([scenario_returns.get(s, 0) for s in symbols])
        volatilities = np.array([scenario_volatilities.get(s, 0) for s in symbols])

        port_return = np.dot(weights, returns)
        port_vol = np.sqrt(np.dot(weights, np.dot(
            scenario_correlations * np.outer(volatilities, volatilities),
            weights
        )))

        # Simulate drawdown
        np.random.seed(42)
        cumulative_returns = [1.0]
        for _ in range(duration_days):
            daily_ret = np.random.normal(port_return / 252, port_vol / np.sqrt(252))
            cumulative_returns.append(cumulative_returns[-1] * (1 + daily_ret / 100))

        cumulative_returns = np.array(cumulative_returns)
        drawdown = np.max(cumulative_returns / np.maximum.accumulate(cumulative_returns) - 1)
        worst_drawdown_pct = drawdown * 100

        # Estimate recovery time (when back to peak)
        peak_idx = np.argmax(cumulative_returns)
        after_peak = cumulative_returns[peak_idx:]
        recovery_idx = np.where(after_peak >= cumulative_returns[peak_idx])[0]
        recovery_days = recovery_idx[0] if len(recovery_idx) > 1 else duration_days

        # Check for constraint violations under stress
        violations = []
        if port_vol > 50.0:
            violations.append(f"High volatility under stress: {port_vol:.1f}%")
        if worst_drawdown_pct < -30.0:
            violations.append(f"Large drawdown: {worst_drawdown_pct:.1f}%")

        feasible = len(violations) == 0

        # Recommendation
        if worst_drawdown_pct < -20.0:
            recommendation = "INCREASE_DIVERSIFICATION"
        elif port_vol > 40.0:
            recommendation = "REDUCE_VOLATILITY"
        elif recovery_days > 100:
            recommendation = "ADD_DEFENSIVE_ASSETS"
        else:
            recommendation = "ACCEPTABLE"

        result = StressTestResult(
            scenario_name=scenario_name,
            allocation_under_stress=target_allocation.copy(),
            constraint_violations=violations,
            portfolio_volatility_pct=port_vol,
            worst_case_drawdown_pct=worst_drawdown_pct,
            recovery_time_days=recovery_days,
            feasible_under_stress=feasible,
            recommendation=recommendation,
        )

        self.test_history.append(result)
        return result

    def compare_allocations_under_stress(
        self,
        allocations: List[Dict[str, float]],
        allocation_names: List[str],
        scenario_returns: Dict[str, float],
        scenario_volatilities: Dict[str, float],
        scenario_correlations: np.ndarray,
        scenario_name: str = "Custom",
    ) -> List[StressTestResult]:
        """
        Compare multiple allocations under scenario stress.

        Parameters:
        -----------
        allocations : list
            List of {symbol: weight %} dicts
        allocation_names : list
            Names for each allocation
        scenario_returns : dict
            {symbol: return %}
        scenario_volatilities : dict
            {symbol: volatility %}
        scenario_correlations : array
            Correlation matrix
        scenario_name : str
            Scenario name

        Returns:
        --------
        List of StressTestResults for comparison
        """
        results = []

        for alloc, name in zip(allocations, allocation_names):
            result = self.stress_test_allocation(
                target_allocation=alloc,
                scenario_returns=scenario_returns,
                scenario_volatilities=scenario_volatilities,
                scenario_correlations=scenario_correlations,
                scenario_name=f"{scenario_name} - {name}",
            )
            results.append(result)

        # Rank by worst-case drawdown
        results.sort(key=lambda r: r.worst_case_drawdown_pct, reverse=True)

        logger.info(f"Compared {len(allocations)} allocations under {scenario_name}")
        return results

    def get_robust_allocation(
        self,
        candidate_allocations: List[Dict[str, float]],
        scenarios: List[Dict],  # {name, returns, volatilities, correlations}
    ) -> tuple:
        """
        Find allocation most robust across scenarios.

        Parameters:
        -----------
        candidate_allocations : list
            List of candidate allocations
        scenarios : list
            List of scenarios to test

        Returns:
        --------
        (best_allocation, stress_results for that allocation)
        """
        if not candidate_allocations:
            return None, []

        # Test each allocation across all scenarios
        all_results = {}

        for i, alloc in enumerate(candidate_allocations):
            alloc_name = f"Allocation_{i+1}"
            worst_drawdowns = []

            for scenario in scenarios:
                result = self.stress_test_allocation(
                    target_allocation=alloc,
                    scenario_returns=scenario.get("returns", {}),
                    scenario_volatilities=scenario.get("volatilities", {}),
                    scenario_correlations=scenario.get("correlations", np.eye(len(alloc))),
                    scenario_name=scenario.get("name", "Unknown"),
                )
                worst_drawdowns.append(result.worst_case_drawdown_pct)

            # Score: best average drawdown across scenarios
            avg_drawdown = np.mean(worst_drawdowns)
            all_results[i] = {
                "allocation": alloc,
                "avg_drawdown": avg_drawdown,
                "results": all_results.get(i, {}).get("results", []),
            }

        # Find best
        best_idx = min(all_results.keys(), key=lambda k: all_results[k]["avg_drawdown"])
        best_alloc = all_results[best_idx]["allocation"]

        logger.info(
            f"Found robust allocation: Allocation_{best_idx+1} "
            f"(avg drawdown {all_results[best_idx]['avg_drawdown']:.1f}%)"
        )

        return best_alloc, all_results[best_idx].get("results", [])

    def get_test_summary(self, limit: int = 10) -> Dict[str, any]:
        """
        Get summary of stress testing.

        Parameters:
        -----------
        limit : int
            Number of recent tests to include

        Returns:
        --------
        Summary dict
        """
        recent = self.test_history[-limit:]

        if not recent:
            return {
                "total_tests": 0,
                "recent_tests": [],
                "avg_worst_drawdown_pct": 0,
                "feasible_count": 0,
            }

        drawdowns = [r.worst_case_drawdown_pct for r in recent]
        feasible = sum(1 for r in recent if r.feasible_under_stress)

        return {
            "total_tests": len(self.test_history),
            "recent_tests": [
                {
                    "scenario": r.scenario_name,
                    "volatility_pct": round(r.portfolio_volatility_pct, 2),
                    "worst_drawdown_pct": round(r.worst_case_drawdown_pct, 2),
                    "recovery_days": r.recovery_time_days,
                    "feasible": r.feasible_under_stress,
                }
                for r in recent
            ],
            "avg_worst_drawdown_pct": round(np.mean(drawdowns), 2),
            "feasible_count": feasible,
            "feasible_ratio_pct": round((feasible / len(recent)) * 100, 1),
        }


# Global instance
_stress_tester: RebalancingStressTester = None


def get_rebalancing_stress_tester() -> RebalancingStressTester:
    """Get or create stress tester."""
    global _stress_tester
    if _stress_tester is None:
        _stress_tester = RebalancingStressTester()
    return _stress_tester
