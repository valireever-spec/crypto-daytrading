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
from backend.analytics.backtest_engine import BacktestEngine
from backend.analytics.historical_data import init_historical_service, get_historical_service
from backend.analytics.regime_detector import get_regime_detector
from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader, TradingConfig
from backend.execution.smart_executor import init_smart_executor
from backend.analytics.tax_calculator import init_tax_calculator, Jurisdiction
from backend.api.routers.tax import router as tax_router
from backend.analytics.stock_analyzer import init_stock_optimizer
from backend.api.routers.stocks import router as stocks_router
from backend.api.routers.backup_analytics import router as backup_analytics_router
from backend.analytics.portfolio_analyzer import init_portfolio_analyzer
from backend.api.routers.risk_metrics import router as risk_metrics_router
from backend.api.routers.portfolio_allocation import router as portfolio_allocation_router
from backend.api.routers.backtest_allocation import router as backtest_allocation_router
from backend.api.routers.attribution import router as attribution_router

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Global state
websocket_task: asyncio.Task = None
stream_task: asyncio.Task = None
simulator_task: asyncio.Task = None
autonomous_trader_task: asyncio.Task = None
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
    global websocket_task, stream_task, simulator_task, autonomous_trader_task

    # Startup
    logger.info("Starting crypto daytrading platform...")

    # Initialize paper trading engine
    init_paper_trading(starting_capital=settings.initial_capital)
    logger.info(f"Paper trading engine initialized with {settings.initial_capital} EUR")

    # Initialize signal generator
    init_signal_generator()
    logger.info("Signal generator initialized")

    # Initialize portfolio analyzer (for backup analytics)
    init_portfolio_analyzer()
    logger.info("Portfolio analyzer initialized")

    # Initialize allocation manager
    init_allocation()
    logger.info("Allocation manager initialized")

    # Initialize strategy analytics
    init_analytics(lookback_days=30)
    logger.info("Strategy analytics initialized")

    # Initialize historical data service
    init_historical_service()
    logger.info("Historical data service initialized")

    # Initialize regime detector
    init_regime_detector()
    logger.info("Regime detector initialized")

    # Initialize smart executor for trade validation
    init_smart_executor()
    logger.info("Smart executor initialized")

    # Initialize tax calculator (default to Germany)
    init_tax_calculator(Jurisdiction.GERMANY)
    logger.info("Tax calculator initialized (Germany)")

    # Initialize stock trading optimizer (default to Germany)
    init_stock_optimizer("DE")
    logger.info("Stock trading optimizer initialized (Germany)")

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

    # Initialize price simulator (fallback when Binance doesn't send data)
    from backend.exchange.price_simulator import init_simulator
    simulator = init_simulator()

    # Start simulator to inject prices if WebSocket doesn't receive them
    async def inject_simulated_prices():
        """Continuously inject simulated prices into stream cache (fallback only)."""
        fallback_logged = False
        while True:
            try:
                stream_client = get_stream_client()
                if stream_client:
                    # Only inject if WebSocket is connected but hasn't received real prices (timeout)
                    if stream_client.is_connected and len(stream_client.price_cache) == 0:
                        if not fallback_logged:
                            logger.warning("Binance WebSocket connected but no price data. Using fallback simulator...")
                            fallback_logged = True
                        simulator.update()
                        prices = simulator.get_prices()
                        from datetime import datetime
                        for symbol, price in prices.items():
                            stream_client.price_cache[symbol] = price
                            stream_client.last_update[symbol] = datetime.utcnow()
                        logger.debug(f"Injected simulated prices (fallback)")
                    elif len(stream_client.price_cache) > 0:
                        # Real Binance data is flowing, reset fallback flag
                        fallback_logged = False
                await asyncio.sleep(3)  # Update every 3 seconds
            except Exception as e:
                logger.error(f"Simulator injection error: {e}")
                await asyncio.sleep(5)

    simulator_task = asyncio.create_task(inject_simulated_prices())

    # Initialize and start autonomous trader
    global autonomous_trader_task
    trader_config = TradingConfig(
        enabled=True,
        entry_threshold=60.0,
        exit_profit_target=0.03,
        exit_stop_loss=0.02,
        position_size_pct=0.10,
        max_positions=5,
        symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    )
    autonomous_trader = init_autonomous_trader(trader_config)
    autonomous_trader_task = asyncio.create_task(autonomous_trader.start())
    logger.info("Autonomous trader initialized and started")

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

    # Cancel simulator task
    if simulator_task and not simulator_task.done():
        simulator_task.cancel()

    # Stop autonomous trader
    if autonomous_trader_task and not autonomous_trader_task.done():
        trader = get_autonomous_trader()
        if trader:
            await trader.stop()
        autonomous_trader_task.cancel()

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

