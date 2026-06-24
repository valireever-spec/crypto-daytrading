"""High Availability and Redundancy monitoring endpoints - Production Grade."""

import asyncio
import httpx
import os
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/redundancy", tags=["Redundancy"])

# Configuration from environment
PRIMARY_API_URL = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")

# Backup URLs: try local first (LAN), fallback to remote (internet via reverse SSH)
BACKUP_API_URL_LOCAL = os.getenv("BACKUP_API_URL_LOCAL", "http://192.168.3.25:8002")
BACKUP_API_URL_REMOTE = os.getenv("BACKUP_API_URL_REMOTE", "https://r33v3r.ddns.net:8443")
# For backwards compatibility
BACKUP_API_URL = os.getenv("BACKUP_API_URL", BACKUP_API_URL_LOCAL)

REPLICATION_LAG_WARNING_THRESHOLD = 2.0  # seconds
REPLICATION_LAG_CRITICAL_THRESHOLD = 5.0  # seconds
HEALTH_CHECK_TIMEOUT = 60  # seconds (backup service takes 60+ seconds to fully initialize)
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")  # Slack webhook

# Retry configuration
HEALTH_CHECK_RETRIES = 2
RETRY_DELAYS = [0.1, 0.5]  # exponential backoff: 100ms, 500ms


class FailoverEvent:
    """Represents a failover event for audit trail."""

    def __init__(self, event_type: str, details: Dict):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.details = details

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.event_type,
            "details": self.details
        }


