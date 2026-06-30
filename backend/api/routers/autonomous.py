"""API endpoints for autonomous trading control."""

import logging
import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.trading.autonomous_trader import get_autonomous_trader
from backend.core.config_manager import ConfigManager
from backend.core.immutable_logger import get_immutable_logger

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Autonomous Trading"])


class ConfigUpdateRequest(BaseModel):
    """Request model for config updates."""

    enabled: Optional[bool] = None
    entry_threshold: Optional[float] = None
    exit_profit_target: Optional[float] = None
    exit_stop_loss: Optional[float] = None
    position_size_pct: Optional[float] = None
    max_positions: Optional[int] = None
    max_daily_loss_pct: Optional[float] = None
    symbols: Optional[List[str]] = None
    loop_sleep_seconds: Optional[float] = None  # Controls trading frequency (seconds)
    quality_gate_entry: Optional[float] = None  # Min data quality for NEW entries (%)
    quality_gate_exit: Optional[float] = None  # Min data quality for exits (%)


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
    return JSONResponse(
        {"status": "started", "message": "Autonomous trading is now active"}
    )


@router.post("/api/autonomous/stop")
async def stop_autonomous_trading():
    """Stop autonomous trading."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    trader.config.enabled = False
    logger.info("Autonomous trading disabled")
    return JSONResponse(
        {"status": "stopped", "message": "Autonomous trading is now paused"}
    )


@router.get("/api/autonomous/config")
async def get_trading_config():
    """Get autonomous trading configuration."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    return JSONResponse(
        {
            "entry_threshold": trader.config.entry_threshold,
            "exit_profit_target": trader.config.exit_profit_target,
            "exit_stop_loss": trader.config.exit_stop_loss,
            "position_size_pct": trader.config.position_size_pct,
            "max_positions": trader.config.max_positions,
            "max_daily_loss_pct": trader.config.max_daily_loss_pct,
            "symbols": trader.config.symbols,
            "enabled": trader.config.enabled,
            "loop_sleep_seconds": trader.config.loop_sleep_seconds,
            "quality_gate_entry": trader.config.quality_gate_entry,
            "quality_gate_exit": trader.config.quality_gate_exit,
        }
    )


