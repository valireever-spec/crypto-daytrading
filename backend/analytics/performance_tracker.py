"""
Phase 326: Performance Tracker

Track recommendation quality and calibration over time.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RecommendationRecord:
    """Record of a portfolio recommendation."""

    timestamp: datetime
    allocation: Dict[str, float]  # {symbol: weight %}
    expected_return_pct: float
    expected_volatility_pct: float
    scenario_type: str  # "upside", "base", "downside", "custom"
    target_type: str  # "return" or "volatility"


@dataclass
class OutcomeRecord:
    """Actual portfolio outcome."""

    timestamp: datetime
    actual_return_pct: float
    actual_volatility_pct: float
    recommendation_timestamp: datetime  # When the recommendation was made


@dataclass
class PerformanceMetrics:
    """Performance metrics for recommendations."""

    total_recommendations: int
    avg_forecast_return_pct: float
    avg_actual_return_pct: float
    forecast_error_pct: float
    forecast_accuracy_pct: float  # % of predictions with correct sign
    avg_volatility_error_pct: float
    sharpe_improvement: float
    upside_capture_ratio: float  # Actual return when upside predicted / Predicted return


class PerformanceTracker:
    """Track recommendation quality and accuracy."""

    def __init__(self, lookback_days: int = 90):
        """Initialize performance tracker."""
        self.lookback_days = lookback_days
        self.recommendations: List[RecommendationRecord] = []
        self.outcomes: List[OutcomeRecord] = []

    def record_recommendation(
        self,
        allocation: Dict[str, float],
        expected_return_pct: float,
        expected_volatility_pct: float,
        scenario_type: str = "base",
        target_type: str = "return",
    ) -> None:
        """
        Record a portfolio recommendation.

        Parameters:
        -----------
        allocation : dict
            {symbol: weight %}
        expected_return_pct : float
            Recommended return expectation
        expected_volatility_pct : float
            Recommended volatility expectation
        scenario_type : str
            Type of scenario
        target_type : str
            Optimization target ("return" or "volatility")
        """
        record = RecommendationRecord(
            timestamp=datetime.now(timezone.utc),
            allocation=allocation.copy(),
            expected_return_pct=expected_return_pct,
            expected_volatility_pct=expected_volatility_pct,
            scenario_type=scenario_type,
            target_type=target_type,
        )
        self.recommendations.append(record)
        logger.info(
            f"Recorded recommendation: return {expected_return_pct:.1f}%, vol {expected_volatility_pct:.1f}%"
        )

    def record_outcome(
        self,
        actual_return_pct: float,
        actual_volatility_pct: float,
        recommendation_timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record actual portfolio outcome.

        Parameters:
        -----------
        actual_return_pct : float
            Realized return (%)
        actual_volatility_pct : float
            Realized volatility (%)
        recommendation_timestamp : datetime
            When the recommendation was made (default: most recent)
        """
        if recommendation_timestamp is None:
            # Use most recent recommendation
            if self.recommendations:
                recommendation_timestamp = self.recommendations[-1].timestamp
            else:
                recommendation_timestamp = datetime.now(timezone.utc)

        record = OutcomeRecord(
            timestamp=datetime.now(timezone.utc),
            actual_return_pct=actual_return_pct,
            actual_volatility_pct=actual_volatility_pct,
            recommendation_timestamp=recommendation_timestamp,
        )
        self.outcomes.append(record)
        logger.info(
            f"Recorded outcome: return {actual_return_pct:.1f}%, vol {actual_volatility_pct:.1f}%"
        )

    def get_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """
        Calculate performance metrics.

        Returns:
        --------
        PerformanceMetrics with accuracy analysis
        """
        if not self.recommendations or not self.outcomes:
            return None

        # Filter to recommendations within lookback window
        cutoff_date = datetime.now(timezone.utc) - pd.Timedelta(days=self.lookback_days)

        recent_recs = [r for r in self.recommendations if r.timestamp >= cutoff_date]
        recent_outcomes = [o for o in self.outcomes if o.timestamp >= cutoff_date]

        if not recent_recs or not recent_outcomes:
            return None

        # Match recommendations to outcomes
        matched_pairs = []
        for rec in recent_recs:
            for outcome in recent_outcomes:
                if outcome.recommendation_timestamp == rec.timestamp:
                    matched_pairs.append((rec, outcome))

        if not matched_pairs:
            return None

        # Calculate metrics
        forecast_returns = [rec.expected_return_pct for rec, _ in matched_pairs]
        actual_returns = [outcome.actual_return_pct for _, outcome in matched_pairs]
        forecast_vols = [rec.expected_volatility_pct for rec, _ in matched_pairs]
        actual_vols = [outcome.actual_volatility_pct for _, outcome in matched_pairs]

        # Forecast error (RMSE)
        forecast_error = np.sqrt(
            np.mean((np.array(forecast_returns) - np.array(actual_returns)) ** 2)
        )

        # Directional accuracy (% correct sign)
        correct_direction = sum(
            1 for f, a in zip(forecast_returns, actual_returns) if (f > 0) == (a > 0)
        )
        directional_accuracy = (correct_direction / len(matched_pairs)) * 100

        # Volatility error
        volatility_error = np.mean(
            np.abs(np.array(forecast_vols) - np.array(actual_vols))
        )

        # Sharpe improvement (if we beat buy-and-hold)
        avg_forecast_return = np.mean(forecast_returns)
        avg_actual_return = np.mean(actual_returns)
        avg_forecast_vol = np.mean(forecast_vols)
        avg_actual_vol = np.mean(actual_vols)

        forecast_sharpe = (avg_forecast_return - 2.0) / (avg_forecast_vol + 1e-6)
        actual_sharpe = (avg_actual_return - 2.0) / (avg_actual_vol + 1e-6)
        sharpe_improvement = actual_sharpe - forecast_sharpe

        # Upside capture (if upside scenario predicted)
        upside_recs = [
            (rec, outcome)
            for rec, outcome in matched_pairs
            if rec.scenario_type == "upside"
        ]
        if upside_recs:
            upside_forecasts = [rec.expected_return_pct for rec, _ in upside_recs]
            upside_actuals = [outcome.actual_return_pct for _, outcome in upside_recs]
            upside_capture = np.mean(upside_actuals) / (
                np.mean(upside_forecasts) + 1e-6
            )
        else:
            upside_capture = 1.0

        return PerformanceMetrics(
            total_recommendations=len(recent_recs),
            avg_forecast_return_pct=avg_forecast_return,
            avg_actual_return_pct=avg_actual_return,
            forecast_error_pct=forecast_error,
            forecast_accuracy_pct=directional_accuracy,
            avg_volatility_error_pct=volatility_error,
            sharpe_improvement=sharpe_improvement,
            upside_capture_ratio=upside_capture,
        )

    def get_scenario_performance(
        self, scenario_type: str
    ) -> Optional[Dict[str, float]]:
        """
        Get performance for a specific scenario type.

        Parameters:
        -----------
        scenario_type : str
            Type of scenario ("upside", "base", "downside", etc.)

        Returns:
        --------
        Performance metrics dict or None
        """
        scenario_recs = [
            r for r in self.recommendations if r.scenario_type == scenario_type.lower()
        ]

        if not scenario_recs:
            return None

        # Match to outcomes
        matched = []
        for rec in scenario_recs:
            for outcome in self.outcomes:
                if outcome.recommendation_timestamp == rec.timestamp:
                    matched.append((rec, outcome))

        if not matched:
            return None

        forecast_returns = [rec.expected_return_pct for rec, _ in matched]
        actual_returns = [outcome.actual_return_pct for _, outcome in matched]

        return {
            "scenario": scenario_type,
            "count": len(matched),
            "avg_forecast_return_pct": np.mean(forecast_returns),
            "avg_actual_return_pct": np.mean(actual_returns),
            "error_pct": np.mean(
                np.abs(np.array(forecast_returns) - np.array(actual_returns))
            ),
            "positive_accuracy_pct": (
                sum(1 for a in actual_returns if a > 0) / len(actual_returns)
            )
            * 100,
        }

    def clear_records(self) -> None:
        """Clear all records."""
        self.recommendations = []
        self.outcomes = []
        logger.info("Cleared all performance records")

    def get_summary(self) -> Dict[str, any]:
        """
        Get summary of tracker state.

        Returns:
        --------
        Summary dict with counts and recent records
        """
        metrics = self.get_performance_metrics()

        return {
            "total_recommendations": len(self.recommendations),
            "total_outcomes": len(self.outcomes),
            "matched_pairs": len(
                [
                    (r, o)
                    for r in self.recommendations
                    for o in self.outcomes
                    if o.recommendation_timestamp == r.timestamp
                ]
            ),
            "performance_metrics": {
                "avg_forecast_return_pct": metrics.avg_forecast_return_pct
                if metrics
                else None,
                "avg_actual_return_pct": metrics.avg_actual_return_pct
                if metrics
                else None,
                "forecast_accuracy_pct": metrics.forecast_accuracy_pct
                if metrics
                else None,
                "sharpe_improvement": metrics.sharpe_improvement if metrics else None,
            }
            if metrics
            else None,
            "recent_recommendations": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "expected_return_pct": r.expected_return_pct,
                    "scenario_type": r.scenario_type,
                }
                for r in self.recommendations[-5:]
            ],
        }


# Global instance
_performance_tracker: PerformanceTracker = None


def get_performance_tracker() -> PerformanceTracker:
    """Get or create performance tracker."""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker
