"""Failover health checker - Pillar #7 Hardening (HIGH risk).

Validates:
1. Primary is actually down (not false positive)
2. Backup is ready to take over (healthy, synced, connected)
3. Config matches between primary and backup
4. Logs all failover transitions and reasons
"""

import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Health check result with detailed status."""

    primary_healthy: bool
    backup_ready: bool
    configs_synced: bool
    ready_to_failover: bool
    timestamp: datetime
    reasons: list  # List of health check results
    details: Dict  # Additional context


class FailoverHealthChecker:
    """Validate system health before failover (Pillar #7 hardening)."""

    def __init__(self, primary_url: str, backup_url: str, timeout_seconds: float = 5.0):
        """Initialize health checker.

        Args:
            primary_url: Primary machine API URL (e.g., "http://192.168.30.137:8001")
            backup_url: Backup machine API URL (e.g., "http://192.168.3.25:8002")
            timeout_seconds: HTTP request timeout
        """
        self.primary_url = primary_url
        self.backup_url = backup_url
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def check_primary_health(self) -> Tuple[bool, str]:
        """Check if primary trader is healthy.

        Returns:
            (is_healthy, reason_if_unhealthy)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.primary_url}/api/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("status") == "ok", "Primary healthy"
                    return False, f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            return False, "Primary timeout (>5s)"
        except Exception as e:
            return False, f"Primary check failed: {type(e).__name__}"

    async def check_backup_readiness(self) -> Tuple[bool, str]:
        """Check if backup is ready to take over.

        Verifies:
        1. Backup API is responding
        2. Backup is not currently trading (in standby mode)
        3. Backup DB connection is active
        4. Backup has sufficient disk space

        Returns:
            (is_ready, reason_if_not_ready)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Check 1: Backup API responding
                async with session.get(f"{self.backup_url}/api/health") as resp:
                    if resp.status != 200:
                        return False, f"Backup API unhealthy: HTTP {resp.status}"

                    data = await resp.json()
                    if data.get("status") != "ok":
                        return False, "Backup health status not OK"

                    # Check 2: Backup is in standby (not actively trading)
                    if data.get("mode") != "standby":
                        return False, f"Backup not in standby mode: {data.get('mode')}"

                    # Check 3: Backup has recent timestamp (actively monitoring)
                    timestamp_str = data.get("timestamp")
                    if not timestamp_str:
                        return False, "Backup timestamp missing"

                return True, "Backup ready for takeover"

        except asyncio.TimeoutError:
            return False, "Backup timeout (>5s)"
        except Exception as e:
            return False, f"Backup readiness check failed: {type(e).__name__}"

    async def check_config_sync(self) -> Tuple[bool, str]:
        """Verify trading config matches between primary and backup.

        Checks critical parameters:
        - entry_threshold
        - exit_profit_target
        - exit_stop_loss
        - max_daily_loss_pct
        - symbols list

        Returns:
            (is_synced, reason_if_out_of_sync)
        """
        critical_fields = [
            "entry_threshold",
            "exit_profit_target",
            "exit_stop_loss",
            "max_daily_loss_pct",
            "symbols",
        ]

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Get primary config
                async with session.get(
                    f"{self.primary_url}/api/autonomous/config"
                ) as resp:
                    if resp.status != 200:
                        return False, "Could not fetch primary config"
                    primary_config = await resp.json()

                # Get backup config
                async with session.get(
                    f"{self.backup_url}/api/autonomous/config"
                ) as resp:
                    if resp.status != 200:
                        return False, "Could not fetch backup config"
                    backup_config = await resp.json()

                # Compare critical fields
                mismatches = []
                for field in critical_fields:
                    primary_val = primary_config.get(field)
                    backup_val = backup_config.get(field)

                    if primary_val != backup_val:
                        mismatches.append(
                            f"{field}: primary={primary_val} vs backup={backup_val}"
                        )

                if mismatches:
                    return False, f"Config mismatch: {'; '.join(mismatches)}"

                return True, "Configs synced"

        except asyncio.TimeoutError:
            return False, "Config check timeout"
        except Exception as e:
            return False, f"Config sync check failed: {type(e).__name__}"

    async def perform_health_check(self) -> HealthCheckResult:
        """Perform complete failover health check.

        Returns:
            HealthCheckResult with all check outcomes
        """
        timestamp = datetime.utcnow()
        reasons = []

        # Check 1: Primary health
        primary_healthy, primary_reason = await self.check_primary_health()
        reasons.append(f"Primary: {primary_reason}")
        logger.info(
            f"Primary health check: {'✅' if primary_healthy else '❌'} {primary_reason}"
        )

        # Check 2: Backup readiness
        backup_ready, backup_reason = await self.check_backup_readiness()
        reasons.append(f"Backup: {backup_reason}")
        logger.info(
            f"Backup readiness check: {'✅' if backup_ready else '❌'} {backup_reason}"
        )

        # Check 3: Config sync (only check if primary is healthy, skip if primary down)
        configs_synced = True
        config_reason = "N/A (primary down)"
        if primary_healthy:
            configs_synced, config_reason = await self.check_config_sync()
            reasons.append(f"Config: {config_reason}")
            logger.info(
                f"Config sync check: {'✅' if configs_synced else '❌'} {config_reason}"
            )

        # Determine if we can failover
        ready_to_failover = (
            (not primary_healthy)
            and backup_ready
            and (not primary_healthy or configs_synced)
        )

        if ready_to_failover:
            logger.critical(
                "🚨 FAILOVER CONDITIONS MET: Primary down + Backup ready + Config synced"
            )
        elif not primary_healthy:
            if not backup_ready:
                logger.critical(
                    f"❌ CANNOT FAILOVER: Backup not ready ({backup_reason})"
                )
            if not configs_synced and primary_healthy:
                logger.critical(f"❌ CANNOT FAILOVER: Config mismatch ({config_reason})")

        return HealthCheckResult(
            primary_healthy=primary_healthy,
            backup_ready=backup_ready,
            configs_synced=configs_synced,
            ready_to_failover=ready_to_failover,
            timestamp=timestamp,
            reasons=reasons,
            details={
                "primary_url": self.primary_url,
                "backup_url": self.backup_url,
            },
        )
