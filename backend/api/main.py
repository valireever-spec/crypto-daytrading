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
from backend.exchange.binance_stream import init_stream_client, get_stream_client
from backend.exchange.paper_trading import init_paper_trading, get_paper_trading
from backend.analytics.signals import init_signal_generator, get_signal_generator
from backend.analytics.allocation import init_allocation, get_allocation
from backend.analytics.strategy_analytics import init_analytics, get_analytics

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Global state
websocket_task: asyncio.Task = None
stream_task: asyncio.Task = None
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

    # Initialize strategy analytics
    init_analytics(lookback_days=30)
    logger.info("Strategy analytics initialized")

    # Initialize Binance stream client (real prices)
    stream_client = await init_stream_client()
    logger.info("Binance stream client initialized")

    # Subscribe to price streams
    async def on_price_update(symbol: str, data: dict) -> None:
        """Handle price updates from Binance stream."""
        try:
            if "k" in data:  # Kline (candle)
                price = float(data["k"]["c"])
            elif "p" in data:  # Ticker
                price = float(data["p"])
            else:
                return

            logger.debug(f"{symbol}: ${price:.2f}")
        except Exception as e:
            logger.error(f"Error processing price update: {e}")

    # Subscribe to major pairs
    pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    for pair in pairs:
        stream_name = f"{pair.lower()}@kline_1m"
        stream_client.subscribe(stream_name, on_price_update)

    # Start stream in background
    global stream_task
    stream_task = asyncio.create_task(stream_client.connect())

    # Initialize old WebSocket (keeping for backward compatibility)
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

    # Disconnect stream client
    stream_client = get_stream_client()
    if stream_client:
        await stream_client.disconnect()

    # Cancel stream task
    if stream_task and not stream_task.done():
        stream_task.cancel()

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
    strategy_name: str = None,
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
        strategy_name=strategy_name,
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


# === Price Feed Endpoints (FR-010: Binance WebSocket) ===


