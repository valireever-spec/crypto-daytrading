"""Alert system for production incidents."""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Alert delivery channels."""
    SLACK = "slack"
    EMAIL = "email"
    LOG = "log"
    MEMORY = "memory"


@dataclass
class Alert:
    """Alert event."""
    id: str
    severity: AlertSeverity
    title: str
    message: str
    service: str
    timestamp: str
    resolved: bool = False
    resolution_time: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.rules: List[Dict] = self._init_rules()
        self.max_history = 1000

    def _init_rules(self) -> List[Dict]:
        """Initialize alert rules."""
        return [
            {
                "name": "high_memory",
                "condition": "memory > 90",
                "severity": AlertSeverity.CRITICAL,
                "enabled": True
            },
            {
                "name": "high_cpu",
                "condition": "cpu > 90",
                "severity": AlertSeverity.WARNING,
                "enabled": True
            },
            {
                "name": "disk_full",
                "condition": "disk > 90",
                "severity": AlertSeverity.CRITICAL,
                "enabled": True
            },
            {
                "name": "db_disconnect",
                "condition": "database.healthy == False",
                "severity": AlertSeverity.CRITICAL,
                "enabled": True
            },
            {
                "name": "api_down",
                "condition": "api.healthy == False",
                "severity": AlertSeverity.CRITICAL,
                "enabled": True
            },
            {
                "name": "stale_data",
                "condition": "data_age > 3600",
                "severity": AlertSeverity.WARNING,
                "enabled": True
            }
        ]

    async def create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        service: str,
        alert_id: str = None
    ) -> Alert:
        """Create a new alert."""
        if alert_id is None:
            alert_id = f"{service}_{len(self.alerts)}"

        alert = Alert(
            id=alert_id,
            severity=severity,
            title=title,
            message=message,
            service=service,
            timestamp=datetime.utcnow().isoformat()
        )

        self.alerts.append(alert)
        if len(self.alerts) > self.max_history:
            self.alerts.pop(0)

        # Track active critical/warning alerts
        if severity in [AlertSeverity.CRITICAL, AlertSeverity.WARNING]:
            self.active_alerts[alert_id] = alert

        logger.warning(f"[{severity.upper()}] {title}: {message}")

        # Send notifications
        await self._send_notifications(alert)

        return alert

    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolution_time = datetime.utcnow().isoformat()
            del self.active_alerts[alert_id]

            logger.info(f"Alert resolved: {alert.title}")
            return True

        return False

    async def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications."""
        channels = self._get_channels_for_severity(alert.severity)

        for channel in channels:
            try:
                if channel == AlertChannel.SLACK:
                    await self._send_slack(alert)
                elif channel == AlertChannel.EMAIL:
                    await self._send_email(alert)
                elif channel == AlertChannel.LOG:
                    logger.warning(f"Alert: {alert.title} - {alert.message}")
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")

    def _get_channels_for_severity(self, severity: AlertSeverity) -> List[AlertChannel]:
        """Determine which channels to use based on severity."""
        if severity == AlertSeverity.CRITICAL:
            return [AlertChannel.LOG, AlertChannel.SLACK]
        elif severity == AlertSeverity.WARNING:
            return [AlertChannel.LOG]
        else:
            return [AlertChannel.LOG]

    async def _send_slack(self, alert: Alert) -> None:
        """Send alert to Slack."""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("Slack webhook not configured, skipping")
            return

        try:
            import aiohttp

            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9900",
                AlertSeverity.CRITICAL: "#ff0000"
            }.get(alert.severity, "#808080")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.message,
                        "fields": [
                            {"title": "Service", "value": alert.service, "short": True},
                            {"title": "Severity", "value": alert.severity.value, "short": True},
                            {"title": "Time", "value": alert.timestamp, "short": False}
                        ]
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Slack notification failed: {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    async def _send_email(self, alert: Alert) -> None:
        """Send alert via email."""
        email_to = os.getenv("ALERT_EMAIL_TO")
        if not email_to:
            logger.debug("Alert email not configured, skipping")
            return

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_server = os.getenv("SMTP_SERVER", "localhost")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_pass = os.getenv("SMTP_PASS", "")

            msg = MIMEMultipart()
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"
            msg["From"] = smtp_user or "alerts@trading-bot.local"
            msg["To"] = email_to

            body = f"""
Alert Details:
- Service: {alert.service}
- Severity: {alert.severity.value}
- Message: {alert.message}
- Time: {alert.timestamp}
            """

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.debug(f"Email notification sent to {email_to}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self.alerts[-limit:]

    def get_alerts_by_service(self, service: str) -> List[Alert]:
        """Get alerts for a specific service."""
        return [a for a in self.alerts if a.service == service]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts of a specific severity."""
        return [a for a in self.alerts if a.severity == severity]


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def init_alert_manager() -> AlertManager:
    """Initialize alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
        logger.info("Alert manager initialized")
    return _alert_manager


def get_alert_manager() -> Optional[AlertManager]:
    """Get alert manager instance."""
    return _alert_manager
