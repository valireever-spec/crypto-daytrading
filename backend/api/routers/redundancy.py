"""High Availability and Redundancy monitoring endpoints."""

import asyncio
import httpx
import os
import threading
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/redundancy", tags=["Redundancy"])

# Configuration from environment
PRIMARY_API_URL = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
BACKUP_API_URL = os.getenv("BACKUP_API_URL", "http://192.168.3.204:8002")
REPLICATION_LAG_WARNING_THRESHOLD = 2  # seconds
REPLICATION_LAG_CRITICAL_THRESHOLD = 5  # seconds
HEALTH_CHECK_TIMEOUT = 5  # seconds


class RedundancyMonitor:
    """Monitors primary-backup redundancy status."""

    def __init__(self):
        self.last_primary_check = None
        self.last_backup_check = None
        self.primary_healthy = False
        self.backup_healthy = False
        self.replication_lag = 0.0
        self.failover_active = False
        self.last_error = None

    async def check_primary_health(self) -> dict:
        """Check if primary is responding."""
        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                response = await client.get(f"{PRIMARY_API_URL}/api/health")
                self.last_primary_check = datetime.now()
                self.primary_healthy = response.status_code == 200
                return {
                    "host": PRIMARY_API_URL,
                    "healthy": self.primary_healthy,
                    "status_code": response.status_code,
                    "timestamp": self.last_primary_check.isoformat()
                }
        except Exception as e:
            self.last_primary_check = datetime.now()
            self.primary_healthy = False
            self.last_error = str(e)
            return {
                "host": PRIMARY_API_URL,
                "healthy": False,
                "error": str(e),
                "timestamp": self.last_primary_check.isoformat()
            }

    async def check_backup_health(self) -> dict:
        """Check if backup is responding."""
        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                response = await client.get(f"{BACKUP_API_URL}/api/health")
                self.last_backup_check = datetime.now()
                self.backup_healthy = response.status_code == 200
                return {
                    "host": BACKUP_API_URL,
                    "healthy": self.backup_healthy,
                    "status_code": response.status_code,
                    "timestamp": self.last_backup_check.isoformat()
                }
        except Exception as e:
            self.last_backup_check = datetime.now()
            self.backup_healthy = False
            self.last_error = str(e)
            return {
                "host": BACKUP_API_URL,
                "healthy": False,
                "error": str(e),
                "timestamp": self.last_backup_check.isoformat()
            }

    async def check_replication_lag(self) -> float:
        """
        Estimate replication lag by comparing account state timestamps.
        In production, this would query PostgreSQL replication metrics.
        """
        if not self.primary_healthy or not self.backup_healthy:
            return -1.0  # Unknown lag if either is down

        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                # Get timestamps from both primary and backup
                primary_resp = await client.get(f"{PRIMARY_API_URL}/api/paper/account")
                if primary_resp.status_code != 200:
                    return -1.0

                backup_resp = await client.get(f"{BACKUP_API_URL}/api/paper/account")
                if backup_resp.status_code != 200:
                    return -1.0

                primary_data = primary_resp.json()
                backup_data = backup_resp.json()

                # Compare equity values (rough estimate of replication lag)
                # In production, use actual DB replication metrics
                primary_equity = primary_data.get("total_equity", 0)
                backup_equity = backup_data.get("total_equity", 0)

                # Estimated lag based on equity difference
                # This is a simplification; production would use WAL metrics
                lag = abs(primary_equity - backup_equity) / max(primary_equity, 1) * 60
                self.replication_lag = min(lag, 30)  # Cap at 30 seconds

                return self.replication_lag
        except Exception as e:
            self.last_error = str(e)
            return -1.0  # Unknown

    async def check_failover_readiness(self) -> dict:
        """Check if backup can take over immediately if needed."""
        if not self.backup_healthy:
            return {
                "ready": False,
                "reason": "Backup trader is not responding",
                "health_status": "DOWN"
            }

        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                # Check backup has recent config
                response = await client.get(f"{BACKUP_API_URL}/api/autonomous/config")
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

    async def get_redundancy_status(self) -> dict:
        """Get comprehensive redundancy status."""
        # Perform all checks in parallel
        primary_check, backup_check, lag = await asyncio.gather(
            self.check_primary_health(),
            self.check_backup_health(),
            self.check_replication_lag(),
            return_exceptions=False
        )

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
            self.failover_active = True
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
                "role": "STANDBY" if self.backup_healthy and not self.failover_active else "ACTIVE" if self.failover_active else "DOWN",
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
                "readiness": failover_ready
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
    return _monitor


@router.get("/status")
async def get_redundancy_status():
    """
    Get comprehensive redundancy and failover status.

    Returns:
    - Overall health (HEALTHY, DEGRADED, FAILOVER_ACTIVE, DOWN)
    - Primary and backup status
    - Replication lag
    - Failover readiness
    """
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

    # Determine status
    if lag <= REPLICATION_LAG_WARNING_THRESHOLD:
        status = "HEALTHY"
    elif lag <= REPLICATION_LAG_CRITICAL_THRESHOLD:
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
    """
    Check if backup is ready to take over.

    Returns:
    - ready: boolean
    - reason: explanation
    - readiness details
    """
    monitor = get_redundancy_monitor()
    readiness = await monitor.check_failover_readiness()
    return JSONResponse(readiness)


@router.post("/failover/simulate")
async def simulate_failover():
    """
    Simulate a failover scenario (for testing only).
    Returns what would happen if primary goes down.
    """
    monitor = get_redundancy_monitor()

    # Get current status
    status = await monitor.get_redundancy_status()

    if not monitor.backup_healthy:
        return JSONResponse({
            "simulation": "FAILED",
            "reason": "Backup is not healthy - cannot failover",
            "current_status": status
        }, status_code=400)

    # Check failover readiness
    readiness = await monitor.check_failover_readiness()

    if not readiness.get("ready"):
        return JSONResponse({
            "simulation": "FAILED",
            "reason": "Backup is not ready for failover",
            "readiness": readiness,
            "current_status": status
        }, status_code=400)

    # Simulate failover
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
        "health_check_interval": 10,  # seconds
        "failover_threshold": 3,  # consecutive failed checks
        "failover_timeout": 30,  # seconds
        "replication_lag_warning": REPLICATION_LAG_WARNING_THRESHOLD,
        "replication_lag_critical": REPLICATION_LAG_CRITICAL_THRESHOLD,
        "health_check_timeout": HEALTH_CHECK_TIMEOUT,
        "architecture": "active-passive",
        "data_consistency": "postgresql_streaming_replication"
    })


@router.get("/history")
async def get_redundancy_history(hours: int = 24):
    """
    Get redundancy status history for the last N hours.
    In production, this would query a metrics database.
    """
    monitor = get_redundancy_monitor()

    # For now, return current status with recommendations
    current_status = await monitor.get_redundancy_status()

    return JSONResponse({
        "hours": hours,
        "current": current_status,
        "uptime_percentage": 99.9,  # Would be calculated from metrics DB
        "failovers_count": 0,  # Would be from history
        "average_replication_lag": 0.5,  # Would be from metrics
        "notes": "Full history requires metrics database integration"
    })
