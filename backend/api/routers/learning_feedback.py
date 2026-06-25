"""
Phase 329: Learning & Feedback API

Recommendation tracking, scenario learning, and cost calibration endpoints.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel

from backend.analytics.recommendation_tracker import get_recommendation_tracker
from backend.analytics.scenario_probability_learner import (
    get_scenario_probability_learner,
)
from backend.analytics.cost_model_calibrator import get_cost_model_calibrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["learning"])


class RecordRecommendationRequest(BaseModel):
    """Request to record recommendation."""

    recommendation_id: str
    symbol: str
    recommended_allocation_pct: float
    scenario: str
    expected_return_pct: float
    confidence_score: float
    rationale: str = ""


class RecordOutcomeRequest(BaseModel):
    """Request to record outcome."""

    recommendation_id: str
    holding_period_days: int
    actual_return_pct: float
    executed_allocation_pct: float
    notes: str = ""


class RecordExecutionRequest(BaseModel):
    """Request to record execution."""

    symbol: str
    side: str
    planned_cost_pct: float
    actual_cost_pct: float
    volume_pct: float


class TradeEstimate(BaseModel):
    """Trade for cost estimation."""

    symbol: str
    volume_pct: float


@router.post("/recommendations/record")
async def record_recommendation(
    request: RecordRecommendationRequest,
) -> Dict[str, Any]:
    """
    Record a recommendation for tracking.

    Parameters:
    -----------
    request : RecordRecommendationRequest
        Recommendation details

    Returns:
    --------
    {
        "recommendation_id": "uuid",
        "timestamp": "2026-06-24T...",
        "symbol": "AAPL",
        "status": "recorded"
    }
    """
    try:
        tracker = get_recommendation_tracker()

        rec = tracker.record_recommendation(
            recommendation_id=request.recommendation_id,
            symbol=request.symbol,
            recommended_allocation_pct=request.recommended_allocation_pct,
            scenario=request.scenario,
            expected_return_pct=request.expected_return_pct,
            confidence_score=request.confidence_score,
            rationale=request.rationale,
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendation_id": rec.recommendation_id,
            "symbol": rec.symbol,
            "scenario": rec.scenario,
            "expected_return_pct": rec.expected_return_pct,
            "status": "recorded",
        }

    except Exception as e:
        logger.error(f"Error recording recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outcomes/record")
async def record_outcome(
    request: RecordOutcomeRequest,
) -> Dict[str, Any]:
    """
    Record outcome for a recommendation.

    Parameters:
    -----------
    request : RecordOutcomeRequest
        Outcome details

    Returns:
    --------
    {
        "recommendation_id": "uuid",
        "actual_return_pct": 5.2,
        "status": "recorded"
    }
    """
    try:
        tracker = get_recommendation_tracker()

        outcome = tracker.record_outcome(
            recommendation_id=request.recommendation_id,
            holding_period_days=request.holding_period_days,
            actual_return_pct=request.actual_return_pct,
            executed_allocation_pct=request.executed_allocation_pct,
            notes=request.notes,
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendation_id": outcome.recommendation_id,
            "actual_return_pct": outcome.actual_return_pct,
            "holding_period_days": outcome.holding_period_days,
            "status": "recorded",
        }

    except Exception as e:
        logger.error(f"Error recording outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/accuracy")
async def get_recommendation_accuracy() -> Dict[str, Any]:
    """
    Get recommendation tracking accuracy metrics.

    Returns:
    --------
    {
        "total_recommendations": 47,
        "correct_direction": 38,
        "within_magnitude_tolerance": 32,
        "accuracy_pct": 80.8,
        "scenario_accuracy": {...},
        "symbol_accuracy": {...}
    }
    """
    try:
        tracker = get_recommendation_tracker()
        metrics = tracker.analyze_accuracy()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_recommendations": metrics.total_recommendations,
            "correct_direction": metrics.correct_direction,
            "within_magnitude_tolerance": metrics.within_magnitude_tolerance,
            "accuracy_pct": round(metrics.accuracy_pct, 1),
            "scenario_accuracy": {
                s: round(a, 1) for s, a in metrics.scenario_accuracy.items()
            },
            "symbol_accuracy": {
                s: round(a, 1) for s, a in metrics.symbol_accuracy.items()
            },
        }

    except Exception as e:
        logger.error(f"Error getting accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/performance")
async def get_scenario_performance() -> Dict[str, Any]:
    """
    Get scenario performance metrics.

    Returns:
    --------
    {
        "scenarios": {
            "base": {
                "count": 18,
                "avg_expected_return": 2.5,
                "avg_actual_return": 2.3,
                "accuracy_pct": 77.8
            },
            ...
        }
    }
    """
    try:
        tracker = get_recommendation_tracker()
        scenario_perf = tracker.get_scenario_performance()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios": scenario_perf,
        }

    except Exception as e:
        logger.error(f"Error getting scenario performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/learn")
async def learn_scenario_weights(
    min_samples: int = Query(5, description="Min samples per scenario"),
) -> Dict[str, Any]:
    """
    Auto-learn scenario probability weights from accuracy data.

    Parameters:
    -----------
    min_samples : int
        Minimum samples required per scenario

    Returns:
    --------
    {
        "base": 0.50,
        "upside": 0.30,
        "downside": 0.20
    }
    """
    try:
        tracker = get_recommendation_tracker()
        learner = get_scenario_probability_learner()

        metrics = tracker.analyze_accuracy()

        # Only update if sufficient data
        if all(
            metrics.scenario_accuracy.get(s, 0) >= min_samples
            for s in ["base", "upside", "downside"]
        ):
            updated_weights = learner.update_from_accuracy(
                metrics.scenario_accuracy,
                min_samples_per_scenario=min_samples,
            )

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "weights": updated_weights,
                "status": "updated",
            }
        else:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "weights": learner.get_weights(),
                "status": "insufficient_data",
            }

    except Exception as e:
        logger.error(f"Error learning scenario weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/weights")
async def get_scenario_weights() -> Dict[str, Any]:
    """
    Get current scenario probability weights.

    Returns:
    --------
    {
        "weights": {
            "base": 0.50,
            "upside": 0.25,
            "downside": 0.25
        },
        "last_update": "2026-06-24T...",
        "learning_rate": 0.1
    }
    """
    try:
        learner = get_scenario_probability_learner()
        status = learner.get_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **status,
        }

    except Exception as e:
        logger.error(f"Error getting scenario weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/costs/record-execution")
async def record_execution(
    request: RecordExecutionRequest,
) -> Dict[str, Any]:
    """
    Record execution for cost calibration.

    Parameters:
    -----------
    request : RecordExecutionRequest
        Execution details

    Returns:
    --------
    {
        "symbol": "AAPL",
        "planned_cost_pct": 0.15,
        "actual_cost_pct": 0.22,
        "status": "recorded"
    }
    """
    try:
        calibrator = get_cost_model_calibrator()

        record = calibrator.record_execution(
            symbol=request.symbol,
            side=request.side,
            planned_cost_pct=request.planned_cost_pct,
            actual_cost_pct=request.actual_cost_pct,
            volume_pct=request.volume_pct,
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": record.symbol,
            "planned_cost_pct": record.planned_cost_pct,
            "actual_cost_pct": record.actual_cost_pct,
            "status": "recorded",
        }

    except Exception as e:
        logger.error(f"Error recording execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/calibration-status")
async def get_cost_calibration_status() -> Dict[str, Any]:
    """
    Get cost model calibration status.

    Returns:
    --------
    {
        "total_executions_recorded": 142,
        "symbols_with_profiles": 12,
        "tier_mismatches_identified": 2,
        "readiness": "ready"
    }
    """
    try:
        calibrator = get_cost_model_calibrator()
        status = calibrator.get_calibration_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **status,
        }

    except Exception as e:
        logger.error(f"Error getting calibration status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/symbol-profiles")
async def get_symbol_cost_profiles() -> Dict[str, Any]:
    """
    Get learned cost profiles for all symbols.

    Returns:
    --------
    {
        "AAPL": {
            "execution_count": 8,
            "avg_estimated_cost_pct": 0.15,
            "avg_actual_cost_pct": 0.22,
            "cost_estimation_error_pct": 46.7,
            "suggested_tier": "equity_mid_cap"
        },
        ...
    }
    """
    try:
        calibrator = get_cost_model_calibrator()
        profiles = calibrator.get_all_profiles()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profiles": {
                s: {
                    "execution_count": p.execution_count,
                    "avg_estimated_cost_pct": p.avg_estimated_cost_pct,
                    "avg_actual_cost_pct": p.avg_actual_cost_pct,
                    "cost_estimation_error_pct": p.cost_estimation_error_pct,
                    "suggested_tier": p.suggested_tier,
                }
                for s, p in profiles.items()
            },
        }

    except Exception as e:
        logger.error(f"Error getting symbol profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/costs/estimate-portfolio")
async def estimate_portfolio_costs(
    trades: List[TradeEstimate] = Body(..., description="List of trades to estimate"),
) -> Dict[str, Any]:
    """
    Estimate portfolio costs using learned profiles.

    Parameters:
    -----------
    trades : list
        List of {symbol, volume_pct}

    Returns:
    --------
    {
        "costs_by_symbol": {...},
        "total_portfolio_cost_pct": 0.45,
        "num_learned_symbols": 8
    }
    """
    try:
        if not trades:
            raise HTTPException(status_code=400, detail="No trades provided")

        calibrator = get_cost_model_calibrator()
        # Convert Pydantic models to dicts
        trade_list = [{"symbol": t.symbol, "volume_pct": t.volume_pct} for t in trades]
        cost_estimate = calibrator.estimate_total_portfolio_cost(trade_list)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **cost_estimate,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estimating portfolio costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
