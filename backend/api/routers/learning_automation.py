"""
Phase 330: Learning Automation API

Endpoints for recommendation tracking daemon and scenario auto-reweighting.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel

from backend.analytics.recommendation_tracking_daemon import get_recommendation_tracking_daemon
from backend.analytics.scenario_auto_reweighting_scheduler import get_scenario_auto_reweighting_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


class ExecutionRecord(BaseModel):
    """Execution record for outcome matching."""
    symbol: str
    side: str  # BUY or SELL
    timestamp: str
    price: float
    allocation_pct: float
    quantity: float = 0.0


@router.post("/daemon/sync-recommendations")
async def sync_recommendations_to_outcomes(
    executions: List[ExecutionRecord] = Body(default=[], description="Execution records (optional; auto-loads from audit log if empty)"),
    auto_load: bool = Query(True, description="Auto-load from audit log if no executions provided"),
) -> Dict[str, Any]:
    """
    Run recommendation tracking daemon: match recommendations to portfolio outcomes.

    Call this daily (systemd timer at 08:30). Auto-loads executions from audit log if not provided.

    Parameters:
    -----------
    executions : list
        Daily execution records (buy/sell) - optional, auto-loads from trade_audit.jsonl if empty
    auto_load : bool
        If true and executions empty, automatically load from audit log

    Returns:
    --------
    {
        "matched_count": 5,
        "recorded_count": 5,
        "errors": 0,
        "skipped_duplicates": 0,
        "source": "provided" | "audit_log",
        "timestamp": "2026-06-24T08:30:00Z"
    }
    """
    try:
        from backend.analytics.execution_log_loader import (
            load_executions_from_audit_log,
            get_last_sync_timestamp,
            save_sync_timestamp,
        )

        daemon = get_recommendation_tracking_daemon()
        exec_list = []
        source = "provided"

        # Use provided executions or auto-load from audit log
        if executions:
            # Convert Pydantic models to dicts
            exec_list = [
                {
                    "symbol": e.symbol,
                    "side": e.side,
                    "timestamp": e.timestamp,
                    "price": e.price,
                    "allocation_pct": e.allocation_pct,
                    "quantity": e.quantity,
                }
                for e in executions
            ]
        elif auto_load:
            # Auto-load from audit log since last sync
            last_sync = get_last_sync_timestamp()
            exec_list = load_executions_from_audit_log(since_timestamp=last_sync)
            source = "audit_log"
        else:
            logger.warning("No executions and auto_load disabled")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "matched_count": 0,
                "recorded_count": 0,
                "errors": 0,
                "skipped_duplicates": 0,
                "source": "none",
            }

        result = daemon.run_daily_sync(exec_list)

        # Save sync timestamp for next run
        if result["recorded_count"] > 0 or result["matched_count"] > 0:
            save_sync_timestamp(datetime.now(timezone.utc).isoformat())

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            **result,
        }

    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daemon/last-run")
async def get_daemon_last_run() -> Dict[str, Any]:
    """
    Get last daemon run timestamp and status.

    Returns:
    --------
    {
        "last_run": "2026-06-24T08:30:00Z",
        "status": "ready"
    }
    """
    try:
        daemon = get_recommendation_tracking_daemon()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_run": daemon.last_run,
            "status": "ready",
        }

    except Exception as e:
        logger.error(f"Error getting daemon status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/reweight-scenarios")
async def trigger_scenario_reweighting() -> Dict[str, Any]:
    """
    Manually trigger scenario auto-reweighting (or via systemd timer monthly).

    Returns:
    --------
    {
        "status": "reweighted",
        "old_weights": {...},
        "new_weights": {...},
        "accuracy_pct": 75.2,
        "scenario_accuracy": {...},
        "recommendation_count": 42,
        "timestamp": "2026-06-24T..."
    }
    """
    try:
        scheduler = get_scenario_auto_reweighting_scheduler()
        result = scheduler.run_reweighting()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    except Exception as e:
        logger.error(f"Reweighting error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """
    Get scenario auto-reweighting scheduler status.

    Returns:
    --------
    {
        "last_reweight": "2026-06-23T12:00:00Z",
        "reweight_count": 3,
        "min_total_recommendations_for_reweight": 15,
        "status": "ready"
    }
    """
    try:
        scheduler = get_scenario_auto_reweighting_scheduler()
        status = scheduler.get_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **status,
        }

    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/history")
async def get_reweighting_history(
    limit: int = Query(10, description="Number of recent reweightings"),
) -> Dict[str, Any]:
    """
    Get history of scenario reweightings.

    Parameters:
    -----------
    limit : int
        Maximum number of records to return

    Returns:
    --------
    {
        "history": [
            {
                "timestamp": "2026-06-23T12:00:00Z",
                "old_weights": {...},
                "new_weights": {...},
                "accuracy": {...}
            },
            ...
        ]
    }
    """
    try:
        scheduler = get_scenario_auto_reweighting_scheduler()
        history = scheduler.get_reweighting_history()[-limit:]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "history": history,
        }

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/learned-estimates")
async def get_learned_cost_estimates(
    symbols: List[str] = Query(default=[], description="Symbols to estimate costs for (empty = all)"),
) -> Dict[str, Any]:
    """
    Get learned cost estimates from calibration data.

    Returns actual execution costs learned from historical trades.

    Parameters:
    -----------
    symbols : list
        Symbols to estimate (if empty, returns all learned symbols)

    Returns:
    --------
    {
        "total_cost_pct": 0.45,
        "costs_by_symbol": {
            "AAPL": {
                "execution_cost_pct": 0.15,
                "slippage_cost_pct": 0.05,
                "total_cost_pct": 0.20,
                "confidence": "learned",
                "samples": 8
            }
        }
    }
    """
    try:
        from backend.analytics.cost_model_calibrator import get_cost_model_calibrator, get_learned_costs_for_trade

        calibrator = get_cost_model_calibrator()
        profiles = calibrator.get_all_profiles()

        # Filter by requested symbols
        if symbols:
            profiles = {s: p for s, p in profiles.items() if s in symbols}

        costs_by_symbol = {}
        total_cost = 0.0

        for symbol, profile in profiles.items():
            cost_data = get_learned_costs_for_trade(symbol, volume_pct=1.0)
            if cost_data:
                costs_by_symbol[symbol] = cost_data
                total_cost += cost_data.get("total_cost_pct", 0)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_cost_pct": round(total_cost, 4),
            "costs_by_symbol": costs_by_symbol,
            "learned_symbols_count": len(profiles),
        }

    except Exception as e:
        logger.error(f"Error getting learned costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/accuracy-metrics")
async def get_dashboard_accuracy_metrics() -> Dict[str, Any]:
    """
    Get recommendation accuracy metrics for dashboard.

    Returns:
    --------
    {
        "overall_accuracy_pct": 75.2,
        "total_recommendations": 47,
        "correct_direction": 38,
        "scenario_accuracy": {
            "base": 80.5,
            "upside": 70.2,
            "downside": 65.1
        },
        "symbol_accuracy": {
            "AAPL": 78.3,
            "MSFT": 72.5,
            ...
        },
        "trend": [
            {"date": "2026-06-24", "accuracy": 75.2, "count": 5}
        ]
    }
    """
    try:
        from backend.analytics.recommendation_tracker import get_recommendation_tracker

        tracker = get_recommendation_tracker()
        metrics = tracker.analyze_accuracy()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_accuracy_pct": round(metrics.accuracy_pct, 1),
            "total_recommendations": metrics.total_recommendations,
            "correct_direction": metrics.correct_direction,
            "within_magnitude": metrics.within_magnitude_tolerance,
            "scenario_accuracy": {
                s: round(a, 1) for s, a in metrics.scenario_accuracy.items()
            },
            "symbol_accuracy": {
                s: round(a, 1) for s, a in metrics.symbol_accuracy.items()
            },
        }

    except Exception as e:
        logger.error(f"Error getting accuracy metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/scenario-heatmap")
async def get_dashboard_scenario_heatmap() -> Dict[str, Any]:
    """
    Get scenario performance heatmap for dashboard.

    Returns:
    --------
    {
        "scenarios": {
            "base": {
                "count": 18,
                "avg_expected": 2.5,
                "avg_actual": 2.3,
                "accuracy": 77.8
            }
        },
        "matrix": [
            {"scenario": "base", "expected": 2.5, "actual": 2.3, "delta": -0.2}
        ]
    }
    """
    try:
        from backend.analytics.recommendation_tracker import get_recommendation_tracker

        tracker = get_recommendation_tracker()
        perf = tracker.get_scenario_performance()

        # Build heatmap matrix
        matrix = []
        for scenario, metrics in perf.items():
            matrix.append({
                "scenario": scenario,
                "count": metrics.get("count", 0),
                "avg_expected": metrics.get("avg_expected_return", 0),
                "avg_actual": metrics.get("avg_actual_return", 0),
                "delta": metrics.get("avg_actual_return", 0) - metrics.get("avg_expected_return", 0),
                "accuracy": metrics.get("accuracy_pct", 0),
            })

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios": perf,
            "matrix": matrix,
        }

    except Exception as e:
        logger.error(f"Error getting scenario heatmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/cost-calibration")
async def get_dashboard_cost_calibration() -> Dict[str, Any]:
    """
    Get cost calibration status for dashboard.

    Returns:
    --------
    {
        "total_executions": 142,
        "symbols_learned": 12,
        "avg_estimation_error": 35.2,
        "top_errors": [
            {"symbol": "AAPL", "error_pct": 46.7, "samples": 8}
        ],
        "readiness": "confident"
    }
    """
    try:
        from backend.analytics.cost_model_calibrator import get_cost_model_calibrator

        calibrator = get_cost_model_calibrator()
        profiles = calibrator.get_all_profiles()
        status = calibrator.get_calibration_status()

        # Calculate average error
        errors = [p.cost_estimation_error_pct for p in profiles.values()]
        avg_error = sum(errors) / len(errors) if errors else 0

        # Top error symbols
        top_errors = sorted(
            [
                {
                    "symbol": s,
                    "error_pct": round(p.cost_estimation_error_pct, 1),
                    "samples": p.execution_count,
                }
                for s, p in profiles.items()
            ],
            key=lambda x: x["error_pct"],
            reverse=True,
        )[:5]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_executions": status.get("total_executions_recorded", 0),
            "symbols_learned": status.get("symbols_with_profiles", 0),
            "avg_estimation_error": round(avg_error, 1),
            "top_errors": top_errors,
            "readiness": status.get("readiness", "learning"),
        }

    except Exception as e:
        logger.error(f"Error getting cost calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/learning-pipeline")
async def get_learning_pipeline_health() -> Dict[str, Any]:
    """
    Get overall learning pipeline health.

    Returns:
    --------
    {
        "overall_status": "healthy",
        "components": {
            "recommendation_tracker": "operational",
            "scenario_learner": "operational",
            "cost_calibrator": "learning",
            "tracking_daemon": "ready",
            "reweighting_scheduler": "ready"
        }
    }
    """
    try:
        from backend.analytics.recommendation_tracker import get_recommendation_tracker
        from backend.analytics.scenario_probability_learner import get_scenario_probability_learner
        from backend.analytics.cost_model_calibrator import get_cost_model_calibrator
        from datetime import timedelta

        tracker = get_recommendation_tracker()
        learner = get_scenario_probability_learner()
        calibrator = get_cost_model_calibrator()
        daemon = get_recommendation_tracking_daemon()
        scheduler = get_scenario_auto_reweighting_scheduler()

        now = datetime.now(timezone.utc)

        # Determine component statuses with staleness checks
        tracker_status = "operational" if tracker.recommendations else "initializing"

        # Check if tracker data is stale (>30 days old)
        if tracker.recommendations:
            latest_rec = max(
                (datetime.fromisoformat(r.timestamp) for r in tracker.recommendations),
                default=now
            )
            if now - latest_rec > timedelta(days=30):
                tracker_status = "stale"

        learner_status = "operational"
        calibrator_status = "learning" if len(calibrator.executions) < 20 else "confident"

        daemon_status = "ready"
        if daemon.last_run:
            last_run = datetime.fromisoformat(daemon.last_run)
            if now - last_run > timedelta(hours=24):
                daemon_status = "stale"
        else:
            daemon_status = "awaiting_first_run"

        scheduler_status = "ready"
        if scheduler.last_reweight_timestamp:
            last_reweight = datetime.fromisoformat(scheduler.last_reweight_timestamp)
            if now - last_reweight > timedelta(days=40):  # Monthly + buffer
                scheduler_status = "stale"

        # Overall status
        all_statuses = [tracker_status, learner_status, calibrator_status, daemon_status, scheduler_status]
        if all(s in ["operational", "ready", "confident"] for s in all_statuses):
            overall = "healthy"
        elif any(s == "stale" for s in all_statuses):
            overall = "degraded"
        elif all(s != "error" for s in all_statuses):
            overall = "degraded"
        else:
            overall = "error"

        return {
            "timestamp": now.isoformat(),
            "overall_status": overall,
            "components": {
                "recommendation_tracker": tracker_status,
                "scenario_learner": learner_status,
                "cost_calibrator": calibrator_status,
                "tracking_daemon": daemon_status,
                "reweighting_scheduler": scheduler_status,
            },
            "metrics": {
                "total_recommendations": len(tracker.recommendations),
                "total_outcomes": len(tracker.outcomes),
                "executions_recorded": len(calibrator.executions),
                "daemon_last_run": daemon.last_run,
                "scheduler_reweight_count": len(scheduler.reweight_history),
            },
            "thresholds": {
                "recommendation_stale_days": 30,
                "daemon_stale_hours": 24,
                "scheduler_stale_days": 40,
            },
        }

    except Exception as e:
        logger.error(f"Error getting pipeline health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
