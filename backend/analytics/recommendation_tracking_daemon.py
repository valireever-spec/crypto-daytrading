"""
Phase 330: Recommendation Tracking Daemon

Daily batch job to match recommendations against portfolio outcomes.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PortfolioState:
    """Portfolio state at a point in time."""
    timestamp: str  # ISO format
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    allocation_pct: float


@dataclass
class OutcomeCalculation:
    """Calculated outcome from recommendation."""
    recommendation_id: str
    symbol: str
    holding_period_days: int
    entry_price: float
    exit_price: float
    entry_allocation_pct: float
    exit_allocation_pct: float
    actual_return_pct: float  # (exit - entry) / entry * 100
    recommendation_matched: bool


class RecommendationTrackingDaemon:
    """Match recommendations to portfolio outcomes daily."""

    def __init__(self):
        """Initialize daemon."""
        self.last_run = None

    def calculate_holding_outcome(
        self,
        recommendation_id: str,
        symbol: str,
        entry_timestamp: str,
        entry_price: float,
        entry_allocation_pct: float,
        exit_timestamp: str,
        exit_price: float,
        exit_allocation_pct: float,
    ) -> OutcomeCalculation:
        """
        Calculate outcome for a held recommendation.

        Parameters:
        -----------
        recommendation_id : str
            Recommendation ID
        symbol : str
            Trading symbol
        entry_timestamp : str
            When recommendation was made (ISO)
        entry_price : float
            Price at recommendation time
        entry_allocation_pct : float
            Allocated percentage at entry
        exit_timestamp : str
            When position was closed
        exit_price : float
            Price at exit
        exit_allocation_pct : float
            Allocated percentage at exit

        Returns:
        --------
        OutcomeCalculation with return metrics
        """
        # Calculate holding period
        entry_dt = datetime.fromisoformat(entry_timestamp)
        exit_dt = datetime.fromisoformat(exit_timestamp)
        holding_days = (exit_dt - entry_dt).days

        # Calculate return
        if entry_price > 0:
            price_return = (exit_price - entry_price) / entry_price * 100
        else:
            price_return = 0.0

        # Allocation-weighted return
        avg_allocation = (entry_allocation_pct + exit_allocation_pct) / 2
        actual_return = price_return * (avg_allocation / 100)

        outcome = OutcomeCalculation(
            recommendation_id=recommendation_id,
            symbol=symbol,
            holding_period_days=holding_days,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_allocation_pct=entry_allocation_pct,
            exit_allocation_pct=exit_allocation_pct,
            actual_return_pct=actual_return,
            recommendation_matched=True,
        )

        logger.info(
            f"Calculated outcome {recommendation_id}: {symbol} "
            f"{holding_days}d, {actual_return:.2f}% return"
        )
        return outcome

    def match_recommendations_to_executions(
        self,
        recommendations: List[Dict],  # From recommendation_tracker
        executions: List[Dict],  # Buy/sell execution log
    ) -> List[OutcomeCalculation]:
        """
        Match recommendations to actual portfolio executions.

        Parameters:
        -----------
        recommendations : list
            Pending recommendations (not yet matched)
        executions : list
            Buy/sell execution records

        Returns:
        --------
        List of OutcomeCalculation for matched recommendations
        """
        outcomes = []

        for rec in recommendations:
            symbol = rec.get("symbol")
            rec_id = rec.get("recommendation_id")
            entry_time = rec.get("timestamp")
            entry_alloc = rec.get("recommended_allocation_pct")

            # Find matching buy execution
            buy_exec = next(
                (e for e in executions
                 if e.get("symbol") == symbol
                 and e.get("side") == "BUY"
                 and datetime.fromisoformat(e.get("timestamp", "")) > datetime.fromisoformat(entry_time)),
                None
            )

            if not buy_exec:
                continue

            # Find matching sell execution
            sell_exec = next(
                (e for e in executions
                 if e.get("symbol") == symbol
                 and e.get("side") == "SELL"
                 and datetime.fromisoformat(e.get("timestamp", "")) > datetime.fromisoformat(buy_exec.get("timestamp", ""))),
                None
            )

            if not sell_exec:
                continue  # Still holding

            # Calculate outcome
            outcome = self.calculate_holding_outcome(
                recommendation_id=rec_id,
                symbol=symbol,
                entry_timestamp=buy_exec.get("timestamp"),
                entry_price=buy_exec.get("price", 0),
                entry_allocation_pct=buy_exec.get("allocation_pct", entry_alloc),
                exit_timestamp=sell_exec.get("timestamp"),
                exit_price=sell_exec.get("price", 0),
                exit_allocation_pct=sell_exec.get("allocation_pct", entry_alloc),
            )

            outcomes.append(outcome)

        return outcomes

    def record_outcomes_from_executions(
        self,
        executions: List[Dict],
    ) -> Dict[str, any]:
        """
        Process executions and record matching outcomes.

        Parameters:
        -----------
        executions : list
            Buy/sell execution records from paper trading log

        Returns:
        --------
        {matched_count, recorded_count, errors}
        """
        from backend.analytics.recommendation_tracker import get_recommendation_tracker

        tracker = get_recommendation_tracker()

        # Get pending recommendations (those without outcomes)
        rec_with_outcomes = set(o.recommendation_id for o in tracker.outcomes)
        pending_recs = [
            r for r in tracker.recommendations
            if r.recommendation_id not in rec_with_outcomes
        ]

        if not pending_recs:
            logger.info("No pending recommendations to match")
            return {"matched_count": 0, "recorded_count": 0, "errors": 0}

        # Convert to dicts for matching
        rec_dicts = [
            {
                "recommendation_id": r.recommendation_id,
                "symbol": r.symbol,
                "timestamp": r.timestamp,
                "recommended_allocation_pct": r.recommended_allocation_pct,
            }
            for r in pending_recs
        ]

        # Match recommendations to executions
        outcomes = self.match_recommendations_to_executions(rec_dicts, executions)

        # Record outcomes
        recorded_count = 0
        for outcome in outcomes:
            try:
                tracker.record_outcome(
                    recommendation_id=outcome.recommendation_id,
                    holding_period_days=outcome.holding_period_days,
                    actual_return_pct=outcome.actual_return_pct,
                    executed_allocation_pct=outcome.exit_allocation_pct,
                    notes=f"Auto-matched: {outcome.entry_price:.2f} → {outcome.exit_price:.2f}",
                )
                recorded_count += 1
            except Exception as e:
                logger.error(f"Failed to record outcome {outcome.recommendation_id}: {e}")

        logger.info(
            f"Matched {len(outcomes)} recommendations, recorded {recorded_count} outcomes"
        )

        return {
            "matched_count": len(outcomes),
            "recorded_count": recorded_count,
            "errors": len(outcomes) - recorded_count,
        }

    def run_daily_sync(
        self,
        executions: List[Dict],
    ) -> Dict[str, any]:
        """
        Run daily synchronization: match recommendations to outcomes.

        Call this as a systemd timer (daily at 08:30).

        Parameters:
        -----------
        executions : list
            Execution records from the day

        Returns:
        --------
        Status dictionary
        """
        self.last_run = datetime.now(timezone.utc).isoformat()

        result = self.record_outcomes_from_executions(executions)

        logger.info(f"Daily sync complete: {result}")
        return {
            "timestamp": self.last_run,
            **result,
        }


# Global instance
_daemon: RecommendationTrackingDaemon = None


def get_recommendation_tracking_daemon() -> RecommendationTrackingDaemon:
    """Get or create daemon."""
    global _daemon
    if _daemon is None:
        _daemon = RecommendationTrackingDaemon()
    return _daemon
