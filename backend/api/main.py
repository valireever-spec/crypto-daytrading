"""FastAPI main application for crypto daytrading platform."""

import logging
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.core.structured_logging import setup_structured_logging
from backend.core.metrics import get_metrics

# Setup structured logging
setup_structured_logging()
logger = logging.getLogger(__name__)

# Import lifecycle management
from backend.api.lifecycle import lifespan
from backend.api.middleware import LogAndMetricsMiddleware

# Import all routers
from backend.api.routers.tax import router as tax_router
from backend.api.routers.autonomous import router as autonomous_router
from backend.api.routers.monitoring import router as monitoring_router
from backend.api.routers.risk_management import router as risk_router
from backend.api.routers.multi_asset import router as multi_asset_router
from backend.api.routers.failover import router as failover_router
from backend.api.routers.stocks import router as stocks_router
from backend.api.routers.backup_analytics import router as backup_analytics_router
from backend.api.routers.risk_metrics import router as risk_metrics_router
from backend.api.routers.portfolio_allocation import router as portfolio_allocation_router
from backend.api.routers.backtest_allocation import router as backtest_allocation_router
from backend.api.routers.attribution import router as attribution_router
from backend.api.routers.recommendation import router as recommendation_router
from backend.api.routers.recommendation_advanced import router as recommendation_advanced_router
from backend.api.routers.rebalancing import router as rebalancing_router
from backend.api.routers.production_hardening import router as production_hardening_router
from backend.api.routers.learning_feedback import router as learning_feedback_router
from backend.api.routers.learning_automation import router as learning_automation_router
from backend.api.routers.regime import router as regime_router
from backend.api.routers.user import router as user_router
from backend.api.routers.portfolio import router as portfolio_router
from backend.api.routers.redundancy import router as redundancy_router
from backend.api.routers.ha_postgres import router as ha_postgres_router
from backend.api.routers.dashboard_wrapper import router as dashboard_wrapper_router
from backend.api.routers.trading_control import router as trading_control_router
from backend.api.routers.dashboard_integration import router as dashboard_integration_router
from backend.api.routers.allocation_management import router as allocation_management_router

# Create FastAPI application
app = FastAPI(
    title="Crypto Daytrading Platform",
    description="Autonomous trading system with HA failover",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(LogAndMetricsMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# SECURITY HEADERS & STATIC FILES
# ============================================================================

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    return response

# Serve favicon (fixes OpaqueResponseBlocking error)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", status_code=204, media_type="image/x-icon")

# Register all routers
routers = [
    tax_router,
    autonomous_router,
    monitoring_router,
    risk_router,
    multi_asset_router,
    failover_router,
    stocks_router,
    backup_analytics_router,
    risk_metrics_router,
    portfolio_allocation_router,
    backtest_allocation_router,
    attribution_router,
    recommendation_router,
    recommendation_advanced_router,
    rebalancing_router,
    production_hardening_router,
    learning_feedback_router,
    learning_automation_router,
    regime_router,
    user_router,
    portfolio_router,
    redundancy_router,
    ha_postgres_router,
    dashboard_wrapper_router,
    trading_control_router,
    dashboard_integration_router,
    allocation_management_router,
]

for router in routers:
    app.include_router(router)


# ============================================================================
# CORE API ENDPOINTS
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "Crypto daytrading platform online ✅"}


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """Check system health."""
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.circuit_breaker import get_circuit_breaker

        engine = get_paper_trading()
        circuit_breaker = get_circuit_breaker()

        if not engine:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "Paper trading engine not ready"},
            )

        return JSONResponse(
            {
                "status": "healthy",
                "circuit_breaker": circuit_breaker.get_status_report(),
                "account": engine.get_account_state(),
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


@app.get("/api/paper/account")
async def get_paper_account() -> JSONResponse:
    """Get paper trading account state."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialized")

        return JSONResponse(engine.get_account_state())
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper/positions")
async def get_paper_positions() -> JSONResponse:
    """Get open positions."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialized")

        positions = engine.get_positions()
        return JSONResponse(positions)
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper/trades")
async def get_paper_trades(limit: int = 100) -> JSONResponse:
    """Get trade history."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialized")

        trades = engine.get_trades(limit=limit)
        return JSONResponse(trades)
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper/reset")
async def reset_paper_trading(capital: float = None) -> JSONResponse:
    """Reset paper trading with optional custom capital (DANGEROUS - for testing only)."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialized")

        if capital and capital > 0:
            engine.starting_capital = capital
            engine.cash = capital
            logger.warning(f"⚠️ Paper trading capital set to: €{capital:.2f}")
        else:
            engine.reset()
            logger.warning("⚠️ Paper trading reset by API call")
            capital = engine.starting_capital

        return JSONResponse({"status": "reset", "capital": capital, "account": engine.get_account_state()})
    except Exception as e:
        logger.error(f"Error resetting paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper/status")
