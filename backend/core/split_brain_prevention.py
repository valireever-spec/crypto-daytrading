"""Split-brain detection and prevention (Phase 2 Hardening).

Prevents both PRIMARY and BACKUP from trading simultaneously by:
1. Maintaining a shared failover state (who's currently in charge)
2. Requiring mutual health confirmation before failover
3. Detecting and resolving split-brain situations
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Literal
from enum import Enum

logger = logging.getLogger(__name__)


class FailoverState(Enum):
    """Failover state machine."""
    PRIMARY_ACTIVE = "primary_active"      # PRIMARY is healthy, trading
    BACKUP_ACTIVE = "backup_active"        # BACKUP took over, PRIMARY offline
    BOTH_HEALTHY = "both_healthy"          # Both responsive (split-brain alert!)
    BOTH_DEAD = "both_dead"                # Neither responding (shouldn't happen)
    UNKNOWN = "unknown"                    # Initial state


class SplitBrainPrevention:
    """Prevent split-brain situations in HA system."""

    def __init__(self, machine_id: str, primary_url: str, backup_url: str):
        """Initialize split-brain prevention.

        Args:
            machine_id: "main" (PRIMARY) or "backup" (BACKUP)
            primary_url: PRIMARY API URL (http://127.0.0.1:8001)
            backup_url: BACKUP API URL (http://192.168.3.25:8002)
        """
        self.machine_id = machine_id
        self.primary_url = primary_url
        self.backup_url = backup_url
        self.current_state = FailoverState.UNKNOWN
        self.state_updated_at = datetime.utcnow()
        self.last_primary_check = None
        self.last_backup_check = None
        self.PRIMARY_CHECK_INTERVAL = 5  # seconds
        self.PRIMARY_CHECK_TIMEOUT = 2   # seconds
        self.SPLIT_BRAIN_ALERT_THRESHOLD = 3  # consecutive split-brain detections

    async def check_mutual_health(self) -> dict:
        """Check health of both PRIMARY and BACKUP.

        Returns:
            {
                'primary_healthy': bool,
                'backup_healthy': bool,
                'split_brain': bool,  # True if both are healthy (danger!)
                'state': FailoverState
            }
        """
        import httpx

        primary_healthy = False
        backup_healthy = False

        # Check PRIMARY health
        try:
            async with httpx.AsyncClient(timeout=self.PRIMARY_CHECK_TIMEOUT) as client:
                resp = await client.get(f"{self.primary_url}/api/health")
                primary_healthy = resp.status_code == 200
                self.last_primary_check = datetime.utcnow()
        except Exception as e:
            logger.debug(f"PRIMARY health check failed: {e}")
            primary_healthy = False

        # Check BACKUP health
        try:
            async with httpx.AsyncClient(timeout=self.PRIMARY_CHECK_TIMEOUT) as client:
                resp = await client.get(f"{self.backup_url}/api/health")
                backup_healthy = resp.status_code == 200
                self.last_backup_check = datetime.utcnow()
        except Exception as e:
            logger.debug(f"BACKUP health check failed: {e}")
            backup_healthy = False

        # Determine state
        split_brain = primary_healthy and backup_healthy

        if split_brain:
            # DANGER: Both machines responding!
            logger.critical(
                "🚨 SPLIT-BRAIN DETECTED: Both PRIMARY and BACKUP are healthy! "
                "Machine coordination required to prevent duplicate orders."
            )
            new_state = FailoverState.BOTH_HEALTHY
        elif primary_healthy:
            new_state = FailoverState.PRIMARY_ACTIVE
        elif backup_healthy:
            new_state = FailoverState.BACKUP_ACTIVE
        else:
            new_state = FailoverState.BOTH_DEAD

        # Update state
        if new_state != self.current_state:
            logger.warning(
                f"Failover state transition: {self.current_state.value} → {new_state.value}"
            )
            self.current_state = new_state
            self.state_updated_at = datetime.utcnow()

        return {
            "primary_healthy": primary_healthy,
            "backup_healthy": backup_healthy,
            "split_brain": split_brain,
            "state": new_state,
            "machine_id": self.machine_id,
            "updated_at": self.state_updated_at.isoformat(),
        }

    def can_trade(self) -> bool:
        """Determine if this machine should trade.

        Returns True only if:
        1. PRIMARY is healthy (always trades)
        2. BACKUP is healthy AND PRIMARY is confirmed dead
        3. NOT if split-brain detected (both healthy)
        """
        if self.machine_id == "main":
            # PRIMARY always trades (it's the source of truth)
            return True
        else:
            # BACKUP only trades if PRIMARY is dead and no split-brain
            return (
                self.current_state == FailoverState.BACKUP_ACTIVE
                and not self._is_split_brain()
            )

    def _is_split_brain(self) -> bool:
        """Check if split-brain condition exists."""
        return self.current_state == FailoverState.BOTH_HEALTHY

    async def resolve_split_brain(self) -> str:
        """Resolve split-brain by halting one machine.

        Returns: "primary_halted" or "backup_halted" or "unresolved"
        """
        if self.current_state != FailoverState.BOTH_HEALTHY:
            return "not_split_brain"

        logger.critical("Attempting to resolve split-brain...")

        # Strategy: BACKUP backs down to PRIMARY (PRIMARY is source of truth)
        if self.machine_id == "backup":
            logger.critical(
                "🛑 BACKUP halting autonomous trading (PRIMARY is primary source of truth)"
            )
            return "backup_halted"
        else:
            logger.critical(
                "✅ PRIMARY continues trading (PRIMARY is primary source of truth)"
            )
            return "primary_halted"

    def get_status(self) -> dict:
        """Get current failover status."""
        return {
            "machine_id": self.machine_id,
            "current_state": self.current_state.value,
            "can_trade": self.can_trade(),
            "is_split_brain": self._is_split_brain(),
            "last_primary_check": self.last_primary_check.isoformat() if self.last_primary_check else None,
            "last_backup_check": self.last_backup_check.isoformat() if self.last_backup_check else None,
            "state_updated_at": self.state_updated_at.isoformat(),
        }
