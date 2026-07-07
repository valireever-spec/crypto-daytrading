"""Real-time monitoring endpoints for strategy visibility."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from datetime import datetime, timezone
from pathlib import Path

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])

@router.get("/metrics")
async def get_metrics():
    """Get current trading metrics (signals, trades, system health)."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        from datetime import timezone

        collector = get_metrics_collector()
        stats = collector.get_statistics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
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
        
        collector = get_metrics_collector()
        
        # Get health for system status
        try:
            health = requests.get("http://127.0.0.1:8001/api/health", timeout=2).json()
        except:
            health = {}
        
        stats = collector.get_statistics()
        recent_trades = collector.get_trades_since(minutes=120)
        recent_signals = collector.get_signals_since(minutes=120)
        from datetime import timezone

        # Calculate metrics
        exits = [t for t in recent_trades if t.side == 'SELL']
        win_rate = collector.get_win_rate([None]) if exits else 0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
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
        except:
            health = {}

        metrics = []

        # Trading metrics
        metrics.append(f"# HELP crypto_trading_signals_total Total signals generated")
        metrics.append(f"# TYPE crypto_trading_signals_total counter")
        metrics.append(f"crypto_trading_signals_total {stats.get('total_signals', 0)}")

        metrics.append(f"# HELP crypto_trading_trades_total Total trades executed")
        metrics.append(f"# TYPE crypto_trading_trades_total counter")
        metrics.append(f"crypto_trading_trades_total {stats.get('total_trades', 0)}")

        metrics.append(f"# HELP crypto_trading_win_rate_2h Win rate last 2 hours")
        metrics.append(f"# TYPE crypto_trading_win_rate_2h gauge")
        metrics.append(f"crypto_trading_win_rate_2h {stats.get('win_rate_2h', 0)}")

        # System metrics
        account = health.get('account', {})
        metrics.append(f"# HELP crypto_trading_cash_available Available cash")
        metrics.append(f"# TYPE crypto_trading_cash_available gauge")
        metrics.append(f"crypto_trading_cash_available {account.get('cash', 0)}")

        metrics.append(f"# HELP crypto_trading_daily_pnl Daily profit/loss")
        metrics.append(f"# TYPE crypto_trading_daily_pnl gauge")
        metrics.append(f"crypto_trading_daily_pnl {account.get('daily_pnl', 0)}")

        metrics.append(f"# HELP crypto_trading_positions_open Open positions")
        metrics.append(f"# TYPE crypto_trading_positions_open gauge")
        metrics.append(f"crypto_trading_positions_open {account.get('active_positions', 0)}")

        cb_state = health.get('circuit_breaker', {}).get('state', 'UNKNOWN')
        cb_value = 1 if cb_state == 'CLOSED' else 0
        metrics.append(f"# HELP crypto_trading_circuit_breaker Circuit breaker state (1=CLOSED, 0=OPEN)")
        metrics.append(f"# TYPE crypto_trading_circuit_breaker gauge")
        metrics.append(f"crypto_trading_circuit_breaker {cb_value}")

        return Response(content="\n".join(metrics), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-metrics")
async def get_dashboard_metrics():
    """Get comprehensive dashboard metrics for UI display."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        import requests

        collector = get_metrics_collector()
        dashboard_data = collector.get_dashboard_metrics()

        # Add system health and account data
        account = {}
        try:
            # Get account data from paper trading engine (correct endpoint)
            from backend.exchange.paper_trading import get_paper_trading
            engine = get_paper_trading()
            if engine:
                account_state = engine.get_account_state()
                account = {
                    'cash': account_state.get('cash', 0),
                    'daily_pnl': account_state.get('daily_pnl', 0),
                    'total_pnl': account_state.get('total_pnl', 0),
                    'active_positions': len(engine.get_positions()),
                }
        except:
            pass

        dashboard_data['system'] = {
            'cash': account.get('cash', 0),
            'daily_pnl': account.get('daily_pnl', 0),
            'total_pnl': account.get('total_pnl', 0),
            'open_positions': account.get('active_positions', 0),
        }

        dashboard_data['timestamp'] = datetime.now(timezone.utc).isoformat()

        return dashboard_data
    except Exception as e:
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
                </ul>
            </body>
        </html>
        """)
