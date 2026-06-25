"""
Phase 322: Portfolio Allocation API Endpoints

REST API for portfolio optimization, efficient frontier, and rebalancing.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from backend.analytics.portfolio_optimizer import (
    get_portfolio_optimizer,
)
from backend.exchange.paper_trading import get_paper_trading
from backend.analytics.historical_data import get_historical_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/allocation", tags=["allocation"])


@router.get("/optimize")
async def get_optimal_allocation(
    risk_level: str = Query(
        "balanced", description="conservative/moderate/balanced/aggressive/extreme"
    ),
    lookback_days: int = Query(
        365, ge=30, le=1000, description="Days of history for optimization"
    ),
) -> Dict[str, Any]:
    """
    Get optimal portfolio allocation for a risk level.

    Parameters:
    -----------
    risk_level : str
        Portfolio risk level: conservative, moderate, balanced, aggressive, or extreme
    lookback_days : int
        Days of historical data to use for optimization (30-1000)

    Returns:
    --------
    {
        "risk_level": "balanced",
        "target_return_pct": 8.5,
        "target_volatility_pct": 15.3,
        "allocation": {
            "BTCUSDT": 35.2,
            "EQ_AAPL": 32.1,
            "EQ_MSFT": 28.5,
            ...
        },
        "sharpe_ratio": 0.85,
        "diversification_ratio": 1.4,
        "timestamp": "2026-06-24T..."
    }
    """
    try:
        if risk_level not in [
            "conservative",
            "moderate",
            "balanced",
            "aggressive",
            "extreme",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Risk level must be: conservative, moderate, balanced, aggressive, or extreme",
            )

        # Get historical returns
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(
                status_code=503, detail="Historical data service not available"
            )

        # Fetch returns for common symbols
        symbols = ["BTCUSDT", "EQ_AAPL", "EQ_MSFT", "EQ_GOOGL", "EQ_NVDA"]
        returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(
                    symbol, timeframe="1d", limit=lookback_days
                )
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    returns[symbol] = df["return"]
            except Exception as e:
                logger.debug(f"Could not fetch {symbol}: {e}")
                continue

        if not returns:
            raise HTTPException(status_code=400, detail="No historical data available")

        # Optimize
        optimizer = get_portfolio_optimizer()
        allocation = optimizer.optimize_portfolio(
            returns=returns,
            risk_level=risk_level,
        )

        # Handle NaN values
        def safe_round(val, decimals=2):
            if pd.isna(val) or (isinstance(val, float) and (val != val)):
                return 0
            return round(val, decimals)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "risk_level": allocation.risk_level,
            "target_return_pct": safe_round(allocation.target_return_pct, 2),
            "target_volatility_pct": safe_round(allocation.target_volatility_pct, 2),
            "allocation": {
                k: safe_round(v, 2) for k, v in allocation.allocation.items()
            },
            "sharpe_ratio": safe_round(allocation.sharpe_ratio, 2),
            "diversification_ratio": safe_round(allocation.diversification_ratio, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/efficient-frontier")
async def get_efficient_frontier(
    lookback_days: int = Query(365, ge=30, le=1000, description="Days of history"),
    n_points: int = Query(20, ge=5, le=50, description="Number of frontier points"),
) -> Dict[str, Any]:
    """
    Get efficient frontier for portfolio.

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "frontier": [
            {
                "volatility_pct": 5.2,
                "expected_return_pct": 3.8,
                "sharpe_ratio": 0.45,
                "allocation": {...}
            },
            ...
        ],
        "optimal_point": {...}  # Max Sharpe ratio point
    }
    """
    try:
        # Get historical returns
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(
                status_code=503, detail="Historical data service not available"
            )

        symbols = ["BTCUSDT", "EQ_AAPL", "EQ_MSFT", "EQ_GOOGL", "EQ_NVDA"]
        returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(
                    symbol, timeframe="1d", limit=lookback_days
                )
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    returns[symbol] = df["return"]
            except Exception as e:
                logger.debug(f"Could not fetch {symbol}: {e}")
                continue

        if not returns:
            raise HTTPException(status_code=400, detail="No historical data available")

        # Calculate frontier
        optimizer = get_portfolio_optimizer()
        frontier = optimizer.efficient_frontier(returns=returns, n_points=n_points)

        if not frontier:
            raise HTTPException(
                status_code=400, detail="Could not calculate efficient frontier"
            )

        # Find point with max Sharpe (filter out NaN)
        valid_frontier = [p for p in frontier if not pd.isna(p.sharpe_ratio)]
        if not valid_frontier:
            valid_frontier = frontier

        optimal = max(
            valid_frontier,
            key=lambda p: p.sharpe_ratio if not pd.isna(p.sharpe_ratio) else 0,
        )

        def safe_round(val, decimals=2):
            if pd.isna(val) or (isinstance(val, float) and (val != val)):
                return 0
            return round(val, decimals)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "frontier": [
                {
                    "volatility_pct": safe_round(p.volatility_pct, 2),
                    "expected_return_pct": safe_round(p.expected_return_pct, 2),
                    "sharpe_ratio": safe_round(p.sharpe_ratio, 2),
                    "allocation": {
                        k: safe_round(v, 2) for k, v in p.allocation.items()
                    },
                }
                for p in frontier
            ],
            "optimal_point": {
                "volatility_pct": safe_round(optimal.volatility_pct, 2),
                "expected_return_pct": safe_round(optimal.expected_return_pct, 2),
                "sharpe_ratio": safe_round(optimal.sharpe_ratio, 2),
                "allocation": {
                    k: safe_round(v, 2) for k, v in optimal.allocation.items()
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating efficient frontier: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current-allocation")
async def get_current_allocation() -> Dict[str, Any]:
    """
    Get current portfolio allocation.

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "total_value_eur": 100000,
        "allocation": {
            "BTCUSDT": {
                "value_eur": 35000,
                "weight_pct": 35.0,
                "quantity": 0.7,
                "entry_price": 50000
            },
            ...
        }
    }
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=503, detail="Paper trading engine not available"
            )

        positions = engine.get_positions()
        account = engine.get_account_state()
        total_value = account.get("total_equity", 0)

        allocation = {}
        for pos in positions:
            symbol = pos["symbol"]
            value = pos.get("value_eur", 0)
            weight = (value / total_value * 100) if total_value > 0 else 0

            allocation[symbol] = {
                "value_eur": round(value, 2),
                "weight_pct": round(weight, 2),
                "quantity": round(pos.get("quantity", 0), 4),
                "entry_price": round(pos.get("entry_price", 0), 2),
                "current_price": round(pos.get("price", 0), 2),
            }

        # Calculate concentration
        weights = [a["weight_pct"] for a in allocation.values()]
        herfindahl = sum(w**2 for w in weights) / 10000  # Normalized to 0-1

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_value_eur": round(total_value, 2),
            "num_positions": len(allocation),
            "allocation": allocation,
            "concentration_ratio": round(max(weights) if weights else 0, 2),
            "herfindahl_index": round(herfindahl, 4),  # 1/n = perfectly diversified
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommended-rebalancing")
async def get_recommended_rebalancing(
    risk_level: str = Query("balanced", description="Target risk level"),
    max_trade_pct: float = Query(
        2.0, ge=0.1, le=10.0, description="Max trade size as % of portfolio"
    ),
) -> Dict[str, Any]:
    """
    Get rebalancing recommendations to reach target allocation.

    Parameters:
    -----------
    risk_level : str
        Target risk level: conservative, moderate, balanced, aggressive, extreme
    max_trade_pct : float
        Maximum trade size as percentage of portfolio (0.1-10%)

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "current_allocation": {...},
        "target_allocation": {...},
        "trades": [
            {
                "symbol": "BTCUSDT",
                "action": "SELL",
                "current_value_eur": 35000,
                "target_value_eur": 30000,
                "trade_amount_eur": -5000,
                "current_weight_pct": 35.0,
                "target_weight_pct": 30.0,
                "execution_cost_eur": 5,
                "tax_impact_eur": 50
            },
            ...
        ],
        "total_trade_volume_eur": 15000,
        "estimated_cost_eur": 20,
        "estimated_tax_eur": 150,
        "rationale": "..."
    }
    """
    try:
        if risk_level not in [
            "conservative",
            "moderate",
            "balanced",
            "aggressive",
            "extreme",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Risk level must be: conservative, moderate, balanced, aggressive, or extreme",
            )

        # Get current allocation
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=503, detail="Paper trading engine not available"
            )

        positions = engine.get_positions()
        account = engine.get_account_state()
        total_value = account.get("total_equity", 0)

        if not positions:
            raise HTTPException(status_code=400, detail="No positions to rebalance")

        current_positions = {p["symbol"]: p.get("value_eur", 0) for p in positions}

        # Get target allocation
        hist_service = get_historical_service()
        symbols = ["BTCUSDT", "EQ_AAPL", "EQ_MSFT", "EQ_GOOGL", "EQ_NVDA"]
        returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(symbol, timeframe="1d", limit=365)
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    returns[symbol] = df["return"]
            except Exception:
                continue

        optimizer = get_portfolio_optimizer()
        target = optimizer.optimize_portfolio(returns=returns, risk_level=risk_level)

        # Generate plan
        plan = optimizer.generate_rebalancing_plan(
            current_positions=current_positions,
            target_allocation=target.allocation,
            total_value=total_value,
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "current_allocation": {
                k: round(v, 2) for k, v in plan.current_allocation.items()
            },
            "target_allocation": {
                k: round(v, 2) for k, v in plan.target_allocation.items()
            },
            "trades": plan.trades,
            "total_trade_volume_eur": round(plan.total_trade_volume_eur, 2),
            "estimated_cost_eur": round(plan.estimated_cost_eur, 2),
            "estimated_tax_eur": round(plan.tax_impact_eur, 2),
            "rationale": plan.rationale,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating rebalancing plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-return-profile")
async def get_risk_return_profile() -> Dict[str, Any]:
    """
    Get risk/return profile for all risk levels.

    Returns:
    --------
    {
        "profiles": [
            {
                "risk_level": "conservative",
                "target_return_pct": 4.2,
                "target_volatility_pct": 5.5,
                "sharpe_ratio": 1.2,
                "suitable_for": "Retirees, capital preservation"
            },
            ...
        ]
    }
    """
    try:
        # Get historical data
        hist_service = get_historical_service()
        symbols = ["BTCUSDT", "EQ_AAPL", "EQ_MSFT", "EQ_GOOGL", "EQ_NVDA"]
        returns = {}

        for symbol in symbols:
            try:
                df = hist_service.get_candles(symbol, timeframe="1d", limit=365)
                if not df.empty and len(df) > 20:
                    df["return"] = df["close"].pct_change() * 100
                    returns[symbol] = df["return"]
            except Exception:
                continue

        optimizer = get_portfolio_optimizer()

        profiles = []
        risk_levels = ["conservative", "moderate", "balanced", "aggressive", "extreme"]
        descriptions = [
            "Capital preservation, low volatility",
            "Conservative growth, low risk",
            "Balanced approach, moderate risk",
            "Growth-oriented, higher risk tolerance",
            "Maximum growth, high risk tolerance",
        ]

        for risk_level, description in zip(risk_levels, descriptions):
            allocation = optimizer.optimize_portfolio(
                returns=returns if returns else {},
                risk_level=risk_level,
            )

            profiles.append(
                {
                    "risk_level": risk_level,
                    "target_return_pct": round(allocation.target_return_pct, 2),
                    "target_volatility_pct": round(allocation.target_volatility_pct, 2),
                    "sharpe_ratio": round(allocation.sharpe_ratio, 2),
                    "suitable_for": description,
                }
            )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "profiles": profiles,
        }

    except Exception as e:
        logger.error(f"Error getting risk/return profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
