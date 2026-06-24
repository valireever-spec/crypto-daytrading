"""
Phase 323: Portfolio Backtest API Endpoints

REST API for backtesting allocation strategies and analyzing results.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Body
import pandas as pd

from backend.analytics.portfolio_backtest_engine_v2 import (
    get_backtest_engine,
    BacktestResult,
)
from backend.analytics.backtest_analyzer import BacktestAnalyzer
from backend.analytics.historical_data import get_historical_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# Store results in memory
_backtest_results: Dict[str, BacktestResult] = {}
_result_counter = 0


@router.post("/allocation")
async def backtest_allocation(
    allocation: Dict[str, float] = Body(...),
    strategy_name: str = Query("test_allocation"),
    lookback_days: int = Query(365, ge=30, le=2000),
    transaction_cost_bps: int = Query(10, ge=0, le=100),  # basis points
    tax_rate_pct: float = Query(27.0, ge=0, le=50),
) -> Dict[str, Any]:
    """
    Backtest a single allocation strategy.

    Parameters:
    -----------
    allocation : dict
        Portfolio allocation: {symbol: weight %}
    strategy_name : str
        Name for this strategy
    lookback_days : int
        Days of historical data to use (30-2000)
    transaction_cost_bps : int
        Transaction costs in basis points (0-100)
    tax_rate_pct : float
        Capital gains tax rate (0-50%)

    Returns:
    --------
    {
        "strategy_name": "...",
        "total_return_pct": 12.5,
        "annualized_return_pct": 10.2,
        "volatility_pct": 15.3,
        "sharpe_ratio": 0.75,
        "sortino_ratio": 0.95,
        "max_drawdown_pct": -18.5,
        "win_rate_pct": 55.2,
        "num_rebalances": 0,
        "metrics": {...}
    }
    """
    try:
        # Fetch historical data
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=503, detail="Historical data service not available")

        symbols = list(allocation.keys())
        historical_returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(symbol, timeframe="1d", limit=lookback_days)
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    historical_returns[symbol] = df["return"]
            except Exception as e:
                logger.debug(f"Could not fetch {symbol}: {e}")
                continue

        if not historical_returns:
            raise HTTPException(status_code=400, detail="No historical data available")

        # Run backtest
        engine = get_backtest_engine()
        result = engine.backtest_allocation(
            historical_returns=historical_returns,
            allocation=allocation,
            strategy_name=strategy_name,
            transaction_cost_pct=transaction_cost_bps / 10000,
            tax_rate=tax_rate_pct / 100,
        )

        # Store result
        global _result_counter
        _result_counter += 1
        result_id = f"backtest_{_result_counter}"
        _backtest_results[result_id] = result

        def safe_round(val, decimals=2):
            if pd.isna(val) or (isinstance(val, float) and (val != val)):
                return 0
            return round(val, decimals)

        return {
            "result_id": result_id,
            "timestamp": datetime.utcnow().isoformat(),
            "strategy_name": result.strategy_name,
            "allocation": {k: safe_round(v, 2) for k, v in result.allocation.items()},
            "period_days": result.period_days,
            "total_return_pct": safe_round(result.total_return_pct, 2),
            "annualized_return_pct": safe_round(result.annualized_return_pct, 2),
            "volatility_pct": safe_round(result.volatility_pct, 2),
            "sharpe_ratio": safe_round(result.sharpe_ratio, 2),
            "sortino_ratio": safe_round(result.sortino_ratio, 2),
            "max_drawdown_pct": safe_round(result.max_drawdown_pct, 2),
            "calmar_ratio": safe_round(result.calmar_ratio, 2),
            "win_rate_pct": safe_round(result.win_rate_pct, 2),
            "best_day_pct": safe_round(result.best_day_return_pct, 2),
            "worst_day_pct": safe_round(result.worst_day_return_pct, 2),
            "positive_months": result.positive_months,
            "total_months": result.total_months,
            "num_rebalances": result.num_rebalances,
            "transaction_cost_pct": safe_round(result.total_transaction_cost_pct, 2),
            "tax_cost_pct": safe_round(result.total_tax_cost_pct, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error backtesting allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rolling-optimization")
async def backtest_rolling_optimization(
    risk_level: str = Query("balanced", description="conservative/moderate/balanced/aggressive/extreme"),
    rebalance_freq: str = Query("monthly", description="monthly/quarterly/annual"),
    lookback_days: int = Query(365, ge=30, le=2000),
    transaction_cost_bps: int = Query(10, ge=0, le=100),
) -> Dict[str, Any]:
    """
    Backtest with rolling window optimization and rebalancing.

    Parameters:
    -----------
    risk_level : str
        Target risk level for optimization
    rebalance_freq : str
        Rebalancing frequency: monthly, quarterly, or annual
    lookback_days : int
        Days of historical data
    transaction_cost_bps : int
        Transaction costs in basis points

    Returns:
    --------
    Backtest results with rolling optimization
    """
    try:
        if risk_level not in ["conservative", "moderate", "balanced", "aggressive", "extreme"]:
            raise HTTPException(status_code=400, detail="Invalid risk level")

        if rebalance_freq not in ["monthly", "quarterly", "annual"]:
            raise HTTPException(status_code=400, detail="Invalid rebalance frequency")

        # Fetch historical data
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=503, detail="Historical data service not available")

        symbols = ["BTCUSDT", "EQ_AAPL", "EQ_MSFT", "EQ_GOOGL", "EQ_NVDA"]
        historical_returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(symbol, timeframe="1d", limit=lookback_days)
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    historical_returns[symbol] = df["return"]
            except Exception:
                continue

        if not historical_returns:
            raise HTTPException(status_code=400, detail="No historical data available")

        # Run backtest
        engine = get_backtest_engine()
        result = engine.backtest_rolling_optimization(
            historical_returns=historical_returns,
            risk_level=risk_level,
            rebalance_freq=rebalance_freq,
            strategy_name=f"rolling_{risk_level}_{rebalance_freq}",
            transaction_cost_pct=transaction_cost_bps / 10000,
        )

        # Store result
        global _result_counter
        _result_counter += 1
        result_id = f"backtest_{_result_counter}"
        _backtest_results[result_id] = result

        def safe_round(val, decimals=2):
            if pd.isna(val) or (isinstance(val, float) and (val != val)):
                return 0
            return round(val, decimals)

        return {
            "result_id": result_id,
            "timestamp": datetime.utcnow().isoformat(),
            "strategy_name": result.strategy_name,
            "risk_level": risk_level,
            "rebalance_freq": rebalance_freq,
            "allocation": {k: safe_round(v, 2) for k, v in result.allocation.items()},
            "total_return_pct": safe_round(result.total_return_pct, 2),
            "annualized_return_pct": safe_round(result.annualized_return_pct, 2),
            "volatility_pct": safe_round(result.volatility_pct, 2),
            "sharpe_ratio": safe_round(result.sharpe_ratio, 2),
            "max_drawdown_pct": safe_round(result.max_drawdown_pct, 2),
            "win_rate_pct": safe_round(result.win_rate_pct, 2),
            "num_rebalances": result.num_rebalances,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error backtesting rolling optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_allocations(
    allocations: Dict[str, Dict[str, float]] = Body(...),
    lookback_days: int = Query(365, ge=30, le=2000),
) -> Dict[str, Any]:
    """
    Compare multiple allocation strategies.

    Parameters:
    -----------
    allocations : dict
        {strategy_name: {symbol: weight %}}
    lookback_days : int
        Days of historical data

    Returns:
    --------
    Comparison results with rankings
    """
    try:
        # Fetch historical data
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=503, detail="Historical data service not available")

        # Get all symbols from all allocations
        all_symbols = set()
        for allocation in allocations.values():
            all_symbols.update(allocation.keys())

        historical_returns = {}

        for symbol in all_symbols:
            try:
                df = hist_service.get_candles(symbol, timeframe="1d", limit=lookback_days)
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    historical_returns[symbol] = df["return"]
            except Exception:
                continue

        if not historical_returns:
            raise HTTPException(status_code=400, detail="No historical data available")

        # Run comparison
        engine = get_backtest_engine()
        comparison = engine.backtest_multiple_allocations(
            historical_returns=historical_returns,
            allocations=allocations,
        )

        # Analyze
        analyzer = BacktestAnalyzer()
        comparison_analysis = analyzer.compare_allocations(comparison)
        recommendations = analyzer.generate_recommendations(comparison)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "num_strategies": len(comparison.results),
            "best_sharpe": comparison.best_sharpe,
            "best_return": comparison.best_return,
            "best_risk_adjusted": comparison.best_risk_adjusted,
            "rankings": comparison.comparison_metrics,
            "best_performers": comparison_analysis.get("best_performers", {}),
            "recommendations": recommendations,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing allocations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{result_id}")
async def get_backtest_results(
    result_id: str,
    include_metrics: bool = Query(True),
    include_daily_returns: bool = Query(False),
) -> Dict[str, Any]:
    """
    Get backtest results by ID.

    Parameters:
    -----------
    result_id : str
        Result ID from backtest endpoints
    include_metrics : bool
        Include detailed metrics
    include_daily_returns : bool
        Include daily returns series (large)

    Returns:
    --------
    Backtest result with optional details
    """
    if result_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Result not found")

    result = _backtest_results[result_id]
    analyzer = BacktestAnalyzer()

    response = {
        "result_id": result_id,
        "timestamp": datetime.utcnow().isoformat(),
        "strategy_name": result.strategy_name,
        "allocation": {k: round(v, 2) for k, v in result.allocation.items()},
        "period_days": result.period_days,
        "total_return_pct": round(result.total_return_pct, 2),
        "annualized_return_pct": round(result.annualized_return_pct, 2),
        "volatility_pct": round(result.volatility_pct, 2),
        "sharpe_ratio": round(result.sharpe_ratio, 2),
        "max_drawdown_pct": round(result.max_drawdown_pct, 2),
    }

    if include_metrics:
        metrics = analyzer.calculate_metrics(result.daily_returns)
        response["detailed_metrics"] = metrics

        rolling = analyzer.analyze_rolling_performance(result, period="monthly")
        response["monthly_performance"] = rolling

    if include_daily_returns:
        response["daily_returns"] = [round(r, 3) for r in result.daily_returns.values]

    return response


@router.post("/analyze")
async def analyze_results(
    result_id: str = Query(...),
    benchmark_return_pct: Optional[float] = Query(None),
    benchmark_volatility_pct: Optional[float] = Query(None),
) -> Dict[str, Any]:
    """
    Analyze backtest results in detail.

    Parameters:
    -----------
    result_id : str
        Result ID to analyze
    benchmark_return_pct : float
        Optional benchmark annual return for comparison
    benchmark_volatility_pct : float
        Optional benchmark annual volatility for comparison

    Returns:
    --------
    Detailed analysis results
    """
    if result_id not in _backtest_results:
        raise HTTPException(status_code=404, detail="Result not found")

    result = _backtest_results[result_id]
    analyzer = BacktestAnalyzer()

    # Basic analysis
    metrics = analyzer.calculate_metrics(result.daily_returns)
    monthly_perf = analyzer.analyze_rolling_performance(result, period="monthly")
    quarterly_perf = analyzer.analyze_rolling_performance(result, period="quarterly")

    response = {
        "strategy_name": result.strategy_name,
        "metrics": metrics,
        "monthly_performance": monthly_perf,
        "quarterly_performance": quarterly_perf,
    }

    # Benchmark comparison if provided
    if benchmark_return_pct is not None and benchmark_volatility_pct is not None:
        benchmark_comp = analyzer.compare_to_benchmark(
            result,
            benchmark_return_pct,
            benchmark_volatility_pct,
        )
        response["benchmark_comparison"] = benchmark_comp

    return response


@router.get("/summary")
async def get_backtest_summary() -> Dict[str, Any]:
    """
    Get summary of all backtests.

    Returns:
    --------
    Summary statistics across all tests
    """
    if not _backtest_results:
        return {
            "total_backtests": 0,
            "results": [],
        }

    summaries = []
    for result_id, result in _backtest_results.items():
        summaries.append({
            "result_id": result_id,
            "strategy_name": result.strategy_name,
            "total_return_pct": round(result.total_return_pct, 2),
            "sharpe_ratio": round(result.sharpe_ratio, 2),
            "max_drawdown_pct": round(result.max_drawdown_pct, 2),
        })

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_backtests": len(_backtest_results),
        "results": summaries,
    }
