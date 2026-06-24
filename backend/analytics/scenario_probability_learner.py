"""
Phase 329: Scenario Probability Learning

Auto-reweight scenario probabilities based on historical accuracy.
"""

import logging
from typing import Dict, Tuple
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger(__name__)


class ScenarioProbabilityLearner:
    """Learn scenario probabilities from historical performance."""

    def __init__(
        self,
        initial_weights: Dict[str, float] = None,
        learning_rate: float = 0.1,
    ):
        """
        Initialize learner.

        Parameters:
        -----------
        initial_weights : dict
            Initial scenario weights {scenario: probability}
            Default: equal weight (base=0.5, upside=0.25, downside=0.25)
        learning_rate : float
            How fast to adapt weights (0.0-1.0)
        """
        self.learning_rate = learning_rate
        self.last_update = datetime.now(timezone.utc).isoformat()

        if initial_weights is None:
            self.weights = {
                "base": 0.50,
                "upside": 0.25,
                "downside": 0.25,
            }
        else:
            self.weights = initial_weights

    def update_from_accuracy(
        self,
        scenario_accuracy: Dict[str, float],  # {scenario: accuracy %}
        min_samples_per_scenario: int = 5,
    ) -> Dict[str, float]:
        """
        Update scenario weights based on historical accuracy.

        Parameters:
        -----------
        scenario_accuracy : dict
            Accuracy by scenario {scenario: accuracy %}
        min_samples_per_scenario : int
            Minimum samples required to update

        Returns:
        --------
        Updated weights {scenario: probability}
        """
        # Only update if we have enough samples
        if not scenario_accuracy or len(scenario_accuracy) < 2:
            logger.warning("Insufficient scenario accuracy data for update")
            return self.weights

        # Calculate confidence (inverse of variance)
        accuracy_values = list(scenario_accuracy.values())
        if len(accuracy_values) > 1:
            variance = np.var(accuracy_values)
            confidence = max(0.0, 1.0 - variance / 10000)  # Normalize to [0, 1]
        else:
            confidence = 0.5

        # Weight by accuracy: higher accuracy = higher weight
        accuracy_sum = sum(
            max(0.1, acc) for acc in scenario_accuracy.values()
        )

        new_weights = {}
        for scenario, accuracy in scenario_accuracy.items():
            normalized_accuracy = max(0.1, accuracy) / accuracy_sum
            new_weights[scenario] = normalized_accuracy

        # Blend old and new weights
        blended = {}
        for scenario in self.weights:
            old_weight = self.weights.get(scenario, 0.33)
            new_weight = new_weights.get(scenario, 0.33)

            # Adjust learning rate by confidence
            effective_rate = self.learning_rate * confidence

            blended[scenario] = (
                old_weight * (1 - effective_rate) +
                new_weight * effective_rate
            )

        # Normalize to ensure sum = 1.0
        total = sum(blended.values())
        if total > 0:
            blended = {s: w / total for s, w in blended.items()}

        self.weights = blended
        self.last_update = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Updated scenario weights: {self.weights}, confidence={confidence:.2f}"
        )
        return self.weights

    def suggest_reweighting(
        self,
        scenario_accuracy: Dict[str, float],
        current_weights: Dict[str, float] = None,
    ) -> Tuple[Dict[str, float], str]:
        """
        Suggest scenario weight adjustments.

        Parameters:
        -----------
        scenario_accuracy : dict
            Accuracy by scenario
        current_weights : dict
            Current scenario weights (default: use internal)

        Returns:
        --------
        (suggested_weights, recommendation_text)
        """
        if current_weights is None:
            current_weights = self.weights

        # Identify best/worst scenarios
        best_scenario = max(scenario_accuracy, key=scenario_accuracy.get)
        worst_scenario = min(scenario_accuracy, key=scenario_accuracy.get)

        best_accuracy = scenario_accuracy[best_scenario]
        worst_accuracy = scenario_accuracy[worst_scenario]

        suggested = current_weights.copy()

        # Strong signal: accuracy spread > 30 percentage points
        accuracy_spread = best_accuracy - worst_accuracy
        if accuracy_spread > 30:
            # Increase best, decrease worst
            improvement_pct = accuracy_spread / 100

            suggested[best_scenario] = min(0.6, current_weights[best_scenario] * (1 + improvement_pct))
            suggested[worst_scenario] = max(0.1, current_weights[worst_scenario] * (1 - improvement_pct))

            # Rebalance middle
            remaining = 1.0 - suggested[best_scenario] - suggested[worst_scenario]
            for s in suggested:
                if s not in [best_scenario, worst_scenario]:
                    suggested[s] = remaining / (len(suggested) - 2)

            # Normalize
            total = sum(suggested.values())
            suggested = {s: w / total for s, w in suggested.items()}

            recommendation = f"Strong signal: {best_scenario} accuracy {best_accuracy:.0f}% vs {worst_scenario} {worst_accuracy:.0f}%. Recommend increasing {best_scenario} weight."
        else:
            recommendation = "Accuracy spread insufficient for reweighting recommendation."

        return suggested, recommendation

    def decay_weights(self, days_since_last_update: int = 30) -> Dict[str, float]:
        """
        Decay weights toward uniform distribution over time.

        Parameters:
        -----------
        days_since_last_update : int
            Days since last update

        Returns:
        --------
        Decayed weights
        """
        uniform = {
            "base": 1.0 / len(self.weights),
            "upside": 1.0 / len(self.weights),
            "downside": 1.0 / len(self.weights),
        }

        # Decay rate: 50% weight decay over 60 days
        decay_factor = 0.5 ** (days_since_last_update / 60)

        decayed = {}
        for scenario in self.weights:
            current = self.weights.get(scenario, uniform.get(scenario, 0.33))
            uniform_weight = uniform.get(scenario, 0.33)

            decayed[scenario] = (
                current * decay_factor +
                uniform_weight * (1 - decay_factor)
            )

        # Normalize
        total = sum(decayed.values())
        if total > 0:
            decayed = {s: w / total for s, w in decayed.items()}

        return decayed

    def get_weights(self) -> Dict[str, float]:
        """Get current scenario weights."""
        return self.weights.copy()

    def get_status(self) -> Dict:
        """Get learner status."""
        return {
            "weights": self.weights,
            "last_update": self.last_update,
            "learning_rate": self.learning_rate,
        }


# Global instance
_learner: ScenarioProbabilityLearner = None


def get_scenario_probability_learner() -> ScenarioProbabilityLearner:
    """Get or create scenario probability learner."""
    global _learner
    if _learner is None:
        _learner = ScenarioProbabilityLearner()
    return _learner