async def get_paper_status() -> JSONResponse:
    """Get paper trading status including autonomous trader state."""
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.trading.autonomous_trader import get_autonomous_trader

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=503, detail="Paper trading engine not initialized")

        trader = get_autonomous_trader()
        trader_status = trader.get_status() if trader else {"status": "not_initialized"}

        return JSONResponse(
            {
                "account": engine.get_account_state(),
                "positions": engine.get_positions(),
                "trades_count": len(engine.get_trades()),
                "autonomous_trader": trader_status,
            }
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_current_metrics() -> JSONResponse:
    """Get current system metrics."""
    try:
        metrics = get_metrics()
        return JSONResponse(metrics.to_dict())
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ha/heartbeat")
async def receive_heartbeat(data: dict = None) -> JSONResponse:
    """BACKUP: Receive heartbeat from PRIMARY.

    Heartbeat proves PRIMARY is alive and tunnel is healthy.
    Used for explicit failover detection (not just HTTP checks).
    """
    try:
        machine_id = os.getenv("MACHINE_ID", "main")
        if machine_id != "backup":
            return JSONResponse(
                status_code=403,
                content={"error": "This endpoint is for BACKUP only"}
            )

        if not data:
            return JSONResponse(status_code=400, content={"error": "Heartbeat data required"})

        # Get heartbeat monitor from global state
        from backend.core.heartbeat import get_heartbeat_monitor
        monitor = get_heartbeat_monitor()
        if monitor:
            monitor.on_heartbeat_received(data)

        return JSONResponse({
            "status": "received",
            "timestamp": datetime.now().isoformat(),
            "message": "Heartbeat recorded"
        })

    except Exception as e:
        logger.error(f"Heartbeat receive error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/ha/heartbeat-status")
async def get_heartbeat_status() -> JSONResponse:
    """Get heartbeat monitor status (BACKUP only)."""
    try:
        machine_id = os.getenv("MACHINE_ID", "main")
        from backend.core.heartbeat import get_heartbeat_monitor, get_heartbeat_sender

        if machine_id == "backup":
            # BACKUP: show monitor status
            monitor = get_heartbeat_monitor()
            return JSONResponse(monitor.get_status() if monitor else {"status": "not_initialized"})
        else:
            # PRIMARY: show sender status
            sender = get_heartbeat_sender()
            return JSONResponse(sender.get_status() if sender else {"status": "not_initialized"})

    except Exception as e:
        logger.error(f"Heartbeat status error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/ha/sync-from-primary")
async def sync_state_from_primary(state: dict = None) -> JSONResponse:
    """BACKUP: Receive state sync from PRIMARY."""
    try:
        machine_id = os.getenv("MACHINE_ID", "main")
        if machine_id != "backup":
            return JSONResponse(
                status_code=403,
                content={"error": "This endpoint is for BACKUP only"}
            )

        if not state:
            return JSONResponse(status_code=400, content={"error": "State required"})

        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.database import get_database

        engine = get_paper_trading()
        db = get_database()

        # Apply state: cash, positions, config
        if "cash" in state:
            engine.cash = state["cash"]

        if "total_pnl" in state:
            engine.total_pnl = state["total_pnl"]

        # Sync positions (both database and in-memory)
        if "positions" in state:
            db.clear_all_positions()
            engine.positions.clear()  # Clear in-memory positions too!

            for pos in state["positions"]:
                try:
                    entry_time_str = pos.get("entry_time")
                    if isinstance(entry_time_str, str):
                        # Parse ISO format string to datetime
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                    else:
                        entry_time = entry_time_str or datetime.utcnow()

                    # Insert into database
                    db.insert_position(
                        symbol=pos["symbol"],
                        quantity=pos["quantity"],
                        entry_price=pos["entry_price"],
                        entry_time=entry_time
                    )

                    # Also load into in-memory cache
                    from backend.exchange.paper_trading import Position
                    engine.positions[pos["symbol"]] = Position(
                        symbol=pos["symbol"],
                        side="LONG",  # Synced positions are always long (buy)
                        quantity=pos["quantity"],
                        entry_price=pos["entry_price"],
                        entry_time=entry_time,
                        current_price=pos.get("current_price", pos["entry_price"])
                    )
                except Exception as pos_err:
                    logger.warning(f"Failed to sync position {pos.get('symbol')}: {pos_err}")

        logger.info(f"✅ BACKUP synced: cash={state.get('cash')}, positions={len(state.get('positions', []))} (in-memory + DB)")
        return JSONResponse({"status": "synced", "timestamp": datetime.now().isoformat()})

    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/ha/status")
async def get_ha_status() -> JSONResponse:
    """Get HA status (PRIMARY or BACKUP, health)."""
    try:
        machine_id = os.getenv("MACHINE_ID", "main")
        primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")

        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()

        # Check if PRIMARY is reachable (fast check, fail quickly)
        primary_healthy = False
        try:
            import httpx
            resp = httpx.get(f"{primary_url}/api/health", timeout=0.5)
            primary_healthy = resp.status_code == 200
        except:
            primary_healthy = False

        return JSONResponse({
            "machine_id": machine_id,
            "role": "PRIMARY" if machine_id == "main" else "BACKUP",
            "primary_healthy": primary_healthy,
            "account": engine.get_account_state() if engine else None,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"HA status error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/ha/split-brain-status")
async def get_split_brain_status() -> JSONResponse:
    """Get split-brain detection status (Phase 2 HA Hardening)."""
    try:
        from backend.failover.ha_wrapper import get_ha_wrapper

        wrapper = get_ha_wrapper()
        if not wrapper:
            return JSONResponse(
                status_code=500,
                content={"error": "HA wrapper not initialized"}
            )

        status = wrapper.split_brain_prevention.get_status()
        can_trade = wrapper.split_brain_prevention.can_trade()

        return JSONResponse({
            "status": "ok",
            "machine_id": status["machine_id"],
            "current_state": status["current_state"],
            "is_split_brain": status["is_split_brain"],
            "can_trade": can_trade,
            "failover_status": status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Split-brain status error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# Mount static files if they exist
static_path = Path(__file__).parent.parent.parent / "frontend"
if static_path.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    except Exception as e:
        logger.warning(f"Could not mount static files: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
