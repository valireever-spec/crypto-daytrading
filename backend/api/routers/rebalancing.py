"""
Phase 327: Rebalancing API

REST endpoints for constrained portfolio rebalancing.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Query

from backend.analytics.rebalancing_engine import (
    get_rebalancing_engine,
)
from backend.analytics.rebalancing_stress_tester import (
    get_rebalancing_stress_tester,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rebalancing", tags=["rebalancing"])


@router.post("/analyze-drift")
async def analyze_drift(
    current_allocation: Dict[str, float] = Body(..., description="Current allocation {symbol: weight %}"),
    target_allocation: Dict[str, float] = Body(..., description="Target allocation {symbol: weight %}"),
    drift_threshold_pct: float = Query(5.0, description="Drift trigger threshold (%)"),
) -> Dict[str, Any]:
    """
    Analyze portfolio drift from target allocation.

    Parameters:
    -----------
    current_allocation : dict
        {symbol: current weight %}
    target_allocation : dict
        {symbol: target weight %}
    drift_threshold_pct : float
        Trigger rebalancing if drift exceeds this (%)

    Returns:
    --------
    {
        "total_drift_pct": 7.5,
        "requires_rebalancing": true,
        "drift_per_symbol": {symbol: drift %},
        "drift_threshold_pct": 5.0
    }
    """
    try:
        if not current_allocation or not target_allocation:
            raise HTTPException(status_code=400, detail="Missing allocations")

        engine = get_rebalancing_engine()
        engine.drift_threshold_pct = drift_threshold_pct

        drift = engine.analyze_drift(current_allocation, target_allocation)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_drift_pct": round(drift.total_drift_pct, 2),
            "requires_rebalancing": drift.requires_rebalancing,
            "drift_per_symbol": {k: round(v, 2) for k, v in drift.drift_per_symbol.items()},
            "drift_threshold_pct": drift.drift_threshold_pct,
            "current_allocation": {k: round(v, 2) for k, v in drift.current_allocation.items()},
            "target_allocation": {k: round(v, 2) for k, v in drift.target_allocation.items()},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-plan")
async def generate_rebalancing_plan(
    current_allocation: Dict[str, float] = Body(..., description="Current allocation"),
    target_allocation: Dict[str, float] = Body(..., description="Target allocation"),
    portfolio_value_eur: float = Body(..., description="Portfolio value in EUR"),
    execution_cost_bps: float = Query(10.0, description="Execution cost in basis points"),
    tax_rate_pct: float = Query(27.0, description="Tax rate (%)"),
) -> Dict[str, Any]:
    """
    Generate rebalancing trade plan.

    Parameters:
    -----------
    current_allocation : dict
        Current allocation {symbol: weight %}
    target_allocation : dict
        Target allocation {symbol: weight %}
    portfolio_value_eur : float
        Portfolio value in EUR
    execution_cost_bps : float
        Execution cost in basis points
    tax_rate_pct : float
        Tax rate (%)

    Returns:
    --------
    {
        "trades": [
            {"symbol": "BTCUSDT", "side": "BUY", "amount_pct": 2.5},
            ...
        ],
        "total_cost_pct": 0.15,
        "estimated_slippage_pct": 0.05,
        "tax_impact_pct": 0.12,
        "feasible": true,
        "estimated_execution_time_min": 12.5
    }
    """
    try:
        if portfolio_value_eur <= 0:
            raise HTTPException(status_code=400, detail="Portfolio value must be positive")

        engine = get_rebalancing_engine()
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=portfolio_value_eur,
            execution_cost_bps=execution_cost_bps,
            tax_rate_pct=tax_rate_pct,
        )

        # Cost breakdown
        cost_breakdown = engine.estimate_cost_breakdown(plan)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "trades": [
                {
                    "symbol": symbol,
                    "side": side,
                    "amount_pct": round(pct, 2),
                    "amount_eur": round(pct * portfolio_value_eur / 100, 2),
                }
                for symbol, side, pct in plan.trades
            ],
            "total_cost_pct": round(plan.total_cost_pct, 4),
            "estimated_slippage_pct": round(plan.estimated_slippage_pct, 4),
            "tax_impact_pct": round(plan.tax_impact_pct, 4),
            "total_cost_eur": round(
                (plan.total_cost_pct + plan.estimated_slippage_pct + plan.tax_impact_pct) *
                portfolio_value_eur / 100,
                2
            ),
            "feasible": plan.feasible,
            "constraint_violations": plan.constraint_violations,
            "estimated_execution_time_min": round(plan.estimated_execution_time_min, 1),
            "cost_breakdown": {k: round(v, 4) for k, v in cost_breakdown.items()},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating rebalancing plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/break-into-tranches")
async def break_into_tranches(
    current_allocation: Dict[str, float] = Body(..., description="Current allocation"),
    target_allocation: Dict[str, float] = Body(..., description="Target allocation"),
    portfolio_value_eur: float = Body(..., description="Portfolio value in EUR"),
    max_tranche_pct: float = Query(2.0, description="Max % per tranche"),
    tranche_interval_min: float = Query(5.0, description="Minutes between tranches"),
) -> Dict[str, Any]:
    """
    Break large rebalancing into smaller tranches.

    Parameters:
    -----------
    current_allocation : dict
        Current allocation
    target_allocation : dict
        Target allocation
    portfolio_value_eur : float
        Portfolio value
    max_tranche_pct : float
        Max portfolio % per tranche
    tranche_interval_min : float
        Minutes between tranches

    Returns:
    --------
    {
        "total_tranches": 3,
        "tranches": [
            {
                "tranche_num": 1,
                "trades": [...],
                "estimated_cost_pct": 0.05,
                "execution_time_min": 5.0
            },
            ...
        ],
        "total_execution_time_min": 15.0
    }
    """
    try:
        engine = get_rebalancing_engine()

        # Generate full plan
        full_plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=portfolio_value_eur,
        )

        # Break into tranches
        tranches = engine.break_into_tranches(
            plan=full_plan,
            max_tranche_pct=max_tranche_pct,
            tranche_interval_min=tranche_interval_min,
        )

        total_time = sum(t.estimated_execution_time_min for t in tranches)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tranches": len(tranches),
            "max_tranche_pct": max_tranche_pct,
            "tranches": [
                {
                    "tranche_num": i + 1,
                    "trades": [
                        {
                            "symbol": symbol,
                            "side": side,
                            "amount_pct": round(pct, 2),
                        }
                        for symbol, side, pct in t.trades
                    ],
                    "estimated_cost_pct": round(t.total_cost_pct, 4),
                    "execution_time_min": round(t.estimated_execution_time_min, 1),
                }
                for i, t in enumerate(tranches)
            ],
            "total_execution_time_min": round(total_time, 1),
        }

    except Exception as e:
        logger.error(f"Error breaking into tranches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stress-test")
async def stress_test_rebalancing(
    target_allocation: Dict[str, float] = Body(..., description="Target allocation"),
    scenario_name: str = Query("Custom", description="Scenario name"),
) -> Dict[str, Any]:
    """
    Stress test rebalancing plan under market scenario.

    Parameters:
    -----------
    target_allocation : dict
        Target allocation {symbol: weight %}
    scenario_name : str
        Name of scenario to test

    Returns:
    --------
    {
        "scenario": "Bull Market",
        "portfolio_volatility_pct": 12.5,
        "worst_case_drawdown_pct": -18.3,
        "recovery_time_days": 45,
        "feasible_under_stress": true,
        "recommendation": "ACCEPTABLE"
    }
    """
    try:
        if not target_allocation:
            raise HTTPException(status_code=400, detail="No allocation provided")

        # Create synthetic scenario returns
        symbols = list(target_allocation.keys())
        scenario_returns = {symbol: 8.0 for symbol in symbols}
        scenario_volatilities = {symbol: 15.0 for symbol in symbols}
        scenario_correlations = np.eye(len(symbols)) * 0.7 + np.ones((len(symbols), len(symbols))) * 0.3

        tester = get_rebalancing_stress_tester()
        result = tester.stress_test_allocation(
            target_allocation=target_allocation,
            scenario_returns=scenario_returns,
            scenario_volatilities=scenario_volatilities,
            scenario_correlations=scenario_correlations,
            scenario_name=scenario_name,
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "scenario": result.scenario_name,
            "portfolio_volatility_pct": round(result.portfolio_volatility_pct, 2),
            "worst_case_drawdown_pct": round(result.worst_case_drawdown_pct, 2),
            "recovery_time_days": result.recovery_time_days,
            "feasible_under_stress": result.feasible_under_stress,
            "constraint_violations": result.constraint_violations,
            "recommendation": result.recommendation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stress testing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_rebalancing_history(limit: int = Query(10, description="Number of recent records")) -> Dict[str, Any]:
    """
    Get rebalancing history.

    Parameters:
    -----------
    limit : int
        Number of recent records to return

    Returns:
    --------
    {
        "total_rebalancings": 25,
        "recent_rebalancings": [
            {
                "trades": [...],
                "total_cost_pct": 0.15,
                "feasible": true
            },
            ...
        ]
    }
    """
    try:
        engine = get_rebalancing_engine()
        history = engine.get_rebalancing_history(limit)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_rebalancings": len(engine.rebalancing_history),
            "recent_rebalancings": [
                {
                    "num_trades": len(plan.trades),
                    "total_cost_pct": round(plan.total_cost_pct, 4),
                    "estimated_slippage_pct": round(plan.estimated_slippage_pct, 4),
                    "tax_impact_pct": round(plan.tax_impact_pct, 4),
                    "feasible": plan.feasible,
                    "execution_time_min": round(plan.estimated_execution_time_min, 1),
                }
                for plan in history
            ],
        }

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Add numpy import
import numpy as np
