"""
Phase 328: Feedback Loop Engine

Close the loop: performance metrics inform future recommendations.
"""

import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CalibrationReport:
    """Calibration analysis report."""
    scenario_accuracy_pct: Dict[str, float]  # {scenario: accuracy %}
    recommendation_quality_score: float  # 0-100
    constraint_effectiveness: float  # How well constraints worked
    suggested_adjustments: Dict[str, Any]
    is_healthy: bool  # < 50% accuracy = needs tuning


class FeedbackLoopEngine:
    """Close the feedback loop: outcomes inform future decisions."""

    def __init__(self, min_samples_for_calibration: int = 10):
        """
        Initialize feedback loop engine.

        Parameters:
        -----------
        min_samples_for_calibration : int
            Minimum recommendations to calibrate from
        """
        self.min_samples = min_samples_for_calibration
        self.calibration_history: list = []

    def analyze_recommendation_accuracy(
        self,
        recommendations: list,  # RecommendationRecord objects
        outcomes: list,  # OutcomeRecord objects
    ) -> Tuple[float, Dict[str, float]]:
        """
        Analyze how accurate recommendations were.

        Parameters:
        -----------
        recommendations : list
            Past recommendations
        outcomes : list
            Actual outcomes

        Returns:
        --------
        (overall_accuracy_pct, accuracy_by_scenario)
        """
        if len(recommendations) < self.min_samples:
            return 0.0, {}

        # Match recommendations to outcomes
        accuracy_by_scenario = {}
        total_accuracy = 0.0
        matches = 0

        for rec in recommendations:
            for outcome in outcomes:
                if outcome.recommendation_timestamp == rec.timestamp:
                    # Check if direction was correct
                    direction_correct = (rec.expected_return_pct > 0) == (
                        outcome.actual_return_pct > 0
                    )

                    # Check if magnitude was close (within 2x)
                    if rec.expected_return_pct != 0:
                        magnitude_ratio = abs(
                            outcome.actual_return_pct / rec.expected_return_pct
                        )
                        magnitude_ok = 0.5 <= magnitude_ratio <= 2.0
                    else:
                        magnitude_ok = True

                    accuracy = 100.0 if (direction_correct and magnitude_ok) else 0.0

                    scenario = rec.scenario_type
                    if scenario not in accuracy_by_scenario:
                        accuracy_by_scenario[scenario] = []
                    accuracy_by_scenario[scenario].append(accuracy)

                    total_accuracy += accuracy
                    matches += 1

        # Calculate averages
        overall_accuracy = (total_accuracy / matches * 100) if matches > 0 else 0.0
        scenario_accuracy = {
            scenario: np.mean(scores)
            for scenario, scores in accuracy_by_scenario.items()
        }

        return overall_accuracy, scenario_accuracy

    def generate_calibration_report(
        self,
        recommendations: list,
        outcomes: list,
        performance_metrics: Optional[Dict] = None,
    ) -> CalibrationReport:
        """
        Generate a full calibration report.

        Parameters:
        -----------
        recommendations : list
            Past recommendations
        outcomes : list
            Outcomes
        performance_metrics : dict
            Optional performance metrics from tracker

        Returns:
        --------
        CalibrationReport with analysis
        """
        overall_acc, scenario_acc = self.analyze_recommendation_accuracy(
            recommendations, outcomes
        )

        # Quality score: average of accuracies
        quality_score = overall_acc

        # Constraint effectiveness: how many plans were feasible?
        feasible_count = sum(1 for rec in recommendations if getattr(rec, "feasible", True))
        constraint_effectiveness = (feasible_count / len(recommendations) * 100) if recommendations else 100

        # Generate suggestions
        suggestions = {}
        if overall_acc < 40:
            suggestions["increase_scenario_samples"] = True
            suggestions["recalibrate_weights"] = True
        if overall_acc < 20:
            suggestions["review_historical_returns"] = True
        if constraint_effectiveness < 50:
            suggestions["relax_constraints"] = True

        is_healthy = overall_acc >= 50

        report = CalibrationReport(
            scenario_accuracy_pct=scenario_acc,
            recommendation_quality_score=quality_score,
            constraint_effectiveness=constraint_effectiveness,
            suggested_adjustments=suggestions,
            is_healthy=is_healthy,
        )

        self.calibration_history.append(report)
        return report

    def suggest_constraint_adjustments(
        self,
        performance_report: CalibrationReport,
        current_constraints: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Suggest constraint adjustments based on performance.

        Parameters:
        -----------
        performance_report : CalibrationReport
            Performance analysis
        current_constraints : dict
            Current constraint values

        Returns:
        --------
        Suggested new constraint values
        """
        adjusted = current_constraints.copy()

        # If recommendations are too optimistic, tighten constraints
        if performance_report.recommendation_quality_score < 30:
            for key in adjusted:
                if "max" in key.lower():
                    adjusted[key] *= 0.8  # Reduce max positions by 20%
                    logger.info(f"Suggesting {key} reduction: {current_constraints[key]:.1f}% → {adjusted[key]:.1f}%")

        # If recommendations are too conservative, loosen constraints
        elif performance_report.recommendation_quality_score > 80:
            for key in adjusted:
                if "max" in key.lower():
                    adjusted[key] *= 1.1  # Increase max positions by 10%
                    logger.info(f"Suggesting {key} increase: {current_constraints[key]:.1f}% → {adjusted[key]:.1f}%")

        return adjusted

    def suggest_scenario_weights(
        self,
        performance_report: CalibrationReport,
    ) -> Dict[str, float]:
        """
        Suggest scenario probability adjustments.

        Parameters:
        -----------
        performance_report : CalibrationReport
            Performance analysis

        Returns:
        --------
        Suggested scenario weights (0-1, sum to 1)
        """
        scenario_acc = performance_report.scenario_accuracy_pct

        if not scenario_acc:
            return {}

        # Weight by accuracy
        total = sum(max(0.1, acc) for acc in scenario_acc.values())  # Min 0.1 weight
        weights = {
            scenario: max(0.1, acc) / total
            for scenario, acc in scenario_acc.items()
        }

        # Normalize
        total_weight = sum(weights.values())
        weights = {s: w / total_weight for s, w in weights.items()}

        return weights

    def get_recalibration_status(self) -> Dict[str, Any]:
        """Get current recalibration status."""
        if not self.calibration_history:
            return {
                "status": "not_calibrated",
                "recommendation_quality_score": 0,
                "num_recommendations_analyzed": 0,
            }

        latest = self.calibration_history[-1]
        return {
            "status": "healthy" if latest.is_healthy else "needs_tuning",
            "recommendation_quality_score": latest.recommendation_quality_score,
            "constraint_effectiveness": latest.constraint_effectiveness,
            "last_calibration_date": None,  # Would be set from report
            "suggestions_pending": len(latest.suggested_adjustments) > 0,
        }


# Global instance
_feedback_engine: FeedbackLoopEngine = None


def get_feedback_loop_engine() -> FeedbackLoopEngine:
    """Get or create feedback loop engine."""
    global _feedback_engine
    if _feedback_engine is None:
        _feedback_engine = FeedbackLoopEngine()
    return _feedback_engine
