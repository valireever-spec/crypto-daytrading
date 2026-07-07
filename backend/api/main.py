"""FastAPI main application for crypto daytrading platform."""

import logging
import os
from pathlib import Path
from datetime import datetime

# CRITICAL: Load .env FIRST before any imports that use os.getenv()
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                if key and key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

from typing import Optional  # noqa: E402

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, FileResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402

from backend.api.error_handlers import (
    APIError,
    api_error_handler,
    validation_error_handler,
    general_exception_handler,
)
from backend.core.structured_logging import setup_structured_logging
from backend.core.metrics import get_metrics

# Setup structured logging
setup_structured_logging()
logger = logging.getLogger(__name__)

# Import lifecycle management
from backend.api.lifecycle import lifespan
from backend.api.middleware import LogAndMetricsMiddleware
from backend.api.middleware_enhanced import EnhancedLoggingMiddleware

# Import all routers
from backend.api.routers.tax import router as tax_router
from backend.api.routers.autonomous import router as autonomous_router
from backend.api.routers.emergency import router as emergency_router
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
from backend.api.routers.config import router as config_router
from backend.api.routers.metrics import router as metrics_router
from backend.api.routers.trade_verification import router as verification_router
from backend.api.routers.parameter_monitoring import router as parameter_monitoring_router
from backend.api.routers.health import router as health_router
from backend.api.routers.performance_dashboard import router as performance_router

