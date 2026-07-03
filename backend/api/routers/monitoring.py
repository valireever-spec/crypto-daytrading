"""API endpoints for production monitoring and health checks."""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.core.health_checker import init_health_checker, get_health_checker
from backend.core.alerting import init_alert_manager, get_alert_manager, AlertSeverity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/health")
async def get_health_status():
    """Get comprehensive system health status."""
    health_checker = get_health_checker()
    if not health_checker:
        health_checker = init_health_checker()

    result = await health_checker.check_all()
    return JSONResponse(result)


@router.get("/health/service/{service_name}")
async def get_service_health(service_name: str):
    """Get health status for a specific service."""
    health_checker = get_health_checker()
    if not health_checker:
        raise HTTPException(status_code=500, detail="Health checker not initialized")

    status = health_checker.last_checks.get(service_name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    return JSONResponse(status.to_dict())


@router.get("/health/history/{service_name}")
async def get_health_history(service_name: str, limit: int = 50):
    """Get health check history for a service."""
    health_checker = get_health_checker()
    if not health_checker:
        raise HTTPException(status_code=500, detail="Health checker not initialized")

    history = health_checker.get_history(service_name)
    return JSONResponse(
        {"service": service_name, "history": history[-limit:], "total": len(history)}
    )


@router.get("/alerts")
async def get_alerts(status: str = "all", limit: int = 100):
    """Get alerts."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    if status == "active":
        alerts = alert_manager.get_active_alerts()
    elif status == "resolved":
        alerts = [a for a in alert_manager.get_alert_history(limit) if a.resolved]
    else:  # all
        alerts = alert_manager.get_alert_history(limit)

    return JSONResponse(
        {
            "count": len(alerts),
            "status": status,
            "alerts": [a.to_dict() for a in alerts],
        }
    )


@router.get("/alerts/active")
async def get_active_alerts():
    """Get all active alerts."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    alerts = alert_manager.get_active_alerts()
    return JSONResponse({"count": len(alerts), "alerts": [a.to_dict() for a in alerts]})


@router.get("/alerts/service/{service_name}")
async def get_service_alerts(service_name: str):
    """Get alerts for a specific service."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    alerts = alert_manager.get_alerts_by_service(service_name)
    return JSONResponse(
        {
            "service": service_name,
            "count": len(alerts),
            "alerts": [a.to_dict() for a in alerts],
        }
    )


@router.get("/alerts/severity/{severity}")
async def get_alerts_by_severity(severity: str):
    """Get alerts by severity."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    try:
        sev = AlertSeverity(severity.lower())
        alerts = alert_manager.get_alerts_by_severity(sev)
        return JSONResponse(
            {
                "severity": severity,
                "count": len(alerts),
                "alerts": [a.to_dict() for a in alerts],
            }
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {severity}. Must be one of: {', '.join([s.value for s in AlertSeverity])}",
        )


@router.post("/alerts/create")
async def create_alert(severity: str, title: str, message: str, service: str):
    """Create a manual alert."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    try:
        sev = AlertSeverity(severity.lower())
        alert = await alert_manager.create_alert(sev, title, message, service)
        return JSONResponse({"status": "created", "alert": alert.to_dict()})
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Mark an alert as resolved."""
    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    resolved = await alert_manager.resolve_alert(alert_id)
    if resolved:
        return JSONResponse({"status": "resolved", "alert_id": alert_id})
    else:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


@router.get("/status")
async def get_system_status():
    """Get overall system status."""
    health_checker = get_health_checker()
    if not health_checker:
        health_checker = init_health_checker()

    alert_manager = get_alert_manager()
    if not alert_manager:
        alert_manager = init_alert_manager()

    health = await health_checker.check_all()
    active_alerts = alert_manager.get_active_alerts()

    return JSONResponse(
        {
            "timestamp": health["timestamp"],
            "health": health,
            "alerts": {
                "active": len(active_alerts),
                "critical": len(
                    [a for a in active_alerts if a.severity.value == "critical"]
                ),
                "warning": len(
                    [a for a in active_alerts if a.severity.value == "warning"]
                ),
            },
        }
    )


@router.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    import psutil

    return JSONResponse(
        {
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
            },
            "memory": {
                "used_mb": psutil.virtual_memory().used / 1024 / 1024,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "used_gb": psutil.disk_usage("/").used / 1024 / 1024 / 1024,
                "free_gb": psutil.disk_usage("/").free / 1024 / 1024 / 1024,
                "percent": psutil.disk_usage("/").percent,
            },
        }
    )