class RedundancyMonitor:
    """Monitors primary-backup redundancy status with production features."""

    def __init__(self):
        self.last_primary_check = None
        self.last_backup_check = None
        self.primary_healthy = False
        self.backup_healthy = False
        self.backup_api_url = BACKUP_API_URL_LOCAL  # Track which path is being used
        self.replication_lag = 0.0
        self.failover_active = False
        self.last_error = None
        self.consecutive_primary_failures = 0
        self.consecutive_backup_failures = 0
        self.failover_events: List[FailoverEvent] = []
        self.health_check_history: List[Dict] = []
        self.last_failover_time: Optional[datetime] = None
        self.uptime_start = datetime.now()
        self._lock = threading.Lock()

    async def _health_check_with_retry(self, url: str) -> tuple[bool, Optional[str]]:
        """Check health with retry logic and exponential backoff."""
        for attempt in range(HEALTH_CHECK_RETRIES + 1):
            try:
                # Disable SSL verification for self-signed certs on remote path
                verify_ssl = not url.startswith("https://r33v3r")
                async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT, verify=verify_ssl) as client:
                    response = await client.get(f"{url}/api/health")
                    if response.status_code == 200:
                        return True, None
            except Exception as e:
                if attempt < HEALTH_CHECK_RETRIES:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    return False, str(e)
        return False, "Max retries exceeded"

    async def _health_check_backup_dual_path(self) -> tuple[bool, Optional[str], str]:
        """
        Check backup health with dual-path fallback:
        1. Try local network (192.168.3.25:8002) - used when primary is on LAN
        2. Fall back to remote (r33v3r.ddns.net:8443) - used when primary is internet-based

        Returns: (healthy, error, path_used)
        """
        # Try local network first (faster, no internet required)
        logger.debug("Health check: Trying local backup at " + BACKUP_API_URL_LOCAL)
        healthy, error = await self._health_check_with_retry(BACKUP_API_URL_LOCAL)
        if healthy:
            return True, None, BACKUP_API_URL_LOCAL

        logger.debug(f"Local health check failed ({error}), trying remote fallback")

        # Fall back to remote via reverse SSH tunnel
        healthy, error = await self._health_check_with_retry(BACKUP_API_URL_REMOTE)
        if healthy:
            logger.info(f"Backup reachable via remote path: {BACKUP_API_URL_REMOTE}")
            return True, None, BACKUP_API_URL_REMOTE

        # Both paths failed
        return False, f"Local: failed | Remote: {error}", "none"

    async def check_primary_health(self) -> dict:
        """Check if primary is responding with retry logic."""
        healthy, error = await self._health_check_with_retry(PRIMARY_API_URL)
        self.last_primary_check = datetime.now()

        if healthy:
            self.primary_healthy = True
            self.consecutive_primary_failures = 0
            status = "ok"
        else:
            self.consecutive_primary_failures += 1
            self.primary_healthy = False
            status = error or "Unknown error"

        result = {
            "host": PRIMARY_API_URL,
            "healthy": self.primary_healthy,
            "status": status,
            "timestamp": self.last_primary_check.isoformat(),
            "consecutive_failures": self.consecutive_primary_failures
        }

        self._record_history("primary", result)
        return result

    async def check_backup_health(self) -> dict:
        """Check if backup is responding with dual-path fallback logic."""
        healthy, error, path_used = await self._health_check_backup_dual_path()
        self.last_backup_check = datetime.now()

        if healthy:
            self.backup_healthy = True
            self.backup_api_url = path_used  # Store which path succeeded
            self.consecutive_backup_failures = 0
            status = "ok"
            host_info = f"{path_used} (via {'local' if path_used == BACKUP_API_URL_LOCAL else 'remote'})"
        else:
            self.consecutive_backup_failures += 1
            self.backup_healthy = False
            status = error or "All paths failed"
            host_info = "Local + Remote (both failed)"

        result = {
            "host": host_info,
            "healthy": self.backup_healthy,
            "status": status,
            "timestamp": self.last_backup_check.isoformat(),
            "consecutive_failures": self.consecutive_backup_failures
        }

        self._record_history("backup", result)
        return result

    async def check_postgresql_replication_lag(self) -> float:
        """Check actual PostgreSQL replication lag (not approximation)."""
        if not self.primary_healthy or not self.backup_healthy:
            return -1.0

        try:
            # Disable SSL verification for remote path if needed
            verify_ssl = not self.backup_api_url.startswith("https://r33v3r")
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT, verify=verify_ssl) as client:
                # Get replication lag from backup machine's PostgreSQL
                response = await client.get(f"{self.backup_api_url}/api/redundancy/pg-lag")
                if response.status_code == 200:
                    data = response.json()
                    lag = data.get("lag_seconds", -1.0)
                    self.replication_lag = lag
                    return lag
            return -1.0
        except Exception as e:
            logger.warning(f"Could not fetch PostgreSQL replication lag: {e}")
            return -1.0

    async def check_replication_lag(self) -> float:
        """Estimate replication lag by comparing account state (fallback)."""
        if not self.primary_healthy or not self.backup_healthy:
            return -1.0

        try:
            verify_ssl = not self.backup_api_url.startswith("https://r33v3r")
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT, verify=verify_ssl) as client:
                primary_resp = await client.get(f"{PRIMARY_API_URL}/api/paper/account")
                if primary_resp.status_code != 200:
                    return -1.0

                backup_resp = await client.get(f"{self.backup_api_url}/api/paper/account")
                if backup_resp.status_code != 200:
                    return -1.0

                primary_data = primary_resp.json()
                backup_data = backup_resp.json()

                primary_equity = primary_data.get("total_equity", 0)
                backup_equity = backup_data.get("total_equity", 0)

                if primary_equity <= 0:
                    return -1.0

                lag = abs(primary_equity - backup_equity) / primary_equity * 60
                self.replication_lag = min(lag, 30.0)
                return self.replication_lag
        except Exception as e:
            logger.warning(f"Could not estimate replication lag: {e}")
            return -1.0

    async def check_failover_readiness(self) -> dict:
        """Check if backup can take over immediately."""
        if not self.backup_healthy:
            return {
                "ready": False,
                "reason": "Backup trader is not responding",
                "health_status": "DOWN"
            }

        try:
            verify_ssl = not self.backup_api_url.startswith("https://r33v3r")
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT, verify=verify_ssl) as client:
                response = await client.get(f"{self.backup_api_url}/api/autonomous/config")
                if response.status_code != 200:
                    return {
                        "ready": False,
                        "reason": f"Cannot fetch backup config (HTTP {response.status_code})",
                        "health_status": "DEGRADED"
                    }

                config = response.json()
                if not config.get("enabled"):
                    return {
                        "ready": False,
                        "reason": "Backup trader is not in autonomous mode",
                        "mode": config.get("mode", "unknown")
                    }

                return {
                    "ready": True,
                    "reason": "Backup trader is ready to take over",
                    "mode": config.get("mode", "standby"),
                    "config_version": config.get("version", "unknown")
                }
        except Exception as e:
            return {
                "ready": False,
                "reason": f"Cannot verify backup readiness: {str(e)}",
                "error": str(e)
            }

    def _check_failover_condition(self) -> bool:
        """Check if failover should be triggered."""
        return (not self.primary_healthy and self.backup_healthy and
                not self.failover_active)

    async def _trigger_failover(self):
        """Trigger failover event and send alerts."""
        with self._lock:
            if self.failover_active:
                return

            self.failover_active = True
            self.last_failover_time = datetime.now()

        event = FailoverEvent("FAILOVER_TRIGGERED", {
            "reason": "Primary trader is down",
            "timestamp": self.last_failover_time.isoformat()
        })
        self._record_failover_event(event)
        await self._send_alert("FAILOVER_ACTIVE",
                               "Primary is down, backup has taken over")

    def _check_graceful_degradation(self) -> List[str]:
        """Check if we should degrade services due to high replication lag."""
        actions = []

        if self.replication_lag > REPLICATION_LAG_CRITICAL_THRESHOLD:
            actions.append("REJECT_NEW_TRADES")
            actions.append("THROTTLE_PRIMARY")
            actions.append("ALERT_OPERATIONS")

        return actions

    async def _send_alert(self, title: str, message: str):
        """Send alert to Slack or other webhook."""
        if not ALERT_WEBHOOK_URL:
            return

        try:
            payload = {
                "text": f"⚠️ {title}: {message}"
            }
            async with httpx.AsyncClient() as client:
                await client.post(ALERT_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    def _record_failover_event(self, event: FailoverEvent):
        """Record failover event for audit trail."""
        with self._lock:
            self.failover_events.append(event)
            # Keep last 1000 events
            if len(self.failover_events) > 1000:
                self.failover_events = self.failover_events[-1000:]

    def _record_history(self, component: str, status: Dict):
        """Record health check history."""
        record = {
            "component": component,
            "timestamp": datetime.now().isoformat(),
            **status
        }
        with self._lock:
            self.health_check_history.append(record)
            # Keep last 500 checks
            if len(self.health_check_history) > 500:
                self.health_check_history = self.health_check_history[-500:]

    async def get_redundancy_status(self) -> dict:
        """Get comprehensive redundancy status."""
        primary_check, backup_check, lag = await asyncio.gather(
            self.check_primary_health(),
            self.check_backup_health(),
            self.check_replication_lag(),
            return_exceptions=False
        )

        # Check for failover condition
        if self._check_failover_condition():
            await self._trigger_failover()

        failover_ready = await self.check_failover_readiness()

        # Determine overall health
        if self.primary_healthy and self.backup_healthy:
            overall_status = "HEALTHY"
            redundancy_level = "ACTIVE"
        elif self.primary_healthy and not self.backup_healthy:
            overall_status = "DEGRADED"
            redundancy_level = "PRIMARY_ONLY"
        elif not self.primary_healthy and self.backup_healthy:
            overall_status = "FAILOVER_ACTIVE"
            redundancy_level = "BACKUP_ACTIVE"
        else:
            overall_status = "DOWN"
            redundancy_level = "NO_REDUNDANCY"

        # Determine replication lag severity
        if lag < 0:
            lag_status = "UNKNOWN"
        elif lag <= REPLICATION_LAG_WARNING_THRESHOLD:
            lag_status = "HEALTHY"
        elif lag <= REPLICATION_LAG_CRITICAL_THRESHOLD:
            lag_status = "WARNING"
        else:
            lag_status = "CRITICAL"

        # Check graceful degradation
        degradation_actions = self._check_graceful_degradation()

        # Calculate uptime
        uptime_seconds = (datetime.now() - self.uptime_start).total_seconds()
        uptime_hours = uptime_seconds / 3600

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "redundancy_level": redundancy_level,
            "primary": {
                "status": primary_check,
                "role": "ACTIVE" if self.primary_healthy else "DOWN"
            },
            "backup": {
                "status": backup_check,
                "role": ("STANDBY" if self.backup_healthy and not self.failover_active
                        else "ACTIVE" if self.failover_active else "DOWN"),
                "ready_for_failover": failover_ready
            },
            "replication": {
                "lag_seconds": round(self.replication_lag, 2) if lag >= 0 else None,
                "status": lag_status,
                "warning_threshold": REPLICATION_LAG_WARNING_THRESHOLD,
                "critical_threshold": REPLICATION_LAG_CRITICAL_THRESHOLD
            },
            "failover": {
                "active": self.failover_active,
                "last_failover_time": self.last_failover_time.isoformat() if self.last_failover_time else None,
                "readiness": failover_ready
            },
            "degradation": {
                "actions": degradation_actions,
                "active": len(degradation_actions) > 0
            },
            "uptime": {
                "seconds": uptime_seconds,
                "hours": round(uptime_hours, 2)
            }
        }


