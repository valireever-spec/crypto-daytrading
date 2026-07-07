"""Alert notifications for critical events."""

import logging
import os
import time
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
        # Telegram configuration
        self._telegram_token_val = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "").strip()
        self._telegram_chat_id_val = os.getenv("ALERT_TELEGRAM_CHAT_ID", "").strip()
        # Alert deduplication: time-based cooldown per symbol (1 min between same alert type)
        self._last_alert_time = {}  # {symbol: timestamp}
        self._alert_cooldown = 60  # seconds - prevent same alert type repeating
        # Trade statistics for alerts
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def _telegram_token(self) -> str:
        """Get Telegram bot token."""
        return self._telegram_token_val

    def _telegram_chat_id(self) -> str:
        """Get Telegram chat ID."""
        return self._telegram_chat_id_val

    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self._telegram_token() and self._telegram_chat_id())

    def _should_send_alert(self, symbol: str) -> bool:
        """
        Check if we should send an alert (time-based deduplication).
        Only send if 60+ seconds have passed since last alert for this symbol.
        This prevents spam even if exact same loss % changes slightly (0.10% → 0.11%).
        """
        now = time.time()
        last_time = self._last_alert_time.get(symbol, 0)
        elapsed = now - last_time
        if elapsed >= self._alert_cooldown:
            self._last_alert_time[symbol] = now
            return True
        logger.debug(f"Alert deduplication: {symbol} alert sent {elapsed:.0f}s ago, skipping")
        return False

    async def alert_circuit_breaker_open(self, reason: str) -> bool:
        """Alert that circuit breaker has opened."""
        try:
            message = f"🚨 CIRCUIT BREAKER OPENED: {reason}"
            logger.critical(message)
            await self._send_slack_alert(message, "danger")
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "danger")
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
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "danger")
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
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "danger")
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
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "warning")
            return True
        except Exception as e:
            logger.error(f"Failed to send data quality alert: {e}")
            return False

    async def alert_trade_entry(self, symbol: str, quantity: float, entry_price: float,
                                remaining_cash: float, signal_reason: str) -> bool:
        """Alert when a trade entry is executed."""
        try:
            position_value = quantity * entry_price
            utc_time = datetime.utcnow().strftime("%H:%M:%S UTC")
            message = (
                f"📍 ENTRY: {symbol} ({utc_time})\n"
                f"   Price: ${entry_price:.2f}\n"
                f"   Qty: {quantity:.4f}\n"
                f"   Value: ${position_value:.2f}\n"
                f"   Cash Left: €{remaining_cash:.2f}\n"
                f"   Signal: {signal_reason}"
            )
            logger.info(message.replace("\n", " "))

            await self._send_slack_alert(message, "info")
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "info")
            return True
        except Exception as e:
            logger.error(f"Failed to send entry alert: {e}")
            return False

    async def alert_trade_exit(self, symbol: str, pnl: float, pnl_pct: float,
                               remaining_cash: float, hold_time_sec: int, is_win: bool) -> bool:
        """Alert when a trade exit is executed (profit or loss)."""
        try:
            self.total_trades += 1
            if is_win:
                self.winning_trades += 1
                emoji = "✅"
            else:
                self.losing_trades += 1
                emoji = "❌"

            win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
            hold_min = hold_time_sec // 60
            hold_sec = hold_time_sec % 60
            utc_time = datetime.utcnow().strftime("%H:%M:%S UTC")

            message = (
                f"{emoji} EXIT: {symbol} ({utc_time})\n"
                f"   P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)\n"
                f"   Cash: €{remaining_cash:.2f}\n"
                f"   Hold: {hold_min}m {hold_sec}s\n"
                f"   Record: {self.winning_trades}W / {self.losing_trades}L ({win_rate:.0f}%)"
            )
            logger.info(message.replace("\n", " "))

            await self._send_slack_alert(message, "info" if is_win else "warning")
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "info" if is_win else "warning")
            return True
        except Exception as e:
            logger.error(f"Failed to send exit alert: {e}")
            return False

    async def alert_profit_target_hit(self, symbol: str, pnl_pct: float) -> bool:
        """Alert that a profit target has been hit (legacy - use alert_trade_exit instead)."""
        try:
            # Just log, don't send alert (real alert sent by alert_trade_exit)
            logger.info(f"✅ PROFIT TARGET HIT: {symbol} ({pnl_pct:.2f}%)")
            return True
        except Exception as e:
            logger.error(f"Failed to log profit alert: {e}")
            return False

    async def alert_stop_loss_hit(self, symbol: str, pnl_pct: float) -> bool:
        """Alert that a stop loss has been triggered (legacy - use alert_trade_exit instead)."""
        try:
            # Deduplication: max 1 alert per symbol per 60 seconds
            if not self._should_send_alert(symbol):
                logger.debug(f"Deduplication: {symbol} stop loss alert sent recently, skipping")
                return False

            message = f"🛑 STOP LOSS HIT: {symbol} ({pnl_pct:.2f}%)"
            logger.warning(message)

            await self._send_slack_alert(message, "warning")
            if self.is_telegram_configured():
                await self._send_telegram_alert(message, "warning")
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

    async def _send_telegram_alert(self, message: str, severity: str = "info") -> bool:
        """Send alert to Telegram (both PRIMARY and BACKUP send alerts)."""
        # Both machines send alerts so user has visibility during failover
        # BACKUP alerts are prefixed with [BACKUP] so user knows PRIMARY is down
        if not self.is_telegram_configured():
            logger.debug("Telegram not configured, skipping alert")
            return False

        try:
            import aiohttp

            machine_id = os.getenv("MACHINE_ID", "main")
            machine_label = "[PRIMARY]" if machine_id == "main" else "[BACKUP 🚨]"

            # Prefix message with machine label for clarity
            prefixed_message = f"{machine_label} {message}"

            token = self._telegram_token()
            chat_id = self._telegram_chat_id()

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": prefixed_message,
                "parse_mode": "HTML"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Telegram alert sent: {message[:50]}...")
                        return True
                    else:
                        logger.error(f"❌ Telegram alert failed: HTTP {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False

    async def test_telegram(self) -> Dict[str, bool]:
        """Test Telegram configuration."""
        if not self.is_telegram_configured():
            return {"success": False, "error": "Telegram not configured"}

        machine_id = os.getenv("MACHINE_ID", "main")
        machine_label = "PRIMARY" if machine_id == "main" else "BACKUP"
        test_msg = f"🧪 Test alert from {machine_label} (crypto-daytrading)"
        result = await self._send_telegram_alert(test_msg, "info")
        return {"success": result}


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
    if _alert_manager.is_telegram_configured():
        logger.info("✅ Telegram alerts enabled")
    else:
        logger.warning(
            "⚠️ Telegram alerts disabled (set ALERT_TELEGRAM_BOT_TOKEN and ALERT_TELEGRAM_CHAT_ID to enable)"
        )
    return _alert_manager
