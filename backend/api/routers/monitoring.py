"""Real-time monitoring endpoints for strategy visibility."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from datetime import datetime
from pathlib import Path

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])

@router.get("/metrics")
async def get_metrics():
    """Get current trading metrics (signals, trades, system health)."""
    try:
        from backend.core.trading_metrics import get_metrics_collector
        
        collector = get_metrics_collector()
        stats = collector.get_statistics()
        
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
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
        
        # Calculate metrics
        exits = [t for t in recent_trades if t.side == 'SELL']
        win_rate = collector.get_win_rate([None]) if exits else 0
        
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
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

@router.get("/dashboard")
async def get_dashboard():
    """Serve real-time monitoring dashboard."""
    dashboard_path = Path(__file__).parent.parent.parent / "frontend" / "monitoring_dashboard.html"

    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        return HTMLResponse("""
        <html>
            <body style="background: #0f1419; color: #e0e0e0; font-family: monospace; padding: 20px;">
                <h1>📊 Trading Monitoring Dashboard</h1>
                <p>Dashboard file not found. Visit: <strong>/api/monitoring/metrics</strong></p>
                <p>Available endpoints:</p>
                <ul>
                    <li>GET /api/monitoring/metrics - All metrics and statistics</li>
                    <li>GET /api/monitoring/signals - Recent signal decisions</li>
                    <li>GET /api/monitoring/trades - Recent trade executions</li>
                    <li>GET /api/monitoring/dashboard-data - Data for dashboard visualization</li>
                </ul>
            </body>
        </html>
        """)
