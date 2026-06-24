"""
Phase 325: Scenario Analysis Engine

Monte Carlo simulation and scenario-based analysis for portfolio recommendations.
"""

import logging
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Scenario analysis results."""
    scenario_name: str
    probability_pct: float
    expected_return_pct: float
    worst_case_pct: float
    best_case_pct: float
    probability_loss_pct: float
    expected_shortfall_pct: float


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results."""
    n_simulations: int
    expected_return_pct: float
    volatility_pct: float
    percentile_5th_pct: float
    percentile_25th_pct: float
    percentile_50th_pct: float
    percentile_75th_pct: float
    percentile_95th_pct: float
    probability_positive_pct: float
    best_case_pct: float
    worst_case_pct: float


class ScenarioAnalyzer:
    """Analyze portfolio scenarios and Monte Carlo simulations."""

    def __init__(self):
        """Initialize scenario analyzer."""
        self.risk_free_rate = 0.02

    def monte_carlo_simulation(
        self,
        historical_returns: Dict[str, pd.Series],  # symbol -> daily returns (%)
        allocation: Dict[str, float],  # symbol -> weight %
        time_horizon_days: int = 252,
        n_simulations: int = 10000,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation for portfolio.

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocation : dict
            {symbol: weight %}
        time_horizon_days : int
            Number of days to simulate
        n_simulations : int
            Number of simulation paths

        Returns:
        --------
        MonteCarloResult with distribution metrics
        """
        # Calculate mean returns and covariance
        symbols = list(allocation.keys())
        returns_list = []

        for symbol in symbols:
            if symbol in historical_returns:
                returns_list.append(historical_returns[symbol].values)

        if not returns_list:
            return MonteCarloResult(
                n_simulations=n_simulations,
                expected_return_pct=0,
                volatility_pct=0,
                percentile_5th_pct=0,
                percentile_25th_pct=0,
                percentile_50th_pct=0,
                percentile_75th_pct=0,
                percentile_95th_pct=0,
                probability_positive_pct=0,
                best_case_pct=0,
                worst_case_pct=0,
            )

        returns_array = np.array(returns_list).T
        mean_returns = returns_array.mean(axis=0) * 252  # Annualize
        cov_matrix = np.cov(returns_array.T) * 252

        # Portfolio mean and vol
        weights = np.array([allocation.get(s, 0) / 100 for s in symbols])
        port_mean = np.dot(weights, mean_returns)
        port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

        # Run simulations
        np.random.seed(42)
        simulations = []

        for _ in range(n_simulations):
            # Daily returns for time horizon
            daily_returns = np.random.normal(
                port_mean / 252,
                port_vol / np.sqrt(252),
                time_horizon_days,
            )

            # Cumulative return
            total_return = (1 + daily_returns / 100).prod() - 1
            simulations.append(total_return * 100)

        simulations = np.array(simulations)

        return MonteCarloResult(
            n_simulations=n_simulations,
            expected_return_pct=float(np.mean(simulations)),
            volatility_pct=float(np.std(simulations)),
            percentile_5th_pct=float(np.percentile(simulations, 5)),
            percentile_25th_pct=float(np.percentile(simulations, 25)),
            percentile_50th_pct=float(np.percentile(simulations, 50)),
            percentile_75th_pct=float(np.percentile(simulations, 75)),
            percentile_95th_pct=float(np.percentile(simulations, 95)),
            probability_positive_pct=float((simulations > 0).mean() * 100),
            best_case_pct=float(np.max(simulations)),
            worst_case_pct=float(np.min(simulations)),
        )

    def analyze_upside_scenario(
        self,
        historical_returns: Dict[str, pd.Series],
        allocation: Dict[str, float],
        target_return_pct: float = 10.0,
    ) -> ScenarioResult:
        """
        Analyze upside scenario (market outperforms expectations).

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocation : dict
            {symbol: weight %}
        target_return_pct : float
            Target return for probability calculation

        Returns:
        --------
        ScenarioResult for upside scenario
        """
        mc_result = self.monte_carlo_simulation(
            historical_returns=historical_returns,
            allocation=allocation,
            n_simulations=5000,
        )

        # Probability of exceeding target
        prob_positive = mc_result.probability_positive_pct

        return ScenarioResult(
            scenario_name="Upside Scenario",
            probability_pct=prob_positive,
            expected_return_pct=mc_result.percentile_75th_pct,
            worst_case_pct=mc_result.percentile_50th_pct,
            best_case_pct=mc_result.percentile_95th_pct,
            probability_loss_pct=100 - prob_positive,
            expected_shortfall_pct=mc_result.percentile_95th_pct,
        )

    def analyze_downside_scenario(
        self,
        historical_returns: Dict[str, pd.Series],
        allocation: Dict[str, float],
    ) -> ScenarioResult:
        """
        Analyze downside scenario (market underperforms).

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocation : dict
            {symbol: weight %}

        Returns:
        --------
        ScenarioResult for downside scenario
        """
        mc_result = self.monte_carlo_simulation(
            historical_returns=historical_returns,
            allocation=allocation,
            n_simulations=5000,
        )

        # Probability of loss
        prob_loss = 100 - mc_result.probability_positive_pct

        return ScenarioResult(
            scenario_name="Downside Scenario",
            probability_pct=prob_loss,
            expected_return_pct=mc_result.percentile_25th_pct,
            worst_case_pct=mc_result.percentile_5th_pct,
            best_case_pct=mc_result.percentile_50th_pct,
            probability_loss_pct=prob_loss,
            expected_shortfall_pct=mc_result.percentile_5th_pct,
        )

    def base_case_scenario(
        self,
        historical_returns: Dict[str, pd.Series],
        allocation: Dict[str, float],
    ) -> ScenarioResult:
        """
        Analyze base case scenario (historical expectations).

        Returns:
        --------
        ScenarioResult for base case scenario
        """
        mc_result = self.monte_carlo_simulation(
            historical_returns=historical_returns,
            allocation=allocation,
            n_simulations=5000,
        )

        return ScenarioResult(
            scenario_name="Base Case Scenario",
            probability_pct=50.0,
            expected_return_pct=mc_result.expected_return_pct,
            worst_case_pct=mc_result.percentile_25th_pct,
            best_case_pct=mc_result.percentile_75th_pct,
            probability_loss_pct=100 - mc_result.probability_positive_pct,
            expected_shortfall_pct=mc_result.percentile_5th_pct,
        )


# Global instance
_scenario_analyzer: ScenarioAnalyzer = None


def get_scenario_analyzer() -> ScenarioAnalyzer:
    """Get or create scenario analyzer."""
    global _scenario_analyzer
    if _scenario_analyzer is None:
        _scenario_analyzer = ScenarioAnalyzer()
    return _scenario_analyzer
