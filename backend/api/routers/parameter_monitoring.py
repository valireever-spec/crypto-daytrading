"""API endpoints for real-time parameter monitoring.

Exposes critical trading parameters:
- Trend filter (1h RSI > 50)
- Signals (generation, quality, strength)
- Stops (stop loss effectiveness)
- Targets (profit target effectiveness)
- Exit reasons (why positions closed)
- Entry reasons (why positions opened)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

router = APIRouter(prefix="/api/parameters", tags=["Parameter Monitoring"])


@router.get("/summary")
async def get_parameter_summary():
    """Get complete parameter monitoring summary."""
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        summary = monitor.get_parameter_summary()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "OK",
            "parameters": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend-filter")
async def get_trend_filter(minutes: int = 60):
    """Monitor trend filter (1h RSI > 50) effectiveness.

    Returns:
    - total_signals: How many signals generated
    - trend_filter_passed: Signals that passed 1h RSI > 50 check
    - pass_rate_pct: Percentage that passed
    - recent_1h_rsi_range: Current market strength
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_trend_filter_stats(minutes=minutes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": minutes,
            "trend_filter": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_signals_quality(minutes: int = 60):
    """Monitor signal quality.

    Returns:
    - total_signals: Count of signals generated
    - avg_strength: Average signal strength (0-100)
    - signal_strength_distribution: Weak/Medium/Strong breakdown
    - regime_distribution: Uptrend/Downtrend/Ranging breakdown
    - signals_per_minute: Generation rate
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_signal_quality(minutes=minutes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": minutes,
            "signals": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stops")
async def get_stop_loss_monitoring(minutes: int = 120):
    """Monitor stop loss effectiveness.

    Returns:
    - stop_loss_hits: Count of stop loss exits
    - avg_loss_pct: Average loss percentage
    - worst_loss_pct: Worst single stop loss
    - best_loss_pct: Best (smallest) stop loss
    - avg_hold_seconds: How long before stop hit
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_stop_loss_stats(minutes=minutes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": minutes,
            "stops": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/targets")
async def get_profit_target_monitoring(minutes: int = 120):
    """Monitor profit target effectiveness.

    Returns:
    - profit_target_hits: Count of profit target exits
    - avg_win_pct: Average profit percentage
    - best_win_pct: Best single profit target hit
    - worst_win_pct: Smallest profit target hit
    - avg_hold_seconds: How long to reach target
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_profit_target_stats(minutes=minutes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": minutes,
            "targets": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exit-reasons")
async def get_exit_reasons(minutes: int = 120):
    """Monitor exit reason distribution.

    Returns:
    - distribution: Count of each exit reason type
    - avg_pnl_by_reason: Average P&L for each exit reason
    - most_common_exit: Which reason exits most often

    Shows if you're exiting more by stop loss vs profit target vs timeout.
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_exit_reason_distribution(minutes=minutes)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_minutes": minutes,
            "exit_reasons": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entry-reasons")
async def get_entry_reasons():
    """Monitor entry reason distribution.

    Returns:
    - distribution: Count of each entry reason type
    - most_common_entry: Which reason enters most often

    Shows if you're entering on momentum, RSI dips, grid, etc.
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()
        data = monitor.get_entry_reason_distribution()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_reasons": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-check")
async def parameter_health_check():
    """Quick health check of all critical parameters.

    Returns status of each parameter type.
    GREEN: Operating normally
    YELLOW: Minor issues
    RED: Critical issue
    """
    try:
        from backend.core.parameter_monitor import get_parameter_monitor

        monitor = get_parameter_monitor()

        # Quick health assessment
        trend = monitor.get_trend_filter_stats(minutes=60)
        signals = monitor.get_signal_quality(minutes=60)
        stops = monitor.get_stop_loss_stats(minutes=120)
        targets = monitor.get_profit_target_stats(minutes=120)
        exit_reasons = monitor.get_exit_reason_distribution(minutes=120)
        entry_reasons = monitor.get_entry_reason_distribution()

        health = {
            "trend_filter": (
                "🟢 GREEN" if trend.get("pass_rate_pct", 0) >= 50 else
                "🟡 YELLOW" if trend.get("pass_rate_pct", 0) >= 20 else
                "🔴 RED"
            ),
            "signals": (
                "🟢 GREEN" if signals.get("total_signals", 0) > 0 else
                "🟡 YELLOW"
            ),
            "stops": (
                "🟢 GREEN" if stops.get("status") == "OK" else
                "🟡 YELLOW"
            ),
            "targets": (
                "🟢 GREEN" if targets.get("status") == "OK" else
                "🟡 YELLOW"
            ),
            "exit_reasons": (
                "🟢 GREEN" if exit_reasons.get("total_exits", 0) > 0 else
                "🟡 YELLOW"
            ),
            "entry_reasons": (
                "🟢 GREEN" if entry_reasons.get("total_entries", 0) > 0 else
                "🟡 YELLOW"
            ),
        }

        overall_status = (
            "🟢 HEALTHY" if all(s.startswith("🟢") for s in health.values()) else
            "🟡 CAUTION" if any(s.startswith("🟡") for s in health.values()) else
            "🔴 CRITICAL"
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "parameters": health,
            "summary": {
                "trend_filter_pass_rate": trend.get("pass_rate_pct", 0),
                "signal_count_1h": signals.get("total_signals", 0),
                "stop_loss_hits": stops.get("stop_loss_hits", 0),
                "profit_target_hits": targets.get("profit_target_hits", 0),
                "total_exits": exit_reasons.get("total_exits", 0),
                "total_entries": entry_reasons.get("total_entries", 0),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_parameter_dashboard():
    """Serve parameter monitoring dashboard HTML."""
    dashboard_path = Path(__file__).parent.parent.parent / "frontend" / "parameter_monitor_dashboard.html"

    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        return HTMLResponse("""
        <html>
            <body style="background: #0f1419; color: #e0e0e0; font-family: monospace; padding: 20px;">
                <h1>Parameter Monitor Dashboard</h1>
                <p>Dashboard file not found at: {}</p>
                <p>Available endpoints:</p>
                <ul>
                    <li>GET /api/parameters/summary - All parameters</li>
                    <li>GET /api/parameters/health-check - System health</li>
                    <li>GET /api/parameters/trend-filter - Trend filter metrics</li>
                    <li>GET /api/parameters/signals - Signal quality</li>
                    <li>GET /api/parameters/stops - Stop loss effectiveness</li>
                    <li>GET /api/parameters/targets - Profit target effectiveness</li>
                    <li>GET /api/parameters/exit-reasons - Exit reason breakdown</li>
                    <li>GET /api/parameters/entry-reasons - Entry reason breakdown</li>
                </ul>
            </body>
        </html>
        """.format(str(dashboard_path)))
