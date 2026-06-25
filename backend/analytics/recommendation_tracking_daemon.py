"""
Phase 330: Recommendation Tracking Daemon

Daily batch job to match recommendations against portfolio outcomes.
"""

import logging
from typing import Dict, List, Optional
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
    actual_return_pct: Optional[
        float
    ]  # (exit - entry) / entry * 100, None if invalid entry price
    recommendation_matched: bool
    error: Optional[str] = None  # Error message if calculation failed


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
        if entry_price <= 0:
            logger.warning(
                f"Invalid entry price {entry_price} for {symbol}; skipping return calculation"
            )
            price_return = None
            actual_return = None
        else:
            price_return = (exit_price - entry_price) / entry_price * 100
            # Use entry allocation (actual position size held)
            actual_return = price_return * (entry_allocation_pct / 100)

        error = None
        if actual_return is None:
            error = "Invalid entry price for return calculation"

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
            error=error,
        )

        if actual_return is not None:
            logger.info(
                f"Calculated outcome {recommendation_id}: {symbol} "
                f"{holding_days}d, {actual_return:.2f}% return"
            )
        else:
            logger.warning(f"Outcome calculation failed {recommendation_id}: {error}")

        return outcome

    def match_recommendations_to_executions(
        self,
        recommendations: List[Dict],  # From recommendation_tracker
        executions: List[Dict],  # Buy/sell execution log
    ) -> List[OutcomeCalculation]:
        """
        Match recommendations to actual portfolio executions.

        Uses recommendation_id field in execution to identify matching trades.
        Falls back to symbol + timestamp for executions without rec_id.

        Parameters:
        -----------
        recommendations : list
            Pending recommendations (not yet matched)
        executions : list
            Buy/sell execution records (may have recommendation_id field)

        Returns:
        --------
        List of OutcomeCalculation for matched recommendations
        """
        outcomes = []
        matched_exec_ids = set()

        for rec in recommendations:
            symbol = rec.get("symbol")
            rec_id = rec.get("recommendation_id")
            entry_time = rec.get("timestamp")
            entry_alloc = rec.get("recommended_allocation_pct")

            # Prefer matching by recommendation_id if available
            buy_exec = next(
                (
                    e
                    for e in executions
                    if (
                        e.get("recommendation_id") == rec_id
                        or (
                            e.get("symbol") == symbol
                            and e.get("side") == "BUY"
                            and self._safe_timestamp_parse(e.get("timestamp", ""))
                            > self._safe_timestamp_parse(entry_time)
                        )
                    )
                    and e.get("side") == "BUY"
                    and id(e) not in matched_exec_ids
                ),
                None,
            )

            if not buy_exec:
                continue

            buy_exec_id = id(buy_exec)
            matched_exec_ids.add(buy_exec_id)

            # Find matching sell execution (after buy)
            sell_exec = next(
                (
                    e
                    for e in executions
                    if (
                        e.get("recommendation_id") == rec_id
                        or (
                            e.get("symbol") == symbol
                            and e.get("side") == "SELL"
                            and self._safe_timestamp_parse(e.get("timestamp", ""))
                            > self._safe_timestamp_parse(buy_exec.get("timestamp", ""))
                        )
                    )
                    and e.get("side") == "SELL"
                    and id(e) not in matched_exec_ids
                ),
                None,
            )

            if not sell_exec:
                matched_exec_ids.discard(buy_exec_id)  # Release buy if no sell found
                continue  # Still holding

            matched_exec_ids.add(id(sell_exec))

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

    def _safe_timestamp_parse(self, timestamp_str: str) -> datetime:
        """Parse timestamp safely with fallback."""
        if not timestamp_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse timestamp: {timestamp_str}")
            return datetime.now(timezone.utc)

    def record_outcomes_from_executions(
        self,
        executions: List[Dict],
    ) -> Dict[str, any]:
        """
        Process executions and record matching outcomes (idempotent).

        Parameters:
        -----------
        executions : list
            Buy/sell execution records from paper trading log

        Returns:
        --------
        {matched_count, recorded_count, errors, skipped_duplicates}
        """
        from backend.analytics.recommendation_tracker import get_recommendation_tracker

        tracker = get_recommendation_tracker()

        # Get pending recommendations (those without outcomes)
        rec_with_outcomes = set(o.recommendation_id for o in tracker.outcomes)
        pending_recs = [
            r
            for r in tracker.recommendations
            if r.recommendation_id not in rec_with_outcomes
        ]

        if not pending_recs:
            logger.info("No pending recommendations to match")
            return {
                "matched_count": 0,
                "recorded_count": 0,
                "errors": 0,
                "skipped_duplicates": 0,
            }

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

        # Record outcomes with deduplication
        recorded_count = 0
        skipped_duplicates = 0
        errors = 0

        for outcome in outcomes:
            # Check again if outcome already recorded (idempotency guard)
            if outcome.recommendation_id in rec_with_outcomes:
                logger.warning(
                    f"Outcome {outcome.recommendation_id} already recorded; skipping duplicate"
                )
                skipped_duplicates += 1
                continue

            try:
                # Only record if actual_return is valid
                if outcome.actual_return_pct is not None:
                    tracker.record_outcome(
                        recommendation_id=outcome.recommendation_id,
                        holding_period_days=outcome.holding_period_days,
                        actual_return_pct=outcome.actual_return_pct,
                        executed_allocation_pct=outcome.exit_allocation_pct,
                        notes=f"Auto-matched: {outcome.entry_price:.2f} → {outcome.exit_price:.2f}",
                    )
                    recorded_count += 1
                else:
                    logger.warning(
                        f"Skipped recording outcome {outcome.recommendation_id}: {outcome.error}"
                    )
                    errors += 1
            except Exception as e:
                logger.error(
                    f"Failed to record outcome {outcome.recommendation_id}: {e}"
                )
                errors += 1

        logger.info(
            f"Matched {len(outcomes)} recommendations, recorded {recorded_count}, "
            f"skipped {skipped_duplicates} duplicates, {errors} errors"
        )

        return {
            "matched_count": len(outcomes),
            "recorded_count": recorded_count,
            "errors": errors,
            "skipped_duplicates": skipped_duplicates,
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
