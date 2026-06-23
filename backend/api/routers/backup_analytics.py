"""
Backup Analytics Router - Available only when backup is in standby mode
Provides portfolio analysis, risk metrics, and reporting endpoints
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import httpx
import os

from backend.analytics.portfolio_analyzer import get_portfolio_analyzer

router = APIRouter(prefix="/api/backup", tags=["backup-analytics"])


async def fetch_primary_state() -> dict:
    """Fetch account state from primary via tunnel"""
    primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{primary_url}/api/paper/account")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach primary: {str(e)}")


async def fetch_primary_trades() -> list:
    """Fetch trade history from primary"""
    primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{primary_url}/api/paper/trades?limit=1000")
            data = response.json()
            return data.get("trades", [])
    except Exception:
        return []


@router.get("/daily-report")
async def get_daily_report():
    """
    Get comprehensive daily portfolio report

    Returns: P&L, risk metrics, drift analysis, signal quality
    """
    analyzer = get_portfolio_analyzer()

    # Fetch latest data from primary
    account_state = await fetch_primary_state()
    trades = await fetch_primary_trades()

    # Update analyzer
    analyzer.set_account_state(account_state)
    analyzer.set_trades_history(trades)

    return analyzer.generate_daily_report()


@router.get("/pnl")
async def get_daily_pnl():
    """Get daily P&L breakdown"""
    analyzer = get_portfolio_analyzer()

    account_state = await fetch_primary_state()
    trades = await fetch_primary_trades()

    analyzer.set_account_state(account_state)
    analyzer.set_trades_history(trades)

    return analyzer.calculate_daily_pnl()


@router.get("/risk-metrics")
async def get_risk_metrics():
    """
    Get risk metrics: Sharpe ratio, drawdown, VaR, volatility
    """
    analyzer = get_portfolio_analyzer()

    trades = await fetch_primary_trades()
    analyzer.set_trades_history(trades)

    return analyzer.calculate_risk_metrics()


@router.get("/portfolio-drift")
async def get_portfolio_drift():
    """
    Detect portfolio drift from target allocation

    Returns: Current allocation, targets, drift, rebalance needed
    """
    analyzer = get_portfolio_analyzer()

    account_state = await fetch_primary_state()
    analyzer.set_account_state(account_state)

    return analyzer.calculate_portfolio_drift()


@router.get("/signal-quality")
async def get_signal_quality():
    """
    Analyze signal quality by entry signal type

    Returns: Win rate, count, avg PnL by signal type
    """
    analyzer = get_portfolio_analyzer()

    trades = await fetch_primary_trades()
    analyzer.set_trades_history(trades)

    return analyzer.calculate_signal_quality()


@router.get("/status")
async def get_backup_status():
    """
    Get backup status: Running in analytics mode or active trading
    """
    # Check if primary is reachable
    primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
    primary_healthy = True

    try:
        async with httpx.AsyncClient(timeout=2) as client:
            await client.get(f"{primary_url}/api/health")
    except Exception:
        primary_healthy = False

    return {
        "status": "active_trading" if not primary_healthy else "analytics_standby",
        "mode": "autonomous",
        "primary_reachable": primary_healthy,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/trigger-analysis")
async def trigger_full_analysis():
    """
    Trigger complete analysis suite

    Useful for scheduled daily reports
    """
    analyzer = get_portfolio_analyzer()

    # Fetch all data
    account_state = await fetch_primary_state()
    trades = await fetch_primary_trades()

    analyzer.set_account_state(account_state)
    analyzer.set_trades_history(trades)

    return {
        "analysis_complete": True,
        "timestamp": datetime.now().isoformat(),
        "report": analyzer.generate_daily_report(),
    }