# Include routers
app.include_router(tax_router)
app.include_router(stocks_router)
app.include_router(backup_analytics_router)  # Backup analytics (standby mode)
app.include_router(risk_metrics_router)  # Risk metrics API (Phase 321)
app.include_router(portfolio_allocation_router)  # Portfolio allocation optimizer (Phase 322)
app.include_router(backtest_allocation_router)  # Portfolio backtesting (Phase 323)
app.include_router(attribution_router)  # Performance attribution (Phase 324)

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


# === Historical Backtesting Endpoints (Phase 2 Week 6) ===


@app.post("/api/backtest/run")
async def run_backtest(
    symbol: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
) -> JSONResponse:
    """Run backtest for a strategy on historical data.

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT', 'AAPL')
        strategy_name: Name of strategy to backtest
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_capital: Starting balance (default 10000)

    Returns:
        Backtest results with performance metrics
    """
    from datetime import datetime

    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start >= end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    try:
        # Get historical data
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol} in date range"
            )

        # Define strategy functions for backtesting
        def momentum_strategy(df: pd.DataFrame) -> float:
            """Simple momentum strategy - buy on RSI > 70, sell on RSI < 30."""
            if len(df) < 14:
                return 0.0
            prices = df["Close"]
            # Calculate RSI
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            # Return position (0.5 = 50% invested)
            return 0.5 if current_rsi > 70 else (0.0 if current_rsi < 30 else 0.25)

        def reversion_strategy(df: pd.DataFrame) -> float:
            """Simple reversion strategy - buy on RSI < 30, sell on RSI > 70."""
            if len(df) < 14:
                return 0.0
            prices = df["Close"]
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            return 0.5 if current_rsi < 30 else (0.0 if current_rsi > 70 else 0.25)

        def grid_strategy(df: pd.DataFrame) -> float:
            """Simple grid strategy - consistent 25% investment."""
            return 0.25

        # Get strategy function
        strategies = {
            "momentum": momentum_strategy,
            "reversion": reversion_strategy,
            "grid": grid_strategy,
        }

        if strategy_name.lower() not in strategies:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_name}")

        strategy_func = strategies[strategy_name.lower()]

        # Run backtest
        engine = BacktestEngine(initial_capital=initial_capital)
        metrics = engine.backtest_strategy(ohlcv, strategy_func, symbol, strategy_name)

        return JSONResponse(
            {
                "strategy": strategy_name,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "ending_capital": round(metrics.ending_capital, 2),
                "total_pnl": round(metrics.total_pnl, 2),
                "total_pnl_pct": round(metrics.total_pnl_pct, 2),
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "win_rate_pct": round(metrics.win_rate_pct, 1),
                "avg_win": round(metrics.avg_win, 2),
                "avg_loss": round(metrics.avg_loss, 2),
                "expectancy": round(metrics.expectancy, 2),
                "profit_factor": round(metrics.profit_factor, 2),
                "sharpe_ratio": round(metrics.sharpe_ratio, 2),
                "sortino_ratio": round(metrics.sortino_ratio, 2),
                "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
                "recovery_factor": round(metrics.recovery_factor, 2),
                "avg_holding_days": round(metrics.avg_holding_days, 1),
                "largest_win": round(metrics.largest_win, 2),
                "largest_loss": round(metrics.largest_loss, 2),
                "consecutive_wins": metrics.consecutive_wins,
                "max_consecutive_losses": metrics.max_consecutive_losses,
            }
        )

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@app.get("/api/backtest/data-range/{symbol}")
async def get_backtest_data_range(symbol: str) -> JSONResponse:
    """Get available data date range for backtesting.

    Args:
        symbol: Trading symbol

    Returns:
        Available start and end dates
    """
    hist_service = get_historical_service()
    if not hist_service:
        raise HTTPException(status_code=500, detail="Historical data service not initialized")

    date_range = hist_service.get_data_range(symbol)

    if date_range is None:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data available for {symbol}"
        )

    start_date, end_date = date_range
    return JSONResponse(
        {
            "symbol": symbol,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_available": (end_date - start_date).days,
        }
    )


