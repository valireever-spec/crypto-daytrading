"""FastAPI main application for crypto daytrading platform."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Union

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.exchange.binance_websocket import init_websocket, get_websocket
from backend.exchange.paper_trading import init_paper_trading, get_paper_trading
from backend.analytics.signals import init_signal_generator, get_signal_generator
from backend.analytics.allocation import init_allocation, get_allocation

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Global state
websocket_task: asyncio.Task = None
_trading_paused: bool = False
current_prices: dict = {}  # symbol -> latest price


def get_trading_paused() -> bool:
    """Get current trading paused state."""
    global _trading_paused
    return _trading_paused


def set_trading_paused(paused: bool) -> None:
    """Set trading paused state."""
    global _trading_paused
    _trading_paused = paused


def reset_trading_paused() -> None:
    """Reset trading paused state (for testing)."""
    global _trading_paused
    _trading_paused = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global websocket_task

    # Startup
    logger.info("Starting crypto daytrading platform...")

    # Initialize paper trading engine
    init_paper_trading(starting_capital=settings.initial_capital)
    logger.info(f"Paper trading engine initialized with {settings.initial_capital} EUR")

    # Initialize signal generator
    init_signal_generator()
    logger.info("Signal generator initialized")

    # Initialize allocation manager
    init_allocation()
    logger.info("Allocation manager initialized")

    # Initialize WebSocket
    ws = await init_websocket(testnet=settings.binance_testnet)

    # Subscribe to demo streams (BTCUSDT)
    async def on_price_update(symbol: str, data: dict) -> None:
        """Handle price updates from WebSocket."""
        # Extract price from kline or trade data
        if "k" in data:  # Kline (candle)
            close_price = float(data["k"]["c"])
        elif "p" in data:  # Trade
            close_price = float(data["p"])
        else:
            return

        # Update paper trading engine
        engine = get_paper_trading()
        if engine:
            engine.mark_to_market({symbol: close_price})
            logger.debug(f"{symbol}: {close_price}")

    # Subscribe to streams
    ws.subscribe("btcusdt@kline_1m", on_price_update)
    ws.subscribe("btcusdt@trade", on_price_update)
    ws.subscribe("ethusdt@kline_1m", on_price_update)

    # Start WebSocket connection in background
    websocket_task = asyncio.create_task(ws.connect())

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Shutting down crypto daytrading platform...")
    if websocket_task and not websocket_task.done():
        websocket_task.cancel()
    if ws:
        await ws.disconnect()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Crypto Daytrading Platform",
    description="Real-time paper and live trading with Binance WebSocket",
    version="1.0.0-phase1",
    lifespan=lifespan,
)

# Mount frontend
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# === Health Check Endpoints ===


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """System health check."""
    ws = get_websocket()
    ws_status = await ws.get_connection_status() if ws else {"connected": False}

    engine = get_paper_trading()
    account = engine.get_account_state() if engine else {}

    return JSONResponse(
        {
            "status": "ok",
            "mode": settings.trading_mode,
            "websocket": ws_status,
            "paper_trading": account,
        }
    )


# === Paper Trading Endpoints (FR-002) ===


@app.get("/api/paper/account")
async def get_paper_account() -> JSONResponse:
    """Get paper trading account state."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    return JSONResponse(engine.get_account_state())


@app.post("/api/paper/order")
async def place_paper_order(
    symbol: str,
    side: str,
    quantity: float,
    current_price: float,
    order_type: str = "MARKET",
) -> JSONResponse:
    """Place a paper trading order."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    if side not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")

    result = await engine.place_order(
        symbol=symbol.upper(),
        side=side,  # type: ignore
        quantity=quantity,
        current_price=current_price,
        order_type=order_type,  # type: ignore
    )

    return JSONResponse(result)


@app.get("/api/paper/positions")
async def get_paper_positions() -> JSONResponse:
    """Get open positions."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    return JSONResponse({"positions": engine.get_positions()})


