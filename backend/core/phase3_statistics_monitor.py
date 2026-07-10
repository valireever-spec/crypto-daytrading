"""
Phase 3 Statistics Monitor - Integration of statistical validation and Kelly positioning.

Monitors trading performance and provides:
- Daily statistical summaries (win rate, SE, 95% CI)
- Kelly criterion recommendations for position sizing
- Market regime classification tracking
- Statistical improvement analysis across test tiers
"""

import logging
import json
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import asdict

from backend.core.statistical_validator import (
    StatisticalValidator,
    TradeResult,
    StatisticalSummary,
)
from backend.core.kelly_calculator import KellyCalculator
from backend.core.market_regime_detector import MarketRegimeDetector

logger = logging.getLogger(__name__)


class Phase3StatisticsMonitor:
    """Monitor Phase 3 fine-tuning with statistical rigor."""

    def __init__(self):
        """Initialize the statistics monitor."""
        self.baseline_summary: Optional[StatisticalSummary] = None
        self.current_summary: Optional[StatisticalSummary] = None
        self.tier_summaries: Dict[str, StatisticalSummary] = {}

    def load_trades_from_db(
        self, trades: List[Dict], period_name: str = "Period"
    ) -> StatisticalSummary:
        """Load trades and calculate statistical summary.

        Args:
            trades: List of trade dicts with keys: symbol, pnl, pnl_pct, is_win
            period_name: Name of the period (e.g., "Days 1-3 Baseline")

        Returns:
            StatisticalSummary with all statistical measures
        """
        trade_results = [
            TradeResult(
                symbol=t.get("symbol", "UNKNOWN"),
                pnl=t.get("pnl", 0.0),
                pnl_pct=t.get("pnl_pct", 0.0),
                is_win=t.get("is_win", False),
            )
            for t in trades
        ]

        summary = StatisticalValidator.evaluate_period(
            trade_results, period_name=period_name
        )

        if summary.period_name.startswith("Days 1-3"):
            self.baseline_summary = summary
        self.current_summary = summary

        return summary

    def calculate_kelly_recommendation(
        self,
        win_rate: float,
        avg_win_pct: float = 0.02,
        avg_loss_pct: float = 0.01,
    ) -> Dict:
        """Calculate Kelly criterion and position sizing recommendation.

        Args:
            win_rate: Win rate from statistical summary
            avg_win_pct: Average win as % (default +2%)
            avg_loss_pct: Average loss as % (default -1%)

        Returns:
            Dict with Kelly calculation and sizing recommendations
        """
        kelly_result = KellyCalculator.calculate_kelly(
            win_rate, avg_win_pct, avg_loss_pct
        )

        if not kelly_result:
            return {"status": "INVALID", "reason": "Strategy not profitable at this win rate"}

        return {
            "status": "VALID",
            "win_rate": kelly_result.win_rate * 100,
            "kelly_fraction_full": kelly_result.kelly_fraction_full * 100,
            "kelly_fraction_half": kelly_result.kelly_fraction_half * 100,
            "kelly_fraction_quarter": kelly_result.kelly_fraction_quarter * 100,
            "recommended_position_pct": kelly_result.recommended_position_pct,
            "aggressive_position_pct": kelly_result.aggressive_position_pct,
            "is_profitable": kelly_result.is_profitable,
            "kelly_validity": kelly_result.kelly_validity,
        }

    def check_statistical_improvement(self) -> Dict:
        """Check if current period shows statistical improvement over baseline.

        Returns:
            Dict with improvement analysis
        """
        if not self.baseline_summary or not self.current_summary:
            return {"status": "INCOMPLETE", "reason": "Missing baseline or current summary"}

        improvement = StatisticalValidator.is_statistically_improved(
            self.current_summary, self.baseline_summary, improvement_threshold=0.025
        )

        return {
            "improvement_pct": improvement.get("improvement_pct", 0.0),
            "is_improved": improvement.get("is_improved", False),
            "reason": improvement.get("reason", ""),
            "ci_overlap": improvement.get("overlap", True),
            "baseline_ci": [
                self.baseline_summary.ci_lower * 100,
                self.baseline_summary.ci_upper * 100,
            ],
            "current_ci": [
                self.current_summary.ci_lower * 100,
                self.current_summary.ci_upper * 100,
            ],
        }

    def generate_daily_log(self) -> Dict:
        """Generate comprehensive daily log for Phase 3 monitoring.

        Returns:
            Dict with all daily metrics and recommendations
        """
        if not self.current_summary:
            return {"status": "NO_DATA", "timestamp": datetime.utcnow().isoformat()}

        daily_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "period": self.current_summary.period_name,
                "trades": self.current_summary.total_trades,
                "wins": self.current_summary.winning_trades,
                "losses": self.current_summary.losing_trades,
                "win_rate_pct": self.current_summary.win_rate * 100,
                "avg_pnl": self.current_summary.avg_pnl,
                "avg_win_pnl": self.current_summary.avg_win_pnl,
                "avg_loss_pnl": self.current_summary.avg_loss_pnl,
                "ci_lower_pct": self.current_summary.ci_lower * 100,
                "ci_upper_pct": self.current_summary.ci_upper * 100,
                "standard_error_pct": self.current_summary.standard_error * 100,
                "confidence_level": self.current_summary.confidence_level,
                "data_sufficiency": self.current_summary.is_sufficient_data,
            },
            "kelly": self.calculate_kelly_recommendation(
                self.current_summary.win_rate
            ),
        }

        if self.baseline_summary:
            daily_log["improvement"] = self.check_statistical_improvement()

        return daily_log

    def save_daily_log(self, output_path: str = "logs/phase3_daily_log.json") -> bool:
        """Save daily log to file.

        Args:
            output_path: Path to save JSON log

        Returns:
            True if successful, False otherwise
        """
        try:
            daily_log = self.generate_daily_log()

            # Load existing log if it exists
            existing_logs = []
            try:
                with open(output_path, "r") as f:
                    existing_logs = json.load(f)
                    if not isinstance(existing_logs, list):
                        existing_logs = [existing_logs]
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            # Append new log
            existing_logs.append(daily_log)

            # Save updated log
            import os
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(existing_logs, f, indent=2, default=str)

            logger.info(f"✅ Daily log saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save daily log: {e}", exc_info=True)
            return False

    def generate_tier_summary(self, tier_name: str, trades: List[Dict]) -> Dict:
        """Generate summary for a specific test tier.

        Args:
            tier_name: Tier identifier (e.g., "Tier 1a - RSI Threshold")
            trades: List of trades in this tier

        Returns:
            Dict with tier summary and comparisons
        """
        summary = self.load_trades_from_db(trades, period_name=tier_name)
        self.tier_summaries[tier_name] = summary

        tier_summary = {
            "tier": tier_name,
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "trades": summary.total_trades,
                "wins": summary.winning_trades,
                "losses": summary.losing_trades,
                "win_rate_pct": summary.win_rate * 100,
                "ci_lower_pct": summary.ci_lower * 100,
                "ci_upper_pct": summary.ci_upper * 100,
                "avg_pnl": summary.avg_pnl,
                "confidence_level": summary.confidence_level,
            },
            "kelly": self.calculate_kelly_recommendation(summary.win_rate),
        }

        # Compare to previous tier
        if self.baseline_summary:
            comparison = StatisticalValidator.is_statistically_improved(
                summary, self.baseline_summary, improvement_threshold=0.025
            )
            tier_summary["vs_baseline"] = comparison

        return tier_summary

    def generate_positioning_table(self) -> str:
        """Generate position sizing table for various win rate scenarios.

        Returns:
            Formatted table string
        """
        win_rates = [0.305, 0.32, 0.34, 0.36, 0.38, 0.40]
        return KellyCalculator.generate_position_sizing_table(
            win_rates, avg_win_pct=0.02, avg_loss_pct=0.01
        )

    def log_summary(self) -> None:
        """Log current statistics summary to logger."""
        if not self.current_summary:
            logger.info("No statistics available yet")
            return

        logger.info(
            f"📊 Phase 3 Statistics Summary:\n"
            f"  Period: {self.current_summary.period_name}\n"
            f"  Trades: {self.current_summary.total_trades} "
            f"({self.current_summary.winning_trades}W/{self.current_summary.losing_trades}L)\n"
            f"  Win Rate: {self.current_summary.win_rate*100:.1f}% "
            f"[95% CI: {self.current_summary.ci_lower*100:.1f}%-{self.current_summary.ci_upper*100:.1f}%]\n"
            f"  Data Sufficiency: {self.current_summary.confidence_level}\n"
            f"  Avg P&L: €{self.current_summary.avg_pnl:.2f}"
        )

        kelly = self.calculate_kelly_recommendation(self.current_summary.win_rate)
        if kelly.get("status") == "VALID":
            logger.info(
                f"💰 Kelly Recommendation (Quarter-Kelly):\n"
                f"  Recommended Position Size: {kelly.get('recommended_position_pct', 0):.2f}%\n"
                f"  Kelly Fraction (f*): {kelly.get('kelly_fraction_full', 0):.2f}%\n"
                f"  Status: {'✅ PROFITABLE' if kelly.get('is_profitable') else '❌ NOT PROFITABLE'}"
            )


# Singleton instance
_monitor_instance: Optional[Phase3StatisticsMonitor] = None


def get_statistics_monitor() -> Phase3StatisticsMonitor:
    """Get or create the Phase 3 statistics monitor singleton."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = Phase3StatisticsMonitor()
    return _monitor_instance
