"""
Phase 325 (Integration): Scenario Analyzer

Analyzes market scenarios for allocation decisions.
Used by Phase 330 for scenario probability updates.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result."""
    scenario: str = "base"
    simulations: int = 10000
    mean_return_pct: float = 0.0
    std_return_pct: float = 0.0
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_50: float = 0.0
    percentile_75: float = 0.0
    percentile_95: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    expected_return_pct: float = 0.0
    volatility_pct: float = 0.0
    probability_positive_pct: float = 50.0


@dataclass
class ScenarioResult:
    """Scenario analysis result."""
    scenario_name: str
    expected_return_pct: float
    volatility_pct: float
    probability_pct: float
    sharpe_ratio: float = 0.0


class ScenarioAnalyzer:
    """Analyze scenarios for portfolio allocation."""

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize analyzer."""
        self.risk_free_rate = risk_free_rate
        # Initial scenario weights (can be updated by Phase 330 scheduler)
        self.scenario_probabilities = {
            "base": 0.50,
            "upside": 0.25,
            "downside": 0.25,
        }

    def get_scenario_weights(self) -> Dict[str, float]:
        """Get current scenario probability weights."""
        return self.scenario_probabilities.copy()

    def update_scenario_weights(self, new_weights: Dict[str, float]) -> bool:
        """
        Update scenario probability weights.

        Called by Phase 330 scheduler after reweighting.

        Parameters:
        -----------
        new_weights : dict
            New weights {scenario: probability}

        Returns:
        --------
        True if update successful
        """
        # Validate weights
        if not new_weights:
            logger.warning("Cannot update with empty weights")
            return False

        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.01:  # Allow 1% tolerance
            logger.warning(f"Invalid weights (sum={total}): {new_weights}")
            return False

        old_weights = self.scenario_probabilities.copy()
        self.scenario_probabilities = new_weights

        logger.info(f"Updated scenario weights: {old_weights} → {new_weights}")
        return True

    def analyze(self, market_data: dict = None) -> Dict:
        """
        Analyze scenarios (placeholder for Phase 325 logic).

        Parameters:
        -----------
        market_data : dict
            Market context (optional)

        Returns:
        --------
        Analysis result with scenario scores
        """
        return {
            "timestamp": "",
            "scenarios": self.scenario_probabilities.copy(),
            "recommendation": "base",
        }

    def monte_carlo_simulation(
        self,
        scenario: str = "base",
        mean_return: float = 5.0,
        volatility: float = 15.0,
        simulations: int = 10000,
        historical_returns: Optional[Dict] = None,
        allocation: Optional[Dict] = None,
        time_horizon_days: int = 252,
        n_simulations: Optional[int] = None,
        **kwargs
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation for a scenario.

        Parameters:
        -----------
        scenario : str
            Scenario type (base/upside/downside)
        mean_return : float
            Mean expected return %
        volatility : float
            Return volatility %
        simulations : int
            Number of simulations
        historical_returns : dict
            Optional dict of symbol -> returns series for empirical distribution
        allocation : dict
            Optional allocation weights
        time_horizon_days : int
            Time horizon in days
        n_simulations : int
            Alternative simulations parameter

        Returns:
        --------
        MonteCarloResult with percentiles and statistics
        """
        import numpy as np

        # Use n_simulations if provided (for API compatibility)
        if n_simulations is not None:
            simulations = n_simulations

        # If historical returns provided, use empirical distribution
        if historical_returns and isinstance(historical_returns, dict):
            all_returns = []
            for symbol, returns_series in historical_returns.items():
                if hasattr(returns_series, 'values'):
                    all_returns.extend(returns_series.values)
                elif isinstance(returns_series, (list, np.ndarray)):
                    all_returns.extend(returns_series)

            if all_returns:
                mean_return = np.mean(all_returns)
                volatility = np.std(all_returns)

        # Simple Monte Carlo: normal distribution
        returns = np.random.normal(mean_return, volatility, simulations)

        # Calculate probability of positive return
        prob_positive = (returns > 0).sum() / len(returns) * 100

        return MonteCarloResult(
            scenario=scenario,
            simulations=simulations,
            mean_return_pct=float(np.mean(returns)),
            std_return_pct=float(np.std(returns)),
            percentile_5=float(np.percentile(returns, 5)),
            percentile_25=float(np.percentile(returns, 25)),
            percentile_50=float(np.percentile(returns, 50)),
            percentile_75=float(np.percentile(returns, 75)),
            percentile_95=float(np.percentile(returns, 95)),
            sharpe_ratio=float((mean_return - self.risk_free_rate) / volatility) if volatility > 0 else 0.0,
            expected_return_pct=float(np.mean(returns)),
            volatility_pct=float(np.std(returns)),
            probability_positive_pct=float(prob_positive),
        )

    def analyze_upside_scenario(
        self,
        historical_returns: Dict,
        allocation: Dict,
        **kwargs
    ) -> ScenarioResult:
        """Analyze upside scenario (upper percentile returns)."""
        import numpy as np

        all_returns = []
        for symbol, returns_series in historical_returns.items():
            if hasattr(returns_series, 'values'):
                all_returns.extend(returns_series.values)
            elif isinstance(returns_series, (list, np.ndarray)):
                all_returns.extend(returns_series)

        if all_returns:
            upside_return = np.percentile(all_returns, 75)
            std_dev = np.std(all_returns)
        else:
            upside_return = 10.0
            std_dev = 5.0

        return ScenarioResult(
            scenario_name="Upside Scenario",
            expected_return_pct=float(upside_return),
            volatility_pct=float(std_dev),
            probability_pct=25.0,
            sharpe_ratio=float((upside_return - self.risk_free_rate) / std_dev) if std_dev > 0 else 0.0,
        )

    def analyze_downside_scenario(
        self,
        historical_returns: Dict,
        allocation: Dict,
        **kwargs
    ) -> ScenarioResult:
        """Analyze downside scenario (lower percentile returns)."""
        import numpy as np

        all_returns = []
        for symbol, returns_series in historical_returns.items():
            if hasattr(returns_series, 'values'):
                all_returns.extend(returns_series.values)
            elif isinstance(returns_series, (list, np.ndarray)):
                all_returns.extend(returns_series)

        if all_returns:
            downside_return = np.percentile(all_returns, 25)
            std_dev = np.std(all_returns)
        else:
            downside_return = -5.0
            std_dev = 5.0

        return ScenarioResult(
            scenario_name="Downside Scenario",
            expected_return_pct=float(downside_return),
            volatility_pct=float(std_dev),
            probability_pct=25.0,
            sharpe_ratio=float((downside_return - self.risk_free_rate) / std_dev) if std_dev > 0 else 0.0,
        )

    def base_case_scenario(
        self,
        historical_returns: Dict,
        allocation: Dict,
        **kwargs
    ) -> ScenarioResult:
        """Analyze base case scenario (median returns)."""
        import numpy as np

        all_returns = []
        for symbol, returns_series in historical_returns.items():
            if hasattr(returns_series, 'values'):
                all_returns.extend(returns_series.values)
            elif isinstance(returns_series, (list, np.ndarray)):
                all_returns.extend(returns_series)

        if all_returns:
            base_return = np.median(all_returns)
            std_dev = np.std(all_returns)
        else:
            base_return = 2.5
            std_dev = 5.0

        return ScenarioResult(
            scenario_name="Base Case Scenario",
            expected_return_pct=float(base_return),
            volatility_pct=float(std_dev),
            probability_pct=50.0,
            sharpe_ratio=float((base_return - self.risk_free_rate) / std_dev) if std_dev > 0 else 0.0,
        )


# Global instance
_analyzer: ScenarioAnalyzer = None


def get_scenario_analyzer() -> ScenarioAnalyzer:
    """Get or create scenario analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ScenarioAnalyzer()
    return _analyzer