@app.get("/api/paper/trades")
async def get_paper_trades(limit: int = 100) -> JSONResponse:
    """Get trade history."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    return JSONResponse({"trades": engine.get_trades(limit)})


@app.post("/api/paper/reset")
async def reset_paper_trading() -> JSONResponse:
    """Reset paper trading account."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    engine.reset()
    return JSONResponse({"status": "reset", "account": engine.get_account_state()})


@app.get("/api/paper/status")
async def get_paper_status() -> JSONResponse:
    """Get paper trading status."""
    ws = get_websocket()
    ws_status = await ws.get_connection_status() if ws else {"connected": False}

    engine = get_paper_trading()
    account = engine.get_account_state() if engine else {}

    return JSONResponse(
        {
            "mode": "PAPER",
            "websocket": ws_status,
            "account": account,
        }
    )


# === Signal Generation Endpoints (FR-003, FR-004) ===


@app.post("/api/signals/calculate")
async def calculate_signal(symbol: str, prices: list[float]) -> JSONResponse:
    """Calculate trading signal for a symbol.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        prices: List of closing prices (at least 20 required)

    Returns:
        Signal with score (-100 to +100), grade, indicators
    """
    if not prices or len(prices) < 3:
        return JSONResponse(
            {
                "status": "ERROR",
                "reason": "Need at least 3 prices",
            },
            status_code=400,
        )

    try:
        import pandas as pd

        price_series = pd.Series(prices)
        signal_gen = get_signal_generator()

        if not signal_gen:
            raise HTTPException(
                status_code=500, detail="Signal generator not initialized"
            )

        signal = await signal_gen.generate_signal(symbol.upper(), price_series)
        return JSONResponse(signal)

    except Exception as e:
        logger.error(f"Error calculating signal: {e}")
        return JSONResponse(
            {"status": "ERROR", "reason": str(e)}, status_code=500
        )


# === Manual Order Endpoints (FR-005) ===


@app.post("/api/order/manual")
async def place_manual_order(
    symbol: str,
    side: str,
    quantity: float,
    current_price: float,
    order_type: str = "MARKET",
) -> JSONResponse:
    """Place a manual order via trader button click.

    Args:
        symbol: Trading symbol
        side: BUY or SELL
        quantity: Order quantity
        current_price: Current market price
        order_type: MARKET or LIMIT

    Returns:
        Order confirmation
    """
    if get_trading_paused():
        return JSONResponse(
            {
                "status": "REJECTED",
                "reason": "Trading is paused",
            },
            status_code=400,
        )

    engine = get_paper_trading()
    if not engine:
        raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

    if side not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")

    result = await engine.place_order(
        symbol=symbol.upper(),
        side=side,  # type: ignore
        quantity=quantity,
        current_price=current_price,
        order_type=order_type,  # type: ignore
    )

    return JSONResponse(result)


# === Trading Control Endpoints (FR-007) ===


@app.post("/api/trading/pause")
async def pause_trading() -> JSONResponse:
    """Pause trading (no new signals, existing positions hold)."""
    set_trading_paused(True)
    logger.info("Trading paused")
    return JSONResponse({"status": "paused", "message": "Trading paused"})


@app.post("/api/trading/resume")
async def resume_trading() -> JSONResponse:
    """Resume trading after pause."""
    set_trading_paused(False)
    logger.info("Trading resumed")
    return JSONResponse({"status": "trading", "message": "Trading resumed"})


@app.get("/api/trading/status")
async def get_trading_status() -> JSONResponse:
    """Get current trading status."""
    paused = get_trading_paused()

    engine = get_paper_trading()
    account = engine.get_account_state() if engine else {}

    return JSONResponse(
        {
            "trading_paused": paused,
            "mode": "PAUSED" if paused else "TRADING",
            "account": account,
        }
    )


# === Dashboard Endpoint (FR-008) ===


