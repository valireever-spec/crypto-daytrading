"""Advanced risk management and portfolio risk calculations."""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class VaRCalculator:
    """Value at Risk calculations using Monte Carlo simulation."""

    @staticmethod
    def monte_carlo_var(
        returns: np.ndarray,
        confidence: float = 0.95,
        time_horizon_days: int = 1,
        simulations: int = 10000,
    ) -> float:
        """
        Calculate VaR using Monte Carlo simulation.

        Args:
            returns: Historical returns array
            confidence: Confidence level (0.95 = 95%)
            time_horizon_days: Number of days to project
            simulations: Number of Monte Carlo simulations

        Returns:
            Value at Risk (as percentage of portfolio value)
        """
        if len(returns) < 30:
            return 0.0

        # Calculate statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Scale to time horizon
        scaled_mean = mean_return * time_horizon_days
        scaled_std = std_return * np.sqrt(time_horizon_days)

        # Run Monte Carlo simulation
        simulated_returns = np.random.normal(
            loc=scaled_mean, scale=scaled_std, size=simulations
        )

        # Calculate percentile (VaR)
        var_percentile = (1 - confidence) * 100
        var = np.percentile(simulated_returns, var_percentile)

        return float(var)

    @staticmethod
    def historical_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        """
        Calculate VaR using historical method.

        Args:
            returns: Historical returns array
            confidence: Confidence level

        Returns:
            Value at Risk
        """
        if len(returns) < 20:
            return 0.0

        var_percentile = (1 - confidence) * 100
        var = np.percentile(returns, var_percentile)
        return float(var)

    @staticmethod
    def cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).
        Average of losses beyond VaR.

        Args:
            returns: Historical returns array
            confidence: Confidence level

        Returns:
            CVaR (average of worst X% returns)
        """
        if len(returns) < 20:
            return 0.0

        var = VaRCalculator.historical_var(returns, confidence)
        cvar = returns[returns <= var].mean()
        return float(cvar) if not np.isnan(cvar) else float(var)


class DrawdownCalculator:
    """Drawdown analysis and monitoring."""

    @staticmethod
    def calculate_drawdown(prices: np.ndarray) -> Tuple[float, float, int]:
        """
        Calculate current drawdown from peak.

        Args:
            prices: Price array

        Returns:
            (current_drawdown_pct, max_drawdown_pct, days_in_drawdown)
        """
        if len(prices) < 2:
            return 0.0, 0.0, 0

        # Calculate running maximum
        running_max = np.maximum.accumulate(prices)

        # Calculate drawdown
        drawdown = (prices - running_max) / running_max

        # Current drawdown
        current_drawdown = float(drawdown[-1])

        # Maximum drawdown
        max_drawdown = float(np.min(drawdown))

        # Days in current drawdown
        current_peak_idx = np.where(prices == running_max[-1])[0][-1]
        days_in_drawdown = len(prices) - current_peak_idx - 1

        return current_drawdown, max_drawdown, int(days_in_drawdown)

    @staticmethod
    def max_drawdown_duration(prices: np.ndarray) -> int:
        """Get duration of maximum historical drawdown in days."""
        if len(prices) < 2:
            return 0

        running_max = np.maximum.accumulate(prices)
        drawdown = (prices - running_max) / running_max

        # Find consecutive days below 0
        in_drawdown = drawdown < 0
        drawdown_runs = np.diff(
            np.where(np.diff(np.concatenate(([0], in_drawdown, [0]))) != 0)[0]
        )

        if len(drawdown_runs) == 0:
            return 0

        return int(
            np.max(drawdown_runs[1::2])
        )  # Every other element is drawdown duration


class CorrelationAnalyzer:
    """Portfolio correlation and concentration risk analysis."""

    @staticmethod
    def calculate_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate correlation matrix between assets.

        Args:
            returns_df: DataFrame with returns by symbol

        Returns:
            Correlation matrix
        """
        if returns_df.empty or len(returns_df) < 2:
            return pd.DataFrame()

        return returns_df.corr()

    @staticmethod
    def concentration_risk(weights: Dict[str, float]) -> float:
        """
        Calculate portfolio concentration risk (Herfindahl index).

        Range: 0 (perfectly diversified) to 1 (fully concentrated)

        Args:
            weights: Position weights {symbol: weight}

        Returns:
            HHI concentration metric (0-1)
        """
        if not weights:
            return 0.0

        total = sum(weights.values())
        if total == 0:
            return 0.0

        normalized = np.array([w / total for w in weights.values()])
        hhi = np.sum(normalized**2)

        return float(hhi)

    @staticmethod
    def systemic_risk(
        returns_df: pd.DataFrame, portfolio_returns: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate systemic (beta) and idiosyncratic risk for each asset.

        Args:
            returns_df: Asset returns
            portfolio_returns: Portfolio returns

        Returns:
            Beta and idiosyncratic volatility for each asset
        """
        if returns_df.empty or len(portfolio_returns) < 2:
            return {}

        results = {}

        for symbol in returns_df.columns:
            asset_returns = returns_df[symbol].values

            # Calculate beta
            covariance = np.cov(asset_returns, portfolio_returns)[0, 1]
            variance = np.var(portfolio_returns)

            beta = covariance / variance if variance > 0 else 0

            # Calculate idiosyncratic risk
            predicted = beta * portfolio_returns
            residuals = asset_returns - predicted
            idiosyncratic_vol = np.std(residuals)

            results[symbol] = {
                "beta": float(beta),
                "idiosyncratic_volatility": float(idiosyncratic_vol),
                "systematic_risk": abs(float(beta)),
            }

        return results


class VolatilityCalculator:
    """Volatility calculations and regime detection."""

    @staticmethod
    def calculate_volatility(returns: np.ndarray, annualized: bool = True) -> float:
        """
        Calculate volatility (standard deviation of returns).

        Args:
            returns: Return array
            annualized: If True, annualize the volatility (252 trading days)

        Returns:
            Volatility as percentage
        """
        if len(returns) < 2:
            return 0.0

        vol = np.std(returns)

        if annualized:
            vol *= np.sqrt(252)

        return float(vol)

    @staticmethod
    def garch_volatility(returns: np.ndarray) -> float:
        """
        Simple GARCH(1,1) volatility estimate.

        Args:
            returns: Return array

        Returns:
            Estimated volatility
        """
        if len(returns) < 10:
            return VolatilityCalculator.calculate_volatility(returns)

        # GARCH(1,1) parameters
        omega = 0.00001
        alpha = 0.05
        beta = 0.94

        # Initialize
        long_var = np.var(returns)
        h = long_var

        # Calculate conditional variance
        for ret in returns[-20:]:  # Use recent returns
            h = omega + alpha * (ret**2) + beta * h

        return float(np.sqrt(h))

    @staticmethod
    def ewma_volatility(returns: np.ndarray, span: int = 30) -> float:
        """
        Exponentially weighted moving average volatility.

        Args:
            returns: Return array
            span: Number of days for EWMA

        Returns:
            EWMA volatility
        """
        if len(returns) < 2:
            return 0.0

        squared_returns = returns**2
        ewma = pd.Series(squared_returns).ewm(span=span).mean()

        vol = np.sqrt(ewma.iloc[-1])
        return float(vol)


class PortfolioRiskCalculator:
    """Integrated portfolio risk calculator."""

    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.historical_prices: Dict[str, List[float]] = {}

    def add_position(self, symbol: str, quantity: float, entry_price: float):
        """Add a position to the portfolio."""
        self.positions[symbol] = {
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": entry_price,
        }

    def update_price(self, symbol: str, price: float):
        """Update current price for a symbol."""
        if symbol in self.positions:
            self.positions[symbol]["current_price"] = price

    def add_price_history(self, symbol: str, prices: List[float]):
        """Add historical price data."""
        self.historical_prices[symbol] = prices

    def calculate_portfolio_var(self, confidence: float = 0.95) -> float:
        """
        Calculate portfolio Value at Risk.

        Args:
            confidence: Confidence level (0.95 = 95%)

        Returns:
            VaR as percentage of total portfolio value
        """
        total_value = self.get_portfolio_value()
        if total_value == 0:
            return 0.0

        # For simplicity, use weighted average of individual VaRs
        total_var = 0.0

        for symbol, pos in self.positions.items():
            if symbol in self.historical_prices:
                prices = np.array(self.historical_prices[symbol])
                returns = np.diff(prices) / prices[:-1]

                position_value = pos["quantity"] * pos["current_price"]
                weight = position_value / total_value

                var = VaRCalculator.historical_var(returns, confidence)
                total_var += weight * var

        return float(total_var)

    def calculate_portfolio_cvar(self, confidence: float = 0.95) -> float:
        """Calculate Conditional VaR for portfolio."""
        total_value = self.get_portfolio_value()
        if total_value == 0:
            return 0.0

        total_cvar = 0.0

        for symbol, pos in self.positions.items():
            if symbol in self.historical_prices:
                prices = np.array(self.historical_prices[symbol])
                returns = np.diff(prices) / prices[:-1]

                position_value = pos["quantity"] * pos["current_price"]
                weight = position_value / total_value

                cvar = VaRCalculator.cvar(returns, confidence)
                total_cvar += weight * cvar

        return float(total_cvar)

    def calculate_drawdown(self) -> Dict:
        """Calculate portfolio drawdown metrics."""
        prices = []

        for symbol, pos in self.positions.items():
            if symbol in self.historical_prices:
                hist_prices = np.array(self.historical_prices[symbol])
                position_prices = hist_prices * pos["quantity"]
                prices.append(position_prices)

        if not prices:
            return {"current": 0.0, "max": 0.0, "duration_days": 0}

        portfolio_prices = np.sum(prices, axis=0)
        current, max_dd, duration = DrawdownCalculator.calculate_drawdown(
            portfolio_prices
        )

        return {
            "current": float(current),
            "max": float(max_dd),
            "duration_days": int(duration),
        }

    def calculate_concentration_risk(self) -> float:
        """Calculate portfolio concentration risk."""
        total_value = self.get_portfolio_value()
        if total_value == 0:
            return 0.0

        weights = {}
        for symbol, pos in self.positions.items():
            position_value = pos["quantity"] * pos["current_price"]
            weights[symbol] = position_value

        return CorrelationAnalyzer.concentration_risk(weights)

    def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        total = 0.0
        for pos in self.positions.values():
            total += pos["quantity"] * pos["current_price"]
        return total

    def get_position_values(self) -> Dict[str, float]:
        """Get value of each position."""
        return {
            symbol: pos["quantity"] * pos["current_price"]
            for symbol, pos in self.positions.items()
        }

    def calculate_risk_summary(self) -> Dict:
        """Calculate comprehensive risk summary."""
        return {
            "portfolio_value": self.get_portfolio_value(),
            "var_95": self.calculate_portfolio_var(0.95),
            "var_99": self.calculate_portfolio_var(0.99),
            "cvar_95": self.calculate_portfolio_cvar(0.95),
            "drawdown": self.calculate_drawdown(),
            "concentration": self.calculate_concentration_risk(),
            "positions": self.get_position_values(),
        }
