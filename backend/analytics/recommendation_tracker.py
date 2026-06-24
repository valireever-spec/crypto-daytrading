"""
Phase 329: Recommendation Tracking Service

Record recommendations and their outcomes for continuous learning.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
from pathlib import Path

logger = logging.getLogger(__name__)

TRACKER_DIR = Path("logs/recommendation_tracking")


@dataclass
class RecommendationRecord:
    """Single recommendation record."""
    recommendation_id: str  # UUID for tracking
    timestamp: str  # ISO format
    symbol: str
    recommended_allocation_pct: float
    scenario: str  # "base", "upside", "downside"
    expected_return_pct: float
    confidence_score: float  # 0-100
    rationale: str


@dataclass
class OutcomeRecord:
    """Actual outcome for a recommendation."""
    recommendation_id: str
    outcome_timestamp: str  # ISO format
    holding_period_days: int
    actual_return_pct: float
    executed_allocation_pct: float
    notes: str


@dataclass
class AccuracyMetrics:
    """Tracking accuracy metrics."""
    total_recommendations: int
    correct_direction: int
    within_magnitude_tolerance: int
    accuracy_pct: float
    scenario_accuracy: Dict[str, float]  # {scenario: accuracy %}
    symbol_accuracy: Dict[str, float]  # {symbol: accuracy %}


class RecommendationTracker:
    """Track recommendations and outcomes for continuous learning."""

    def __init__(self, tracking_dir: Path = TRACKER_DIR):
        """
        Initialize tracker.

        Parameters:
        -----------
        tracking_dir : Path
            Directory for storing tracking records
        """
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)

        self.recommendations: List[RecommendationRecord] = []
        self.outcomes: List[OutcomeRecord] = []

        self._load_from_disk()

    def _load_from_disk(self):
        """Load tracking history from disk."""
        rec_file = self.tracking_dir / "recommendations.jsonl"
        outcome_file = self.tracking_dir / "outcomes.jsonl"

        if rec_file.exists():
            try:
                with open(rec_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.recommendations.append(
                                RecommendationRecord(**data)
                            )
            except Exception as e:
                logger.warning(f"Failed to load recommendations: {e}")

        if outcome_file.exists():
            try:
                with open(outcome_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.outcomes.append(OutcomeRecord(**data))
            except Exception as e:
                logger.warning(f"Failed to load outcomes: {e}")

    def record_recommendation(
        self,
        recommendation_id: str,
        symbol: str,
        recommended_allocation_pct: float,
        scenario: str,
        expected_return_pct: float,
        confidence_score: float,
        rationale: str = "",
    ) -> RecommendationRecord:
        """
        Record a new recommendation.

        Parameters:
        -----------
        recommendation_id : str
            Unique identifier (UUID)
        symbol : str
            Trading symbol
        recommended_allocation_pct : float
            Recommended allocation (0-100)
        scenario : str
            Scenario type ("base", "upside", "downside")
        expected_return_pct : float
            Expected return projection
        confidence_score : float
            Confidence (0-100)
        rationale : str
            Brief explanation

        Returns:
        --------
        RecommendationRecord
        """
        rec = RecommendationRecord(
            recommendation_id=recommendation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            recommended_allocation_pct=recommended_allocation_pct,
            scenario=scenario,
            expected_return_pct=expected_return_pct,
            confidence_score=confidence_score,
            rationale=rationale,
        )

        self.recommendations.append(rec)
        self._append_to_file("recommendations.jsonl", rec)

        logger.info(f"Recorded recommendation {recommendation_id}: {symbol} {scenario}")
        return rec

    def record_outcome(
        self,
        recommendation_id: str,
        holding_period_days: int,
        actual_return_pct: float,
        executed_allocation_pct: float,
        notes: str = "",
    ) -> OutcomeRecord:
        """
        Record outcome for a recommendation.

        Parameters:
        -----------
        recommendation_id : str
            References recommendation
        holding_period_days : int
            Days held
        actual_return_pct : float
            Actual return realized
        executed_allocation_pct : float
            Actual allocation (may differ from recommendation)
        notes : str
            Any notes on execution

        Returns:
        --------
        OutcomeRecord
        """
        outcome = OutcomeRecord(
            recommendation_id=recommendation_id,
            outcome_timestamp=datetime.now(timezone.utc).isoformat(),
            holding_period_days=holding_period_days,
            actual_return_pct=actual_return_pct,
            executed_allocation_pct=executed_allocation_pct,
            notes=notes,
        )

        self.outcomes.append(outcome)
        self._append_to_file("outcomes.jsonl", outcome)

        logger.info(f"Recorded outcome {recommendation_id}: {actual_return_pct:.2f}% return")
        return outcome

    def _append_to_file(self, filename: str, record: object):
        """Append record to JSONL file."""
        try:
            filepath = self.tracking_dir / filename
            with open(filepath, "a") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write {filename}: {e}")

    def analyze_accuracy(
        self,
        magnitude_tolerance: float = 2.0,
    ) -> AccuracyMetrics:
        """
        Analyze recommendation accuracy.

        Parameters:
        -----------
        magnitude_tolerance : float
            Ratio threshold (0.5–2.0 considered correct)

        Returns:
        --------
        AccuracyMetrics with detailed breakdown
        """
        if not self.recommendations or not self.outcomes:
            return AccuracyMetrics(
                total_recommendations=len(self.recommendations),
                correct_direction=0,
                within_magnitude_tolerance=0,
                accuracy_pct=0.0,
                scenario_accuracy={},
                symbol_accuracy={},
            )

        # Match recommendations to outcomes
        scenario_correct = {}
        symbol_correct = {}
        scenario_total = {}
        symbol_total = {}

        correct_direction = 0
        within_magnitude = 0
        matches = 0

        for outcome in self.outcomes:
            # Find matching recommendation
            rec = next(
                (r for r in self.recommendations
                 if r.recommendation_id == outcome.recommendation_id),
                None
            )

            if not rec:
                continue

            matches += 1

            # Check direction
            expected_positive = rec.expected_return_pct > 0
            actual_positive = outcome.actual_return_pct > 0

            if expected_positive == actual_positive:
                correct_direction += 1

                # Check magnitude
                if rec.expected_return_pct != 0:
                    ratio = abs(
                        outcome.actual_return_pct / rec.expected_return_pct
                    )
                    if 1.0 / magnitude_tolerance <= ratio <= magnitude_tolerance:
                        within_magnitude += 1

            # Track by scenario
            if rec.scenario not in scenario_correct:
                scenario_correct[rec.scenario] = 0
                scenario_total[rec.scenario] = 0

            scenario_total[rec.scenario] += 1
            if expected_positive == actual_positive:
                scenario_correct[rec.scenario] += 1

            # Track by symbol
            if rec.symbol not in symbol_correct:
                symbol_correct[rec.symbol] = 0
                symbol_total[rec.symbol] = 0

            symbol_total[rec.symbol] += 1
            if expected_positive == actual_positive:
                symbol_correct[rec.symbol] += 1

        # Calculate percentages
        overall_accuracy = (correct_direction / matches * 100) if matches > 0 else 0.0

        scenario_accuracy = {
            s: (scenario_correct[s] / scenario_total[s] * 100)
            for s in scenario_total
        }

        symbol_accuracy = {
            s: (symbol_correct[s] / symbol_total[s] * 100)
            for s in symbol_total
        }

        return AccuracyMetrics(
            total_recommendations=len(self.recommendations),
            correct_direction=correct_direction,
            within_magnitude_tolerance=within_magnitude,
            accuracy_pct=overall_accuracy,
            scenario_accuracy=scenario_accuracy,
            symbol_accuracy=symbol_accuracy,
        )

    def get_matched_pairs(self) -> List[Tuple[RecommendationRecord, OutcomeRecord]]:
        """Get matched recommendation-outcome pairs."""
        pairs = []
        for outcome in self.outcomes:
            rec = next(
                (r for r in self.recommendations
                 if r.recommendation_id == outcome.recommendation_id),
                None
            )
            if rec:
                pairs.append((rec, outcome))

        return pairs

    def get_scenario_performance(self) -> Dict[str, Dict]:
        """Get performance metrics by scenario."""
        pairs = self.get_matched_pairs()
        scenario_metrics = {}

        for scenario in ["base", "upside", "downside"]:
            matching_pairs = [
                (r, o) for r, o in pairs if r.scenario == scenario
            ]

            if matching_pairs:
                avg_expected = sum(r.expected_return_pct for r, _ in matching_pairs) / len(matching_pairs)
                avg_actual = sum(o.actual_return_pct for _, o in matching_pairs) / len(matching_pairs)
                direction_correct = sum(
                    1 for r, o in matching_pairs
                    if (r.expected_return_pct > 0) == (o.actual_return_pct > 0)
                )
                accuracy = direction_correct / len(matching_pairs) * 100

                scenario_metrics[scenario] = {
                    "count": len(matching_pairs),
                    "avg_expected_return": round(avg_expected, 2),
                    "avg_actual_return": round(avg_actual, 2),
                    "accuracy_pct": round(accuracy, 1),
                }

        return scenario_metrics


# Global instance
_tracker: RecommendationTracker = None


def get_recommendation_tracker() -> RecommendationTracker:
    """Get or create tracker."""
    global _tracker
    if _tracker is None:
        _tracker = RecommendationTracker()
    return _tracker
