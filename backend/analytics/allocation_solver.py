"""
Phase 325: Allocation Solver

Solve for optimal allocations given return or risk targets.
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class SolverResult:
    """Allocation solver result."""
    target_type: str  # "return" or "volatility"
    target_value: float
    allocation: Dict[str, float]  # symbol -> weight %
    expected_return_pct: float
    expected_volatility_pct: float
    sharpe_ratio: float
    feasible: bool
    explanation: str


class AllocationSolver:
    """Solve for optimal allocations given constraints."""

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize allocation solver."""
        self.risk_free_rate = risk_free_rate

    def solve_for_return(
        self,
        historical_returns: Dict[str, pd.Series],
        target_return_pct: float,
        max_single_position_pct: float = 25.0,
    ) -> SolverResult:
        """
        Find allocation that targets a specific return.

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        target_return_pct : float
            Target annual return (%)
        max_single_position_pct : float
            Maximum position size (%)

        Returns:
        --------
        SolverResult with optimal allocation
        """
        symbols = list(historical_returns.keys())
        n = len(symbols)

        # Align and calculate stats
        min_len = min(len(s) for s in historical_returns.values())
        returns_array = np.array([historical_returns[s].tail(min_len).values for s in symbols]).T

        mean_returns = returns_array.mean(axis=0) * 252
        cov_matrix = np.cov(returns_array.T) * 252

        # Optimization
        def objective(w):
            port_vol = np.sqrt(np.dot(w, np.dot(cov_matrix, w)))
            return port_vol

        def return_constraint(w):
            return np.dot(w, mean_returns) - target_return_pct

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": return_constraint},
        ]

        bounds = tuple((0, max_single_position_pct / 100) for _ in range(n))
        x0 = np.array([1.0 / n] * n)

        try:
            result = minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500},
            )

            if result.success:
                weights = result.x
                port_return = np.dot(weights, mean_returns)
                port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
                sharpe = (port_return - self.risk_free_rate) / (port_vol + 1e-6)

                allocation = {s: float(w) * 100 for s, w in zip(symbols, weights)}

                return SolverResult(
                    target_type="return",
                    target_value=target_return_pct,
                    allocation=allocation,
                    expected_return_pct=port_return * 100,
                    expected_volatility_pct=port_vol * 100,
                    sharpe_ratio=sharpe,
                    feasible=True,
                    explanation=f"Optimal allocation found targeting {target_return_pct:.1f}% return",
                )
            else:
                # Fallback to equal weight
                equal_weight = 100 / n
                allocation = {s: equal_weight for s in symbols}

                return SolverResult(
                    target_type="return",
                    target_value=target_return_pct,
                    allocation=allocation,
                    expected_return_pct=np.dot([1/n]*n, mean_returns) * 100,
                    expected_volatility_pct=0,
                    sharpe_ratio=0,
                    feasible=False,
                    explanation=f"Target {target_return_pct:.1f}% return not feasible with constraints",
                )
        except Exception as e:
            logger.error(f"Error solving for return: {e}")
            equal_weight = 100 / n
            allocation = {s: equal_weight for s in symbols}
            return SolverResult(
                target_type="return",
                target_value=target_return_pct,
                allocation=allocation,
                expected_return_pct=0,
                expected_volatility_pct=0,
                sharpe_ratio=0,
                feasible=False,
                explanation=f"Optimization failed: {str(e)}",
            )

    def solve_for_volatility(
        self,
        historical_returns: Dict[str, pd.Series],
        target_volatility_pct: float,
        max_single_position_pct: float = 25.0,
    ) -> SolverResult:
        """
        Find allocation that targets a specific volatility (risk).

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        target_volatility_pct : float
            Target annual volatility (%)
        max_single_position_pct : float
            Maximum position size (%)

        Returns:
        --------
        SolverResult with optimal allocation
        """
        symbols = list(historical_returns.keys())
        n = len(symbols)

        # Align and calculate stats
        min_len = min(len(s) for s in historical_returns.values())
        returns_array = np.array([historical_returns[s].tail(min_len).values for s in symbols]).T

        mean_returns = returns_array.mean(axis=0) * 252
        cov_matrix = np.cov(returns_array.T) * 252

        # Optimization: maximize return for given volatility
        def objective(w):
            port_return = np.dot(w, mean_returns)
            return -port_return  # Negative because we minimize

        def vol_constraint(w):
            target_vol = target_volatility_pct / 100
            return target_vol - np.sqrt(np.dot(w, np.dot(cov_matrix, w)))

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "ineq", "fun": vol_constraint},
        ]

        bounds = tuple((0, max_single_position_pct / 100) for _ in range(n))
        x0 = np.array([1.0 / n] * n)

        try:
            result = minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500},
            )

            if result.success:
                weights = result.x
                port_return = np.dot(weights, mean_returns)
                port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
                sharpe = (port_return - self.risk_free_rate) / (port_vol + 1e-6)

                allocation = {s: float(w) * 100 for s, w in zip(symbols, weights)}

                return SolverResult(
                    target_type="volatility",
                    target_value=target_volatility_pct,
                    allocation=allocation,
                    expected_return_pct=port_return * 100,
                    expected_volatility_pct=port_vol * 100,
                    sharpe_ratio=sharpe,
                    feasible=True,
                    explanation=f"Optimal allocation found targeting {target_volatility_pct:.1f}% volatility",
                )
            else:
                equal_weight = 100 / n
                allocation = {s: equal_weight for s in symbols}
                return SolverResult(
                    target_type="volatility",
                    target_value=target_volatility_pct,
                    allocation=allocation,
                    expected_return_pct=0,
                    expected_volatility_pct=0,
                    sharpe_ratio=0,
                    feasible=False,
                    explanation=f"Target {target_volatility_pct:.1f}% volatility not feasible",
                )
        except Exception as e:
            logger.error(f"Error solving for volatility: {e}")
            equal_weight = 100 / n
            allocation = {s: equal_weight for s in symbols}
            return SolverResult(
                target_type="volatility",
                target_value=target_volatility_pct,
                allocation=allocation,
                expected_return_pct=0,
                expected_volatility_pct=0,
                sharpe_ratio=0,
                feasible=False,
                explanation=f"Optimization failed: {str(e)}",
            )


# Global instance
_allocation_solver: AllocationSolver = None


def get_allocation_solver() -> AllocationSolver:
    """Get or create allocation solver."""
    global _allocation_solver
    if _allocation_solver is None:
        _allocation_solver = AllocationSolver()
    return _allocation_solver
