"""
Kelly Criterion calculator for optimal position sizing.

Implements:
- Kelly fraction calculation (f* = (bp - q) / b)
- Fractional Kelly for safety (quarter-Kelly, half-Kelly)
- Position sizing based on win rate and P&L ratios
- Dynamic recalculation after each test period
"""

import logging
from typing import Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KellyResult:
    """Kelly criterion calculation result."""
    win_rate: float
    avg_win_pct: float  # Average win as % of position
    avg_loss_pct: float  # Average loss as % of position

    # Kelly calculations
    kelly_fraction_full: float  # Full Kelly (f*)
    kelly_fraction_half: float  # Half Kelly (f*/2)
    kelly_fraction_quarter: float  # Quarter Kelly (f*/4)

    # Position sizing recommendations (as % of capital)
    recommended_position_pct: float  # Conservative: quarter-Kelly
    aggressive_position_pct: float  # Moderate: half-Kelly

    # Safety assessment
    kelly_validity: bool  # True if (bp - q) > 0
    is_profitable: bool  # True if expected value > 0


class KellyCalculator:
    """Calculate optimal position sizing using Kelly Criterion."""

    @staticmethod
    def calculate_kelly(
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float
    ) -> KellyResult:
        """Calculate Kelly fraction and recommended position sizing.

        Kelly Criterion: f* = (bp - q) / b
        where:
            p = win probability (win rate)
            q = loss probability (1 - win_rate)
            b = odds ratio = avg_win_pct / avg_loss_pct

        Args:
            win_rate: Probability of winning (0.0 - 1.0)
            avg_win_pct: Average profit per win as % (e.g., 0.02 for +2%)
            avg_loss_pct: Average loss per loss as % (e.g., 0.01 for -1%)

        Returns:
            KellyResult with full Kelly, half-Kelly, quarter-Kelly, and recommendations
        """
        if win_rate < 0 or win_rate > 1:
            logger.error(f"Invalid win rate: {win_rate}")
            return None

        if avg_win_pct <= 0 or avg_loss_pct <= 0:
            logger.error(f"Invalid P&L ratios: win {avg_win_pct}, loss {avg_loss_pct}")
            return None

        p = win_rate
        q = 1 - win_rate

        # Kelly odds ratio
        b = avg_win_pct / avg_loss_pct

        # Kelly fraction numerator
        numerator = (b * p) - q
        denominator = b

        # Safety check: Kelly only valid if (bp - q) > 0
        kelly_validity = numerator > 0

        if not kelly_validity:
            logger.warning(
                f"Kelly fraction invalid (strategy not profitable at this win rate): "
                f"(bp - q) = ({b:.2f} * {p:.1%} - {q:.1%}) = {numerator:.4f}"
            )
            kelly_full = 0.0
        else:
            kelly_full = numerator / denominator

        # Fractional Kelly for safety (crypto markets are volatile)
        kelly_half = kelly_full / 2.0
        kelly_quarter = kelly_full / 4.0

        # Conservative recommendation: quarter-Kelly (widely used for crypto)
        recommended_pct = kelly_quarter * 100

        # Aggressive option: half-Kelly
        aggressive_pct = kelly_half * 100

        result = KellyResult(
            win_rate=win_rate,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            kelly_fraction_full=kelly_full,
            kelly_fraction_half=kelly_half,
            kelly_fraction_quarter=kelly_quarter,
            recommended_position_pct=recommended_pct,
            aggressive_position_pct=aggressive_pct,
            kelly_validity=kelly_validity,
            is_profitable=numerator > 0
        )

        # Log results
        logger.info(
            f"💰 Kelly Criterion Calculation:\n"
            f"  Win Rate: {win_rate*100:.1f}%\n"
            f"  Avg Win: {avg_win_pct*100:.2f}% | Avg Loss: {avg_loss_pct*100:.2f}%\n"
            f"  Odds Ratio (b): {b:.2f}\n"
            f"  Kelly Fraction (f*): {kelly_full*100:.2f}%\n"
            f"  Position Sizing (Conservative): {recommended_pct:.2f}% (quarter-Kelly)\n"
            f"  Position Sizing (Aggressive): {aggressive_pct:.2f}% (half-Kelly)\n"
            f"  Expected Value: {'✅ PROFITABLE' if is_profitable else '❌ NOT PROFITABLE'}"
        )

        return result

    @staticmethod
    def compare_kelly_to_current(
        kelly_result: KellyResult,
        current_position_pct: float
    ) -> Dict:
        """Compare current position sizing to Kelly recommendation.

        Args:
            kelly_result: KellyResult from calculate_kelly()
            current_position_pct: Current position sizing as % of capital

        Returns:
            Dict with comparison and recommendation
        """
        if not kelly_result:
            return {"recommendation": "INVALID_KELLY"}

        if current_position_pct < kelly_result.recommended_position_pct * 0.8:
            return {
                "status": "UNDER_SIZED",
                "recommendation": f"Increase from {current_position_pct:.2f}% to {kelly_result.recommended_position_pct:.2f}%",
                "opportunity_cost": kelly_result.recommended_position_pct - current_position_pct,
                "details": "Current position sizing is conservative; Kelly recommends more aggressive sizing"
            }
        elif current_position_pct > kelly_result.aggressive_position_pct * 1.2:
            return {
                "status": "OVER_SIZED",
                "recommendation": f"Decrease from {current_position_pct:.2f}% to {kelly_result.aggressive_position_pct:.2f}%",
                "risk_excess": current_position_pct - kelly_result.aggressive_position_pct,
                "details": "Current position sizing exceeds even aggressive Kelly recommendation; risk too high"
            }
        else:
            return {
                "status": "OPTIMAL",
                "recommendation": f"Keep at {current_position_pct:.2f}% (within Kelly range)",
                "details": "Current position sizing is Kelly-aligned"
            }

    @staticmethod
    def generate_position_sizing_table(
        win_rates: list,
        avg_win_pct: float = 0.02,
        avg_loss_pct: float = 0.01
    ) -> str:
        """Generate a table showing position sizing for various win rates.

        Useful for Phase 3 planning: "If we improve to X% win rate, use Y% position sizing."

        Args:
            win_rates: List of win rates to analyze (e.g., [0.305, 0.32, 0.35])
            avg_win_pct: Average win percentage (default +2%)
            avg_loss_pct: Average loss percentage (default -1%)

        Returns:
            Formatted table as string
        """
        table = "\n📊 POSITION SIZING TABLE BY WIN RATE\n"
        table += "=" * 100 + "\n"
        table += f"{'Win Rate':<12} {'Kelly (f*)':<15} {'Quarter-Kelly':<18} {'Half-Kelly':<15} {'Status':<20}\n"
        table += "-" * 100 + "\n"

        for wr in win_rates:
            result = KellyCalculator.calculate_kelly(wr, avg_win_pct, avg_loss_pct)

            if result.is_profitable:
                status = "✅ Profitable"
            else:
                status = "❌ Not profitable"

            table += (
                f"{wr*100:>10.1f}%  "
                f"{result.kelly_fraction_full*100:>12.2f}%  "
                f"{result.recommended_position_pct:>15.2f}%  "
                f"{result.aggressive_position_pct:>13.2f}%  "
                f"{status:<20}\n"
            )

        table += "=" * 100 + "\n"
        return table
