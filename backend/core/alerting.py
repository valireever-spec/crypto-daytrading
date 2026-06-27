"""Alert notifications for critical events."""

import logging
import os
import json
from typing import Dict, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


class AlertManager:
    """Manage alerts and notifications for critical events."""

    def __init__(self):
        """Initialize alert manager."""
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
        self.email_enabled = os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true"
        self.alert_queue = []

    async def alert_circuit_breaker_open(self, reason: str) -> bool:
        """Alert that circuit breaker has opened."""
        try:
            message = f"🚨 CIRCUIT BREAKER OPENED: {reason}"
            logger.critical(message)
            await self._send_slack_alert(message, "danger")
            return True
        except Exception as e:
            logger.error(f"Failed to send circuit breaker alert: {e}")
            return False

    async def alert_primary_unhealthy(self, reason: str) -> bool:
        """Alert that PRIMARY machine is unhealthy."""
        try:
            message = f"🚨 PRIMARY UNHEALTHY: {reason}"
            logger.critical(message)
            await self._send_slack_alert(message, "danger")
            return True
        except Exception as e:
            logger.error(f"Failed to send primary health alert: {e}")
            return False

    async def alert_daily_loss_limit_exceeded(
        self, daily_pnl: float, limit_pct: float
    ) -> bool:
        """Alert that daily loss limit has been exceeded."""
        try:
            message = f"🛑 DAILY LOSS LIMIT EXCEEDED: €{abs(daily_pnl):.2f} ({limit_pct:.1f}% limit)"
            logger.critical(message)
            await self._send_slack_alert(message, "danger")
            return True
        except Exception as e:
            logger.error(f"Failed to send loss limit alert: {e}")
            return False

    async def alert_data_quality_critical(self, score: float) -> bool:
        """Alert that data quality has dropped to critical levels."""
        try:
            message = f"⚠️ DATA QUALITY CRITICAL: {score:.0f}% (threshold: 30%)"
            logger.warning(message)
            await self._send_slack_alert(message, "warning")
            return True
        except Exception as e:
            logger.error(f"Failed to send data quality alert: {e}")
            return False

    async def alert_profit_target_hit(self, symbol: str, pnl_pct: float) -> bool:
        """Alert that a profit target has been hit."""
        try:
            message = f"✅ PROFIT TARGET HIT: {symbol} ({pnl_pct:.2f}%)"
            logger.info(message)
            # Don't alert on successful trades (too spammy)
            return True
        except Exception as e:
            logger.error(f"Failed to log profit alert: {e}")
            return False

    async def alert_stop_loss_hit(self, symbol: str, pnl_pct: float) -> bool:
        """Alert that a stop loss has been triggered."""
        try:
            message = f"🛑 STOP LOSS HIT: {symbol} ({pnl_pct:.2f}%)"
            logger.warning(message)
            await self._send_slack_alert(message, "warning")
            return True
        except Exception as e:
            logger.error(f"Failed to send stop loss alert: {e}")
            return False

    async def _send_slack_alert(self, message: str, severity: str = "info") -> bool:
        """Send alert to Slack webhook."""
        if not self.slack_webhook:
            logger.debug("Slack webhook not configured, skipping alert")
            return False

        try:
            import aiohttp

            color_map = {
                "info": "#36a64f",      # Green
                "warning": "#ff9900",   # Orange
                "danger": "#ff0000",    # Red
            }

            payload = {
                "attachments": [
                    {
                        "color": color_map.get(severity, "#0099ff"),
                        "title": "Crypto Trading Alert",
                        "text": message,
                        "footer": "Crypto Daytrading System",
                        "ts": int(datetime.utcnow().timestamp()),
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Slack alert sent: {message}")
                        return True
                    else:
                        logger.error(f"❌ Slack alert failed: HTTP {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False


# Global instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def init_alert_manager() -> AlertManager:
    """Initialize alert manager."""
    global _alert_manager
    _alert_manager = AlertManager()
    logger.info("Alert manager initialized")
    if _alert_manager.slack_webhook:
        logger.info("✅ Slack alerts enabled")
    else:
        logger.warning(
            "⚠️ Slack alerts disabled (set SLACK_WEBHOOK_URL to enable)"
        )
    return _alert_manager
