"""Phase 2: HA Cascade Prevention - Integrated Monitoring Loop.

This module ties together metrics collection and alert generation into a
continuous monitoring loop. It:

1. Collects metrics every 5 seconds
2. Analyzes metrics for cascade precursors
3. Triggers alerts when thresholds exceeded
4. Maintains alert history for dashboard
5. Exports metrics in Prometheus format

This is the main entry point for Phase 2 monitoring infrastructure.
"""

import asyncio
import logging
from typing import Optional, Callable, List
from datetime import datetime

from backend.core.phase_2_metrics import (
    Phase2MetricsCollector,
    get_phase2_metrics,
    init_phase2_metrics,
)
from backend.core.phase_2_alerts import (
    Phase2AlertManager,
    Alert,
    AlertSeverity,
    get_phase2_alert_manager,
    init_phase2_alert_manager,
)

logger = logging.getLogger(__name__)


class Phase2MonitoringLoop:
    """Integrated monitoring loop for cascade failure detection.

    Combines metrics collection and alert generation into a continuous
    background task that monitors for cascade precursor conditions.

    Responsibilities:
    1. Collect metrics every 5 seconds
    2. Analyze metrics for threshold violations
    3. Generate alerts when conditions detected
    4. Route alerts to handlers (logging, HTTP callbacks, etc.)
    5. Maintain alert history for dashboards
    """

    def __init__(
        self,
        metrics_collector: Optional[Phase2MetricsCollector] = None,
        alert_manager: Optional[Phase2AlertManager] = None,
    ):
        """Initialize monitoring loop.

        Args:
            metrics_collector: MetricsCollector instance (uses global if None)
            alert_manager: AlertManager instance (uses global if None)
        """
        self.metrics_collector = metrics_collector or get_phase2_metrics()
        self.alert_manager = alert_manager or get_phase2_alert_manager()

        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Alert thresholds (can be overridden)
        self.enable_cascade_detection = True
        self.enable_memory_alerts = True
        self.enable_websocket_alerts = True
        self.enable_ha_alerts = True
        self.enable_exception_alerts = True

        # Alert debouncing (to avoid alert spam)
        self.last_alert_time_by_type: dict = {}
        self.alert_debounce_seconds = 60

        logger.info("Phase 2 Monitoring Loop initialized")

    async def start(self) -> None:
        """Start the monitoring loop.

        Should be called during system startup.
        """
        if self.is_monitoring:
            logger.warning("Monitoring already started")
            return

        self.is_monitoring = True

        # Start metrics collection
        await self.metrics_collector.start_collection()
        logger.info("Metrics collection started")

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Phase 2 Monitoring Loop started")

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False

        # Stop metrics collection
        await self.metrics_collector.stop_collection()

        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Phase 2 Monitoring Loop stopped")

    async def _monitoring_loop(self) -> None:
        """Background loop that continuously monitors metrics.

        Collects metrics, analyzes for cascade precursors, and generates alerts.
        """
        logger.info("Monitoring loop started")

        try:
            while self.is_monitoring:
                try:
                    # Wait for current snapshot (metrics collector runs every 5s)
                    await asyncio.sleep(5)

                    # Get latest snapshot
                    snapshot = self.metrics_collector.get_current_snapshot()
                    if not snapshot:
                        continue

                    # Analyze metrics and generate alerts
                    alerts = self.alert_manager.analyze_metrics(snapshot.to_dict())

                    # Send alerts (with debouncing)
                    for alert in alerts:
                        await self._send_alert_with_debounce(alert)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(
                        f"Error in monitoring loop: {e}", exc_info=True
                    )
                    await asyncio.sleep(5)  # Don't hammer on errors

        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Monitoring loop stopped")

    async def _send_alert_with_debounce(self, alert: Alert) -> None:
        """Send alert with debouncing to prevent alert spam.

        Args:
            alert: Alert object to send
        """
        # Check if we should debounce this alert
        last_time = self.last_alert_time_by_type.get(alert.alert_type, 0)
        time_since_last = (datetime.utcnow().timestamp() - last_time)

        if time_since_last < self.alert_debounce_seconds:
            logger.debug(
                f"Alert debounced: {alert.alert_type} "
                f"(sent {time_since_last:.0f}s ago)"
            )
            return

        # Send alert
        await self.alert_manager.send_alert(alert)
        self.last_alert_time_by_type[alert.alert_type] = datetime.utcnow().timestamp()

    def register_alert_handler(self, handler: Callable) -> None:
        """Register a handler to receive alerts.

        Args:
            handler: Async function that receives Alert object
        """
        self.alert_manager.register_alert_callback(handler)
        logger.info(f"Alert handler registered: {handler.__name__}")

    def get_metrics_summary(self) -> dict:
        """Get current metrics summary.

        Returns:
            Dictionary with current metrics
        """
        snapshot = self.metrics_collector.get_current_snapshot()
        if not snapshot:
            return {"error": "No metrics collected yet"}
        return snapshot.to_dict()

    def get_alerts_summary(self) -> dict:
        """Get current alert summary.

        Returns:
            Dictionary with alert statistics
        """
        return self.alert_manager.get_alert_summary()

    def get_metrics_history(self, minutes: int = 60) -> List[dict]:
        """Get metrics history.

        Args:
            minutes: Number of minutes of history

        Returns:
            List of metric snapshots
        """
        snapshots = self.metrics_collector.get_snapshot_history(minutes)
        return [s.to_dict() for s in snapshots]

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format.

        Returns:
            Prometheus-format text
        """
        return self.metrics_collector.export_prometheus_format()

    def get_cascade_risk_score(self) -> float:
        """Calculate cascade risk score (0-100).

        Score increases with number and severity of cascade precursors:
        - 0: No precursors detected
        - 25: 1 warning-level precursor
        - 50: 2 warning-level precursors or 1 critical
        - 75: 3+ precursors or 2+ critical
        - 100: Cascade alert active

        Returns:
            Risk score from 0 to 100
        """
        snapshot = self.metrics_collector.get_current_snapshot()
        if not snapshot:
            return 0.0

        risk_score = 0.0
        precursor_count = 0

        # Check memory
        if snapshot.memory_percent >= self.alert_manager.memory_critical_percent:
            risk_score += 25  # Critical
            precursor_count += 1
        elif snapshot.memory_percent >= self.alert_manager.memory_warning_percent:
            risk_score += 15  # Warning
            precursor_count += 1

        # Check WebSocket
        if snapshot.ws_max_age_seconds >= self.alert_manager.websocket_stale_critical_seconds:
            risk_score += 25
            precursor_count += 1
        elif snapshot.ws_max_age_seconds >= self.alert_manager.websocket_stale_warning_seconds:
            risk_score += 15
            precursor_count += 1

        # Check HA sync
        if snapshot.ha_sync_latency_ms >= self.alert_manager.ha_sync_latency_critical_ms:
            risk_score += 25
            precursor_count += 1
        elif snapshot.ha_sync_latency_ms >= self.alert_manager.ha_sync_latency_warning_ms:
            risk_score += 15
            precursor_count += 1

        # Check exceptions
        if snapshot.exception_rate_percent >= self.alert_manager.exception_rate_critical_percent:
            risk_score += 25
            precursor_count += 1

        # Cascade bonus (multiple precursors)
        if precursor_count >= 2:
            risk_score = min(100.0, risk_score * 1.5)

        return min(100.0, risk_score)

    def get_system_health(self) -> dict:
        """Get overall system health.

        Returns:
            Dictionary with health status
        """
        snapshot = self.metrics_collector.get_current_snapshot()
        if not snapshot:
            return {
                "status": "UNKNOWN",
                "message": "No metrics collected yet",
            }

        risk_score = self.get_cascade_risk_score()
        alerts = self.alert_manager.get_alert_summary()

        if risk_score >= 75:
            status = "CRITICAL"
            health = "Cascade failure risk HIGH"
        elif risk_score >= 50:
            status = "WARNING"
            health = "Multiple precursors detected"
        elif risk_score >= 25:
            status = "CAUTION"
            health = "Monitor closely"
        else:
            status = "HEALTHY"
            health = "All systems nominal"

        return {
            "status": status,
            "risk_score": risk_score,
            "health_message": health,
            "memory_percent": snapshot.memory_percent,
            "websocket_age_seconds": snapshot.ws_max_age_seconds,
            "ha_sync_latency_ms": snapshot.ha_sync_latency_ms,
            "exception_rate_percent": snapshot.exception_rate_percent,
            "alert_counts": alerts["by_severity"],
        }


# Global monitoring instance
_monitoring_loop: Optional[Phase2MonitoringLoop] = None


def get_phase2_monitoring() -> Phase2MonitoringLoop:
    """Get or create global monitoring loop.

    Returns:
        Phase2MonitoringLoop instance
    """
    global _monitoring_loop
    if _monitoring_loop is None:
        # Initialize components if needed
        metrics = get_phase2_metrics()
        alerts = get_phase2_alert_manager()
        _monitoring_loop = Phase2MonitoringLoop(metrics, alerts)
    return _monitoring_loop


def init_phase2_monitoring() -> Phase2MonitoringLoop:
    """Initialize Phase 2 monitoring.

    Returns:
        Phase2MonitoringLoop instance
    """
    global _monitoring_loop
    metrics = init_phase2_metrics()
    alerts = init_phase2_alert_manager()
    _monitoring_loop = Phase2MonitoringLoop(metrics, alerts)
    logger.info("Phase 2 monitoring initialized")
    return _monitoring_loop


async def sample_alert_handler(alert: Alert) -> None:
    """Sample alert handler for demonstration.

    In production, this would send alerts to:
    - Slack/email
    - Monitoring dashboard
    - HTTP webhook
    - etc.

    Args:
        alert: Alert object
    """
    if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.CASCADE):
        logger.critical(f"🚨 ALERT: {alert.message}")
        logger.critical(f"   Details: {alert.details}")
    elif alert.severity == AlertSeverity.WARNING:
        logger.warning(f"⚠️  WARNING: {alert.message}")
    else:
        logger.info(f"ℹ️  INFO: {alert.message}")