@app.get("/api/prices")
async def get_live_prices() -> JSONResponse:
    """Get current live prices from Binance.

    Returns:
        Dict mapping symbol -> latest price
    """
    client = get_stream_client()
    if not client:
        raise HTTPException(status_code=500, detail="Stream client not initialized")

    prices = client.get_prices(["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    status = await client.get_connection_status()

    return JSONResponse(
        {
            "prices": prices,
            "stream_status": status,
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }
    )


@app.get("/api/price/{symbol}")
async def get_price(symbol: str) -> JSONResponse:
    """Get current price for a symbol.

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')

    Returns:
        Current price and update timestamp
    """
    client = get_stream_client()
    if not client:
        raise HTTPException(status_code=500, detail="Stream client not initialized")

    price = client.get_price(symbol.upper())
    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price data yet for {symbol}. Stream may still be connecting.",
        )

    return JSONResponse(
        {
            "symbol": symbol.upper(),
            "price": price,
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }
    )


@app.get("/api/stream/status")
async def get_stream_status() -> JSONResponse:
    """Get Binance WebSocket stream connection status.

    Returns:
        Stream status with connection state, subscriptions, cache size
    """
    client = get_stream_client()
    if not client:
        raise HTTPException(status_code=500, detail="Stream client not initialized")

    status = await client.get_connection_status()
    return JSONResponse(status)


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


# === Strategy Analytics Endpoints (FR-011: Per-Strategy Performance) ===


@app.post("/api/strategies/record-trade")
async def record_strategy_trade(
    strategy_name: str,
    pnl: float,
    quantity: float,
    entry_price: float,
    exit_price: float,
) -> JSONResponse:
    """Record a trade for a strategy.

    Args:
        strategy_name: Name of the strategy (e.g., 'momentum', 'reversion')
        pnl: Profit/loss amount
        quantity: Trade quantity
        entry_price: Entry price
        exit_price: Exit price

    Returns:
        Updated strategy statistics
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    analytics.record_trade(
        strategy_name=strategy_name,
        pnl=pnl,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
    )

    stats = analytics.get_strategy_stats(strategy_name)
    return JSONResponse(
        {
            "strategy": strategy_name,
            "total_trades": stats.total_trades,
            "winning_trades": stats.winning_trades,
            "losing_trades": stats.losing_trades,
            "win_rate_pct": round(stats.win_rate, 1),
            "total_pnl": stats.total_pnl,
            "avg_win": stats.avg_win,
            "avg_loss": stats.avg_loss,
            "expectancy": stats.expectancy,
        }
    )


@app.get("/api/strategies/stats/{strategy_name}")
async def get_strategy_stats(strategy_name: str) -> JSONResponse:
    """Get statistics for a specific strategy.

    Args:
        strategy_name: Name of the strategy

    Returns:
        Strategy statistics and performance metrics
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    stats = analytics.get_strategy_stats(strategy_name)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")

    # Handle infinity in profit_factor (JSON-safe)
    profit_factor = stats.profit_factor
    if profit_factor == float('inf'):
        profit_factor_value = 999.9
    else:
        profit_factor_value = round(profit_factor, 2)

    return JSONResponse(
        {
            "strategy": strategy_name,
            "total_trades": stats.total_trades,
            "winning_trades": stats.winning_trades,
            "losing_trades": stats.losing_trades,
            "win_rate_pct": round(stats.win_rate, 1),
            "total_pnl": stats.total_pnl,
            "avg_win": round(stats.avg_win, 2),
            "avg_loss": round(stats.avg_loss, 2),
            "largest_win": stats.largest_win,
            "largest_loss": stats.largest_loss,
            "consecutive_wins": stats.consecutive_wins,
            "consecutive_losses": stats.consecutive_losses,
            "expectancy": round(stats.expectancy, 2),
            "profit_factor": profit_factor_value,
            "last_trade_time": stats.last_trade_time.isoformat() if stats.last_trade_time else None,
        }
    )


@app.get("/api/strategies/all-stats")
async def get_all_strategy_stats() -> JSONResponse:
    """Get statistics for all strategies.

    Returns:
        Dictionary mapping strategy names to their statistics
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    all_stats = analytics.get_all_stats()
    strategies_data = {}

    for name, stats in all_stats.items():
        # Handle infinity in profit_factor (JSON-safe)
        profit_factor = stats.profit_factor
        if profit_factor == float('inf'):
            profit_factor_value = 999.9
        else:
            profit_factor_value = round(profit_factor, 2)

        strategies_data[name] = {
            "total_trades": stats.total_trades,
            "winning_trades": stats.winning_trades,
            "losing_trades": stats.losing_trades,
            "win_rate_pct": round(stats.win_rate, 1),
            "total_pnl": stats.total_pnl,
            "expectancy": round(stats.expectancy, 2),
            "profit_factor": profit_factor_value,
        }

    return JSONResponse(
        {
            "strategies": strategies_data,
            "count": len(all_stats),
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }
    )


@app.get("/api/strategies/best")
async def get_best_strategy() -> JSONResponse:
    """Get the best-performing strategy by win rate.

    Returns:
        Best strategy name and its stats, or null if insufficient data
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    best_name = analytics.get_best_strategy()
    if not best_name:
        return JSONResponse(
            {
                "best_strategy": None,
                "reason": "No strategies with sufficient trades (minimum 5)",
            }
        )

    stats = analytics.get_strategy_stats(best_name)
    return JSONResponse(
        {
            "best_strategy": best_name,
            "win_rate_pct": round(stats.win_rate, 1),
            "total_trades": stats.total_trades,
            "expectancy": round(stats.expectancy, 2),
            "total_pnl": stats.total_pnl,
        }
    )


@app.get("/api/strategies/allocation")
async def get_strategy_allocation() -> JSONResponse:
    """Get optimal capital allocation across strategies.

    Uses win rate and expectancy to weight allocation.

    Returns:
        Dictionary mapping strategy names to allocation percentages
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    allocation = analytics.calculate_allocation()

    return JSONResponse(
        {
            "allocation": {name: round(pct * 100, 1) for name, pct in allocation.items()},
            "total_pct": 100.0,
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }
    )


@app.get("/api/strategies/recent-stats/{strategy_name}")
async def get_recent_strategy_stats(strategy_name: str, days: int = 7) -> JSONResponse:
    """Get statistics for recent period only.

    Args:
        strategy_name: Name of the strategy
        days: Number of days to include (default 7)

    Returns:
        Strategy statistics for recent period
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    recent_stats = analytics.get_recent_stats(strategy_name, days=days)

    return JSONResponse(
        {
            "strategy": strategy_name,
            "period_days": days,
            "total_trades": recent_stats.total_trades,
            "winning_trades": recent_stats.winning_trades,
            "losing_trades": recent_stats.losing_trades,
            "win_rate_pct": round(recent_stats.win_rate, 1),
            "total_pnl": recent_stats.total_pnl,
            "expectancy": round(recent_stats.expectancy, 2),
        }
    )


@app.post("/api/strategies/reset/{strategy_name}")
async def reset_strategy(strategy_name: str) -> JSONResponse:
    """Reset statistics for a strategy.

    Args:
        strategy_name: Name of the strategy

    Returns:
        Confirmation of reset
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    analytics.reset_strategy(strategy_name)

    return JSONResponse(
        {
            "status": "reset",
            "strategy": strategy_name,
        }
    )


@app.post("/api/strategies/reset-all")
async def reset_all_strategies() -> JSONResponse:
    """Reset statistics for all strategies.

    Returns:
        Confirmation of reset
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=500, detail="Analytics not initialized")

    analytics.reset_all()

    return JSONResponse(
        {
            "status": "reset_all",
            "strategies_reset": len(analytics.strategies),
        }
    )


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