@app.post("/api/backtest/compare")
async def compare_strategies(
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
) -> JSONResponse:
    """Compare all strategies on historical data.

    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_capital: Starting balance

    Returns:
        Comparison of all strategies
    """
    from datetime import datetime

    try:
        # Parse dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD")

        # Run backtest for each strategy
        strategies = ["momentum", "reversion", "grid"]
        results = {}

        for strategy in strategies:
            try:
                response = await run_backtest(symbol, strategy, start_date, end_date, initial_capital)
                results[strategy] = response.body
            except HTTPException:
                results[strategy] = {"error": "Backtest failed"}

        return JSONResponse(
            {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "strategies": results,
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")


# === Market Regime Detection Endpoints (Phase 2 Week 7) ===


@app.post("/api/regime/detect")
async def detect_market_regime(symbol: str) -> JSONResponse:
    """Detect current market regime for a symbol.

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

        from datetime import datetime, timedelta
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

        metrics = detector.detect_regime(ohlcv, symbol=symbol)

        return JSONResponse(
            {
                "symbol": symbol,
                "regime": metrics.regime,
                "confidence": round(metrics.confidence, 2),
                "volatility_pct": round(metrics.volatility_pct, 2),
                "trend_strength": round(metrics.trend_strength, 2),
                "support_level": round(metrics.support_level, 2),
                "resistance_level": round(metrics.resistance_level, 2),
                "ma_20": round(metrics.ma_20, 2),
                "ma_50": round(metrics.ma_50, 2),
                "rsi": round(metrics.rsi, 1),
                "atr": round(metrics.atr, 2),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection error: {e}")
        raise HTTPException(status_code=500, detail=f"Regime detection failed: {str(e)}")


@app.get("/api/regime/trading-rules/{regime}")
async def get_regime_trading_rules(regime: str) -> JSONResponse:
    """Get recommended trading rules for a market regime.

    Args:
        regime: Market regime (BULL, BEAR, SIDEWAYS, VOLATILE)

    Returns:
        Position sizing, stop loss, take profit, and recommended strategies
    """
    valid_regimes = ["BULL", "BEAR", "SIDEWAYS", "VOLATILE"]
    if regime.upper() not in valid_regimes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid regime. Must be one of: {', '.join(valid_regimes)}"
        )

    try:
        detector = get_regime_detector()
        if not detector:
            raise HTTPException(status_code=500, detail="Regime detector not initialized")

        rules = detector.get_regime_trading_rules(regime.upper())

        return JSONResponse(
            {
                "regime": regime.upper(),
                "position_size_multiplier": rules["position_size_multiplier"],
                "stop_loss_pct": rules["stop_loss_pct"],
                "take_profit_pct": rules["take_profit_pct"],
                "recommended_strategies": rules["recommended_strategies"],
            }
        )

    except Exception as e:
        logger.error(f"Trading rules error: {e}")
        raise HTTPException(status_code=500, detail=f"Trading rules failed: {str(e)}")


@app.post("/api/regime/strategy-impact")
async def analyze_regime_strategy_impact(symbol: str) -> JSONResponse:
    """Analyze how current regime impacts each strategy's performance.

    Args:
        symbol: Trading symbol

    Returns:
        Regime-specific adjustment factors for each strategy
    """
    try:
        # Detect current regime
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=60)

        ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol}"
            )

        detector = get_regime_detector()
        if not detector:
            raise HTTPException(status_code=500, detail="Regime detector not initialized")

        metrics = detector.detect_regime(ohlcv, symbol=symbol)

        # Get strategy adjustments for this regime
        adjustments = {
            "momentum": detector._get_strategy_adjustment("momentum", metrics.regime),
            "reversion": detector._get_strategy_adjustment("reversion", metrics.regime),
            "grid": detector._get_strategy_adjustment("grid", metrics.regime),
        }

        return JSONResponse(
            {
                "symbol": symbol,
                "current_regime": metrics.regime,
                "confidence": round(metrics.confidence, 2),
                "strategy_adjustments": {
                    "momentum": round(adjustments["momentum"], 2),
                    "reversion": round(adjustments["reversion"], 2),
                    "grid": round(adjustments["grid"], 2),
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Strategy impact analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Strategy impact analysis failed: {str(e)}")


# === Smart Trading Gateway Endpoints (Phase 2 Week 8) ===


@app.post("/api/trading/smart-gateway")
async def smart_trading_entry(
    symbol: str,
    quantity: float,
    current_price: float,
    min_confidence: float = 0.6,
) -> JSONResponse:
    """Smart entry decision with regime-aware execution.

    Automatically determines the best strategy to use and position sizing
    based on current market regime and confidence level.

    Args:
        symbol: Trading symbol
        quantity: Requested quantity
        current_price: Current market price
        min_confidence: Minimum regime confidence to execute (0.0-1.0)

    Returns:
        Execution decision with recommended strategy and position sizing
    """
    try:
        # Detect current regime
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=60)

        ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol}"
            )

        detector = get_regime_detector()
        if not detector:
            raise HTTPException(status_code=500, detail="Regime detector not initialized")

        metrics = detector.detect_regime(ohlcv, symbol=symbol)

        # Check confidence threshold
        if metrics.confidence < min_confidence:
            return JSONResponse(
                {
                    "decision": "WAIT",
                    "reason": f"Regime confidence {metrics.confidence:.0%} below threshold {min_confidence:.0%}",
                    "current_regime": metrics.regime,
                    "confidence": round(metrics.confidence, 2),
                }
            )

        # Get trading rules for this regime
        rules = detector.get_regime_trading_rules(metrics.regime)

        # Calculate adjusted position size
        adjusted_quantity = quantity * rules["position_size_multiplier"]

        # Determine best strategy for this regime
        best_strategy = rules["recommended_strategies"][0] if rules["recommended_strategies"] else "grid"

        return JSONResponse(
            {
                "decision": "EXECUTE",
                "symbol": symbol,
                "current_regime": metrics.regime,
                "regime_confidence": round(metrics.confidence, 2),
                "recommended_strategy": best_strategy,
                "original_quantity": quantity,
                "adjusted_quantity": round(adjusted_quantity, 4),
                "adjustment_multiplier": round(rules["position_size_multiplier"], 2),
                "stop_loss_pct": rules["stop_loss_pct"],
                "take_profit_pct": rules["take_profit_pct"],
                "entry_price": round(current_price, 2),
                "stop_loss_price": round(current_price * (1 - rules["stop_loss_pct"] / 100), 2),
                "take_profit_price": round(current_price * (1 + rules["take_profit_pct"] / 100), 2),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart gateway error: {e}")
        raise HTTPException(status_code=500, detail=f"Smart gateway failed: {str(e)}")


@app.get("/api/trading/smart-status")
async def get_smart_trading_status(symbol: str = "BTCUSDT") -> JSONResponse:
    """Get current market regime and smart trading recommendations.

    Args:
        symbol: Trading symbol (default BTCUSDT)

    Returns:
        Current regime, confidence, and recommended strategies
    """
    try:
        # Detect current regime
        hist_service = get_historical_service()
        if not hist_service:
            raise HTTPException(status_code=500, detail="Historical data service not initialized")

        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=60)

        ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
        if ohlcv is None or ohlcv.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol}"
            )

        detector = get_regime_detector()
        if not detector:
            raise HTTPException(status_code=500, detail="Regime detector not initialized")

        metrics = detector.detect_regime(ohlcv, symbol=symbol)
        rules = detector.get_regime_trading_rules(metrics.regime)

        return JSONResponse(
            {
                "symbol": symbol,
                "current_regime": metrics.regime,
                "confidence": round(metrics.confidence, 2),
                "volatility_pct": round(metrics.volatility_pct, 2),
                "trend_strength": round(metrics.trend_strength, 2),
                "rsi": round(metrics.rsi, 1),
                "recommended_strategies": rules["recommended_strategies"],
                "position_multiplier": rules["position_size_multiplier"],
                "risk_settings": {
                    "stop_loss_pct": rules["stop_loss_pct"],
                    "take_profit_pct": rules["take_profit_pct"],
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Smart status error: {e}")
        raise HTTPException(status_code=500, detail=f"Smart status failed: {str(e)}")


# === Autonomous Trading Endpoints ===


@app.get("/api/autonomous/status")
async def get_autonomous_status():
    """Get autonomous trader status."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")
    return JSONResponse(trader.get_status())


@app.post("/api/autonomous/start")
async def start_autonomous_trading():
    """Start autonomous trading."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")
    if trader.running:
        return JSONResponse({"status": "already_running"})
    trader.config.enabled = True
    logger.info("Autonomous trading enabled")
    return JSONResponse({"status": "started", "message": "Autonomous trading is now active"})


@app.post("/api/autonomous/stop")
async def stop_autonomous_trading():
    """Stop autonomous trading."""
    trader = get_autonomous_trader()
    if not trader:
        raise HTTPException(status_code=500, detail="Autonomous trader not initialized")
    trader.config.enabled = False
    logger.info("Autonomous trading disabled")
    return JSONResponse({"status": "stopped", "message": "Autonomous trading is now paused"})


@app.get("/api/autonomous/config")
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


@app.get("/api/autonomous/trades")
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


# === Root Endpoint ===


@app.get("/")
async def root():
    """Root endpoint - serve unified dashboard."""
    # Try unified dashboard first
    unified_path = Path(__file__).parent.parent.parent / "frontend" / "unified-dashboard.html"
    if unified_path.exists():
        return FileResponse(unified_path, media_type="text/html")

    # Fallback to index.html
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


@app.get("/dashboard")
async def dashboard():
    """Dashboard endpoint - serve unified dashboard."""
    unified_path = Path(__file__).parent.parent.parent / "frontend" / "unified-dashboard.html"
    if unified_path.exists():
        return FileResponse(unified_path, media_type="text/html")

    raise HTTPException(status_code=404, detail="Dashboard not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
