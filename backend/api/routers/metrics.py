"""Prometheus metrics exporter for Phase 2 monitoring.

Provides /metrics endpoint that exports all system metrics in Prometheus format.
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", include_in_schema=False)
async def get_prometheus_metrics() -> Response:
    """Export metrics in Prometheus format for Grafana/Prometheus scraping.

    Returns:
        Prometheus-format text response
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring

        monitoring = get_phase2_monitoring()
        prometheus_text = monitoring.export_prometheus_metrics()

        return Response(
            content=prometheus_text,
            media_type="text/plain; version=0.0.4"
        )
    except Exception as e:
        logger.error(f"Error exporting Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", include_in_schema=False)
async def get_metrics_health() -> dict:
    """Get current system health status (for Grafana/dashboard).

    Returns:
        - status: HEALTHY/CAUTION/WARNING/CRITICAL
        - risk_score: 0-100 cascade risk
        - metrics: Current metrics snapshot
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring

        monitoring = get_phase2_monitoring()
        health = monitoring.get_system_health()

        return health
    except Exception as e:
        logger.error(f"Error getting metrics health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", include_in_schema=False)
async def get_metrics_summary() -> dict:
    """Get current metrics summary.

    Returns:
        Dictionary with all current metrics
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring

        monitoring = get_phase2_monitoring()
        summary = monitoring.get_metrics_summary()

        return summary
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade-risk", include_in_schema=False)
async def get_cascade_risk() -> dict:
    """Get cascade risk score (0-100).

    Score indicates probability of cascading failure:
    - 0-25: SAFE - No precursors detected
    - 25-50: CAUTION - 1-2 precursors detected
    - 50-75: WARNING - Multiple precursors or 1 critical
    - 75-100: CRITICAL - High cascade risk, consider failover

    Returns:
        Dictionary with cascade risk details
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring

        monitoring = get_phase2_monitoring()
        risk_score = monitoring.get_cascade_risk_score()

        # Determine risk level
        if risk_score >= 75:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "WARNING"
        elif risk_score >= 25:
            risk_level = "CAUTION"
        else:
            risk_level = "SAFE"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "message": f"Cascade failure risk: {risk_level}",
            "health": monitoring.get_system_health()
        }
    except Exception as e:
        logger.error(f"Error getting cascade risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", include_in_schema=False)
async def get_metrics_history(minutes: int = 60) -> dict:
    """Get historical metrics for dashboard trends.

    Args:
        minutes: Number of minutes of history to return (default 60)

    Returns:
        Dictionary with metric snapshots over time
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring

        monitoring = get_phase2_monitoring()
        history = monitoring.get_metrics_history(minutes)

        return {
            "period_minutes": minutes,
            "snapshot_count": len(history),
            "snapshots": history
        }
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
