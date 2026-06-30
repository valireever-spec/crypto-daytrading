"""Trading control endpoints for pause/resume and position management."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading", tags=["Trading Control"])

# Global trading state
_trading_paused = False


@router.post("/pause")
async def pause_trading() -> JSONResponse:
    """Pause autonomous trading."""
    global _trading_paused
    try:
        from backend.trading.autonomous_trader import get_autonomous_trader

        trader = get_autonomous_trader()
        if trader and hasattr(trader, 'running') and trader.running:
            await trader.stop()

        _trading_paused = True
        logger.warning("🔴 Trading PAUSED")

        return {
            "status": "paused",
            "message": "Trading paused successfully",
            "timestamp": None
        }
    except Exception as e:
        logger.error(f"Error pausing trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume_trading() -> JSONResponse:
    """Resume autonomous trading."""
    global _trading_paused
    try:
        from backend.trading.autonomous_trader import get_autonomous_trader, init_autonomous_trader

        trader = get_autonomous_trader()
        if not trader or not hasattr(trader, 'running') or not trader.running:
            trader = init_autonomous_trader()
            # Start trader in background (don't await, allow endpoint to return immediately)
            import asyncio
            asyncio.create_task(trader.start())
            logger.info("Started autonomous trader background task")
        else:
            logger.info("Autonomous trader already running")

        _trading_paused = False
        logger.warning("🟢 Trading RESUMED")

        return {
            "status": "resumed",
            "message": "Trading resumed successfully",
            "timestamp": None
        }
    except Exception as e:
        logger.error(f"Error resuming trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exit")
async def partial_exit(symbol: str, percentage: float) -> JSONResponse:
    """Close a percentage of a position."""
    try:
        if not symbol or percentage <= 0 or percentage > 1:
            raise HTTPException(status_code=400, detail="Invalid symbol or percentage")

        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Get position
        positions = engine.get_positions()
        position = next((p for p in positions if p['symbol'] == symbol and p['status'] == 'open'), None)

        if not position:
            raise HTTPException(status_code=404, detail=f"No open position found for {symbol}")

        # Calculate exit quantity
        exit_qty = position['quantity'] * percentage

        # Execute market sell order
        order = engine.place_market_order(
            symbol=symbol,
            side='sell',
            quantity=exit_qty,
            source='manual_exit'
        )

        logger.info(f"✅ Partial exit: {symbol} {exit_qty:.4f} @ {percentage*100:.0f}%")

        return {
            "status": "success",
            "symbol": symbol,
            "quantity_exited": exit_qty,
            "percentage": percentage,
            "order_id": order.get('id') if order else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exiting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))