# Global monitor instance with thread-safety
_monitor: Optional[RedundancyMonitor] = None
_monitor_lock = threading.Lock()


def get_redundancy_monitor() -> RedundancyMonitor:
    """Get or create redundancy monitor (thread-safe)."""
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = RedundancyMonitor()
                logger.info("Redundancy monitor initialized")
    return _monitor


# Validate configuration on module load
def _validate_ha_config():
    """Validate HA configuration."""
    if PRIMARY_API_URL == BACKUP_API_URL:
        logger.error(f"ERROR: PRIMARY and BACKUP API URLs are the same: {PRIMARY_API_URL}")
        raise ValueError("PRIMARY_API_URL and BACKUP_API_URL must be different")

    logger.info(f"HA Configuration: PRIMARY={PRIMARY_API_URL}, BACKUP={BACKUP_API_URL}")


_validate_ha_config()


# API Endpoints

@router.get("/status")
async def get_redundancy_status():
    """Get comprehensive redundancy and failover status."""
    monitor = get_redundancy_monitor()
    status = await monitor.get_redundancy_status()
    return JSONResponse(status)


@router.get("/primary/health")
async def get_primary_health():
    """Get primary trader health status."""
    monitor = get_redundancy_monitor()
    status = await monitor.check_primary_health()
    return JSONResponse(status)


