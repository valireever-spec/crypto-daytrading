"""Phase 2: HA Cascade Prevention - Alert Configuration Module.

This module defines alert thresholds and cascade detection logic. It monitors
for precursor conditions that typically lead to cascade failures:

1. Memory pressure (>75% → WARNING, >85% → CRITICAL)
2. WebSocket staleness (>30s → WARNING)
3. HA sync latency (>5s → WARNING, >10s → CRITICAL)
4. Exception spike (>1% error rate → CRITICAL)

When multiple precursors occur together, the CASCADE alert is raised to trigger
emergency response (reduce load, prepare for failover, etc).
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    CASCADE = "cascade"  # Multi-factor cascade failure precursor


class Alert:
    """Represents a single alert."""

    def __init__(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize alert.

        Args:
            alert_type: Type of alert (e.g., 'memory_pressure', 'websocket_stale')
            severity: Alert severity level
            message: Human-readable message
            details: Additional details for diagnosis
        """
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.alert_type,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict())


class Phase2AlertManager:
    """Manages alert generation and cascade detection.

    Alert Thresholds (based on production trading requirements):
    - Memory: >75% = WARNING, >85% = CRITICAL (split-brain risk)
    - WebSocket: >30s stale = WARNING (data gap)
    - HA Sync: >5s latency = WARNING, >10s = CRITICAL
    - Exceptions: >1% error rate = CRITICAL (system instability)

    Cascade Detection:
    - Triggers when >=2 precursor conditions occur simultaneously
    - Example: WebSocket stale + HA sync failure = PREPARE FOR FAILOVER
    """

    def __init__(self):
        """Initialize Phase 2 alert manager."""
        # Alert thresholds
        self.memory_warning_percent = 75
        self.memory_critical_percent = 85

        self.websocket_stale_warning_seconds = 30
        self.websocket_stale_critical_seconds = 60

        self.ha_sync_latency_warning_ms = 5000
        self.ha_sync_latency_critical_ms = 10000

        self.exception_rate_critical_percent = 1.0

        # Alert history (for cascade detection)
        self.recent_alerts: List[Alert] = []
        self.max_recent_alerts = 100

        # Alert routing callbacks
        self.alert_callbacks: List[callable] = []

        logger.info("Phase 2 Alert Manager initialized")

    def register_alert_callback(self, callback: callable) -> None:
        """Register a callback to receive alerts.

        Args:
            callback: Async function that receives Alert object
        """
        self.alert_callbacks.append(callback)
        logger.info(f"Alert callback registered: {callback.__name__}")

    async def send_alert(self, alert: Alert) -> None:
        """Send an alert to all registered handlers.

        Args:
            alert: Alert object to send
        """
        # Log alert
        logger.log(
            logging.WARNING
            if alert.severity == AlertSeverity.WARNING
            else logging.CRITICAL
            if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.CASCADE)
            else logging.INFO,
            f"[{alert.severity.upper()}] {alert.message}",
        )

        # Store in history for cascade detection
        self.recent_alerts.append(alert)
        if len(self.recent_alerts) > self.max_recent_alerts:
            self.recent_alerts.pop(0)

        # Send to all handlers
        for callback in self.alert_callbacks:
            try:
                if callable(callback):
                    await callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback {callback}: {e}")

    def check_memory_pressure(self, memory_percent: float) -> Optional[Alert]:
        """Check for memory pressure alert.

        Args:
            memory_percent: Current memory usage percentage

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if memory_percent >= self.memory_critical_percent:
            return Alert(
                alert_type="memory_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"CRITICAL: Memory {memory_percent:.1f}% (split-brain risk!)",
                details={
                    "current": memory_percent,
                    "threshold": self.memory_critical_percent,
                    "risk": "State divergence between PRIMARY and BACKUP",
                },
            )
        elif memory_percent >= self.memory_warning_percent:
            return Alert(
                alert_type="memory_warning",
                severity=AlertSeverity.WARNING,
                message=f"WARNING: Memory {memory_percent:.1f}% approaching limit",
                details={
                    "current": memory_percent,
                    "threshold": self.memory_warning_percent,
                    "action": "Monitor closely; consider reducing load",
                },
            )
        return None

    def check_websocket_staleness(
        self, max_age_seconds: float, stale_symbols: List[str]
    ) -> Optional[Alert]:
        """Check for WebSocket data staleness.

        Args:
            max_age_seconds: Max age of any symbol's data
            stale_symbols: List of symbols with stale data

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if max_age_seconds >= self.websocket_stale_critical_seconds:
            return Alert(
                alert_type="websocket_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"CRITICAL: WebSocket stale {max_age_seconds:.1f}s (data gap!)",
                details={
                    "max_age_seconds": max_age_seconds,
                    "stale_symbols": stale_symbols,
                    "threshold": self.websocket_stale_critical_seconds,
                    "risk": "Cannot calculate positions; trading halted",
                },
            )
        elif max_age_seconds >= self.websocket_stale_warning_seconds:
            return Alert(
                alert_type="websocket_stale",
                severity=AlertSeverity.WARNING,
                message=f"WARNING: WebSocket stale {max_age_seconds:.1f}s",
                details={
                    "max_age_seconds": max_age_seconds,
                    "stale_symbols": stale_symbols,
                    "threshold": self.websocket_stale_warning_seconds,
                },
            )
        return None

    def check_ha_sync_latency(self, latency_ms: float) -> Optional[Alert]:
        """Check for HA sync latency issues.

        Args:
            latency_ms: Last sync latency in milliseconds

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if latency_ms >= self.ha_sync_latency_critical_ms:
            return Alert(
                alert_type="ha_sync_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"CRITICAL: HA sync latency {latency_ms:.0f}ms (network issue?)",
                details={
                    "latency_ms": latency_ms,
                    "threshold": self.ha_sync_latency_critical_ms,
                    "risk": "BACKUP falling behind PRIMARY; failover risky",
                },
            )
        elif latency_ms >= self.ha_sync_latency_warning_ms:
            return Alert(
                alert_type="ha_sync_slow",
                severity=AlertSeverity.WARNING,
                message=f"WARNING: HA sync latency {latency_ms:.0f}ms",
                details={
                    "latency_ms": latency_ms,
                    "threshold": self.ha_sync_latency_warning_ms,
                    "action": "Monitor network; ensure sufficient bandwidth",
                },
            )
        return None

    def check_exception_spike(self, exception_rate_percent: float) -> Optional[Alert]:
        """Check for exception rate spike.

        Args:
            exception_rate_percent: Exception rate as percentage

        Returns:
            Alert if threshold exceeded, None otherwise
        """
        if exception_rate_percent >= self.exception_rate_critical_percent:
            return Alert(
                alert_type="exception_spike",
                severity=AlertSeverity.CRITICAL,
                message=f"CRITICAL: Exception rate {exception_rate_percent:.2f}% (instability!)",
                details={
                    "rate_percent": exception_rate_percent,
                    "threshold": self.exception_rate_critical_percent,
                    "risk": "System instability; cascade likely",
                },
            )
        return None

    def check_cascade_precursors(self, metrics_snapshot: Dict[str, Any]) -> List[Alert]:
        """Check for cascade failure precursors.

        Cascade detection combines multiple warning signs:
        1. WebSocket stale (data flow stopped)
        2. HA sync failure (state sync failed)
        3. Memory pressure (resource exhaustion)
        4. Exception spike (system instability)

        When >=2 precursors occur together, alerts about cascade risk.

        Args:
            metrics_snapshot: Current metrics snapshot dict

        Returns:
            List of alerts (may be empty, single, or cascade)
        """
        alerts = []
        precursor_count = 0
        precursor_details = []

        # Check each precursor condition
        memory_percent = metrics_snapshot.get("memory", {}).get("percent", 0)
        memory_alert = self.check_memory_pressure(memory_percent)
        if memory_alert:
            alerts.append(memory_alert)
            precursor_count += 1
            precursor_details.append("memory_pressure")

        ws_max_age = metrics_snapshot.get("websocket", {}).get("max_age_seconds", 0)
        ws_stale = metrics_snapshot.get("websocket", {}).get("stale_symbols", [])
        ws_alert = self.check_websocket_staleness(ws_max_age, ws_stale)
        if ws_alert:
            alerts.append(ws_alert)
            precursor_count += 1
            precursor_details.append("websocket_stale")

        ha_latency = metrics_snapshot.get("ha_sync", {}).get("latency_ms", 0)
        ha_alert = self.check_ha_sync_latency(ha_latency)
        if ha_alert:
            alerts.append(ha_alert)
            precursor_count += 1
            precursor_details.append("ha_sync_slow")

        exception_rate = (
            metrics_snapshot.get("exceptions", {}).get("rate_percent", 0)
        )
        exc_alert = self.check_exception_spike(exception_rate)
        if exc_alert:
            alerts.append(exc_alert)
            precursor_count += 1
            precursor_details.append("exception_spike")

        # If multiple precursors, raise CASCADE alert
        if precursor_count >= 2:
            cascade_alert = Alert(
                alert_type="cascade_precursor",
                severity=AlertSeverity.CASCADE,
                message=f"⚠️ CASCADE RISK DETECTED: {precursor_count} precursors active ({', '.join(precursor_details)})",
                details={
                    "precursor_count": precursor_count,
                    "precursors": precursor_details,
                    "memory_percent": memory_percent,
                    "ws_max_age_seconds": ws_max_age,
                    "ha_latency_ms": ha_latency,
                    "exception_rate_percent": exception_rate,
                    "recommendation": "Reduce load immediately; prepare for failover",
                },
            )
            alerts.append(cascade_alert)

        return alerts

    def analyze_metrics(self, metrics_snapshot: Dict[str, Any]) -> List[Alert]:
        """Analyze metrics and generate all applicable alerts.

        This is the main entry point for alert generation.

        Args:
            metrics_snapshot: Current metrics snapshot dict

        Returns:
            List of Alert objects (may be empty)
        """
        alerts = self.check_cascade_precursors(metrics_snapshot)
        return alerts

    def get_recent_alerts(
        self, severity: Optional[AlertSeverity] = None, minutes: int = 60
    ) -> List[Alert]:
        """Get recent alerts, optionally filtered by severity.

        Args:
            severity: Optional severity level to filter by
            minutes: How many minutes of history to include

        Returns:
            List of Alert objects
        """
        cutoff_time = datetime.utcnow().timestamp() - minutes * 60

        alerts = []
        for alert in self.recent_alerts:
            try:
                alert_time = datetime.fromisoformat(alert.timestamp).timestamp()
                if alert_time >= cutoff_time:
                    if severity is None or alert.severity == severity:
                        alerts.append(alert)
            except Exception as e:
                logger.error(f"Error filtering alert: {e}")

        return alerts

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alerts.

        Returns:
            Dictionary with alert statistics
        """
        by_severity = {
            "info": [],
            "warning": [],
            "critical": [],
            "cascade": [],
        }

        for alert in self.recent_alerts:
            by_severity[alert.severity.value].append(alert.to_dict())

        return {
            "total_alerts": len(self.recent_alerts),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "recent": by_severity,
        }


# Global instance
_alert_manager: Optional[Phase2AlertManager] = None


def get_phase2_alert_manager() -> Phase2AlertManager:
    """Get or create global Phase 2 alert manager.

    Returns:
        Phase2AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = Phase2AlertManager()
    return _alert_manager


def init_phase2_alert_manager() -> Phase2AlertManager:
    """Initialize Phase 2 alert manager.

    Returns:
        Phase2AlertManager instance
    """
    global _alert_manager
    _alert_manager = Phase2AlertManager()
    logger.info("Phase 2 alert manager initialized")
    return _alert_manager
