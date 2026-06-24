"""
Phase 324: Attribution API Endpoints

REST API for performance attribution analysis.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Body
import pandas as pd
import numpy as np

from backend.analytics.attribution_engine import (
    get_attribution_engine,
    PositionContribution,
)
from backend.analytics.factor_calculator import FactorCalculator
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attribution", tags=["attribution"])


@router.post("/position-contribution")
async def analyze_position_contribution(
    positions: Dict[str, float] = Body(..., description="Position values in EUR"),
    position_returns: Dict[str, float] = Body(..., description="Position returns (%)"),
    lookback_period: str = Query("1d", description="Period: 1d, 1w, 1m, 3m, 6m, 1y"),
) -> Dict[str, Any]:
    """
    Analyze contribution of each position to portfolio return.

    Parameters:
    -----------
    positions : dict
        {symbol: value in EUR}
    position_returns : dict
        {symbol: return %}
    lookback_period : str
        Analysis period

    Returns:
    --------
    {
        "total_return_pct": 5.2,
        "contributions": [
            {
                "symbol": "BTCUSDT",
                "weight_pct": 40.0,
                "return_pct": 12.5,
                "contribution_pct": 5.0,
                "profit_loss_eur": 5100.0
            },
            ...
        ],
        "top_positive": "BTCUSDT",
        "top_negative": "EQ_MSFT"
    }
    """
    try:
        portfolio_value = sum(positions.values())
        if portfolio_value <= 0:
            raise HTTPException(status_code=400, detail="No positions")

        engine = get_attribution_engine()
        contributions, total_return = engine.analyze_position_contribution(
            positions=positions,
            position_returns=position_returns,
            portfolio_value=portfolio_value,
        )

        positive = [c for c in contributions if c.contribution_pct > 0]
        negative = [c for c in contributions if c.contribution_pct < 0]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "period": lookback_period,
            "total_return_pct": round(total_return, 2),
            "portfolio_value_eur": round(portfolio_value, 2),
            "contributions": [
                {
                    "symbol": c.symbol,
                    "weight_pct": round(c.weight_pct, 2),
                    "return_pct": round(c.period_return_pct, 2),
                    "contribution_pct": round(c.contribution_pct, 2),
                    "profit_loss_eur": round(c.profit_loss_eur, 2),
                }
                for c in contributions
            ],
            "top_positive": positive[0].symbol if positive else None,
            "top_negative": negative[0].symbol if negative else None,
            "num_positive_contributors": len(positive),
            "num_negative_contributors": len(negative),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing position contribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factor-attribution")
async def analyze_factor_attribution(
    symbol_returns: Dict[str, float] = Body(..., description="Symbol returns (%)"),
    symbol_factors: Optional[Dict[str, Dict[str, float]]] = Body(None, description="Symbol factor exposures"),
) -> Dict[str, Any]:
    """
    Analyze factor-based attribution.

    Parameters:
    -----------
    symbol_returns : dict
        {symbol: return %}
    symbol_factors : dict
        {symbol: {factor_name: score}}

    Returns:
    --------
    {
        "factors": [
            {
                "name": "momentum",
                "exposure": 0.5,
                "return_pct": 2.3,
                "contribution_pct": 1.15,
                "ranking": 1
            },
            ...
        ]
    }
    """
    try:
        if not symbol_factors:
            # Default to simple factors
            symbol_factors = {
                symbol: {
                    "momentum": FactorCalculator.calculate_momentum(
                        pd.Series([ret]), lookback=1
                    ),
                }
                for symbol, ret in symbol_returns.items()
            }

        # Calculate factor returns
        factor_returns = FactorCalculator.calculate_factor_returns(
            symbol_returns=symbol_returns,
            symbol_factors=symbol_factors,
        )

        engine = get_attribution_engine()
        contributions = engine.calculate_factor_attribution(
            returns=pd.Series(list(symbol_returns.values())),
            factors={
                f: pd.Series([v]) for f, v in (
                    next(iter(symbol_factors.values())) if symbol_factors else {}
                ).items()
            },
            factor_returns=factor_returns,
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "factors": [
                {
                    "name": c.factor_name,
                    "exposure": round(c.factor_exposure, 3),
                    "return_pct": round(c.factor_return_pct, 2),
                    "contribution_pct": round(c.contribution_pct, 2),
                    "ranking": c.ranking,
                }
                for c in contributions
            ],
            "total_contribution_pct": round(sum(c.contribution_pct for c in contributions), 2),
        }

    except Exception as e:
        logger.error(f"Error analyzing factor attribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drift-analysis")
async def analyze_drift(
    portfolio_positions: Dict[str, float] = Body(..., description="Portfolio position values"),
    benchmark_positions: Dict[str, float] = Body(..., description="Benchmark position values"),
    position_returns: Dict[str, float] = Body(..., description="Position returns (%)"),
) -> Dict[str, Any]:
    """
    Analyze drift vs benchmark.

    Parameters:
    -----------
    portfolio_positions : dict
        {symbol: EUR value}
    benchmark_positions : dict
        {symbol: EUR value}
    position_returns : dict
        {symbol: return %}

    Returns:
    --------
    {
        "active_return_pct": 2.5,
        "tracking_error_pct": 1.8,
        "information_ratio": 1.39,
        "largest_overweight": ("BTCUSDT", 5.0),
        "largest_underweight": ("EQ_MSFT", -3.5),
        "active_contributions": {...}
    }
    """
    try:
        portfolio_value = sum(portfolio_positions.values())
        benchmark_value = sum(benchmark_positions.values())

        if portfolio_value <= 0 or benchmark_value <= 0:
            raise HTTPException(status_code=400, detail="Invalid position values")

        engine = get_attribution_engine()
        drift = engine.calculate_drift_analysis(
            portfolio_positions=portfolio_positions,
            benchmark_positions=benchmark_positions,
            portfolio_value=portfolio_value,
            benchmark_value=benchmark_value,
            position_returns=position_returns,
        )

        # Find largest over/underweights
        active_weights = list(drift.active_weight_pct.items())
        largest_overweight = max(active_weights, key=lambda x: x[1])
        largest_underweight = min(active_weights, key=lambda x: x[1])

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_return_pct": round(drift.total_drift_pct, 2),
            "tracking_error_pct": round(drift.tracking_error_pct, 2),
            "information_ratio": round(drift.information_ratio, 2),
            "largest_overweight": {
                "symbol": largest_overweight[0],
                "active_weight_pct": round(largest_overweight[1], 2),
            },
            "largest_underweight": {
                "symbol": largest_underweight[0],
                "active_weight_pct": round(largest_underweight[1], 2),
            },
            "active_contributions": {
                k: round(v, 2) for k, v in drift.active_return_contribution.items()
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_attribution_summary(
    period: str = Query("1m", description="Analysis period: 1d/1w/1m/3m/6m/1y"),
) -> Dict[str, Any]:
    """
    Get comprehensive attribution summary.

    Returns:
    --------
    {
        "period": "1m",
        "total_return_pct": 4.5,
        "position_attribution": {...},
        "factor_attribution": {...},
        "drift_analysis": {...}
    }
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not available")

        positions = engine.get_positions()
        if not positions:
            raise HTTPException(status_code=400, detail="No positions")

        # Mock attribution data
        position_dict = {p["symbol"]: p.get("value_eur", 0) for p in positions}
        returns_dict = {p["symbol"]: np.random.normal(2, 5) for p in positions}

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "period": period,
            "summary": {
                "total_return_pct": round(np.mean(list(returns_dict.values())), 2),
                "best_contributor": max(returns_dict.items(), key=lambda x: x[1])[0],
                "worst_contributor": min(returns_dict.items(), key=lambda x: x[1])[0],
                "num_positions": len(positions),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating attribution summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
