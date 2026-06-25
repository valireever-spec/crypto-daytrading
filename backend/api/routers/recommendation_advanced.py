"""
Phase 326: Advanced Recommendation API

Constraint management, scenario customization, and performance tracking.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, Query
import numpy as np

from backend.analytics.constraint_manager import get_constraint_manager
from backend.analytics.scenario_customizer import get_scenario_customizer
from backend.analytics.performance_tracker import get_performance_tracker
from backend.api.routers.recommendation import _get_historical_returns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendation", tags=["recommendation"])


@router.post("/constraints/add-sector-limit")
async def add_sector_limit(
    sector: str = Body(..., description="Sector name"),
    max_weight_pct: float = Body(..., description="Maximum weight (%)"),
) -> Dict[str, Any]:
    """
    Add sector exposure limit to constraints.

    Parameters:
    -----------
    sector : str
        Sector name (e.g., "Technology", "Healthcare")
    max_weight_pct : float
        Maximum sector weight (%)

    Returns:
    --------
    {
        "status": "added",
        "constraint": "sector",
        "sector": "Technology",
        "max_weight_pct": 30.0
    }
    """
    try:
        if max_weight_pct <= 0 or max_weight_pct > 100:
            raise HTTPException(
                status_code=400, detail="max_weight_pct must be between 0 and 100"
            )

        manager = get_constraint_manager()
        manager.add_sector_limit(sector, max_weight_pct)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "added",
            "constraint": "sector",
            "sector": sector,
            "max_weight_pct": round(max_weight_pct, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding sector limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/constraints/add-concentration-limit")
async def add_concentration_limit(
    max_single_position_pct: float = Body(..., description="Maximum position size (%)"),
) -> Dict[str, Any]:
    """
    Add concentration limit (max single position).

    Parameters:
    -----------
    max_single_position_pct : float
        Maximum position size (%)

    Returns:
    --------
    {
        "status": "added",
        "constraint": "concentration",
        "max_single_position_pct": 20.0
    }
    """
    try:
        if max_single_position_pct <= 0 or max_single_position_pct > 100:
            raise HTTPException(
                status_code=400,
                detail="max_single_position_pct must be between 0 and 100",
            )

        manager = get_constraint_manager()
        manager.add_concentration_limit(max_single_position_pct)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "added",
            "constraint": "concentration",
            "max_single_position_pct": round(max_single_position_pct, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding concentration limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/constraints/validate")
async def validate_allocation(
    allocation: Dict[str, float] = Body(
        ..., description="Allocation {symbol: weight %}"
    ),
) -> Dict[str, Any]:
    """
    Validate allocation against current constraints.

    Parameters:
    -----------
    allocation : dict
        {symbol: weight %}

    Returns:
    --------
    {
        "valid": true,
        "violations": [],
        "total_constraints": 2
    }
    """
    try:
        if not allocation:
            raise HTTPException(status_code=400, detail="No allocation provided")

        manager = get_constraint_manager()
        is_valid, violations = manager.validate_allocation(allocation)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "valid": is_valid,
            "violations": violations,
            "total_constraints": len(manager.constraints),
            "allocation_sum_pct": round(sum(allocation.values()), 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario/predefined")
async def analyze_predefined_scenario(
    scenario_name: str = Body(..., description="Predefined scenario name"),
    symbols: List[str] = Body(..., description="Symbols to analyze"),
    allocation: Dict[str, float] = Body(
        ..., description="Allocation {symbol: weight %}"
    ),
) -> Dict[str, Any]:
    """
    Analyze portfolio under a predefined scenario.

    Parameters:
    -----------
    scenario_name : str
        Name of predefined scenario (bull_market, bear_market, high_volatility, etc.)
    symbols : list
        Symbols to include
    allocation : dict
        {symbol: weight %}

    Returns:
    --------
    {
        "scenario": "Bull Market",
        "expected_return_pct": 12.5,
        "volatility_pct": 10.2,
        "sharpe_ratio": 0.52,
        "market_conditions": {...}
    }
    """
    try:
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")

        customizer = get_scenario_customizer()
        scenario = customizer.get_predefined_scenario(scenario_name)

        if not scenario:
            available = list(customizer.list_predefined_scenarios().keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scenario. Available: {', '.join(available)}",
            )

        # Fetch historical data
        historical_returns = _get_historical_returns(symbols, lookback_days=500)
        if not historical_returns:
            raise HTTPException(status_code=503, detail="Unable to fetch market data")

        # Analyze scenario
        base_metrics = {
            "expected_return_pct": np.mean(
                [r.mean() * 252 for r in historical_returns.values()]
            )
            * 100,
            "volatility_pct": np.mean(
                [r.std() * np.sqrt(252) for r in historical_returns.values()]
            )
            * 100,
        }

        result = customizer.analyze_scenario(
            scenario, historical_returns, allocation, base_metrics
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario": result.scenario_name,
            "expected_return_pct": round(result.expected_return_pct, 2),
            "volatility_pct": round(result.volatility_pct, 2),
            "sharpe_ratio": round(result.sharpe_ratio, 2),
            "percentile_5th_pct": round(result.percentile_5th_pct, 2),
            "percentile_95th_pct": round(result.percentile_95th_pct, 2),
            "probability_positive_pct": round(result.probability_positive_pct, 1),
            "market_conditions": result.market_conditions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing predefined scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario/list")
async def list_scenarios() -> Dict[str, Any]:
    """
    List all predefined scenarios.

    Returns:
    --------
    {
        "scenarios": [
            {
                "name": "bull_market",
                "description": "Strong growth..."
            },
            ...
        ]
    }
    """
    try:
        customizer = get_scenario_customizer()
        scenarios = customizer.list_predefined_scenarios()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios": [
                {"name": name, "description": desc} for name, desc in scenarios.items()
            ],
            "total": len(scenarios),
        }

    except Exception as e:
        logger.error(f"Error listing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance/record-recommendation")
async def record_recommendation(
    allocation: Dict[str, float] = Body(..., description="Recommended allocation"),
    expected_return_pct: float = Body(..., description="Expected return (%)"),
    expected_volatility_pct: float = Body(..., description="Expected volatility (%)"),
    scenario_type: str = Query("base", description="Scenario type"),
) -> Dict[str, Any]:
    """
    Record a portfolio recommendation for performance tracking.

    Parameters:
    -----------
    allocation : dict
        {symbol: weight %}
    expected_return_pct : float
        Expected return (%)
    expected_volatility_pct : float
        Expected volatility (%)
    scenario_type : str
        Scenario type (upside, base, downside, custom)

    Returns:
    --------
    {"status": "recorded", "timestamp": "2026-06-24T..."}
    """
    try:
        tracker = get_performance_tracker()
        tracker.record_recommendation(
            allocation=allocation,
            expected_return_pct=expected_return_pct,
            expected_volatility_pct=expected_volatility_pct,
            scenario_type=scenario_type,
        )

        return {
            "status": "recorded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario_type": scenario_type,
        }

    except Exception as e:
        logger.error(f"Error recording recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance/record-outcome")
async def record_outcome(
    actual_return_pct: float = Body(..., description="Actual return (%)"),
    actual_volatility_pct: float = Body(..., description="Actual volatility (%)"),
) -> Dict[str, Any]:
    """
    Record actual portfolio outcome.

    Parameters:
    -----------
    actual_return_pct : float
        Realized return (%)
    actual_volatility_pct : float
        Realized volatility (%)

    Returns:
    --------
    {"status": "recorded", "timestamp": "2026-06-24T..."}
    """
    try:
        tracker = get_performance_tracker()
        tracker.record_outcome(
            actual_return_pct=actual_return_pct,
            actual_volatility_pct=actual_volatility_pct,
        )

        return {
            "status": "recorded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actual_return_pct": round(actual_return_pct, 2),
            "actual_volatility_pct": round(actual_volatility_pct, 2),
        }

    except Exception as e:
        logger.error(f"Error recording outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/metrics")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get recommendation performance metrics.

    Returns:
    --------
    {
        "total_recommendations": 10,
        "avg_forecast_return_pct": 8.5,
        "avg_actual_return_pct": 7.2,
        "forecast_accuracy_pct": 65.0,
        "sharpe_improvement": 0.15
    }
    """
    try:
        tracker = get_performance_tracker()
        metrics = tracker.get_performance_metrics()

        if not metrics:
            raise HTTPException(status_code=400, detail="No performance data available")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_recommendations": metrics.total_recommendations,
            "avg_forecast_return_pct": round(metrics.avg_forecast_return_pct, 2),
            "avg_actual_return_pct": round(metrics.avg_actual_return_pct, 2),
            "forecast_error_pct": round(metrics.forecast_error_pct, 2),
            "forecast_accuracy_pct": round(metrics.forecast_accuracy_pct, 1),
            "avg_volatility_error_pct": round(metrics.avg_volatility_error_pct, 2),
            "sharpe_improvement": round(metrics.sharpe_improvement, 2),
            "upside_capture_ratio": round(metrics.upside_capture_ratio, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/summary")
async def get_performance_summary() -> Dict[str, Any]:
    """
    Get comprehensive performance tracking summary.

    Returns:
    --------
    {
        "total_recommendations": 10,
        "total_outcomes": 8,
        "matched_pairs": 8,
        "performance_metrics": {...}
    }
    """
    try:
        tracker = get_performance_tracker()
        summary = tracker.get_summary()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **summary,
        }

    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
