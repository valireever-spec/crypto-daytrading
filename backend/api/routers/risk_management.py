"""API endpoints for advanced risk management."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from backend.analytics.risk_calculator import PortfolioRiskCalculator
from backend.analytics.risk_limits import (
    init_risk_monitor,
    get_risk_monitor,
    RiskLimits,
    RiskMetrics
)
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk", tags=["Risk Management"])


class RiskLimitsUpdate(BaseModel):
    """Request model for updating risk limits."""
    max_drawdown_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None
    max_position_size_pct: Optional[float] = None
    max_var_95: Optional[float] = None
    max_correlation: Optional[float] = None


@router.get("/limits")
async def get_risk_limits():
    """Get current risk limits."""
    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    return JSONResponse({
        "limits": {
            "max_drawdown_pct": monitor.limits.max_drawdown_pct,
            "max_daily_loss_pct": monitor.limits.max_daily_loss_pct,
            "max_position_size_pct": monitor.limits.max_position_size_pct,
            "max_sector_exposure_pct": monitor.limits.max_sector_exposure_pct,
            "max_var_95": monitor.limits.max_var_95,
            "max_correlation": monitor.limits.max_correlation,
            "min_diversification": monitor.limits.min_diversification
        }
    })


@router.post("/limits/update")
async def update_risk_limits(request: RiskLimitsUpdate):
    """Update risk limits."""
    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    # Update limits
    if request.max_drawdown_pct is not None:
        monitor.limits.max_drawdown_pct = request.max_drawdown_pct
    if request.max_daily_loss_pct is not None:
        monitor.limits.max_daily_loss_pct = request.max_daily_loss_pct
    if request.max_position_size_pct is not None:
        monitor.limits.max_position_size_pct = request.max_position_size_pct
    if request.max_var_95 is not None:
        monitor.limits.max_var_95 = request.max_var_95
    if request.max_correlation is not None:
        monitor.limits.max_correlation = request.max_correlation

    logger.info(f"Risk limits updated: {request}")

    return JSONResponse({
        "status": "updated",
        "limits": {
            "max_drawdown_pct": monitor.limits.max_drawdown_pct,
            "max_daily_loss_pct": monitor.limits.max_daily_loss_pct,
            "max_position_size_pct": monitor.limits.max_position_size_pct,
            "max_var_95": monitor.limits.max_var_95
        }
    })


@router.get("/portfolio-var")
async def get_portfolio_var(confidence: float = 0.95):
    """Calculate portfolio Value at Risk."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    account = engine.get_account_state()
    if not account or not account.get('positions'):
        return JSONResponse({
            "portfolio_value": account.get('total_equity', 0),
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "message": "No positions"
        })

    # Create risk calculator
    calc = PortfolioRiskCalculator()

    # Add positions (would normally include historical prices)
    for pos in account.get('positions', []):
        calc.add_position(pos['symbol'], pos['quantity'], pos['entry_price'])
        calc.update_price(pos['symbol'], pos['current_price'])

    return JSONResponse({
        "portfolio_value": calc.get_portfolio_value(),
        "var_95": calc.calculate_portfolio_var(0.95),
        "var_99": calc.calculate_portfolio_var(0.99),
        "cvar_95": calc.calculate_portfolio_cvar(0.95),
        "positions": len(account.get('positions', []))
    })


@router.get("/drawdown")
async def get_portfolio_drawdown():
    """Get portfolio drawdown metrics."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    account = engine.get_account_state()
    if not account:
        raise HTTPException(status_code=500, detail="Account not available")

    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    # Would normally track portfolio value over time
    # For now, return basic metrics
    return JSONResponse({
        "portfolio_value": account.get('total_equity', 0),
        "initial_value": monitor.initial_value or account.get('total_equity', 0),
        "daily_start_value": monitor.daily_start_value or account.get('total_equity', 0),
        "current_drawdown_pct": 0.0,  # Would calculate from historical data
        "max_drawdown_pct": 0.0,
        "days_in_drawdown": 0
    })


@router.get("/status")
async def get_risk_status():
    """Get overall portfolio risk status."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    account = engine.get_account_state()
    if not account:
        raise HTTPException(status_code=500, detail="Account not available")

    # Update monitor with current portfolio value
    risk_level = monitor.update_portfolio_value(account.get('total_equity', 0))

    return JSONResponse({
        "risk_level": risk_level.value,
        "recommended_action": monitor.get_recommended_action(risk_level),
        "portfolio_value": account.get('total_equity', 0),
        "cash": account.get('cash', 0),
        "positions": len(account.get('positions', [])),
        "daily_pnl": account.get('daily_pnl', 0),
        "status": monitor.get_status()
    })