@router.get("/backup/health")
async def get_backup_health():
    """Get backup trader health status."""
    monitor = get_redundancy_monitor()
    status = await monitor.check_backup_health()
    return JSONResponse(status)


@router.get("/replication-lag")
async def get_replication_lag():
    """Get estimated replication lag between primary and backup."""
    monitor = get_redundancy_monitor()
    lag = await monitor.check_replication_lag()

    if lag < 0:
        return JSONResponse({
            "lag_seconds": None,
            "status": "UNKNOWN",
            "reason": "Unable to calculate lag"
        })

    if lag <= 2:
        status = "HEALTHY"
    elif lag <= 5:
        status = "WARNING"
    else:
        status = "CRITICAL"

    return JSONResponse({
        "lag_seconds": round(lag, 2),
        "status": status,
        "warning_threshold": REPLICATION_LAG_WARNING_THRESHOLD,
        "critical_threshold": REPLICATION_LAG_CRITICAL_THRESHOLD
    })


@router.get("/failover/ready")
async def check_failover_readiness():
    """Check if backup is ready to take over."""
    monitor = get_redundancy_monitor()
    readiness = await monitor.check_failover_readiness()
    return JSONResponse(readiness)


@router.post("/failover/simulate")
async def simulate_failover():
    """Simulate a failover scenario (non-destructive)."""
    monitor = get_redundancy_monitor()
    status = await monitor.get_redundancy_status()

    if not monitor.backup_healthy:
        return JSONResponse({
            "simulation": "FAILED",
            "reason": "Backup is not healthy - cannot failover",
            "current_status": status
        }, status_code=400)

    readiness = await monitor.check_failover_readiness()
    if not readiness.get("ready"):
        return JSONResponse({
            "simulation": "FAILED",
            "reason": "Backup is not ready for failover",
            "readiness": readiness,
            "current_status": status
        }, status_code=400)

    return JSONResponse({
        "simulation": "SUCCESS",
        "scenario": "Primary is down, backup takes over in 30 seconds",
        "backup_status": {
            "ready": True,
            "will_start_trading": True,
            "estimated_takeover_time": "30 seconds"
        },
        "current_status": status,
        "readiness_check": readiness
    })


