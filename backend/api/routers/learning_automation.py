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
    executions: List[ExecutionRecord] = Body(..., description="Execution records"),
) -> Dict[str, Any]:
    """
    Run recommendation tracking daemon: match recommendations to portfolio outcomes.

    Call this daily (systemd timer at 08:30) with execution log.

    Parameters:
    -----------
    executions : list
        Daily execution records (buy/sell)

    Returns:
    --------
    {
        "matched_count": 5,
        "recorded_count": 5,
        "errors": 0,
        "timestamp": "2026-06-24T08:30:00Z"
    }
    """
    try:
        if not executions:
            logger.warning("No executions provided for sync")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "matched_count": 0,
                "recorded_count": 0,
                "errors": 0,
            }

        daemon = get_recommendation_tracking_daemon()

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

        result = daemon.run_daily_sync(exec_list)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    except Exception as e:
        logger.error(f"Sync error: {e}")
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

        tracker = get_recommendation_tracker()
        learner = get_scenario_probability_learner()
        calibrator = get_cost_model_calibrator()
        daemon = get_recommendation_tracking_daemon()
        scheduler = get_scenario_auto_reweighting_scheduler()

        # Determine component statuses
        tracker_status = "operational" if tracker.recommendations else "initializing"
        learner_status = "operational"
        calibrator_status = "learning" if len(calibrator.executions) < 20 else "confident"
        daemon_status = "ready" if daemon.last_run else "awaiting_first_run"
        scheduler_status = "ready"

        # Overall status
        all_statuses = [tracker_status, learner_status, calibrator_status, daemon_status, scheduler_status]
        if all(s in ["operational", "ready", "confident"] for s in all_statuses):
            overall = "healthy"
        elif all(s != "error" for s in all_statuses):
            overall = "degraded"
        else:
            overall = "error"

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        }

    except Exception as e:
        logger.error(f"Error getting pipeline health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
