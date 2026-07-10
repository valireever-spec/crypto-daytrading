"""Real-time monitoring endpoints for strategy visibility."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])

# Track if we've synced historical data
_historical_sync_done = False


def _sync_historical_trades_to_metrics():
    """Sync historical trades from paper trading engine to metrics collector."""
    global _historical_sync_done

    if _historical_sync_done:
        return  # Only sync once per API session

    try:
        from backend.core.trading_metrics import get_metrics_collector
        from backend.exchange.paper_trading import get_paper_trading

        collector = get_metrics_collector()
        engine = get_paper_trading()

        if not engine:
            logger.warning("Paper trading engine not initialized, skipping historical sync")
            return

        # Get all trades from engine
        all_trades = engine.get_trades(limit=500)  # Get last 500 trades

        if not all_trades:
            logger.info("No historical trades to sync")
            _historical_sync_done = True
            return

        # Load trades into metrics collector
        for trade in all_trades:
            try:
                collector.record_trade(
                    symbol=trade.get('symbol', 'UNKNOWN'),
                    side=trade.get('side', 'BUY'),
                    entry_price=trade.get('entry_price'),
                    exit_price=trade.get('exit_price'),
                    quantity=trade.get('quantity'),
                    realized_pnl=trade.get('realized_pnl'),
                    realized_pnl_pct=trade.get('realized_pnl_pct'),
                    hold_seconds=trade.get('hold_seconds'),
                    exit_reason=trade.get('exit_reason'),
                    slippage_pct=trade.get('slippage_pct', 0),
                )
            except Exception as e:
                logger.warning(f"Failed to sync trade: {e}")
                continue

        logger.info(f"✅ Synced {len(all_trades)} historical trades to metrics collector")
        _historical_sync_done = True

    except Exception as e:
        logger.error(f"Error syncing historical trades: {e}")
        _historical_sync_done = True

@router.get("/metrics")
async def get_metrics():
    """Get current trading metrics (signals, trades, system health)."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        from datetime import timezone

        # Sync historical trades on first access
        _sync_historical_trades_to_metrics()

        collector = get_metrics_collector()
        stats = collector.get_statistics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": stats,
            "recent_signals_2h": collector.get_signals_since(minutes=120),
            "recent_trades_2h": collector.get_trades_since(minutes=120),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals")
