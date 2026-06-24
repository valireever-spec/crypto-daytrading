"""
Phase 330: Scenario Auto-Reweighting Scheduler

Monthly systemd timer to auto-reweight scenarios based on accuracy.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ScenarioAutoReweightingScheduler:
    """Auto-reweight scenarios monthly based on historical performance."""

    def __init__(self, min_total_recommendations: int = 15):
        """
        Initialize scheduler.

        Parameters:
        -----------
        min_total_recommendations : int
            Minimum recommendations before auto-reweighting
        """
        self.min_total_recs = min_total_recommendations
        self.last_reweight_timestamp = None
        self.reweight_history = []

    def should_reweight(self) -> bool:
        """Check if reweighting is due."""
        from backend.analytics.recommendation_tracker import get_recommendation_tracker

        tracker = get_recommendation_tracker()
        metrics = tracker.analyze_accuracy()

        # Need sufficient data
        if metrics.total_recommendations < self.min_total_recs:
            logger.info(
                f"Insufficient data for reweighting: {metrics.total_recommendations} < {self.min_total_recs}"
            )
            return False

        # Check if all scenarios have minimum samples
        min_samples = 5
        for scenario in ["base", "upside", "downside"]:
            if metrics.scenario_accuracy.get(scenario, 0) < min_samples:
                logger.info(f"Insufficient samples for {scenario}: {metrics.scenario_accuracy.get(scenario, 0)} < {min_samples}")
                return False

        return True

    def run_reweighting(self) -> Dict:
        """
        Execute scenario reweighting and update analyzer.

        Returns:
        --------
        {
            status: "reweighted" | "skipped" | "error",
            old_weights: {...},
            new_weights: {...},
            accuracy: {...},
            recommendation_count: int,
            timestamp: str
        }
        """
        from backend.analytics.recommendation_tracker import (
            get_recommendation_tracker,
            trigger_scenario_reweighting,
        )
        from backend.analytics.scenario_analyzer import get_scenario_analyzer

        tracker = get_recommendation_tracker()
        metrics = tracker.analyze_accuracy()

        if not self.should_reweight():
            return {
                "status": "skipped",
                "reason": f"Insufficient data: {metrics.total_recommendations} recs",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            # Get old weights
            scenario_analyzer = get_scenario_analyzer()
            old_weights = scenario_analyzer.scenario_probabilities.copy()

            # Trigger reweighting
            new_weights = trigger_scenario_reweighting()

            # Update analyzer with new weights
            scenario_analyzer.scenario_probabilities = new_weights

            self.last_reweight_timestamp = datetime.now(timezone.utc).isoformat()
            self.reweight_history.append({
                "timestamp": self.last_reweight_timestamp,
                "old_weights": old_weights,
                "new_weights": new_weights,
                "accuracy": metrics.scenario_accuracy,
            })

            logger.info(
                f"Reweighted scenarios: {old_weights} → {new_weights}, "
                f"accuracy {metrics.accuracy_pct:.1f}%"
            )

            return {
                "status": "reweighted",
                "old_weights": old_weights,
                "new_weights": new_weights,
                "accuracy_pct": round(metrics.accuracy_pct, 1),
                "scenario_accuracy": {
                    s: round(a, 1) for s, a in metrics.scenario_accuracy.items()
                },
                "recommendation_count": metrics.total_recommendations,
                "timestamp": self.last_reweight_timestamp,
            }

        except Exception as e:
            logger.error(f"Reweighting failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_reweighting_history(self) -> list:
        """Get history of reweighting operations."""
        return self.reweight_history.copy()

    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "last_reweight": self.last_reweight_timestamp,
            "reweight_count": len(self.reweight_history),
            "min_total_recommendations_for_reweight": self.min_total_recs,
            "status": "ready",
        }


# Global instance
_scheduler: ScenarioAutoReweightingScheduler = None


def get_scenario_auto_reweighting_scheduler() -> ScenarioAutoReweightingScheduler:
    """Get or create scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScenarioAutoReweightingScheduler()
    return _scheduler
