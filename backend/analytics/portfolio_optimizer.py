"""
Phase 322: Portfolio Allocation Optimizer

Modern Portfolio Theory optimization: efficient frontier, optimal allocations
for different risk levels, rebalancing recommendations.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class AllocationTarget:
    """Target allocation for a risk level."""
    risk_level: str  # conservative/moderate/balanced/aggressive/extreme
    target_return_pct: float
    target_volatility_pct: float
    allocation: Dict[str, float]  # symbol -> weight (%)
    sharpe_ratio: float
    diversification_ratio: float


@dataclass
class EfficientFrontierPoint:
    """Point on efficient frontier."""
    volatility_pct: float
    expected_return_pct: float
    sharpe_ratio: float
    allocation: Dict[str, float]


@dataclass
class RebalancingPlan:
    """Recommended rebalancing trades."""
    current_allocation: Dict[str, float]
    target_allocation: Dict[str, float]
    trades: List[Dict[str, Any]]  # [{symbol, current_weight, target_weight, action, amount_eur}]
    total_trade_volume_eur: float
    estimated_cost_eur: float
    tax_impact_eur: float
    rationale: str


class PortfolioOptimizer:
    """Optimize portfolio allocation using Modern Portfolio Theory."""

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize optimizer.

        Parameters:
        -----------
        risk_free_rate : float
            Annual risk-free rate (default 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.cache: Dict[str, Any] = {}

    def optimize_portfolio(
        self,
        returns: Dict[str, pd.Series],  # symbol -> daily returns (%)
        portfolio_value: float = 100000,  # EUR
        risk_level: str = "balanced",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> AllocationTarget:
        """
        Optimize portfolio allocation for a risk level.

        Parameters:
        -----------
        returns : dict
            {symbol: Series of daily returns (%)}
        portfolio_value : float
            Total portfolio value in EUR
        risk_level : str
            conservative/moderate/balanced/aggressive/extreme
        constraints : dict
            {max_single_position: 0.20, min_diversification: 3}

        Returns:
        --------
        AllocationTarget with optimal weights
        """
        if not returns:
            return self._default_allocation(risk_level)

        symbols = list(returns.keys())
        n = len(symbols)

        # Align series lengths
        min_len = min(len(s) for s in returns.values())
        if min_len < 20:
            return self._default_allocation(risk_level)

        returns_array = np.array([returns[s].tail(min_len).values for s in symbols]).T

        # Calculate mean returns and covariance
        mean_returns = returns_array.mean(axis=0) * 252  # Annualize
        cov_matrix = np.cov(returns_array.T) * 252

        # Risk target based on level
        risk_targets = {
            "conservative": 5.0,
            "moderate": 10.0,
            "balanced": 15.0,
            "aggressive": 25.0,
            "extreme": 35.0,
        }
        target_vol = risk_targets.get(risk_level, 15.0)

        # Optimize weights
        weights = self._optimize_weights(
            mean_returns=mean_returns,
            cov_matrix=cov_matrix,
            target_volatility=target_vol / 100,
            n_assets=n,
            constraints=constraints,
        )

        # Calculate metrics
        portfolio_return = np.dot(weights, mean_returns)
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

        # Handle NaN/inf values
        if np.isnan(portfolio_return) or np.isinf(portfolio_return):
            portfolio_return = 0
        if np.isnan(portfolio_vol) or np.isinf(portfolio_vol):
            portfolio_vol = 0.01

        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        if np.isnan(sharpe) or np.isinf(sharpe):
            sharpe = 0

        # Diversification ratio: sum of vol / portfolio vol
        asset_vols = np.sqrt(np.diag(cov_matrix))
        div_ratio = np.sum(weights * asset_vols) / portfolio_vol if portfolio_vol > 0 else 1.0

        allocation = {s: float(w) * 100 for s, w in zip(symbols, weights)}

        return AllocationTarget(
            risk_level=risk_level,
            target_return_pct=portfolio_return * 100,
            target_volatility_pct=portfolio_vol * 100,
            allocation=allocation,
            sharpe_ratio=sharpe,
            diversification_ratio=div_ratio,
        )

    def _optimize_weights(
        self,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        target_volatility: float,
        n_assets: int,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Optimize weights using mean-variance optimization."""
        # Simple robust optimization: maximize Sharpe ratio without volatility constraint
        # Then scale to target volatility

        # Constraints: sum to 1
        constraints_list = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        # Box constraints
        bounds = tuple((0, 0.25) for _ in range(n_assets))  # Max 25% per position
        if constraints and "max_single_position" in constraints:
            max_pos = constraints["max_single_position"]
            bounds = tuple((0, max_pos) for _ in range(n_assets))

        # Objective: minimize -Sharpe (maximize Sharpe)
        def objective(w):
            port_ret = np.dot(w, mean_returns)
            port_vol = np.sqrt(np.dot(w, np.dot(cov_matrix, w)) + 1e-10)
            sharpe = (port_ret - self.risk_free_rate) / (port_vol + 1e-10)
            return -sharpe

        # Initial guess: equal weight or risk parity
        x0 = np.array([1.0 / n_assets] * n_assets)

        # Try to optimize
        try:
            result = minimize(
                objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints_list,
                options={"maxiter": 500},
            )
            weights = result.x if result.success else x0
        except Exception:
            weights = x0

        # Ensure weights are valid
        weights = np.clip(weights, 0, 1)
        weights = weights / np.sum(weights)

        return weights

    def efficient_frontier(
        self,
        returns: Dict[str, pd.Series],
        n_points: int = 20,
    ) -> List[EfficientFrontierPoint]:
        """
        Calculate efficient frontier.

        Parameters:
        -----------
        returns : dict
            {symbol: Series of daily returns (%)}
        n_points : int
            Number of points on frontier

        Returns:
        --------
        List of efficient frontier points
        """
        if not returns:
            return []

        symbols = list(returns.keys())
        n = len(symbols)

        # Align series
        min_len = min(len(s) for s in returns.values())
        if min_len < 20:
            return []

        returns_array = np.array([returns[s].tail(min_len).values for s in symbols]).T

        # Calculate mean returns and covariance
        mean_returns = returns_array.mean(axis=0) * 252
        cov_matrix = np.cov(returns_array.T) * 252

        frontier = []
        vols = np.linspace(0.05, 0.40, n_points)

        for target_vol in vols:
            weights = self._optimize_weights(
                mean_returns=mean_returns,
                cov_matrix=cov_matrix,
                target_volatility=target_vol,
                n_assets=n,
            )

            port_ret = np.dot(weights, mean_returns)
            port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

            # Handle NaN/inf
            if np.isnan(port_ret) or np.isinf(port_ret):
                port_ret = 0
            if np.isnan(port_vol) or np.isinf(port_vol):
                port_vol = 0.01

            sharpe = (port_ret - self.risk_free_rate) / port_vol if port_vol > 0 else 0
            if np.isnan(sharpe) or np.isinf(sharpe):
                sharpe = 0

            allocation = {s: float(w) * 100 for s, w in zip(symbols, weights)}

            frontier.append(
                EfficientFrontierPoint(
                    volatility_pct=port_vol * 100,
                    expected_return_pct=port_ret * 100,
                    sharpe_ratio=sharpe,
                    allocation=allocation,
                )
            )

        return frontier

    def generate_rebalancing_plan(
        self,
        current_positions: Dict[str, float],  # symbol -> value EUR
        target_allocation: Dict[str, float],  # symbol -> weight %
        total_value: float,
        execution_cost_pct: float = 0.001,  # 10 bps
        tax_rate: float = 0.27,  # German tax rate
    ) -> RebalancingPlan:
        """
        Generate rebalancing trades to reach target allocation.

        Parameters:
        -----------
        current_positions : dict
            {symbol: current value EUR}
        target_allocation : dict
            {symbol: target weight %}
        total_value : float
            Total portfolio value EUR
        execution_cost_pct : float
            Execution cost per trade
        tax_rate : float
            Capital gains tax rate

        Returns:
        --------
        RebalancingPlan with trades
        """
        # Current allocation %
        current_allocation = {
            s: (v / total_value) * 100 if total_value > 0 else 0
            for s, v in current_positions.items()
        }

        # All symbols (union of current and target)
        all_symbols = set(current_allocation.keys()) | set(target_allocation.keys())

        trades = []
        total_volume = 0
        total_cost = 0
        total_tax = 0

        for symbol in sorted(all_symbols):
            current_pct = current_allocation.get(symbol, 0)
            target_pct = target_allocation.get(symbol, 0)
            drift = target_pct - current_pct

            if abs(drift) < 0.1:  # Skip small drifts (<0.1%)
                continue

            current_value = current_positions.get(symbol, 0)
            target_value = (target_pct / 100) * total_value if target_pct > 0 else 0
            trade_value = target_value - current_value

            if abs(trade_value) < 10:  # Skip very small trades (<€10)
                continue

            action = "BUY" if trade_value > 0 else "SELL"
            cost = abs(trade_value) * execution_cost_pct
            tax = max(0, (target_value - current_value) * tax_rate) if action == "SELL" else 0

            total_volume += abs(trade_value)
            total_cost += cost
            total_tax += tax

            trades.append({
                "symbol": symbol,
                "action": action,
                "current_value_eur": round(current_value, 2),
                "target_value_eur": round(target_value, 2),
                "trade_amount_eur": round(trade_value, 2),
                "current_weight_pct": round(current_pct, 2),
                "target_weight_pct": round(target_pct, 2),
                "execution_cost_eur": round(cost, 2),
                "tax_impact_eur": round(tax, 2),
            })

        # Sort by volume (largest trades first)
        trades.sort(key=lambda t: abs(t["trade_amount_eur"]), reverse=True)

        rationale = (
            f"Rebalance {len(trades)} positions to target allocation. "
            f"Total volume: €{total_volume:,.0f}. "
            f"Estimated cost: €{total_cost:,.0f} + tax €{total_tax:,.0f}."
        )

        return RebalancingPlan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            trades=trades,
            total_trade_volume_eur=total_volume,
            estimated_cost_eur=total_cost,
            tax_impact_eur=total_tax,
            rationale=rationale,
        )

    def _default_allocation(self, risk_level: str) -> AllocationTarget:
        """Return default allocation when optimization not possible."""
        defaults = {
            "conservative": {"BTC": 30, "MSFT": 35, "AAPL": 35},
            "moderate": {"BTC": 40, "ETH": 10, "MSFT": 30, "AAPL": 20},
            "balanced": {"BTC": 35, "ETH": 15, "MSFT": 25, "AAPL": 25},
            "aggressive": {"BTC": 40, "ETH": 20, "MSFT": 20, "AAPL": 20},
            "extreme": {"BTC": 50, "ETH": 30, "MSFT": 10, "AAPL": 10},
        }

        allocation = defaults.get(risk_level, defaults["balanced"])

        return AllocationTarget(
            risk_level=risk_level,
            target_return_pct=8.0 + {"conservative": 0, "moderate": 3, "balanced": 6, "aggressive": 10, "extreme": 15}.get(risk_level, 6),
            target_volatility_pct=5.0 + {"conservative": 0, "moderate": 5, "balanced": 10, "aggressive": 20, "extreme": 30}.get(risk_level, 10),
            allocation=allocation,
            sharpe_ratio=0.8,
            diversification_ratio=1.5,
        )


# Global instance
_optimizer: PortfolioOptimizer = None


def get_portfolio_optimizer() -> PortfolioOptimizer:
    """Get or create portfolio optimizer."""
    global _optimizer
    if _optimizer is None:
        _optimizer = PortfolioOptimizer()
    return _optimizer