async def get_signals(minutes: int = 60):
    """Get recent signals (entry decisions)."""
    try:
        from backend.core.trading_metrics import get_metrics_collector

        # Sync historical trades on first access
        _sync_historical_trades_to_metrics()

        collector = get_metrics_collector()
        
        return {
            "signals": collector.get_signals_since(minutes=minutes),
            "count": len(collector.get_signals_since(minutes=minutes)),
            "window_minutes": minutes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades")
async def get_trades(minutes: int = 60):
    """Get recent trades (executions)."""
    try:
        from backend.core.trading_metrics import get_metrics_collector

        # Sync historical trades on first access
        _sync_historical_trades_to_metrics()

        collector = get_metrics_collector()
        
        trades = collector.get_trades_since(minutes=minutes)
        exits = [t for t in trades if t.side == 'SELL']
        entries = [t for t in trades if t.side == 'BUY']
        
        return {
            "trades": trades,
            "count": len(trades),
            "entries": len(entries),
            "exits": len(exits),
            "window_minutes": minutes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-data")
async def get_dashboard_data():
    """Get all data needed for real-time dashboard."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        import requests

        # Sync historical trades on first access
        _sync_historical_trades_to_metrics()

        collector = get_metrics_collector()
        
        # Get health for system status
        try:
            health = requests.get("http://127.0.0.1:8001/api/health", timeout=2).json()
        except Exception as e:
            logger.warning(f"Failed to fetch health status: {e}")
            health = {}
        
        stats = collector.get_statistics()
        recent_trades = collector.get_trades_since(minutes=120)
        recent_signals = collector.get_signals_since(minutes=120)
        from datetime import timezone

        # Calculate metrics
        exits = [t for t in recent_trades if t.side == 'SELL']
        _win_rate = collector.get_win_rate([None]) if exits else 0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "status": health.get("status", "unknown"),
                "cb_state": health.get("circuit_breaker", {}).get("state", "unknown"),
                "cash": health.get("account", {}).get("cash", 0),
                "daily_pnl": health.get("account", {}).get("daily_pnl", 0),
                "open_positions": health.get("account", {}).get("active_positions", 0),
            },
            "performance": {
                "win_rate_2h": stats.get("win_rate_2h", 0),
                "trades_2h": stats.get("recent_trades_2h", 0),
                "signals_2h": stats.get("recent_signals_2h", 0),
                "uptime_seconds": stats.get("uptime_seconds", 0),
            },
            "recent_signals": recent_signals[-10:] if recent_signals else [],  # Last 10
            "recent_trades": recent_trades[-10:] if recent_trades else [],    # Last 10
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account-audit")
async def get_account_audit():
    """Comprehensive account reconciliation audit.

    Compares: in-memory state vs database ground truth, positions, equity.
    CRITICAL: Detects the silent corruption bug where cache is wrong but no errors are thrown.
    """
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.database import get_database
        from backend.core.startup_verification import get_startup_verification_status
        from backend.core.state_monitor import get_state_monitor_status

        engine = get_paper_trading()
        db = get_database()

        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Get all the checks
        verification_status = get_startup_verification_status()
        monitor_status = get_state_monitor_status()

        # Calculate totals
        positions = engine.get_positions()
        positions_value = sum(p.get("quantity", 0) * p.get("current_price", 0) for p in positions)
        total_equity = engine.cash + positions_value

        # Get database ground truth
        trades_pnl = db.get_total_realized_pnl()
        expected_cash = engine.starting_capital + trades_pnl

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "account_audit": {
                "startup_verification": verification_status,
                "continuous_monitor": monitor_status,
                "account_state": {
                    "in_memory_cash": engine.cash,
                    "in_memory_pnl": engine.total_pnl,
                    "in_memory_daily_pnl": engine.daily_pnl,
                },
                "database_ground_truth": {
                    "starting_capital": engine.starting_capital,
                    "trades_sum_pnl": trades_pnl,
                    "expected_cash": expected_cash,
                },
                "positions": {
                    "count": len(positions),
                    "total_value": positions_value,
                    "symbols": [p.get("symbol") for p in positions],
                },
                "equity": {
                    "cash": engine.cash,
                    "positions_value": positions_value,
                    "total_equity": total_equity,
                },
                "discrepancies": {
                    "cash_drift": {
                        "amount": abs(engine.cash - expected_cash),
                        "status": "OK" if abs(engine.cash - expected_cash) < 1.0 else "CRITICAL",
                        "description": f"In-memory cash differs from DB by €{abs(engine.cash - expected_cash):.2f}",
                    },
                    "pnl_drift": {
                        "amount": abs(engine.total_pnl - trades_pnl),
                        "status": "OK" if abs(engine.total_pnl - trades_pnl) < 1.0 else "CRITICAL",
                        "description": f"In-memory P&L differs from DB by €{abs(engine.total_pnl - trades_pnl):.2f}",
                    },
                },
                "health": {
                    "consistent": (
                        abs(engine.cash - expected_cash) < 1.0
                        and abs(engine.total_pnl - trades_pnl) < 1.0
                    ),
                    "trading_safe": verification_status.get("verified", True),
                },
            },
        }

    except Exception as e:
        logger.error(f"Error getting account audit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuit-breaker-status")
async def get_circuit_breaker_status():
    """Get fragility circuit breaker status (for dashboards/alerting)."""
    try:
        from backend.core.fragility_circuit_breaker import get_fragility_breaker

        breaker = get_fragility_breaker()
        metrics = breaker.get_metrics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "circuit_breaker": {
                "is_halted": metrics['is_halted'],
                "halt_reason": metrics['halt_reason'],
                "current_halt_duration_seconds": metrics['current_halt_duration_seconds'],
                "total_halt_count": metrics['halt_count'],
                "exit_failure_count": metrics['exit_failure_count'],
                "sync_failure_count": metrics['sync_failure_count'],
                "websocket_staleness_triggered": metrics['websocket_staleness_triggered'],
                "recent_halt_events": metrics['recent_halts'],
            }
        }
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/prometheus")
async def get_prometheus_metrics():
    """Prometheus-compatible metrics endpoint for external monitoring."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        import requests

        collector = get_metrics_collector()
        stats = collector.get_statistics()

        try:
            health = requests.get("http://127.0.0.1:8001/api/health", timeout=2).json()
        except Exception as e:
            logger.warning(f"Failed to fetch health status for prometheus metrics: {e}")
            health = {}

        metrics = []

        # Trading metrics
        metrics.append("# HELP crypto_trading_signals_total Total signals generated")
        metrics.append("# TYPE crypto_trading_signals_total counter")
        metrics.append(f"crypto_trading_signals_total {stats.get('total_signals', 0)}")

        metrics.append("# HELP crypto_trading_trades_total Total trades executed")
        metrics.append("# TYPE crypto_trading_trades_total counter")
        metrics.append(f"crypto_trading_trades_total {stats.get('total_trades', 0)}")

        metrics.append("# HELP crypto_trading_win_rate_2h Win rate last 2 hours")
        metrics.append("# TYPE crypto_trading_win_rate_2h gauge")
        metrics.append(f"crypto_trading_win_rate_2h {stats.get('win_rate_2h', 0)}")

        # System metrics
        account = health.get('account', {})
        metrics.append("# HELP crypto_trading_cash_available Available cash")
        metrics.append("# TYPE crypto_trading_cash_available gauge")
        metrics.append(f"crypto_trading_cash_available {account.get('cash', 0)}")

        metrics.append("# HELP crypto_trading_daily_pnl Daily profit/loss")
        metrics.append("# TYPE crypto_trading_daily_pnl gauge")
        metrics.append(f"crypto_trading_daily_pnl {account.get('daily_pnl', 0)}")

        metrics.append("# HELP crypto_trading_positions_open Open positions")
        metrics.append("# TYPE crypto_trading_positions_open gauge")
        metrics.append(f"crypto_trading_positions_open {account.get('active_positions', 0)}")

        cb_state = health.get('circuit_breaker', {}).get('state', 'UNKNOWN')
        cb_value = 1 if cb_state == 'CLOSED' else 0
        metrics.append("# HELP crypto_trading_circuit_breaker Circuit breaker state (1=CLOSED, 0=OPEN)")
        metrics.append("# TYPE crypto_trading_circuit_breaker gauge")
        metrics.append(f"crypto_trading_circuit_breaker {cb_value}")

        return Response(content="\n".join(metrics), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-metrics")
async def get_dashboard_metrics():
    """Get comprehensive dashboard metrics for UI display (from paper trading engine)."""
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from datetime import timezone

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Get all trades from engine (source of truth)
        all_trades = engine.get_trades(limit=500)

        # Calculate metrics from actual trades
        exits = [t for t in all_trades if t.get('side') == 'SELL' and t.get('realized_pnl') is not None]
        entries = [t for t in all_trades if t.get('side') == 'BUY']

        # Calculate P&L metrics
        _total_pnl = sum(t.get('realized_pnl', 0) for t in exits)
        winners = [t for t in exits if (t.get('realized_pnl', 0) or 0) > 0]
        losers = [t for t in exits if (t.get('realized_pnl', 0) or 0) <= 0]

        avg_win = sum(t.get('realized_pnl', 0) for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.get('realized_pnl', 0) for t in losers) / len(losers) if losers else 0

        win_rate = (len(winners) / len(exits) * 100) if exits else 0
        risk_reward = abs(avg_win / avg_loss) if (avg_loss and avg_loss != 0) else 0

        # Consecutive losses
        consecutive_losses = 0
        for trade in reversed(exits):
            if (trade.get('realized_pnl', 0) or 0) <= 0:
                consecutive_losses += 1
            else:
                break

        # Get last 5 trades for display
        last_5 = exits[-5:] if exits else []
        last_5_display = []
        for trade in reversed(last_5):
            pnl = trade.get('realized_pnl', 0)
            pnl_pct = trade.get('realized_pnl_pct', 0)
            status = "✅" if pnl > 0 else "❌"
            last_5_display.append({
                'status': status,
                'symbol': trade.get('symbol', 'UNKNOWN'),
                'pnl': round(pnl, 4),
                'pnl_pct': round(pnl_pct, 2),
                'hold_seconds': trade.get('hold_seconds', 0),
                'exit_reason': trade.get('exit_reason', 'unknown')
            })

        # Get account state
        account_state = engine.get_account_state()

        return {
            'summary': {
                'trades_today': len(entries),
                'exits_today': len(exits),
                'total_pnl': account_state.get('total_pnl', 0),  # Use actual account P&L, not sum of historical trades
                'win_rate_pct': round(win_rate, 1),
                'wins': len(winners),
                'losses': len(losers),
            },
            'performance': {
                'avg_win': round(avg_win, 4),
                'avg_loss': round(avg_loss, 4),
                'risk_reward_ratio': round(risk_reward, 2),
                'consecutive_losses': consecutive_losses,
            },
            'recent_trades': last_5_display,
            'system': {
                'cash': account_state.get('cash', 0),
                'daily_pnl': account_state.get('daily_pnl', 0),
                'total_pnl': account_state.get('total_pnl', 0),
                'open_positions': len(engine.get_positions()),
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pnl-reconciliation")
async def verify_pnl_reconciliation():
    """Verify P&L calculation integrity: sum(realized_pnl) should match account equity change.

    CRITICAL: This detects the entry_fee bug where realized_pnl was missing entry fees.
    After fix, this endpoint should return match within ±€1.00
    """
    try:
        from backend.exchange.paper_trading import get_paper_trading
        from backend.core.database import get_database
        import sqlite3

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Method 1: Sum realized_pnl from database
        try:
            db = get_database()
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(realized_pnl) FROM trades WHERE side='SELL'")
            result = cursor.fetchone()
            db_sum_pnl = result[0] if result[0] is not None else 0.0
            conn.close()
        except Exception as e:
            db_sum_pnl = 0.0
            logger.warning(f"Failed to query database: {e}")

        # Method 2: Calculate from account state
        account_state = engine.get_account_state()
        current_equity = account_state.get('cash', 0.0)
        starting_capital = engine.starting_capital
        account_equity_change = current_equity - starting_capital

        # Verify match
        discrepancy = abs(db_sum_pnl - account_equity_change)

        return {
            'reconciliation': {
                'db_sum_realized_pnl': round(db_sum_pnl, 2),
                'account_equity_change': round(account_equity_change, 2),
                'discrepancy': round(discrepancy, 2),
                'status': 'OK' if discrepancy < 1.0 else 'FAIL - DATA INTEGRITY ERROR',
                'message': (
                    "✅ P&L calculation is correct" if discrepancy < 1.0
                    else f"🚨 CRITICAL: P&L mismatch of €{discrepancy:.2f} detected. "
                         f"This indicates entry fees are not being tracked correctly."
                )
            },
            'account': {
                'starting_capital': starting_capital,
                'current_cash': round(current_equity, 2),
                'total_pnl': round(account_state.get('total_pnl', 0), 2),
                'daily_pnl': round(account_state.get('daily_pnl', 0), 2),
            }
        }
    except Exception as e:
        logger.error(f"Error verifying P&L reconciliation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard")
async def get_dashboard():
    """Serve real-time monitoring dashboard."""
    dashboard_path = Path(__file__).parent.parent.parent.parent / "frontend" / "trading_dashboard.html"

    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        return HTMLResponse("""
        <html>
            <body style="background: #0f1419; color: #e0e0e0; font-family: monospace; padding: 20px;">
                <h1>📊 Trading Monitoring Dashboard</h1>
                <p>Dashboard file not found. Visit: <strong>/api/monitoring/dashboard-metrics</strong></p>
                <p>Available endpoints:</p>
                <ul>
                    <li>GET /api/monitoring/dashboard-metrics - Comprehensive dashboard data</li>
                    <li>GET /api/monitoring/metrics - All metrics (JSON)</li>
                    <li>GET /api/monitoring/prometheus - Prometheus-compatible metrics</li>
                    <li>GET /api/monitoring/signals - Recent signal decisions</li>
                    <li>GET /api/monitoring/trades - Recent trade executions</li>
                    <li>GET /api/monitoring/pnl-reconciliation - CRITICAL: Verify P&L integrity</li>
                </ul>
            </body>
        </html>
        """)