@router.post("/api/autonomous/config/update")
async def update_trading_config(request: ConfigUpdateRequest):
    """Update autonomous trading configuration."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    if request.enabled is not None:
        trader.config.enabled = request.enabled
    if request.entry_threshold is not None:
        trader.config.entry_threshold = request.entry_threshold
    if request.exit_profit_target is not None:
        trader.config.exit_profit_target = request.exit_profit_target
    if request.exit_stop_loss is not None:
        trader.config.exit_stop_loss = request.exit_stop_loss
    if request.position_size_pct is not None:
        trader.config.position_size_pct = request.position_size_pct
    if request.max_positions is not None:
        trader.config.max_positions = request.max_positions
    if request.max_daily_loss_pct is not None:
        trader.config.max_daily_loss_pct = request.max_daily_loss_pct
    if request.symbols is not None:
        trader.config.symbols = request.symbols
    if request.loop_sleep_seconds is not None:
        trader.config.loop_sleep_seconds = request.loop_sleep_seconds
    if request.quality_gate_entry is not None:
        trader.config.quality_gate_entry = request.quality_gate_entry
    if request.quality_gate_exit is not None:
        trader.config.quality_gate_exit = request.quality_gate_exit

    # Apply cascading linkage rules
    # Rule 1: Position Size × Max Positions ≤ 25% total risk
    total_risk = trader.config.position_size_pct * trader.config.max_positions
    if total_risk > 25.0:
        if request.position_size_pct is not None and request.max_positions is None:
            # User changed position_size_pct; adjust max_positions down
            trader.config.max_positions = max(
                1, int(25.0 / trader.config.position_size_pct)
            )
            logger.info(
                f"Auto-adjusted max_positions to {trader.config.max_positions} "
                f"to keep total risk ≤25% (position_size_pct={trader.config.position_size_pct}%)"
            )
        else:
            # User changed max_positions; adjust position_size_pct down
            trader.config.position_size_pct = 25.0 / trader.config.max_positions
            logger.info(
                f"Auto-adjusted position_size_pct to {trader.config.position_size_pct:.2f}% "
                f"to keep total risk ≤25% (max_positions={trader.config.max_positions})"
            )

    # Rule 2: Exit Profit Target ÷ Exit Stop Loss = 1.5 risk/reward ratio
    if request.exit_stop_loss is not None and request.exit_profit_target is None:
        # User changed stop_loss; adjust profit_target to maintain 1:1.5
        trader.config.exit_profit_target = trader.config.exit_stop_loss * 1.5
        logger.info(
            f"Auto-adjusted exit_profit_target to {trader.config.exit_profit_target:.4f} "
            f"to maintain 1:1.5 risk/reward (exit_stop_loss={trader.config.exit_stop_loss:.4f})"
        )
    elif request.exit_profit_target is not None and request.exit_stop_loss is None:
        # User changed profit_target; adjust stop_loss to maintain 1:1.5
        trader.config.exit_stop_loss = trader.config.exit_profit_target / 1.5
        logger.info(
            f"Auto-adjusted exit_stop_loss to {trader.config.exit_stop_loss:.4f} "
            f"to maintain 1:1.5 risk/reward (exit_profit_target={trader.config.exit_profit_target:.4f})"
        )

    # Prepare config dict
    config_dict = {
        "entry_threshold": trader.config.entry_threshold,
        "exit_profit_target": trader.config.exit_profit_target,
        "exit_stop_loss": trader.config.exit_stop_loss,
        "position_size_pct": trader.config.position_size_pct,
        "max_positions": trader.config.max_positions,
        "max_daily_loss_pct": trader.config.max_daily_loss_pct,
        "symbols": trader.config.symbols,
        "enabled": trader.config.enabled,
        "loop_sleep_seconds": trader.config.loop_sleep_seconds,
        "quality_gate_entry": trader.config.quality_gate_entry,
        "quality_gate_exit": trader.config.quality_gate_exit,
    }

    # Save to persistent storage
    ConfigManager.save_config(config_dict)

    # Sync to backup if this is primary
    machine_id = os.getenv("MACHINE_ID", "main")
    if machine_id == "main":
        backup_url = os.getenv("BACKUP_MACHINE_URL", "http://192.168.3.25:8002")
        ConfigManager.sync_to_backup(backup_url, config_dict)

    logger.info(f"Updated and persisted trading config: {config_dict}")
    return JSONResponse(
        {
            "status": "updated",
            "persisted": True,
            "synced": machine_id == "main",
            "config": config_dict,
        }
    )


@router.post("/api/autonomous/config/sync")
async def sync_config_from_backup(request: ConfigUpdateRequest):
    """Receive config sync from primary machine (primary → backup)."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")

    # Apply all config fields from sync request
    if request.enabled is not None:
        trader.config.enabled = request.enabled
    if request.entry_threshold is not None:
        trader.config.entry_threshold = request.entry_threshold
    if request.exit_profit_target is not None:
        trader.config.exit_profit_target = request.exit_profit_target
    if request.exit_stop_loss is not None:
        trader.config.exit_stop_loss = request.exit_stop_loss
    if request.position_size_pct is not None:
        trader.config.position_size_pct = request.position_size_pct
    if request.max_positions is not None:
        trader.config.max_positions = request.max_positions
    if request.max_daily_loss_pct is not None:
        trader.config.max_daily_loss_pct = request.max_daily_loss_pct
    if request.symbols is not None:
        trader.config.symbols = request.symbols
    if request.loop_sleep_seconds is not None:
        trader.config.loop_sleep_seconds = request.loop_sleep_seconds
    if request.quality_gate_entry is not None:
        trader.config.quality_gate_entry = request.quality_gate_entry
    if request.quality_gate_exit is not None:
        trader.config.quality_gate_exit = request.quality_gate_exit

    # Apply cascading linkage rules (same as /config/update)
    # Rule 1: Position Size × Max Positions ≤ 25% total risk
    total_risk = trader.config.position_size_pct * trader.config.max_positions
    if total_risk > 25.0:
        if request.position_size_pct is not None and request.max_positions is None:
            # Sync sent position_size_pct; adjust max_positions down
            trader.config.max_positions = max(
                1, int(25.0 / trader.config.position_size_pct)
            )
            logger.info(
                f"[SYNC] Auto-adjusted max_positions to {trader.config.max_positions} "
                f"to keep total risk ≤25%"
            )
        else:
            # Sync sent max_positions; adjust position_size_pct down
            trader.config.position_size_pct = 25.0 / trader.config.max_positions
            logger.info(
                f"[SYNC] Auto-adjusted position_size_pct to {trader.config.position_size_pct:.2f}% "
                f"to keep total risk ≤25%"
            )

    # Rule 2: Exit Profit Target ÷ Exit Stop Loss = 1.5 risk/reward ratio
    if request.exit_stop_loss is not None and request.exit_profit_target is None:
        trader.config.exit_profit_target = trader.config.exit_stop_loss * 1.5
        logger.info(
            f"[SYNC] Auto-adjusted exit_profit_target to {trader.config.exit_profit_target:.4f} "
            f"to maintain 1:1.5 risk/reward"
        )
    elif request.exit_profit_target is not None and request.exit_stop_loss is None:
        trader.config.exit_stop_loss = trader.config.exit_profit_target / 1.5
        logger.info(
            f"[SYNC] Auto-adjusted exit_stop_loss to {trader.config.exit_stop_loss:.4f} "
            f"to maintain 1:1.5 risk/reward"
        )

    # Convert to dict for storage
    config_dict = {
        "entry_threshold": trader.config.entry_threshold,
        "exit_profit_target": trader.config.exit_profit_target,
        "exit_stop_loss": trader.config.exit_stop_loss,
        "position_size_pct": trader.config.position_size_pct,
        "max_positions": trader.config.max_positions,
        "max_daily_loss_pct": trader.config.max_daily_loss_pct,
        "symbols": trader.config.symbols,
        "enabled": trader.config.enabled,
    }

    # PERSIST synced config to disk
    ConfigManager.save_config(config_dict)

    logger.info(f"Synced config from primary: {config_dict}")
    return JSONResponse(
        {
            "status": "synced",
            "message": "Config synced and persisted",
            "persisted": True,
            "config": config_dict,
        }
    )


