"""Alert routing for Phase 2 monitoring.

Routes alerts to appropriate handlers based on severity:
- INFO: Log to standard logger
- WARNING: Log to stderr + Slack (optional)
- CRITICAL: Log to stderr + PagerDuty (optional) + Slack
- CASCADE: Log to stderr + PagerDuty + pause trading + emit emergency stop signal

Alert handlers are non-blocking and use asyncio to prevent performance impact.
"""

import asyncio
import logging
import os
from typing import Callable, Optional

from backend.core.phase_2_alerts import Alert, AlertSeverity

logger = logging.getLogger(__name__)


class AlertRouter:
    """Routes alerts to appropriate handlers based on severity.

    Supports multiple routing strategies:
    - Logging (always)
    - Slack webhook (optional)
    - PagerDuty API (optional)
    - Emergency stop callback (CASCADE alerts)
    """

    def __init__(self):
        """Initialize alert router."""
        self.slack_webhook_url: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
        self.pagerduty_key: Optional[str] = os.getenv("PAGERDUTY_INTEGRATION_KEY")
        self.emergency_stop_callback: Optional[Callable] = None
        self.alert_handlers: dict = {
            AlertSeverity.INFO: [],
            AlertSeverity.WARNING: [],
            AlertSeverity.CRITICAL: [],
            AlertSeverity.CASCADE: [],
        }

        logger.info(
            f"Alert Router initialized "
            f"(Slack: {'enabled' if self.slack_webhook_url else 'disabled'}, "
            f"PagerDuty: {'enabled' if self.pagerduty_key else 'disabled'})"
        )

    def register_handler(
        self, severity: AlertSeverity, handler: Callable
    ) -> None:
        """Register a custom alert handler.

        Args:
            severity: Alert severity level to handle
            handler: Async function that receives Alert object
        """
        self.alert_handlers[severity].append(handler)
        logger.info(f"Alert handler registered for {severity.value}: {handler.__name__}")

    def set_emergency_stop_callback(self, callback: Callable) -> None:
        """Set callback for CASCADE alerts to trigger emergency stop.

        Args:
            callback: Async function to call on CASCADE alert
        """
        self.emergency_stop_callback = callback
        logger.info("Emergency stop callback registered")

    async def route_alert(self, alert: Alert) -> None:
        """Route alert to appropriate handlers.

        Non-blocking - spawns async tasks to handle routing.

        Args:
            alert: Alert object to route
        """
        try:
            # Log alert (always)
            await self._log_alert(alert)

            # Route to specific handlers
            if alert.severity == AlertSeverity.CASCADE:
                await self._handle_cascade_alert(alert)
            elif alert.severity == AlertSeverity.CRITICAL:
                await self._handle_critical_alert(alert)
            elif alert.severity == AlertSeverity.WARNING:
                await self._handle_warning_alert(alert)
            else:
                await self._handle_info_alert(alert)

            # Call custom handlers (non-blocking)
            await self._call_custom_handlers(alert)

        except Exception as e:
            logger.error(f"Error routing alert: {e}", exc_info=True)

    async def _log_alert(self, alert: Alert) -> None:
        """Log alert to standard logger."""
        log_func = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.critical,
            AlertSeverity.CASCADE: logger.critical,
        }.get(alert.severity, logger.info)

        log_func(
            f"[{alert.alert_type.upper()}] {alert.message} | "
            f"Details: {alert.details}"
        )

    async def _handle_cascade_alert(self, alert: Alert) -> None:
        """Handle CASCADE alert with emergency response.

        Steps:
        1. Log to stderr (visible in systemd journal)
        2. Send to PagerDuty for on-call team
        3. Send to Slack for visibility
        4. Call emergency stop callback
        """
        logger.critical("🚨 CASCADE ALERT - EMERGENCY RESPONSE ACTIVATED")

        # Send to PagerDuty (blocking up to timeout)
        if self.pagerduty_key:
            asyncio.create_task(self._send_pagerduty_alert(alert, is_cascade=True))

        # Send to Slack
        if self.slack_webhook_url:
            asyncio.create_task(self._send_slack_alert(alert))

        # Trigger emergency stop
        if self.emergency_stop_callback:
            try:
                asyncio.create_task(self.emergency_stop_callback(alert))
            except Exception as e:
                logger.error(f"Emergency stop callback failed: {e}")

    async def _handle_critical_alert(self, alert: Alert) -> None:
        """Handle CRITICAL alert.

        Steps:
        1. Log to stderr
        2. Send to PagerDuty
        3. Send to Slack
        """
        logger.critical(f"🔴 CRITICAL ALERT: {alert.message}")

        # Send to PagerDuty
        if self.pagerduty_key:
            asyncio.create_task(self._send_pagerduty_alert(alert))

        # Send to Slack
        if self.slack_webhook_url:
            asyncio.create_task(self._send_slack_alert(alert))

    async def _handle_warning_alert(self, alert: Alert) -> None:
        """Handle WARNING alert.

        Steps:
        1. Log to stderr
        2. Send to Slack (if enabled)
        """
        logger.warning(f"⚠️  WARNING: {alert.message}")

        # Send to Slack
        if self.slack_webhook_url:
            asyncio.create_task(self._send_slack_alert(alert))

    async def _handle_info_alert(self, alert: Alert) -> None:
        """Handle INFO alert.

        Steps:
        1. Log to standard logger only
        """
        logger.info(f"ℹ️  INFO: {alert.message}")

    async def _send_slack_alert(self, alert: Alert) -> None:
        """Send alert to Slack webhook.

        Non-blocking - timeout after 5 seconds to prevent blocking.

        Args:
            alert: Alert object to send
        """
        if not self.slack_webhook_url:
            return

        try:
            import httpx

            color_map = {
                AlertSeverity.INFO: "#36a64f",  # Green
                AlertSeverity.WARNING: "#ff9900",  # Orange
                AlertSeverity.CRITICAL: "#ff0000",  # Red
                AlertSeverity.CASCADE: "#ff0000",  # Red
            }

            color = color_map.get(alert.severity, "#999999")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{alert.severity.upper()}: {alert.alert_type}",
                        "text": alert.message,
                        "fields": [
                            {"title": "Timestamp", "value": alert.timestamp, "short": True},
                            {"title": "Type", "value": alert.alert_type, "short": True},
                        ],
                        "footer": "Crypto Daytrading Platform - Phase 2 Monitoring",
                    }
                ]
            }

            # Add details if present
            if alert.details:
                for key, value in list(alert.details.items())[:3]:  # Max 3 fields
                    payload["attachments"][0]["fields"].append({
                        "title": str(key),
                        "value": str(value),
                        "short": True,
                    })

            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.slack_webhook_url, json=payload)
                logger.debug(f"Slack alert sent for {alert.alert_type}")

        except asyncio.TimeoutError:
            logger.warning("Slack alert send timed out (5s)")
        except Exception as e:
            logger.warning(f"Failed to send Slack alert: {e}")

    async def _send_pagerduty_alert(
        self, alert: Alert, is_cascade: bool = False
    ) -> None:
        """Send alert to PagerDuty for incident management.

        Non-blocking - timeout after 10 seconds to prevent blocking.

        Args:
            alert: Alert object to send
            is_cascade: Whether this is a CASCADE alert (affects urgency)
        """
        if not self.pagerduty_key:
            return

        try:
            import httpx

            # CASCADE alerts are CRITICAL severity in PagerDuty
            # CRITICAL alerts are WARNING severity
            pagerduty_severity = "critical" if is_cascade else "warning"

            payload = {
                "routing_key": self.pagerduty_key,
                "event_action": "trigger",
                "dedup_key": f"crypto-daytrading-{alert.alert_type}",
                "payload": {
                    "summary": f"[{alert.severity.upper()}] {alert.message}",
                    "severity": pagerduty_severity,
                    "source": "crypto-daytrading-monitoring",
                    "custom_details": {
                        "alert_type": alert.alert_type,
                        "timestamp": alert.timestamp,
                        "details": alert.details,
                    },
                },
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                )
                if resp.status_code == 202:
                    logger.debug(f"PagerDuty alert sent for {alert.alert_type}")
                else:
                    logger.warning(
                        f"PagerDuty alert failed (status {resp.status_code})"
                    )

        except asyncio.TimeoutError:
            logger.warning("PagerDuty alert send timed out (10s)")
        except Exception as e:
            logger.warning(f"Failed to send PagerDuty alert: {e}")

    async def _call_custom_handlers(self, alert: Alert) -> None:
        """Call all registered custom handlers for this severity level.

        Non-blocking - spawns tasks for each handler.

        Args:
            alert: Alert object
        """
        handlers = self.alert_handlers.get(alert.severity, [])
        for handler in handlers:
            asyncio.create_task(self._call_handler_safe(handler, alert))

    async def _call_handler_safe(
        self, handler: Callable, alert: Alert
    ) -> None:
        """Safely call a handler, catching any exceptions.

        Args:
            handler: Async function to call
            alert: Alert object to pass
        """
        try:
            await handler(alert)
        except Exception as e:
            logger.error(f"Error in alert handler {handler.__name__}: {e}")