# Create FastAPI application with OpenAPI documentation
app = FastAPI(
    title="Crypto Daytrading Platform",
    description="""
    Autonomous crypto trading system with high-availability failover.

    ## Features
    - 24/7 automated trading on Binance
    - Dual-machine failover architecture
    - Real-time portfolio monitoring
    - Multiple trading strategies
    - Circuit breaker risk protection

    ## API Categories
    - **Health**: System status and readiness checks
    - **Trading**: Order execution and position management
    - **Analytics**: Performance metrics and backtesting
    - **Monitoring**: Real-time system metrics
    - **Admin**: Configuration and control
    """,
    version="1.0.0",
    contact={
        "name": "Trading Team",
        "email": "trading@example.com",
        "url": "https://example.com/support",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Add middleware (order matters - registered in reverse order)
app.add_middleware(EnhancedLoggingMiddleware)
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

# ============================================================================
# ERROR HANDLING
# ============================================================================

# Register structured error handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Register all routers
routers = [
    tax_router,
    autonomous_router,
    emergency_router,
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
    config_router,
    metrics_router,
    verification_router,
    parameter_monitoring_router,
    health_router,
    performance_router,
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
    """Check system health with circuit breaker and WebSocket status.

    Returns:
        - 200: Healthy (all systems OK)
        - 503: Degraded or unhealthy
    """
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.circuit_breaker_v2 import get_circuit_breaker
        from backend.exchange.binance_stream import get_stream_client

        engine = get_paper_trading()
        circuit_breaker = get_circuit_breaker()
        stream_client = get_stream_client()

        if not engine:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "Paper trading engine not ready"},
            )

        # Get statuses
        cb_status = circuit_breaker.get_status()
        ws_health = stream_client.check_health() if stream_client else None
        account = engine.get_account_state()

        # Determine overall health (unified stream client)
        ws_healthy = (
            ws_health and
            ws_health.get("overall_healthy", False)
        )

        trading_allowed = cb_status["trading_allowed"]

        # Status mapping
        if not ws_healthy or not trading_allowed:
            http_status = 503 if cb_status["state"] == "OPEN" else 200
        else:
            http_status = 200

        return JSONResponse(
            status_code=http_status,
            content={
                "status": "healthy" if (ws_healthy and trading_allowed) else
                         "degraded" if trading_allowed else "unhealthy",
                "circuit_breaker": cb_status,
                "websocket_health": ws_health,
                "account": account,
                "trading_allowed": trading_allowed,
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/api/test-telegram")
async def test_telegram() -> JSONResponse:
    """Test Telegram configuration by sending a test message."""
    try:
        from backend.core.alerting import get_alert_manager

        alert_mgr = get_alert_manager()
        result = await alert_mgr.test_telegram()

        if result.get("success"):
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Test Telegram message sent"}
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "error": result.get("error", "Unknown error")}
            )
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


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


@app.get("/transactions", include_in_schema=False)
async def get_transactions_page() -> FileResponse:
    """Serve transactions dashboard HTML page."""
    frontend_path = Path(__file__).parent.parent.parent / "frontend"
    transactions_file = frontend_path / "transactions.html"

    if not transactions_file.exists():
        raise HTTPException(status_code=404, detail="Transactions page not found")

    return FileResponse(path=transactions_file, media_type="text/html")


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
        machine_id = os.getenv("MACHINE_ID", "primary").lower()
        # Accept heartbeats on BACKUP machine only
        if machine_id not in ["backup", "secondary"]:
            return JSONResponse(
                status_code=403,
                content={"error": f"This endpoint is for BACKUP only (machine_id={machine_id})"}
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
        machine_id = os.getenv("MACHINE_ID", "primary")
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
        machine_id = os.getenv("MACHINE_ID", "primary")
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
        if engine is None:
            return JSONResponse(
                status_code=500,
                content={"error": "Paper trading engine not initialized"}
            )

        db = get_database()

        # PHASE 2: Atomic sync - all-or-nothing (rollback on any failure)
        try:
            # Validate and prepare state BEFORE any database changes
            synced_positions = []
            if "positions" in state:
                for pos in state["positions"]:
                    entry_time_str = pos.get("entry_time")
                    if isinstance(entry_time_str, str):
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                    else:
                        entry_time = entry_time_str or datetime.utcnow()

                    synced_positions.append({
                        "symbol": pos["symbol"],
                        "quantity": pos["quantity"],
                        "entry_price": pos["entry_price"],
                        "entry_time": entry_time,
                        "current_price": pos.get("current_price", pos["entry_price"])
                    })

            # Atomic transaction: commit all or nothing
            conn = None
            try:
                import sqlite3
                # BACKUP-safe sync: Skip database writes (avoid SQLite locking with PRIMARY)
                # BACKUP only needs in-memory state synced; PRIMARY maintains persistent DB
                machine_id = os.getenv("MACHINE_ID", "primary")

                # Update in-memory cache (works on PRIMARY or BACKUP)
                engine.positions.clear()
                from backend.exchange.paper_trading import Position
                for pos in synced_positions:
                    engine.positions[pos["symbol"]] = Position(
                        symbol=pos["symbol"],
                        side="LONG",
                        quantity=pos["quantity"],
                        entry_price=pos["entry_price"],
                        entry_time=pos["entry_time"],
                        current_price=pos["current_price"]
                    )

                # Only write to database on PRIMARY (avoids SQLite locking on BACKUP)
                if machine_id == "main":
                    conn = sqlite3.connect(db.db_path)
                    try:
                        conn.execute("BEGIN TRANSACTION")
                        # Clear positions inside transaction (can be rolled back)
                        conn.execute("DELETE FROM open_positions WHERE status = 'OPEN'")
                        # Insert all positions inside transaction
                        for pos in synced_positions:
                            db.insert_position(
                                symbol=pos["symbol"],
                                quantity=pos["quantity"],
                                entry_price=pos["entry_price"],
                                entry_time=pos["entry_time"]
                            )
                        # Commit transaction if we got here (no errors)
                        conn.commit()
                        logger.debug("✅ Position sync committed to DB (PRIMARY only)")
                    except Exception as tx_err:
                        conn.rollback()
                        logger.error(f"Sync transaction rolled back: {tx_err}")
                        raise tx_err
                    finally:
                        conn.close()
                else:
                    logger.debug("🔄 Skipping DB write on BACKUP (in-memory state synced)")

            except Exception as tx_err:
                logger.error(f"Sync failed: {tx_err}")
                raise tx_err

            # Update cash and P&L (atomic, simple assignments)
            if "cash" in state:
                engine.cash = state["cash"]
            if "total_pnl" in state:
                engine.total_pnl = state["total_pnl"]

            # Sync configuration from PRIMARY (critical blocker #2)
            if "config" in state:
                from backend.core.runtime_config import get_config_manager
                config_manager = get_config_manager()
                config_updates = state["config"]

                # Update config with values from PRIMARY
                if config_manager.update_config(config_updates):
                    config_manager.save_config()
                    logger.info(
                        f"♻️  Configuration synced from PRIMARY: "
                        f"entry_threshold={config_updates.get('entry_threshold')}, "
                        f"exit_profit={config_updates.get('exit_profit_target'):.3f}, "
                        f"enabled={config_updates.get('enabled')}"
                    )
                else:
                    logger.warning("⚠️  Failed to apply config from PRIMARY (validation error)")

            # Sync deduplication state from PRIMARY (critical blocker #4)
            if "deduplicator_state" in state:
                from backend.core.ha_deduplication import get_ha_deduplicator
                dedup = get_ha_deduplicator()

                seen_orders = state.get("deduplicator_state", {}).get("seen_orders", {})
                for order_key, timestamp_str in seen_orders.items():
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        dedup.seen_orders[order_key] = timestamp
                    except Exception as e:
                        logger.warning(f"Failed to restore dedup entry {order_key}: {e}")

                logger.info(
                    f"♻️  Deduplication state synced: {len(dedup.seen_orders)} order IDs registered"
                )

            # Validate consistency before returning success
            # (cash + positions_value should ≈ total_equity)
            positions_value = sum(
                p.current_price * p.quantity for p in engine.positions.values()
            )
            total_equity = engine.cash + positions_value
            equity_error = abs(total_equity - state.get("total_pnl", 0) - engine.cash)

            if equity_error > 0.01:  # Allow small floating-point error
                logger.warning(f"⚠️ Equity mismatch after sync: {equity_error:.2f} (may indicate corruption)")

            logger.info(f"✅ BACKUP synced atomically: cash={state.get('cash')}, positions={len(synced_positions)}, equity={total_equity:.2f}")

            # CRITICAL: Tell fragility breaker that sync succeeded (prevents divergence detection)
            from backend.core.fragility_circuit_breaker import get_fragility_breaker
            breaker = get_fragility_breaker()
            breaker.record_sync_success()

            return JSONResponse({"status": "synced", "timestamp": datetime.now().isoformat()})

        except Exception as atomic_err:
            logger.error(f"Atomic sync failed (rolled back): {atomic_err}", exc_info=True)
            return JSONResponse(status_code=500, content={
                "error": f"Atomic sync failed: {str(atomic_err)}",
                "detail": "All changes rolled back due to error"
            })

    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/ha/status")
async def get_ha_status() -> JSONResponse:
    """Get HA status (PRIMARY or BACKUP, health)."""
    try:
        # Load .env vars fresh (may not be in os.environ)
        machine_id = "main"  # PRIMARY always checks itself as "main"
        primary_url = "http://192.168.30.137:8001"  # Always PRIMARY IP

        # Override if env vars are available
        env_machine_id = os.getenv("MACHINE_ID")
        if env_machine_id:
            machine_id = env_machine_id

        env_primary_url = os.getenv("PRIMARY_API_URL")
        if env_primary_url:
            primary_url = env_primary_url

        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()

        # Check if PRIMARY is reachable (increased timeout to 2s for network reliability)
        primary_healthy = False
        try:
            import httpx
            # If PRIMARY is checking itself, it should always work
            # If BACKUP is checking PRIMARY, allow up to 2 seconds
            timeout_seconds = 0.5 if machine_id == "main" else 2.0
            resp = httpx.get(f"{primary_url}/api/health", timeout=timeout_seconds)
            primary_healthy = resp.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
            # Log timeout or connection errors for debugging
            logger.debug(f"PRIMARY health check failed: {type(e).__name__}: {e}")
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


@app.post("/api/ha/sync-from-backup")
async def sync_state_from_backup(state: Optional[dict] = None) -> JSONResponse:
    """PRIMARY: Receive state sync from BACKUP after PRIMARY recovery (Phase 2 Component 3).

    Used when PRIMARY comes back online to get latest state from BACKUP.
    Merges BACKUP state with PRIMARY's recovered state.
    """
    try:
        machine_id = os.getenv("MACHINE_ID", "primary")
        if machine_id != "main":
            return JSONResponse(
                status_code=403,
                content={"error": "This endpoint is for PRIMARY only"}
            )

        if not state:
            return JSONResponse(status_code=400, content={"error": "State required"})

        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.database import get_database

        engine = get_paper_trading()
        if engine is None:
            return JSONResponse(
                status_code=500,
                content={"error": "Paper trading engine not initialized"}
            )

        db = get_database()

        # Strategy: If PRIMARY recovered with stale state, use BACKUP's state
        # (BACKUP was actively trading while PRIMARY was down)
        logger.info("📥 PRIMARY receiving state sync from BACKUP recovery...")

        # Merge strategy: BACKUP state overrides PRIMARY's stale state
        if "cash" in state:
            logger.info(f"  Cash: {engine.cash:.2f} → {state['cash']:.2f}")
            engine.cash = state["cash"]

        if "total_pnl" in state:
            logger.info(f"  P&L: {engine.total_pnl:.2f} → {state['total_pnl']:.2f}")
            engine.total_pnl = state["total_pnl"]

        # Sync positions from BACKUP
        if "positions" in state:
            synced_count = 0
            try:
                conn = None
                try:
                    import sqlite3
                    conn = sqlite3.connect(db.db_path)
                    conn.execute("BEGIN TRANSACTION")
                    conn.execute("DELETE FROM open_positions WHERE status = 'OPEN'")

                    for pos in state["positions"]:
                        entry_time_str = pos.get("entry_time")
                        if isinstance(entry_time_str, str):
                            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                        else:
                            entry_time = entry_time_str or datetime.utcnow()

                        db.insert_position(
                            symbol=pos["symbol"],
                            quantity=pos["quantity"],
                            entry_price=pos["entry_price"],
                            entry_time=entry_time
                        )
                        synced_count += 1

                    conn.commit()
                    logger.info(f"  Positions: 0 → {synced_count} (from BACKUP)")

                except Exception as tx_err:
                    if conn:
                        conn.rollback()
                    logger.error(f"Position sync from BACKUP rolled back: {tx_err}")
                    raise tx_err
                finally:
                    if conn:
                        conn.close()

                # Update in-memory cache
                engine.positions.clear()
                from backend.exchange.paper_trading import Position
                for pos in state["positions"]:
                    entry_time_str = pos.get("entry_time")
                    if isinstance(entry_time_str, str):
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                    else:
                        entry_time = entry_time_str or datetime.utcnow()

                    engine.positions[pos["symbol"]] = Position(
                        symbol=pos["symbol"],
                        side="LONG",
                        quantity=pos["quantity"],
                        entry_price=pos["entry_price"],
                        entry_time=entry_time,
                        current_price=pos.get("current_price", pos["entry_price"])
                    )

            except Exception as pos_err:
                logger.error(f"Failed to sync positions from BACKUP: {pos_err}")
                return JSONResponse(status_code=500, content={"error": str(pos_err)})

        logger.info(f"✅ PRIMARY recovered and merged BACKUP state: cash={state.get('cash'):.2f}, positions={len(state.get('positions', []))}")
        return JSONResponse({
            "status": "merged",
            "message": "PRIMARY merged BACKUP state after recovery",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Sync from BACKUP error: {e}", exc_info=True)
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
