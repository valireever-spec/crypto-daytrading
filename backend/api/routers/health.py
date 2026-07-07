"""Health check endpoint for system monitoring and deployment readiness."""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Dict, Any

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
async def health_check() -> Dict[str, Any]:
    """System health check endpoint.

    Returns current system status with timestamp. Used for:
    - Load balancer health checks
    - Deployment monitoring
    - System readiness validation

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "timestamp": ISO 8601 timestamp,
            "version": "1.0.0",
            "services": {
                "database": "online" | "offline",
                "trading_engine": "online" | "offline",
                "api": "online" | "offline"
            }
        }
    """
    try:
        # Check database connectivity
        from backend.core.database import get_database
        db = get_database()
        db_status = "online"
    except Exception as e:
        db_status = "offline"

    # Check trading engine
    try:
        from backend.exchange.paper_trading import get_paper_trading
        engine = get_paper_trading()
        trading_status = "online" if engine else "offline"
    except Exception:
        trading_status = "offline"

    # Determine overall status
    if db_status == "offline" or trading_status == "offline":
        overall_status = "degraded" if db_status == "online" or trading_status == "online" else "unhealthy"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "services": {
            "database": db_status,
            "trading_engine": trading_status,
            "api": "online"
        }
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check for deployment orchestration.

    Returns True only when system is fully ready to handle traffic.
    Used by Kubernetes, Docker Swarm, etc.

    Returns:
        {"ready": true | false}
    """
    health = await health_check()
    return {
        "ready": health["status"] == "healthy"
    }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check - is the process alive and responsive?

    Returns True if process is responsive (not hung).
    Used by orchestration to restart hung processes.

    Returns:
        {"alive": true}
    """
    return {"alive": True}