@router.get("/concentration")
async def get_concentration_risk():
    """Get portfolio concentration risk metrics."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    account = engine.get_account_state()
    if not account or not account.get('positions'):
        return JSONResponse({
            "concentration_hhi": 0.0,
            "message": "No positions",
            "risk_level": "green"
        })

    from backend.analytics.risk_calculator import CorrelationAnalyzer

    # Calculate weights
    weights = {}
    total_value = account.get('total_equity', 0)

    for pos in account.get('positions', []):
        pos_value = pos['quantity'] * pos['current_price']
        weights[pos['symbol']] = pos_value

    hhi = CorrelationAnalyzer.concentration_risk(weights)

    # Determine risk level
    risk_level = "green"
    if hhi > 0.25:
        risk_level = "red"
    elif hhi > 0.15:
        risk_level = "orange"
    elif hhi > 0.10:
        risk_level = "yellow"

    return JSONResponse({
        "concentration_hhi": hhi,
        "positions": len(weights),
        "largest_position_pct": (max(weights.values()) / total_value * 100) if weights else 0,
        "risk_level": risk_level,
        "recommendation": "Diversify further" if hhi > 0.15 else "Concentration risk is acceptable"
    })


@router.post("/position-check/{symbol}")
async def check_position_risk(symbol: str, quantity: float, price: float):
    """Check if a position would violate risk limits."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    account = engine.get_account_state()
    if not account:
        raise HTTPException(status_code=500, detail="Account not available")

    position_value = quantity * price
    portfolio_value = account.get('total_equity', 0)

    # Check if position size is allowed
    allowed = monitor.check_position_size(position_value, portfolio_value)

    position_pct = (position_value / portfolio_value * 100) if portfolio_value > 0 else 0

    return JSONResponse({
        "symbol": symbol,
        "position_value": position_value,
        "position_pct": position_pct,
        "allowed": allowed,
        "limit_pct": monitor.limits.max_position_size_pct,
        "message": "Position size OK" if allowed else "Position exceeds maximum size limit"
    })


@router.get("/recommendations")
async def get_risk_recommendations():
    """Get risk reduction recommendations."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    monitor = get_risk_monitor()
    if not monitor:
        monitor = init_risk_monitor()

    account = engine.get_account_state()
    if not account:
        raise HTTPException(status_code=500, detail="Account not available")

    # Get risk status
    risk_level = monitor.update_portfolio_value(account.get('total_equity', 0))

    recommendations = []

    # Concentration check
    from backend.analytics.risk_calculator import CorrelationAnalyzer
    weights = {}
    for pos in account.get('positions', []):
        pos_value = pos['quantity'] * pos['current_price']
        weights[pos['symbol']] = pos_value

    hhi = CorrelationAnalyzer.concentration_risk(weights)
    if hhi > 0.15:
        recommendations.append({
            "type": "diversification",
            "priority": "high" if hhi > 0.25 else "medium",
            "message": "Reduce concentration risk by diversifying across more positions",
            "action": "Sell largest position" if hhi > 0.25 else "Add new positions"
        })

    # Position size check
    largest_pos = max(weights.values()) if weights else 0
    total_value = account.get('total_equity', 0)
    largest_pct = (largest_pos / total_value * 100) if total_value > 0 else 0

    if largest_pct > monitor.limits.max_position_size_pct:
        recommendations.append({
            "type": "position_size",
            "priority": "high",
            "message": f"Largest position is {largest_pct:.1f}%, exceeds limit of {monitor.limits.max_position_size_pct}%",
            "action": "Reduce position size"
        })

    # Risk level check
    if risk_level.value != "green":
        recommendations.append({
            "type": "overall_risk",
            "priority": "critical" if risk_level.value == "red" else "high",
            "message": monitor.get_recommended_action(risk_level),
            "action": "Follow recommended action immediately"
        })

    return JSONResponse({
        "risk_level": risk_level.value,
        "portfolio_value": total_value,
        "recommendations": recommendations,
        "total_recommendations": len(recommendations)
    })
