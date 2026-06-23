"""FastAPI main application for crypto daytrading platform."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.exchange.binance_websocket import init_websocket, get_websocket
from backend.exchange.paper_trading import init_paper_trading, get_paper_trading

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Global state
websocket_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global websocket_task

    # Startup
    logger.info("Starting crypto daytrading platform...")

    # Initialize paper trading engine
    init_paper_trading(starting_capital=settings.initial_capital)
    logger.info(f"Paper trading engine initialized with {settings.initial_capital} EUR")

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


# === Root Endpoint ===


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint."""
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
