"""API endpoints for production monitoring and health checks."""

import logging
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