@router.get("/health/websocket")
async def get_websocket_staleness():
    """Get WebSocket staleness status (SKILL #1: Staleness Monitor).

    Returns real-time status of price feeds:
    - staleness_secs: Age of last price update
    - is_healthy: Whether reconnect recovery is active
    - reconnect_attempts: Number of reconnect attempts
    """
    from backend.api import lifecycle

    if not lifecycle.staleness_monitor:
        return JSONResponse(
            {
                "status": "unavailable",
                "detail": "Staleness monitor not initialized",
            },
            status_code=503,
        )

    status = lifecycle.staleness_monitor.get_status()

    # Check if any critical staleness
    any_critical = any(
        s["staleness_secs"] > 30
        for s in status["streams"].values()
    )

    return JSONResponse(
        {
            "status": "unhealthy" if any_critical else "healthy",
            "details": status,
        }
    )


# ============================================================================
# SKILL #3: EXPLICIT HEARTBEAT (HA FAILOVER)
# ============================================================================

@router.post("/ha/explicit-heartbeat")
async def receive_explicit_heartbeat(heartbeat: dict):
    """BACKUP: Receive explicit heartbeat from PRIMARY.

    Skill #3: Reliable heartbeat monitoring for auto-failover.
    PRIMARY sends every 2s; if BACKUP misses 3, auto-promote.
    """
    from backend.failover.explicit_heartbeat import get_explicit_heartbeat_monitor

    monitor = get_explicit_heartbeat_monitor()
    if monitor:
        heartbeat_id = heartbeat.get("heartbeat_id", 0)
        monitor.record_heartbeat(heartbeat_id)

        return JSONResponse(
            {
                "status": "received",
                "heartbeat_id": heartbeat_id,
                "timestamp": heartbeat.get("timestamp"),
            }
        )
    else:
        return JSONResponse(
            {"status": "monitor_not_initialized"},
            status_code=503,
        )


@router.get("/ha/explicit-heartbeat/stats")
async def get_explicit_heartbeat_stats():
    """Get heartbeat statistics (BACKUP monitoring PRIMARY)."""
    from backend.failover.explicit_heartbeat import get_explicit_heartbeat_monitor

    monitor = get_explicit_heartbeat_monitor()
    if monitor:
        stats = monitor.get_stats()
        return JSONResponse(
            {
                "monitor_active": monitor.running,
                "stats": stats,
            }
        )
    else:
        return JSONResponse(
            {"monitor_active": False, "stats": None},
            status_code=503,
        )


# ============================================================================
# SKILL #2: PROCESS HEALTH MONITORING (STUCK DETECTION)
# ============================================================================

@router.get("/process/health")
async def get_process_health():
    """Get current process health metrics (Skill #2).

    Monitors: socket count, thread count, memory, CPU.
    Detects: stuck processes (high sockets for >60s), runaway restarts.
    """
    from backend.core.process_health_monitor import get_process_health_monitor

    monitor = get_process_health_monitor()
    if monitor:
        stats = monitor.get_stats()
        is_stuck = monitor.is_stuck()
        runaway_alert = monitor.get_runaway_restart_alert()

        return JSONResponse(
            {
                "health": "stuck" if is_stuck else "healthy",
                "stats": stats,
                "alerts": [runaway_alert] if runaway_alert else [],
            }
        )
    else:
        return JSONResponse(
            {"health": "unknown", "stats": None, "alerts": []},
            status_code=503,
        )


# ============================================================================
# SKILL #5: CIRCUIT BREAKER PERSISTENCE & MANUAL RESET
# ============================================================================

@router.get("/circuit-breaker/stats")
async def get_circuit_breaker_stats():
    """Get CB statistics and history (Skill #5).

    Shows: current state, trip count, recent trips/recoveries.
    """
    from backend.core.circuit_breaker_recovery import get_circuit_breaker_recovery

    recovery = get_circuit_breaker_recovery()
    if recovery:
        stats = recovery.get_stats()
        return JSONResponse(
            {
                "circuit_breaker": stats,
            }
        )
    else:
        return JSONResponse(
            {"circuit_breaker": None},
            status_code=503,
        )


@router.post("/admin/circuit-breaker/reset")
async def reset_circuit_breaker(reason: str = "admin override"):
    """ADMIN ENDPOINT: Manually reset CB without restart (Skill #5).

    This allows recovery from a tripped CB without restarting the entire service.
    Typical use: after issue is resolved, manually reset to resume trading.

    Args:
        reason: Why the reset is being triggered (logged for audit trail)

    Returns:
        Success status and updated CB state
    """
    from backend.core.circuit_breaker_recovery import get_circuit_breaker_recovery

    recovery = get_circuit_breaker_recovery()
    if not recovery:
        return JSONResponse(
            {"success": False, "error": "CB recovery not initialized"},
            status_code=503,
        )

    # Attempt reset
    success = recovery.manual_reset(reason)

    if success:
        return JSONResponse(
            {
                "success": True,
                "message": f"Circuit breaker manually reset (reason: {reason})",
                "new_state": recovery.current_state,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    else:
        return JSONResponse(
            {
                "success": False,
                "error": f"Cannot reset CB (current state: {recovery.current_state})",
                "current_state": recovery.current_state,
            },
            status_code=400,
        )