@app.get("/api/dashboard")
async def get_dashboard() -> JSONResponse:
    """Get live dashboard metrics."""
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(
            status_code=500, detail="Paper trading engine not initialized"
        )

    account = engine.get_account_state()
    positions = engine.get_positions()
    trades = engine.get_trades(limit=10)

    # Calculate metrics
    total_trades = len(engine.trade_history)
    winning_trades = len(
        [t for t in engine.trade_history if t.realized_pnl > 0]
    )
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    return JSONResponse(
        {
            "account": account,
            "positions": positions,
            "recent_trades": trades,
            "metrics": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate_pct": round(win_rate, 1),
                "avg_win": (
                    sum(t.realized_pnl for t in engine.trade_history if t.realized_pnl > 0)
                    / winning_trades
                    if winning_trades > 0
                    else 0
                ),
            },
            "trading_paused": get_trading_paused(),
            "timestamp": pd.Timestamp.now().isoformat(),
        }
    )


# === Allocation Management Endpoints (FR-009) ===


@app.get("/api/allocation")
async def get_current_allocation() -> JSONResponse:
    """Get current strategy allocation.

    Returns:
        Current allocation with momentum, reversion, grid weights
    """
    mgr = get_allocation()
    if not mgr:
        raise HTTPException(status_code=500, detail="Allocation manager not initialized")

    state = mgr.get_allocation()
    return JSONResponse(
        {
            "momentum": state.momentum,
            "reversion": state.reversion,
            "grid": state.grid,
            "preset": state.preset,
        }
    )


@app.post("/api/allocation/save")
async def save_allocation(
    momentum: float, reversion: float, grid: float
) -> JSONResponse:
    """Save custom strategy allocation.

    Args:
        momentum: Momentum strategy weight (0-100)
        reversion: Reversion strategy weight (0-100)
        grid: Grid trading weight (0-100)

    Returns:
        Updated allocation
    """
    if momentum + reversion + grid != 100:
        raise HTTPException(
            status_code=400,
            detail="Allocation weights must sum to 100",
        )

    mgr = get_allocation()
    if not mgr:
        raise HTTPException(status_code=500, detail="Allocation manager not initialized")

    try:
        allocation = mgr.set_allocation(
            momentum=momentum, reversion=reversion, grid=grid, preset="custom"
        )
        logger.info(f"Allocation saved: {allocation}")
        return JSONResponse(
            {
                "status": "saved",
                "momentum": allocation["momentum"],
                "reversion": allocation["reversion"],
                "grid": allocation["grid"],
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/allocation/preset")
async def set_allocation_preset(preset: str) -> JSONResponse:
    """Apply a time-based allocation preset.

    Args:
        preset: Preset name (morning, afternoon, evening)

    Returns:
        Updated allocation
    """
    mgr = get_allocation()
    if not mgr:
        raise HTTPException(status_code=500, detail="Allocation manager not initialized")

    try:
        allocation = mgr.set_preset(preset)
        logger.info(f"Preset '{preset}' applied: {allocation}")
        return JSONResponse(
            {
                "status": "preset_applied",
                "preset": preset,
                "momentum": allocation["momentum"],
                "reversion": allocation["reversion"],
                "grid": allocation["grid"],
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/allocation/reset")
async def reset_allocation() -> JSONResponse:
    """Reset allocation to defaults.

    Returns:
        Default allocation
    """
    mgr = get_allocation()
    if not mgr:
        raise HTTPException(status_code=500, detail="Allocation manager not initialized")

    allocation = mgr.reset_to_default()
    logger.info("Allocation reset to defaults")
    return JSONResponse(
        {
            "status": "reset",
            "momentum": allocation["momentum"],
            "reversion": allocation["reversion"],
            "grid": allocation["grid"],
        }
    )


@app.get("/api/allocation/presets")
async def get_allocation_presets() -> JSONResponse:
    """Get all available allocation presets.

    Returns:
        Dict of preset name -> allocation weights
    """
    mgr = get_allocation()
    if not mgr:
        raise HTTPException(status_code=500, detail="Allocation manager not initialized")

    presets = mgr.get_presets()
    return JSONResponse({"presets": presets})


# === Root Endpoint ===


@app.get("/")
async def root():
    """Root endpoint - serve dashboard or JSON info."""
    frontend_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")

    return JSONResponse(
        {
            "name": "Crypto Daytrading Platform",
            "version": "1.0.0-phase1",
            "mode": settings.trading_mode,
            "status": "running",
            "docs": "/docs",
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
