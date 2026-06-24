"""Global portfolio optimization across asset classes."""

import logging
from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraint:
    """Portfolio optimization constraint."""
    asset_class: str
    min_weight: float = 0.0
    max_weight: float = 1.0
    target_weight: Optional[float] = None


class GlobalPortfolioOptimizer:
    """Optimize portfolio across asset classes and regions."""

    def __init__(self):
        self.constraints: List[OptimizationConstraint] = []
        self.expected_returns: Dict[str, float] = {}
        self.volatilities: Dict[str, float] = {}
        self.correlations: Dict[Tuple[str, str], float] = {}

    def add_constraint(self, constraint: OptimizationConstraint):
        """Add optimization constraint."""
        self.constraints.append(constraint)

    def set_expected_returns(self, returns: Dict[str, float]):
        """Set expected returns for assets."""
        self.expected_returns = returns

    def set_volatilities(self, vols: Dict[str, float]):
        """Set volatilities for assets."""
        self.volatilities = vols

    def set_correlations(self, corr: Dict[Tuple[str, str], float]):
        """Set correlation matrix."""
        self.correlations = corr

    def calculate_efficient_frontier(
        self,
        num_points: int = 50
    ) -> List[Dict]:
        """
        Calculate efficient frontier.

        Returns list of (risk, return, weights) tuples along frontier.
        """
        frontier = []

        # Target returns from minimum to maximum
        if not self.expected_returns:
            logger.warning("No expected returns set")
            return frontier

        min_ret = min(self.expected_returns.values())
        max_ret = max(self.expected_returns.values())

        target_returns = np.linspace(min_ret, max_ret, num_points)

        for target_ret in target_returns:
            weights = self._optimize_for_return(target_ret)
            if weights is not None:
                risk = self._calculate_portfolio_risk(weights)
                frontier.append({
                    "return": target_ret,
                    "risk": risk,
                    "sharpe_ratio": (target_ret - 0.02) / max(risk, 0.001),  # Assume 2% risk-free rate
                    "weights": weights
                })

        return frontier

    def find_optimal_portfolio(
        self,
        target_return: Optional[float] = None,
        risk_aversion: float = 1.0
    ) -> Dict:
        """
        Find optimal portfolio weights.

        Args:
            target_return: Target return (if None, use Sharpe-optimal)
            risk_aversion: Risk aversion coefficient (higher = more conservative)

        Returns:
            Optimal weights dict
        """
        if target_return is not None:
            weights = self._optimize_for_return(target_return)
        else:
            weights = self._optimize_for_sharpe(risk_aversion)

        if weights is None:
            logger.warning("Optimization failed, returning equal weights")
            n_assets = len(self.expected_returns)
            weights = {asset: 1.0 / n_assets for asset in self.expected_returns.keys()}

        return {
            "weights": weights,
            "expected_return": self._calculate_portfolio_return(weights),
            "risk": self._calculate_portfolio_risk(weights),
            "sharpe_ratio": self._calculate_sharpe_ratio(weights)
        }

    def _optimize_for_return(self, target_return: float) -> Optional[Dict[str, float]]:
        """Optimize portfolio for specific return target."""
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return None

        # Simple optimizer: allocate to assets by return relative to target
        weights = {}
        total_weight = 0

        for asset in assets:
            expected_ret = self.expected_returns.get(asset, 0.02)
            vol = self.volatilities.get(asset, 0.2)

            # Weight inversely to volatility, proportional to excess return
            if vol > 0:
                weight = max(0, (expected_ret - 0.02) / (vol ** 2)) if expected_ret > 0.02 else 0.01
            else:
                weight = 0.01

            weights[asset] = weight
            total_weight += weight

        # Normalize to sum to 1
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Apply constraints
        weights = self._apply_constraints(weights)

        return weights

    def _optimize_for_sharpe(self, risk_aversion: float) -> Optional[Dict[str, float]]:
        """Optimize portfolio for maximum Sharpe ratio."""
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return None

        # Inverse volatility weighting (minimum variance portfolio)
        weights = {}
        total_weight = 0

        for asset in assets:
            vol = self.volatilities.get(asset, 0.2)

            if vol > 0:
                weight = 1.0 / (vol ** (2 * risk_aversion))
            else:
                weight = 1.0

            weights[asset] = weight
            total_weight += weight

        # Normalize
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Apply constraints
        weights = self._apply_constraints(weights)

        return weights

    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply weight constraints."""
        for constraint in self.constraints:
            asset = constraint.asset_class

            if asset in weights:
                # Apply min/max bounds
                weights[asset] = max(constraint.min_weight, min(weights[asset], constraint.max_weight))

                # Apply target if specified
                if constraint.target_weight is not None:
                    weights[asset] = constraint.target_weight

        # Re-normalize if needed
        total = sum(weights.values())
        if total > 0 and abs(total - 1.0) > 0.01:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _calculate_portfolio_return(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio expected return."""
        return_sum = sum(
            weights.get(asset, 0) * self.expected_returns.get(asset, 0.02)
            for asset in self.expected_returns.keys()
        )
        return return_sum

    def _calculate_portfolio_risk(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio risk (standard deviation)."""
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return 0.0

        # Construct covariance matrix
        cov_matrix = np.zeros((n, n))

        for i, asset_i in enumerate(assets):
            for j, asset_j in enumerate(assets):
                vol_i = self.volatilities.get(asset_i, 0.2)
                vol_j = self.volatilities.get(asset_j, 0.2)

                if i == j:
                    cov_matrix[i, j] = vol_i ** 2
                else:
                    corr_key = (asset_i, asset_j)
                    corr = self.correlations.get(corr_key, 0.5)
                    cov_matrix[i, j] = corr * vol_i * vol_j

        # Portfolio variance
        w_array = np.array([weights.get(asset, 0) for asset in assets])

        try:
            variance = w_array @ cov_matrix @ w_array
            return np.sqrt(max(variance, 0))
        except Exception as e:
            logger.error(f"Error calculating portfolio risk: {e}")
            return 0.0

    def _calculate_sharpe_ratio(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio Sharpe ratio."""
        ret = self._calculate_portfolio_return(weights)
        risk = self._calculate_portfolio_risk(weights)
        risk_free_rate = 0.02

        if risk > 0:
            return (ret - risk_free_rate) / risk
        return 0.0

    def calculate_rebalancing_plan(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        portfolio_value: float,
        max_transaction_cost_pct: float = 0.1
    ) -> Dict:
        """
        Calculate rebalancing transactions needed.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            portfolio_value: Total portfolio value in USD
            max_transaction_cost_pct: Max acceptable transaction cost

        Returns:
            Rebalancing plan with trades
        """
        trades = []
        total_transaction_cost = 0.0

        for asset in set(current_weights.keys()) | set(target_weights.keys()):
            current_wt = current_weights.get(asset, 0.0)
            target_wt = target_weights.get(asset, 0.0)

            if abs(current_wt - target_wt) < 0.001:
                continue  # Skip if difference is negligible

            current_value = current_wt * portfolio_value
            target_value = target_wt * portfolio_value
            value_change = target_value - current_value

            # Estimate transaction cost (0.1% for liquid assets)
            transaction_cost = abs(value_change) * 0.001

            trades.append({
                "asset": asset,
                "current_weight": current_wt,
                "target_weight": target_wt,
                "weight_change": target_wt - current_wt,
                "current_value": current_value,
                "target_value": target_value,
                "trade_amount": value_change,
                "trade_direction": "BUY" if value_change > 0 else "SELL",
                "transaction_cost": transaction_cost
            })

            total_transaction_cost += transaction_cost

        total_cost_pct = (total_transaction_cost / portfolio_value * 100) if portfolio_value > 0 else 0

        return {
            "trades": sorted(trades, key=lambda x: abs(x["trade_amount"]), reverse=True),
            "total_transaction_cost": total_transaction_cost,
            "total_cost_pct": total_cost_pct,
            "recommended": total_cost_pct <= max_transaction_cost_pct,
            "message": "Rebalancing recommended" if total_cost_pct <= max_transaction_cost_pct else f"Rebalancing cost {total_cost_pct:.2f}% exceeds limit"
        }


# Global optimizer instance
_optimizer: Optional[GlobalPortfolioOptimizer] = None


def init_global_optimizer() -> GlobalPortfolioOptimizer:
    """Initialize global optimizer."""
    global _optimizer
    if _optimizer is None:
        _optimizer = GlobalPortfolioOptimizer()
        logger.info("Global portfolio optimizer initialized")
    return _optimizer


def get_global_optimizer() -> Optional[GlobalPortfolioOptimizer]:
    """Get global optimizer."""
    return _optimizer
