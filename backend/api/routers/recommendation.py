"""
Phase 325: Portfolio Recommendation Engine API

REST API for scenario analysis and allocation recommendations.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Body, Query
import pandas as pd

from backend.analytics.scenario_analyzer import (
    get_scenario_analyzer,
)
from backend.analytics.allocation_solver import (
    get_allocation_solver,
)
from backend.analytics.historical_data import get_historical_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendation", tags=["recommendation"])


def _get_historical_returns(
    symbols: List[str], lookback_days: int = 252
) -> Dict[str, pd.Series]:
    """
    Fetch historical returns for symbols.

    Parameters:
    -----------
    symbols : list
        List of symbols
    lookback_days : int
        Number of days of historical data

    Returns:
    --------
    {symbol: Series of daily returns (%)}
    """
    returns = {}
    service = get_historical_service()

    if not service:
        logger.warning("Historical data service not available")
        return returns

    # Determine date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days + 50)

    for symbol in symbols:
        try:
            df = service.fetch_ohlcv(symbol, start_date, end_date, interval="1d")

            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                continue

            if "Close" in df.columns:
                close = df["Close"]
            elif "close" in df.columns:
                close = df["close"]
            else:
                logger.warning(f"No close price for {symbol}")
                continue

            daily_returns = close.pct_change() * 100
            returns[symbol] = daily_returns.dropna()

        except Exception as e:
            logger.error(f"Error fetching returns for {symbol}: {e}")
            continue

    return returns


@router.post("/scenario-analysis")
async def scenario_analysis(
    symbols: List[str] = Body(..., description="List of symbols to analyze"),
    allocation: Dict[str, float] = Body(
        ..., description="Allocation {symbol: weight %}"
    ),
    time_horizon_days: int = Query(252, description="Time horizon in days"),
    n_simulations: int = Query(10000, description="Number of Monte Carlo simulations"),
) -> Dict[str, Any]:
    """
    Perform scenario analysis using Monte Carlo simulation.

    Parameters:
    -----------
    symbols : list
        Symbols to include in portfolio
    allocation : dict
        {symbol: weight %}
    time_horizon_days : int
        Time horizon for simulation (default: 252 = 1 year)
    n_simulations : int
        Number of simulations (default: 10000)

    Returns:
    --------
    {
        "monte_carlo": {
            "expected_return_pct": 8.5,
            "volatility_pct": 12.3,
            "percentile_5th_pct": -15.2,
            "percentile_95th_pct": 35.8,
            "probability_positive_pct": 72.5
        },
        "scenarios": [
            {
                "name": "Upside",
                "probability_pct": 72.5,
                "expected_return_pct": 25.0,
                "worst_case_pct": 10.0,
                "best_case_pct": 35.8
            },
            ...
        ]
    }
    """
    try:
        # Validate inputs
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")

        total_weight = sum(allocation.values())
        if abs(total_weight - 100.0) > 1.0:
            raise HTTPException(
                status_code=400, detail="Allocation weights must sum to 100%"
            )

        # Fetch historical returns
        historical_returns = _get_historical_returns(
            symbols, lookback_days=max(500, time_horizon_days * 2)
        )

        if not historical_returns:
            raise HTTPException(status_code=503, detail="Unable to fetch market data")

        # Run Monte Carlo
        analyzer = get_scenario_analyzer()
        mc_result = analyzer.monte_carlo_simulation(
            historical_returns=historical_returns,
            allocation=allocation,
            time_horizon_days=time_horizon_days,
            n_simulations=n_simulations,
        )

        # Analyze scenarios
        upside = analyzer.analyze_upside_scenario(
            historical_returns=historical_returns,
            allocation=allocation,
        )
        downside = analyzer.analyze_downside_scenario(
            historical_returns=historical_returns,
            allocation=allocation,
        )
        base_case = analyzer.base_case_scenario(
            historical_returns=historical_returns,
            allocation=allocation,
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols": symbols,
            "allocation": allocation,
            "time_horizon_days": time_horizon_days,
            "n_simulations": n_simulations,
            "monte_carlo": {
                "expected_return_pct": round(mc_result.expected_return_pct, 2),
                "volatility_pct": round(mc_result.volatility_pct, 2),
                "percentile_5th_pct": round(mc_result.percentile_5th_pct, 2),
                "percentile_25th_pct": round(mc_result.percentile_25th_pct, 2),
                "percentile_50th_pct": round(mc_result.percentile_50th_pct, 2),
                "percentile_75th_pct": round(mc_result.percentile_75th_pct, 2),
                "percentile_95th_pct": round(mc_result.percentile_95th_pct, 2),
                "probability_positive_pct": round(
                    mc_result.probability_positive_pct, 1
                ),
                "best_case_pct": round(mc_result.best_case_pct, 2),
                "worst_case_pct": round(mc_result.worst_case_pct, 2),
            },
            "scenarios": [
                {
                    "name": upside.scenario_name,
                    "probability_pct": round(upside.probability_pct, 1),
                    "expected_return_pct": round(upside.expected_return_pct, 2),
                    "worst_case_pct": round(upside.worst_case_pct, 2),
                    "best_case_pct": round(upside.best_case_pct, 2),
                    "expected_shortfall_pct": round(upside.expected_shortfall_pct, 2),
                },
                {
                    "name": base_case.scenario_name,
                    "probability_pct": round(base_case.probability_pct, 1),
                    "expected_return_pct": round(base_case.expected_return_pct, 2),
                    "worst_case_pct": round(base_case.worst_case_pct, 2),
                    "best_case_pct": round(base_case.best_case_pct, 2),
                    "expected_shortfall_pct": round(
                        base_case.expected_shortfall_pct, 2
                    ),
                },
                {
                    "name": downside.scenario_name,
                    "probability_pct": round(downside.probability_pct, 1),
                    "expected_return_pct": round(downside.expected_return_pct, 2),
                    "worst_case_pct": round(downside.worst_case_pct, 2),
                    "best_case_pct": round(downside.best_case_pct, 2),
                    "expected_shortfall_pct": round(downside.expected_shortfall_pct, 2),
                },
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scenario analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/allocation-solver")
async def solve_allocation(
    symbols: List[str] = Body(..., description="Symbols to include"),
    target_type: str = Body(..., description="'return' or 'volatility'"),
    target_value: float = Body(..., description="Target return (%) or volatility (%)"),
    max_single_position_pct: float = Query(25.0, description="Max position size (%)"),
) -> Dict[str, Any]:
    """
    Solve for optimal allocation given a target.

    Parameters:
    -----------
    symbols : list
        Symbols to include
    target_type : str
        "return" to target specific return, "volatility" to target specific risk
    target_value : float
        Target value (return % or volatility %)
    max_single_position_pct : float
        Maximum position size (%)

    Returns:
    --------
    {
        "target_type": "return",
        "target_value": 10.0,
        "allocation": {symbol: weight %},
        "expected_return_pct": 10.0,
        "expected_volatility_pct": 12.5,
        "sharpe_ratio": 0.64,
        "feasible": true
    }
    """
    try:
        # Validate inputs
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")

        if target_type not in ["return", "volatility"]:
            raise HTTPException(
                status_code=400, detail="target_type must be 'return' or 'volatility'"
            )

        if target_value <= 0:
            raise HTTPException(status_code=400, detail="target_value must be positive")

        # Fetch historical returns
        historical_returns = _get_historical_returns(symbols, lookback_days=500)

        if not historical_returns:
            raise HTTPException(status_code=503, detail="Unable to fetch market data")

        # Solve
        solver = get_allocation_solver()

        if target_type == "return":
            result = solver.solve_for_return(
                historical_returns=historical_returns,
                target_return_pct=target_value,
                max_single_position_pct=max_single_position_pct,
            )
        else:
            result = solver.solve_for_volatility(
                historical_returns=historical_returns,
                target_volatility_pct=target_value,
                max_single_position_pct=max_single_position_pct,
            )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_type": result.target_type,
            "target_value": round(result.target_value, 2),
            "allocation": {k: round(v, 2) for k, v in result.allocation.items()},
            "expected_return_pct": round(result.expected_return_pct, 2),
            "expected_volatility_pct": round(result.expected_volatility_pct, 2),
            "sharpe_ratio": round(result.sharpe_ratio, 2),
            "feasible": result.feasible,
            "explanation": result.explanation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error solving allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