@router.get("/api/autonomous/trades")
async def get_trade_history(limit: int = 50):
    """Get recent autonomous trades."""
    try:
        trader = get_autonomous_trader()
        if not trader:
            return JSONResponse(
                {
                    "total": 0,
                    "recent": [],
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                }
            )

        # Safely get trade history
        trade_history = []
        if hasattr(trader, 'trade_history') and trader.trade_history:
            trade_history = trader.trade_history[-limit:] if isinstance(trader.trade_history, list) else []

        return JSONResponse(
            {
                "total": len(trade_history) if trade_history else 0,
                "recent": trade_history,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/immutable-log/status")
async def get_immutable_log_status():
    """Get immutable transaction log status (Pillar #6: State Persistence)."""
    try:
        logger = get_immutable_logger()
        status = logger.get_log_status()
        return JSONResponse(
            {
                "status": "ok",
                "immutable_log": status,
                "message": "Write-once, append-only transaction logging active",
            }
        )
    except Exception as e:
        logger.error(f"Failed to get immutable log status: {e}")
        raise HTTPException(status_code=500, detail=f"Immutable log error: {str(e)}")


@router.post("/api/autonomous/positions/close")
async def close_position(symbol: str):
    """Close all of a specific position."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Get position
        positions = engine.get_positions()
        position = next((p for p in positions if p['symbol'] == symbol and p['status'] == 'open'), None)

        if not position:
            raise HTTPException(status_code=404, detail=f"No open position found for {symbol}")

        # Execute market sell order for full quantity
        order = engine.place_market_order(
            symbol=symbol,
            side='sell',
            quantity=position['quantity'],
            source='manual_close'
        )

        logger.info(f"✅ Position closed: {symbol} {position['quantity']:.4f}")

        return {
            "status": "success",
            "symbol": symbol,
            "quantity_closed": position['quantity'],
            "order_id": order.get('id') if order else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/signals/calculate")
async def calculate_signal(symbol: str):
    """Calculate trading signal for a symbol."""
    try:
        from backend.analytics.signals import get_signal_generator
        from backend.analytics.historical_data import get_historical_service

        # Get signal generator
        generator = get_signal_generator()
        if not generator:
            raise HTTPException(status_code=500, detail="Signal generator not initialized")

        # Get historical data for the symbol
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        prices = hist_service.get_prices(symbol, period=90)
        if prices is None or len(prices) == 0:
            raise HTTPException(status_code=404, detail=f"No price data available for {symbol}")

        # Generate signal
        signal_result = await generator.generate_signal(symbol, prices)

        return {
            "status": "success",
            "symbol": symbol,
            "signal": signal_result.get('signal_value', 0) if signal_result else 0,
            "confidence": signal_result.get('confidence', 0) if signal_result else 0,
            "reasoning": signal_result.get('reasoning', '') if signal_result else '',
            "components": signal_result.get('components', {}) if signal_result else {}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
