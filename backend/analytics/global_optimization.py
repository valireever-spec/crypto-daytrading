"""Global portfolio optimization across asset classes (refactored for quality)."""

import logging
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from dataclasses import dataclass

from backend.config.asset_config import PortfolioOptimizationConfig

logger = logging.getLogger(__name__)


class OptimizationError(ValueError):
    """Raised when optimization fails."""
    pass


class InvalidConstraintError(ValueError):
    """Raised when constraint is invalid."""
    pass


@dataclass
class OptimizationConstraint:
    """Portfolio optimization constraint with validation.

    Attributes:
        asset_class: Asset class identifier
        min_weight: Minimum allocation weight (0-1)
        max_weight: Maximum allocation weight (0-1)
        target_weight: Target allocation (optional)
    """
    asset_class: str
    min_weight: float = 0.0
    max_weight: float = 1.0
    target_weight: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate constraint after initialization.

        Raises:
            InvalidConstraintError: If constraint is invalid
        """
        self.validate()

    def validate(self) -> None:
        """Validate constraint values.

        Raises:
            InvalidConstraintError: If any value is invalid
        """
        if not self.asset_class or not isinstance(self.asset_class, str):
            raise InvalidConstraintError(f"Invalid asset_class: {self.asset_class}")
        if not 0 <= self.min_weight <= 1:
            raise InvalidConstraintError(f"min_weight must be 0-1, got {self.min_weight}")
        if not 0 <= self.max_weight <= 1:
            raise InvalidConstraintError(f"max_weight must be 0-1, got {self.max_weight}")
        if self.min_weight > self.max_weight:
            raise InvalidConstraintError(
                f"min_weight {self.min_weight} > max_weight {self.max_weight}"
            )
        if self.target_weight is not None:
            if not 0 <= self.target_weight <= 1:
                raise InvalidConstraintError(f"target_weight must be 0-1, got {self.target_weight}")


class GlobalPortfolioOptimizer:
    """Optimize portfolio across asset classes and regions (no global state).

    Uses config-driven constants for risk-free rate and transaction costs.
    All parameters are validated at input.

    Example:
        >>> optimizer = GlobalPortfolioOptimizer()
        >>> optimizer.set_expected_returns({"crypto": 0.25, "equity": 0.10})
        >>> optimal = optimizer.find_optimal_portfolio()
    """

    def __init__(
        self,
        risk_free_rate: Optional[float] = None,
        transaction_cost_pct: Optional[float] = None,
    ) -> None:
        """Initialize portfolio optimizer.

        Args:
            risk_free_rate: Risk-free rate for Sharpe calculation. If None, uses config.
            transaction_cost_pct: Transaction cost as % of trade. If None, uses config.

        Raises:
            ValueError: If rates are invalid
        """
        self.risk_free_rate = risk_free_rate if risk_free_rate is not None else PortfolioOptimizationConfig.RISK_FREE_RATE
        self.transaction_cost_pct = transaction_cost_pct if transaction_cost_pct is not None else PortfolioOptimizationConfig.TRANSACTION_COST_PCT

        if not 0 <= self.risk_free_rate <= 1:
            raise ValueError(f"Risk-free rate must be 0-1, got {self.risk_free_rate}")
        if not 0 <= self.transaction_cost_pct <= 1:
            raise ValueError(f"Transaction cost must be 0-1, got {self.transaction_cost_pct}")

        self.constraints: List[OptimizationConstraint] = []
        self.expected_returns: Dict[str, float] = {}
        self.volatilities: Dict[str, float] = {}
        self.correlations: Dict[Tuple[str, str], float] = {}

    def add_constraint(self, constraint: OptimizationConstraint) -> None:
        """Add optimization constraint.

        Args:
            constraint: Optimization constraint

        Raises:
            InvalidConstraintError: If constraint is invalid
        """
        if not isinstance(constraint, OptimizationConstraint):
            raise InvalidConstraintError(f"Expected OptimizationConstraint, got {type(constraint)}")
        constraint.validate()
        self.constraints.append(constraint)

    def set_expected_returns(self, returns: Dict[str, float]) -> None:
        """Set expected returns for assets.

        Args:
            returns: Dict of {asset: expected_return}

        Raises:
            ValueError: If any return is invalid
        """
        if not isinstance(returns, dict):
            raise ValueError(f"Returns must be dict, got {type(returns)}")
        for asset, ret in returns.items():
            if not isinstance(ret, (int, float)):
                raise ValueError(f"Return for {asset} must be numeric, got {type(ret)}")
        self.expected_returns = returns

    def set_volatilities(self, vols: Dict[str, float]) -> None:
        """Set volatilities for assets.

        Args:
            vols: Dict of {asset: volatility}

        Raises:
            ValueError: If any volatility is invalid
        """
        if not isinstance(vols, dict):
            raise ValueError(f"Volatilities must be dict, got {type(vols)}")
        for asset, vol in vols.items():
            if not 0 <= vol <= 1:
                raise ValueError(f"Volatility for {asset} must be 0-1, got {vol}")
        self.volatilities = vols

    def set_correlations(self, corr: Dict[Tuple[str, str], float]) -> None:
        """Set correlation matrix.

        Args:
            corr: Dict of {(asset1, asset2): correlation}

        Raises:
            ValueError: If any correlation is invalid
        """
        if not isinstance(corr, dict):
            raise ValueError(f"Correlations must be dict, got {type(corr)}")
        for pair, corr_val in corr.items():
            if not -1 <= corr_val <= 1:
                raise ValueError(f"Correlation for {pair} must be -1 to 1, got {corr_val}")
        self.correlations = corr

    def calculate_efficient_frontier(
        self,
        num_points: int = 50
    ) -> List[Dict[str, Any]]:
        """Calculate efficient frontier.

        Args:
            num_points: Number of points on frontier

        Returns:
            List of {return, risk, sharpe_ratio, weights} dicts

        Raises:
            OptimizationError: If expected returns not set
        """
        if not self.expected_returns:
            raise OptimizationError("No expected returns set")
        if num_points < 2:
            raise ValueError(f"num_points must be >= 2, got {num_points}")

        frontier = []

        min_ret = min(self.expected_returns.values())
        max_ret = max(self.expected_returns.values())

        target_returns = np.linspace(min_ret, max_ret, num_points)

        for target_ret in target_returns:
            weights = self._optimize_for_return(target_ret)
            if weights is not None:
                risk = self._calculate_portfolio_risk(weights)
                sharpe = self._calculate_sharpe_ratio(weights)
                frontier.append({
                    "return": float(target_ret),
                    "risk": risk,
                    "sharpe_ratio": sharpe,
                    "weights": weights
                })

        return frontier

    def find_optimal_portfolio(
        self,
        target_return: Optional[float] = None,
        risk_aversion: float = 1.0
    ) -> Dict[str, Any]:
        """Find optimal portfolio weights.

        Args:
            target_return: Target return (if None, use Sharpe-optimal)
            risk_aversion: Risk aversion coefficient (higher = more conservative)

        Returns:
            Dict with weights, expected_return, risk, sharpe_ratio

        Raises:
            OptimizationError: If optimization fails
        """
        if not self.expected_returns:
            raise OptimizationError("No expected returns set")
        if risk_aversion <= 0:
            raise ValueError(f"Risk aversion must be > 0, got {risk_aversion}")

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
        """Optimize portfolio for specific return target.

        Args:
            target_return: Target expected return

        Returns:
            Optimized weights dict or None if optimization fails
        """
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return None

        weights: Dict[str, float] = {}
        total_weight = 0.0

        for asset in assets:
            expected_ret = self.expected_returns.get(asset, self.risk_free_rate)
            vol = self.volatilities.get(asset, 0.2)

            if vol > 0:
                excess_ret = expected_ret - self.risk_free_rate
                weight = max(0, excess_ret / (vol ** 2)) if excess_ret > 0 else 0.01
            else:
                weight = 0.01

            weights[asset] = weight
            total_weight += weight

        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        weights = self._apply_constraints(weights)
        return weights

    def _optimize_for_sharpe(self, risk_aversion: float) -> Optional[Dict[str, float]]:
        """Optimize portfolio for maximum Sharpe ratio.

        Args:
            risk_aversion: Risk aversion coefficient

        Returns:
            Optimized weights dict or None if optimization fails
        """
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return None

        weights: Dict[str, float] = {}
        total_weight = 0.0

        for asset in assets:
            vol = self.volatilities.get(asset, 0.2)

            if vol > 0:
                weight = 1.0 / (vol ** (2 * risk_aversion))
            else:
                weight = 1.0

            weights[asset] = weight
            total_weight += weight

        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        weights = self._apply_constraints(weights)
        return weights

    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply weight constraints with validation.

        Args:
            weights: Initial weights dict

        Returns:
            Constrained weights dict
        """
        for constraint in self.constraints:
            asset = constraint.asset_class

            if asset in weights:
                weights[asset] = max(
                    constraint.min_weight,
                    min(weights[asset], constraint.max_weight)
                )

                if constraint.target_weight is not None:
                    weights[asset] = constraint.target_weight

        total = sum(weights.values())
        if total > 0 and abs(total - 1.0) > 0.01:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _calculate_portfolio_return(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio expected return.

        Args:
            weights: Portfolio weights dict

        Returns:
            Expected portfolio return
        """
        return sum(
            weights.get(asset, 0) * self.expected_returns.get(asset, self.risk_free_rate)
            for asset in self.expected_returns.keys()
        )

    def _calculate_portfolio_risk(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio risk (standard deviation).

        Args:
            weights: Portfolio weights dict

        Returns:
            Portfolio standard deviation
        """
        assets = list(self.expected_returns.keys())
        n = len(assets)

        if n == 0:
            return 0.0

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

        w_array = np.array([weights.get(asset, 0) for asset in assets])

        try:
            variance = w_array @ cov_matrix @ w_array
            return float(np.sqrt(max(variance, 0)))
        except Exception as e:
            logger.error(f"Error calculating portfolio risk: {e}")
            return 0.0

    def _calculate_sharpe_ratio(self, weights: Dict[str, float]) -> float:
        """Calculate portfolio Sharpe ratio.

        Args:
            weights: Portfolio weights dict

        Returns:
            Sharpe ratio
        """
        ret = self._calculate_portfolio_return(weights)
        risk = self._calculate_portfolio_risk(weights)

        if risk > 0:
            return (ret - self.risk_free_rate) / risk
        return 0.0

    def calculate_rebalancing_plan(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        portfolio_value: float,
        max_transaction_cost_pct: float = 0.1
    ) -> Dict[str, Any]:
        """Calculate rebalancing transactions needed.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            portfolio_value: Total portfolio value in USD
            max_transaction_cost_pct: Max acceptable transaction cost %

        Returns:
            Rebalancing plan with trades and costs

        Raises:
            ValueError: If inputs are invalid
        """
        if not isinstance(current_weights, dict) or not isinstance(target_weights, dict):
            raise ValueError("Weights must be dicts")
        if portfolio_value <= 0:
            raise ValueError(f"Portfolio value must be positive, got {portfolio_value}")
        if not 0 <= max_transaction_cost_pct <= 100:
            raise ValueError(f"Max cost % must be 0-100, got {max_transaction_cost_pct}")

        trades = []
        total_transaction_cost = 0.0

        for asset in set(current_weights.keys()) | set(target_weights.keys()):
            current_wt = current_weights.get(asset, 0.0)
            target_wt = target_weights.get(asset, 0.0)

            if abs(current_wt - target_wt) < 0.001:
                continue

            current_value = current_wt * portfolio_value
            target_value = target_wt * portfolio_value
            value_change = target_value - current_value

            transaction_cost = abs(value_change) * self.transaction_cost_pct

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
