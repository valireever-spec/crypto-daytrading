"""
Phase 326: Scenario Customizer

Create custom market scenarios by adjusting market conditions.
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MarketScenario:
    """Custom market scenario specification."""
    name: str
    return_multiplier: float = 1.0  # Multiply expected returns by this
    volatility_multiplier: float = 1.0  # Multiply volatility by this
    correlation_multiplier: float = 1.0  # Adjust correlations (0-2)
    duration_days: int = 252  # Time horizon
    description: str = ""


@dataclass
class CustomScenarioResult:
    """Result of custom scenario analysis."""
    scenario_name: str
    expected_return_pct: float
    volatility_pct: float
    sharpe_ratio: float
    percentile_5th_pct: float
    percentile_95th_pct: float
    probability_positive_pct: float
    market_conditions: Dict[str, float]


class ScenarioCustomizer:
    """Create and analyze custom market scenarios."""

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize scenario customizer."""
        self.risk_free_rate = risk_free_rate
        self.predefined_scenarios = self._init_predefined_scenarios()

    def _init_predefined_scenarios(self) -> Dict[str, MarketScenario]:
        """Initialize predefined scenarios."""
        return {
            "bull_market": MarketScenario(
                name="Bull Market",
                return_multiplier=1.5,
                volatility_multiplier=0.8,
                correlation_multiplier=0.7,
                description="Strong growth, lower volatility, reduced correlations",
            ),
            "bear_market": MarketScenario(
                name="Bear Market",
                return_multiplier=0.5,
                volatility_multiplier=1.5,
                correlation_multiplier=1.3,
                description="Declining market, elevated volatility, high correlations",
            ),
            "high_volatility": MarketScenario(
                name="High Volatility",
                return_multiplier=1.0,
                volatility_multiplier=2.0,
                correlation_multiplier=0.9,
                description="Extreme market swings, normal returns",
            ),
            "stagflation": MarketScenario(
                name="Stagflation",
                return_multiplier=0.7,
                volatility_multiplier=1.8,
                correlation_multiplier=1.2,
                description="Low growth, high inflation/volatility",
            ),
            "deflation": MarketScenario(
                name="Deflation",
                return_multiplier=0.6,
                volatility_multiplier=1.2,
                correlation_multiplier=0.9,
                description="Economic contraction, falling prices",
            ),
            "recovery": MarketScenario(
                name="Recovery",
                return_multiplier=1.8,
                volatility_multiplier=0.9,
                correlation_multiplier=0.8,
                description="Post-crisis recovery, strong growth",
            ),
        }

    def get_predefined_scenario(self, scenario_name: str) -> Optional[MarketScenario]:
        """
        Get a predefined scenario.

        Parameters:
        -----------
        scenario_name : str
            Name of predefined scenario

        Returns:
        --------
        MarketScenario or None if not found
        """
        return self.predefined_scenarios.get(scenario_name.lower())

    def list_predefined_scenarios(self) -> Dict[str, str]:
        """
        List all predefined scenarios.

        Returns:
        --------
        {scenario_name: description}
        """
        return {
            name: scenario.description
            for name, scenario in self.predefined_scenarios.items()
        }

    def create_custom_scenario(
        self,
        name: str,
        return_multiplier: float = 1.0,
        volatility_multiplier: float = 1.0,
        correlation_multiplier: float = 1.0,
        duration_days: int = 252,
        description: str = "",
    ) -> MarketScenario:
        """
        Create a custom scenario.

        Parameters:
        -----------
        name : str
            Scenario name
        return_multiplier : float
            Multiply expected returns (1.0 = no change)
        volatility_multiplier : float
            Multiply volatility (1.0 = no change)
        correlation_multiplier : float
            Adjust correlations (1.0 = no change, clipped to [0.1, 2.0])
        duration_days : int
            Time horizon in days

        Returns:
        --------
        MarketScenario
        """
        # Validate inputs
        return_multiplier = max(0.1, return_multiplier)
        volatility_multiplier = max(0.1, volatility_multiplier)
        correlation_multiplier = np.clip(correlation_multiplier, 0.1, 2.0)
        duration_days = max(1, int(duration_days))

        scenario = MarketScenario(
            name=name,
            return_multiplier=return_multiplier,
            volatility_multiplier=volatility_multiplier,
            correlation_multiplier=correlation_multiplier,
            duration_days=duration_days,
            description=description,
        )

        logger.info(f"Created custom scenario: {name} (return x{return_multiplier}, vol x{volatility_multiplier})")
        return scenario

    def apply_scenario_to_returns(
        self,
        scenario: MarketScenario,
        historical_returns: Dict[str, pd.Series],
    ) -> Dict[str, pd.Series]:
        """
        Apply scenario adjustments to historical returns.

        Parameters:
        -----------
        scenario : MarketScenario
            Scenario to apply
        historical_returns : dict
            {symbol: Series of daily returns (%)}

        Returns:
        --------
        {symbol: adjusted Series of daily returns (%)}
        """
        adjusted_returns = {}

        for symbol, returns in historical_returns.items():
            # Apply return multiplier (adjust mean)
            mean_return = returns.mean()
            adjusted_mean = mean_return * scenario.return_multiplier

            # Apply volatility multiplier (adjust std)
            std_return = returns.std()
            adjusted_std = std_return * scenario.volatility_multiplier

            # Standardize returns
            if std_return > 0:
                standardized = (returns - mean_return) / std_return
            else:
                standardized = returns - mean_return

            # Apply scenario adjustments
            adjusted = standardized * adjusted_std + adjusted_mean

            adjusted_returns[symbol] = adjusted

        logger.debug(f"Applied scenario {scenario.name} to {len(adjusted_returns)} symbols")
        return adjusted_returns

    def adjust_correlation_matrix(
        self,
        cov_matrix: np.ndarray,
        scenario: MarketScenario,
    ) -> np.ndarray:
        """
        Adjust correlation matrix for scenario.

        Parameters:
        -----------
        cov_matrix : array
            Original covariance matrix
        scenario : MarketScenario
            Scenario with correlation adjustments

        Returns:
        --------
        Adjusted covariance matrix
        """
        # Extract correlations
        std_devs = np.sqrt(np.diag(cov_matrix))
        corr_matrix = cov_matrix / np.outer(std_devs, std_devs)

        # Adjust correlations toward 1 (increase) or 0 (decrease)
        if scenario.correlation_multiplier > 1.0:
            # Increase correlations (move toward 1)
            alpha = scenario.correlation_multiplier - 1.0
            adjusted_corr = corr_matrix + (1 - corr_matrix) * alpha * 0.5
            np.fill_diagonal(adjusted_corr, 1.0)
        elif scenario.correlation_multiplier < 1.0:
            # Decrease correlations (move toward 0)
            alpha = 1.0 - scenario.correlation_multiplier
            adjusted_corr = corr_matrix * (1 - alpha * 0.5)
            np.fill_diagonal(adjusted_corr, 1.0)
        else:
            adjusted_corr = corr_matrix

        # Reconstruct covariance matrix
        adjusted_cov = adjusted_corr * np.outer(std_devs, std_devs)

        # Guard: ensure covariance matrix is valid (positive semi-definite)
        # Check that diagonal is positive
        if np.any(np.diag(adjusted_cov) <= 0):
            logger.warning("Invalid covariance matrix detected, using regularization")
            # Add small positive value to diagonal (Tikhonov regularization)
            adjusted_cov += np.eye(len(std_devs)) * 1e-6 * np.mean(np.diag(cov_matrix))

        return adjusted_cov

    def analyze_scenario(
        self,
        scenario: MarketScenario,
        historical_returns: Dict[str, pd.Series],
        allocation: Dict[str, float],
        base_metrics: Dict[str, float],
    ) -> CustomScenarioResult:
        """
        Analyze portfolio under a custom scenario.

        Parameters:
        -----------
        scenario : MarketScenario
            Scenario to analyze
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocation : dict
            {symbol: weight %}
        base_metrics : dict
            Base case metrics (expected_return_pct, volatility_pct)

        Returns:
        --------
        CustomScenarioResult with scenario analysis
        """
        # Apply scenario to returns
        adjusted_returns = self.apply_scenario_to_returns(scenario, historical_returns)

        # Calculate scenario metrics
        symbols = list(adjusted_returns.keys())
        returns_array = np.array([adjusted_returns[s].values for s in symbols]).T

        mean_returns = returns_array.mean(axis=0) * 252
        cov_matrix = np.cov(returns_array.T) * 252

        # Adjust correlation for scenario
        cov_matrix = self.adjust_correlation_matrix(cov_matrix, scenario)

        # Calculate portfolio metrics
        weights = np.array([allocation.get(s, 0) / 100 for s in symbols])
        port_return = np.dot(weights, mean_returns) * scenario.return_multiplier
        port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

        sharpe = (port_return - self.risk_free_rate) / (port_vol + 1e-6)

        # Monte Carlo simulation for percentiles
        np.random.seed(42)
        simulations = []
        for _ in range(5000):
            daily_returns = np.random.normal(
                port_return / 252,
                port_vol / np.sqrt(252),
                scenario.duration_days,
            )
            total_return = (1 + daily_returns / 100).prod() - 1
            simulations.append(total_return * 100)

        simulations = np.array(simulations)

        return CustomScenarioResult(
            scenario_name=scenario.name,
            expected_return_pct=float(port_return * 100),
            volatility_pct=float(port_vol * 100),
            sharpe_ratio=float(sharpe),
            percentile_5th_pct=float(np.percentile(simulations, 5)),
            percentile_95th_pct=float(np.percentile(simulations, 95)),
            probability_positive_pct=float((simulations > 0).mean() * 100),
            market_conditions={
                "return_multiplier": scenario.return_multiplier,
                "volatility_multiplier": scenario.volatility_multiplier,
                "correlation_multiplier": scenario.correlation_multiplier,
                "duration_days": scenario.duration_days,
            },
        )


# Global instance
_scenario_customizer: ScenarioCustomizer = None


def get_scenario_customizer() -> ScenarioCustomizer:
    """Get or create scenario customizer."""
    global _scenario_customizer
    if _scenario_customizer is None:
        _scenario_customizer = ScenarioCustomizer()
    return _scenario_customizer
