"""API endpoints for autonomous trading control."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.trading.autonomous_trader import (
    get_autonomous_trader,
    TradingConfig
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Autonomous Trading"])


@router.get("/api/autonomous/status")
async def get_autonomous_status():
    """Get autonomous trader status."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    return JSONResponse(trader.get_status())


@router.post("/api/autonomous/start")
async def start_autonomous_trading():
    """Start autonomous trading."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    if trader.running:
        return JSONResponse({"status": "already_running"})

    trader.config.enabled = True
    logger.info("Autonomous trading enabled")
    return JSONResponse({
        "status": "started",
        "message": "Autonomous trading is now active"
    })


@router.post("/api/autonomous/stop")
async def stop_autonomous_trading():
    """Stop autonomous trading."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    trader.config.enabled = False
    logger.info("Autonomous trading disabled")
    return JSONResponse({
        "status": "stopped",
        "message": "Autonomous trading is now paused"
    })


@router.get("/api/autonomous/config")
async def get_trading_config():
    """Get autonomous trading configuration."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    return JSONResponse({
        "entry_threshold": trader.config.entry_threshold,
        "exit_profit_target": trader.config.exit_profit_target,
        "exit_stop_loss": trader.config.exit_stop_loss,
        "position_size_pct": trader.config.position_size_pct,
        "max_positions": trader.config.max_positions,
        "symbols": trader.config.symbols,
        "enabled": trader.config.enabled
    })


@router.post("/api/autonomous/config/update")
async def update_trading_config(
    entry_threshold: float = None,
    exit_profit_target: float = None,
    exit_stop_loss: float = None,
    position_size_pct: float = None,
    max_positions: int = None,
    symbols: list = None
):
    """Update autonomous trading configuration."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    if entry_threshold is not None:
        trader.config.entry_threshold = entry_threshold
    if exit_profit_target is not None:
        trader.config.exit_profit_target = exit_profit_target
    if exit_stop_loss is not None:
        trader.config.exit_stop_loss = exit_stop_loss
    if position_size_pct is not None:
        trader.config.position_size_pct = position_size_pct
    if max_positions is not None:
        trader.config.max_positions = max_positions
    if symbols is not None:
        trader.config.symbols = symbols

    logger.info(f"Updated trading config: {trader.config}")
    return JSONResponse({
        "status": "updated",
        "config": {
            "entry_threshold": trader.config.entry_threshold,
            "exit_profit_target": trader.config.exit_profit_target,
            "exit_stop_loss": trader.config.exit_stop_loss,
            "position_size_pct": trader.config.position_size_pct,
            "max_positions": trader.config.max_positions,
            "symbols": trader.config.symbols
        }
    })


@router.get("/api/autonomous/trades")
async def get_trade_history(limit: int = 50):
    """Get recent autonomous trades."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    trades = trader.trade_history[-limit:] if trader.trade_history else []
    return JSONResponse({
        "total": len(trader.trade_history),
        "recent": trades,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    })
