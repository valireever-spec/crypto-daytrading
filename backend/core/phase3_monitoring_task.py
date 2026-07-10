"""
Phase 3 Monitoring Task - Periodic monitoring of statistics and Kelly recommendations.

Should be called periodically (e.g., every hour or daily) to:
1. Calculate statistics from recent trades
2. Generate Kelly recommendations
3. Log summaries
4. Check for statistical improvement
"""

import logging
from typing import Optional

from backend.exchange.paper_trading import get_paper_trading
from backend.core.phase3_statistics_monitor import get_statistics_monitor
from backend.core.dynamic_position_sizer import DynamicPositionSizer

logger = logging.getLogger(__name__)


async def run_phase3_monitoring_task(limit_trades: int = 150) -> Optional[dict]:
    """Run Phase 3 monitoring task.

    Args:
        limit_trades: Number of recent trades to analyze

    Returns:
        Dict with monitoring results, or None if error
    """
    try:
        # Get recent trades from paper trading engine
        engine = get_paper_trading()
        if not engine:
            logger.warning("Paper trading engine not initialized")
            return None

        trades = engine.get_trades(limit=limit_trades)
        if not trades:
            logger.warning("No trades available for analysis")
            return None

        # Convert to format expected by statistics monitor
        trade_data = [
            {
                "symbol": t.get("symbol", "UNKNOWN"),
                "pnl": t.get("pnl", 0.0),
                "pnl_pct": t.get("pnl_pct", 0.0),
                "is_win": t.get("pnl", 0.0) > 0,
            }
            for t in trades
        ]

        # Load trades into statistics monitor
        monitor = get_statistics_monitor()
        summary = monitor.load_trades_from_db(
            trade_data, period_name=f"Last {len(trade_data)} trades"
        )

        if not summary:
            logger.warning("Failed to generate statistical summary")
            return None

        # Log statistics
        monitor.log_summary()

        # Calculate Kelly recommendation
        kelly_rec = DynamicPositionSizer.calculate_optimal_position_size(
            summary.win_rate, current_position_pct=0.5
        )

        # Log Kelly recommendation
        logger.info(
            f"💰 Kelly Position Sizing: {kelly_rec.get('recommendation', 'REVIEW')} "
            f"(from {kelly_rec.get('current_position_pct', 0):.2f}% "
            f"to {kelly_rec.get('suggested_position_pct', 0):.2f}%)"
        )

        # Check for improvement vs baseline
        if monitor.baseline_summary:
            improvement = monitor.check_statistical_improvement()
            logger.info(
                f"📈 Improvement vs Baseline: {improvement.get('improvement_pct', 0):.1f}% "
                f"({'✅ Statistically improved' if improvement.get('is_improved') else '⚠️ Not statistically significant'})"
            )

        # Save daily log
        monitor.save_daily_log()

        return {
            "status": "SUCCESS",
            "trades_analyzed": len(trade_data),
            "win_rate_pct": summary.win_rate * 100,
            "avg_pnl": summary.avg_pnl,
            "kelly_recommendation": kelly_rec.get("recommendation"),
            "statistical_improvement": improvement.get("is_improved", False) if monitor.baseline_summary else None,
        }

    except Exception as e:
        logger.error(f"Phase 3 monitoring task failed: {e}", exc_info=True)
        return None


# Monitoring schedule (can be called from systemd timer or cron)
# Recommended: Run daily at 00:00 UTC (midnight) to capture full day's trading
# Command: python -m backend.core.phase3_monitoring_task
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_phase3_monitoring_task())
    if result:
        logger.info(f"✅ Monitoring task completed: {result}")
    else:
        logger.error("❌ Monitoring task failed")
