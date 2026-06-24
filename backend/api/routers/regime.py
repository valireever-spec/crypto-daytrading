"""Market regime analysis and strategy impact endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/regime", tags=["Market Regime"])


@router.post("/strategy-impact")
async def get_strategy_impact(symbol: str = "BTCUSDT") -> JSONResponse:
    """Get strategy impact adjustments based on market regime.

    Returns multipliers for different trading strategies based on current market conditions.
    """
    # Default strategy adjustments (neutral market)
    strategy_adjustments = {
        "momentum": 1.0,      # 1.0 = use full momentum strategy
        "reversion": 1.0,     # 1.0 = use full reversion strategy
        "grid": 1.0,          # 1.0 = use full grid strategy
        "trend": 1.0,         # 1.0 = use full trend strategy
    }

    # Market regime detection (simplified - in production would use regime_detector)
    # For now, return neutral adjustments

    return JSONResponse({
        "symbol": symbol,
        "regime": "neutral",
        "strategy_adjustments": strategy_adjustments,
        "confidence": 0.85,
        "recommended_strategies": ["grid", "momentum"],
        "avoid_strategies": [],
    })