# Global alert router instance
_alert_router: Optional[AlertRouter] = None


def get_alert_router() -> AlertRouter:
    """Get or create global alert router.

    Returns:
        AlertRouter instance
    """
    global _alert_router
    if _alert_router is None:
        _alert_router = AlertRouter()
    return _alert_router


def init_alert_router() -> AlertRouter:
    """Initialize alert router.

    Returns:
        AlertRouter instance
    """
    global _alert_router
    _alert_router = AlertRouter()
    return _alert_router


async def setup_alert_routing() -> None:
    """Set up alert routing in Phase 2 monitoring system.

    This is called during application startup to connect the alert router
    to the Phase 2 monitoring loop.
    """
    try:
        from backend.core.phase_2_monitoring import get_phase2_monitoring
        from backend.core.emergency_stop import trigger_emergency_stop

        router = get_alert_router()
        monitoring = get_phase2_monitoring()

        # Register router's alert handler
        async def router_handler(alert: Alert) -> None:
            await router.route_alert(alert)

        monitoring.register_alert_handler(router_handler)

        # Set emergency stop callback for CASCADE alerts
        router.set_emergency_stop_callback(trigger_emergency_stop)

        logger.info("✅ Alert routing set up successfully")

    except Exception as e:
        logger.error(f"Failed to set up alert routing: {e}")
