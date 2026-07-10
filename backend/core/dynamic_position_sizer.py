"""
Dynamic Position Sizer - Integrates Kelly Criterion with trading position sizing.

Calculates optimal position sizes based on:
- Current win rate from trading performance
- Average win/loss percentages
- Kelly fraction (conservative quarter-Kelly default)
- Current capital and account state
"""

import logging
from typing import Dict, Optional

from backend.core.kelly_calculator import KellyCalculator

logger = logging.getLogger(__name__)


class DynamicPositionSizer:
    """Calculate position sizes using Kelly Criterion."""

    # Baseline assumptions (from system_config.json)
    DEFAULT_AVG_WIN_PCT = 0.02  # +2% average win
    DEFAULT_AVG_LOSS_PCT = 0.01  # -1% average loss
    DEFAULT_POSITION_PCT = 0.5  # 0.5% baseline (quarter-Kelly)

    @staticmethod
    def calculate_optimal_position_size(
        win_rate: float,
        current_position_pct: float = DEFAULT_POSITION_PCT,
        avg_win_pct: float = DEFAULT_AVG_WIN_PCT,
        avg_loss_pct: float = DEFAULT_AVG_LOSS_PCT,
    ) -> Dict:
        """Calculate optimal position size using Kelly Criterion.

        Args:
            win_rate: Current win rate (0.0 - 1.0)
            current_position_pct: Current position sizing (default 0.5%)
            avg_win_pct: Average win as % (default +2%)
            avg_loss_pct: Average loss as % (default -1%)

        Returns:
            Dict with:
            - kelly_result: Kelly calculation result
            - recommendation: Suggested action (INCREASE, MAINTAIN, DECREASE)
            - suggested_position_pct: Suggested new position size
            - rationale: Explanation of recommendation
        """
        if win_rate < 0 or win_rate > 1:
            logger.error(f"Invalid win rate: {win_rate}")
            return {
                "recommendation": "INVALID",
                "rationale": f"Invalid win rate: {win_rate}",
            }

        kelly_result = KellyCalculator.calculate_kelly(
            win_rate, avg_win_pct, avg_loss_pct
        )

        if not kelly_result or not kelly_result.is_profitable:
            return {
                "recommendation": "HALT",
                "suggested_position_pct": 0.0,
                "rationale": "Strategy not profitable at current win rate",
                "kelly_result": None,
            }

        comparison = KellyCalculator.compare_kelly_to_current(
            kelly_result, current_position_pct
        )

        suggested_size = kelly_result.recommended_position_pct
        if comparison["status"] == "OPTIMAL":
            recommendation = "MAINTAIN"
        elif comparison["status"] == "UNDER_SIZED":
            recommendation = "INCREASE"
        elif comparison["status"] == "OVER_SIZED":
            recommendation = "DECREASE"
        else:
            recommendation = "REVIEW"

        return {
            "kelly_result": kelly_result,
            "comparison": comparison,
            "recommendation": recommendation,
            "suggested_position_pct": suggested_size,
            "current_position_pct": current_position_pct,
            "rationale": comparison.get("details", ""),
            "win_rate_pct": win_rate * 100,
        }

    @staticmethod
    def get_position_size_for_capital(
        capital: float,
        position_pct: float,
    ) -> float:
        """Convert percentage position size to dollar amount.

        Args:
            capital: Total capital available
            position_pct: Position size as percentage (e.g., 0.5 for 0.5%)

        Returns:
            Position size in currency (e.g., €5.00 for €1000 capital at 0.5%)
        """
        return capital * (position_pct / 100.0)

    @staticmethod
    def log_kelly_recommendation(
        win_rate: float,
        current_position_pct: float = DEFAULT_POSITION_PCT,
    ) -> None:
        """Log Kelly recommendation to logger.

        Args:
            win_rate: Current win rate
            current_position_pct: Current position size in %
        """
        result = DynamicPositionSizer.calculate_optimal_position_size(
            win_rate, current_position_pct
        )

        if result.get("recommendation") == "HALT":
            logger.warning(f"🛑 {result['rationale']}")
            return

        logger.info(
            f"💰 Position Sizing Recommendation:\n"
            f"  Current Win Rate: {win_rate*100:.1f}%\n"
            f"  Current Position Size: {current_position_pct:.2f}%\n"
            f"  Suggested Position Size: {result.get('suggested_position_pct', 0):.2f}%\n"
            f"  Recommendation: {result.get('recommendation', 'REVIEW')}\n"
            f"  Rationale: {result.get('rationale', '')}"
        )
