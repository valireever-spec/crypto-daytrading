"""
Statistical validation for Phase 3 fine-tuning.

Implements:
- Standard error calculation
- 95% confidence intervals
- Statistical significance testing (p-values)
- Data sufficiency checks
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from math import sqrt

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Single trade result."""
    symbol: str
    pnl: float
    pnl_pct: float
    is_win: bool


@dataclass
class StatisticalSummary:
    """Statistical analysis of a test period."""
    period_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    avg_win_pnl: float
    avg_loss_pnl: float

    # Statistical measures
    standard_error: float
    ci_lower: float  # 95% confidence interval lower bound
    ci_upper: float  # 95% confidence interval upper bound

    # Significance testing
    is_sufficient_data: bool
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"


class StatisticalValidator:
    """Validate trading results statistically."""

    MIN_TRADES_FOR_CONFIDENCE = 150
    MIN_TRADES_FOR_LOW_DATA = 80
    Z_SCORE_95_CONFIDENCE = 1.96  # 95% confidence interval

    @staticmethod
    def calculate_standard_error(win_rate: float, n_trades: int) -> float:
        """Calculate standard error of win rate.

        SE = sqrt(p * (1-p) / n)
        where p = win rate, n = number of trades
        """
        if n_trades < 1:
            return 1.0

        p = win_rate
        se = sqrt(p * (1 - p) / n_trades)
        return se

    @staticmethod
    def calculate_confidence_interval(
        win_rate: float,
        n_trades: int,
        z_score: float = Z_SCORE_95_CONFIDENCE
    ) -> Tuple[float, float]:
        """Calculate 95% confidence interval for win rate.

        CI = win_rate ± (z_score * SE)
        """
        se = StatisticalValidator.calculate_standard_error(win_rate, n_trades)
        margin = z_score * se

        ci_lower = max(0.0, win_rate - margin)
        ci_upper = min(1.0, win_rate + margin)

        return ci_lower, ci_upper

    @staticmethod
    def evaluate_period(
        trades: List[TradeResult],
        period_name: str = "Test Period",
        baseline_win_rate: float = None
    ) -> StatisticalSummary:
        """Evaluate trading period statistically.

        Args:
            trades: List of trade results
            period_name: Name of test period (e.g., "Days 1-3 Baseline")
            baseline_win_rate: For comparison (if available)

        Returns:
            StatisticalSummary with all statistical measures
        """
        n_trades = len(trades)

        if n_trades == 0:
            logger.warning(f"{period_name}: No trades to analyze")
            return None

        # Count wins/losses
        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        win_rate = len(wins) / n_trades if n_trades > 0 else 0.0

        # Calculate P&L metrics
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / n_trades if n_trades > 0 else 0.0

        avg_win_pnl = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        avg_loss_pnl = sum(t.pnl for t in losses) / len(losses) if losses else 0.0

        # Statistical calculations
        se = StatisticalValidator.calculate_standard_error(win_rate, n_trades)
        ci_lower, ci_upper = StatisticalValidator.calculate_confidence_interval(win_rate, n_trades)

        # Data sufficiency assessment
        if n_trades >= StatisticalValidator.MIN_TRADES_FOR_CONFIDENCE:
            is_sufficient = True
            confidence_level = "HIGH"
        elif n_trades >= StatisticalValidator.MIN_TRADES_FOR_LOW_DATA:
            is_sufficient = True
            confidence_level = "MEDIUM"
        else:
            is_sufficient = False
            confidence_level = "LOW"

        summary = StatisticalSummary(
            period_name=period_name,
            total_trades=n_trades,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            avg_win_pnl=avg_win_pnl,
            avg_loss_pnl=avg_loss_pnl,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            is_sufficient_data=is_sufficient,
            confidence_level=confidence_level
        )

        # Log results
        logger.info(
            f"📊 {period_name} Statistical Summary:\n"
            f"  Trades: {n_trades} ({len(wins)} wins, {len(losses)} losses)\n"
            f"  Win Rate: {win_rate*100:.1f}% [95% CI: {ci_lower*100:.1f}%-{ci_upper*100:.1f}%]\n"
            f"  Avg P&L: €{avg_pnl:.2f} (Win: €{avg_win_pnl:.2f}, Loss: €{avg_loss_pnl:.2f})\n"
            f"  Data Sufficiency: {confidence_level} (SE: ±{se*100:.1f}%)"
        )

        return summary

    @staticmethod
    def is_statistically_improved(
        current: StatisticalSummary,
        baseline: StatisticalSummary,
        improvement_threshold: float = 0.025  # 2.5% improvement
    ) -> Dict:
        """Check if current period is statistically better than baseline.

        Args:
            current: Current period statistics
            baseline: Baseline period statistics
            improvement_threshold: Minimum improvement to consider significant (default 2.5%)

        Returns:
            Dict with:
            - is_improved: bool
            - reason: str
            - improvement_pct: float
            - overlap: bool (whether CIs overlap)
        """
        if not current or not baseline:
            return {"is_improved": False, "reason": "Missing data"}

        improvement = current.win_rate - baseline.win_rate

        # Check if confidence intervals overlap
        ci_overlap = (
            current.ci_lower <= baseline.ci_upper and
            current.ci_upper >= baseline.ci_lower
        )

        # Decision logic
        if improvement >= improvement_threshold and not ci_overlap:
            return {
                "is_improved": True,
                "reason": f"Statistically significant improvement: {improvement*100:.1f}% (no CI overlap)",
                "improvement_pct": improvement * 100,
                "overlap": ci_overlap
            }
        elif improvement >= improvement_threshold and ci_overlap:
            return {
                "is_improved": False,
                "reason": f"Improvement {improvement*100:.1f}% but CI overlap (not statistically distinct)",
                "improvement_pct": improvement * 100,
                "overlap": ci_overlap
            }
        elif improvement >= 0:
            return {
                "is_improved": False,
                "reason": f"Marginal improvement: {improvement*100:.1f}% (< {improvement_threshold*100:.1f}% threshold)",
                "improvement_pct": improvement * 100,
                "overlap": ci_overlap
            }
        else:
            return {
                "is_improved": False,
                "reason": f"Regression: {improvement*100:.1f}% (worse than baseline)",
                "improvement_pct": improvement * 100,
                "overlap": ci_overlap
            }
