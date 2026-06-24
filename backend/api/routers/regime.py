"""Market regime analysis and strategy impact endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import logging

from backend.analytics.regime_detector import get_regime_detector
from backend.analytics.historical_data import get_historical_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/regime", tags=["Market Regime"])


@router.get("/detect")
@router.post("/detect")
async def detect_market_regime_router(symbol: str) -> JSONResponse:
    """Detect current market regime for a symbol (BUG FIX #3).

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')

    Returns:
        Current regime classification with confidence and metrics
    """
    try:
        # Get historical data
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        end = datetime.now()
        start = end - timedelta(days=60)

        ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol}"
            )

        # Detect regime
        detector = get_regime_detector()
        if not detector:
            raise HTTPException(status_code=500, detail="Regime detector not initialized")

        metrics = detector.detect_regime(ohlcv)

        return JSONResponse(
            {
                "symbol": symbol,
                "regime": metrics.get("regime", "unknown"),
                "confidence": metrics.get("confidence", 0.8),
                "volatility_pct": metrics.get("volatility_ratio", 1.0),
                "trend_strength": metrics.get("trend_strength", 0.0),
                "support_level": metrics.get("support", 0.0),
                "resistance_level": metrics.get("resistance", 0.0),
                "rsi": metrics.get("rsi_value", 50.0),
                "recommendation": metrics.get("recommendation", ""),
                "volatility_level": metrics.get("volatility_level", "medium"),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection error: {e}")
        raise HTTPException(status_code=500, detail=f"Regime detection failed: {str(e)}")


@router.get("/strategy-impact")
@router.post("/strategy-impact")
async def get_strategy_impact(symbol: str = "BTCUSDT") -> JSONResponse:
    """Get strategy impact adjustments based on market regime (BUG FIX #3).

    Returns multipliers for different trading strategies based on current market conditions.
    Supports both GET and POST for flexibility.
    """
    try:
        # Get regime first
        hist_service = get_historical_service()
        if not hist_service:
            # Fallback to neutral regime if no historical data
            regime = "neutral"
            confidence = 0.5
        else:
            end = datetime.now()
            start = end - timedelta(days=60)
            ohlcv = hist_service.fetch_ohlcv(symbol, start, end)

            if ohlcv is None or ohlcv.empty:
                regime = "neutral"
                confidence = 0.5
            else:
                detector = get_regime_detector()
                if not detector:
                    regime = "neutral"
                    confidence = 0.5
                else:
                    metrics = detector.detect_regime(ohlcv)
                    regime = metrics.get("regime", "neutral")
                    confidence = metrics.get("confidence", 0.8)

        # Adjust strategy weights based on regime
        if regime == "bull":
            strategy_adjustments = {
                "momentum": 1.2,    # Increase momentum in bull
                "reversion": 0.8,   # Decrease reversion
                "grid": 1.0,
                "trend": 1.1,
            }
            recommended = ["momentum", "trend"]
            avoid = ["reversion"]
        elif regime == "bear":
            strategy_adjustments = {
                "momentum": 0.6,    # Avoid momentum in bear
                "reversion": 1.3,   # Increase reversion (catch rebounds)
                "grid": 0.9,
                "trend": 0.7,
            }
            recommended = ["reversion"]
            avoid = ["momentum"]
        elif regime == "sideways":
            strategy_adjustments = {
                "momentum": 0.7,
                "reversion": 1.2,   # Grid works best in sideways
                "grid": 1.3,
                "trend": 0.6,
            }
            recommended = ["grid", "reversion"]
            avoid = ["trend", "momentum"]
        elif regime == "volatile":
            strategy_adjustments = {
                "momentum": 0.8,
                "reversion": 0.9,
                "grid": 0.6,        # Avoid grid in high volatility
                "trend": 1.1,
            }
            recommended = ["trend"]
            avoid = ["grid"]
        else:
            # Neutral/unknown
            strategy_adjustments = {
                "momentum": 1.0,
                "reversion": 1.0,
                "grid": 1.0,
                "trend": 1.0,
            }
            recommended = ["grid", "momentum"]
            avoid = []

        return JSONResponse({
            "symbol": symbol,
            "regime": regime,
            "regime_confidence": confidence,
            "strategy_adjustments": strategy_adjustments,
            "recommended_strategies": recommended,
            "avoid_strategies": avoid,
            "guidance": f"In {regime} market, favor {', '.join(recommended)} strategies"
        })

    except Exception as e:
        logger.error(f"Strategy impact error: {e}")
        raise HTTPException(status_code=500, detail=f"Strategy impact analysis failed: {str(e)}")