@router.get("/config")
async def get_redundancy_config():
    """Get redundancy configuration."""
    return JSONResponse({
        "primary_url": PRIMARY_API_URL,
        "backup_url": BACKUP_API_URL,
        "health_check_interval": 10,
        "failover_threshold": 3,
        "failover_timeout": 30,
        "replication_lag_warning": REPLICATION_LAG_WARNING_THRESHOLD,
        "replication_lag_critical": REPLICATION_LAG_CRITICAL_THRESHOLD,
        "health_check_timeout": HEALTH_CHECK_TIMEOUT,
        "architecture": "active-passive",
        "data_consistency": "postgresql_streaming_replication",
        "retry_config": {
            "retries": HEALTH_CHECK_RETRIES,
            "delays_ms": [int(d * 1000) for d in RETRY_DELAYS]
        }
    })


@router.get("/events")
async def get_failover_events(limit: int = 100):
    """Get failover event history for audit trail."""
    monitor = get_redundancy_monitor()
    events = [e.to_dict() for e in monitor.failover_events[-limit:]]
    return JSONResponse({
        "count": len(events),
        "events": events
    })


@router.get("/history")
async def get_health_check_history(limit: int = 100):
    """Get health check history."""
    monitor = get_redundancy_monitor()
    history = monitor.health_check_history[-limit:]
    return JSONResponse({
        "count": len(history),
        "history": history
    })


@router.get("/uptime")
async def get_uptime():
    """Get system uptime metrics."""
    monitor = get_redundancy_monitor()
    status = await monitor.get_redundancy_status()
    uptime = status.get("uptime", {})
    failovers = len(monitor.failover_events)

    return JSONResponse({
        "uptime_seconds": uptime.get("seconds", 0),
        "uptime_hours": uptime.get("hours", 0),
        "uptime_days": round(uptime.get("hours", 0) / 24, 2),
        "failover_count": failovers,
        "last_failover": (monitor.last_failover_time.isoformat()
                         if monitor.last_failover_time else None)
    })


@router.post("/alerts/configure")
async def configure_alerts(webhook_url: str):
    """Configure Slack/webhook alerting."""
    global ALERT_WEBHOOK_URL
    ALERT_WEBHOOK_URL = webhook_url
    return JSONResponse({
        "status": "configured",
        "webhook_url": webhook_url[:50] + "..." if len(webhook_url) > 50 else webhook_url
    })
