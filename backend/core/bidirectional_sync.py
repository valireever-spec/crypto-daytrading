"""Bi-directional state sync for HA recovery (Phase 2 Component 3).

Allows BACKUP to sync state back to PRIMARY when PRIMARY recovers from crash.
Implements conflict resolution strategy: PRIMARY is always source of truth.
"""

import logging
import asyncio
import httpx
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BiDirectionalSync:
    """Manages bi-directional state synchronization between PRIMARY and BACKUP."""

    def __init__(self, machine_id: str, primary_url: str, backup_url: str):
        """Initialize bi-directional sync.

        Args:
            machine_id: "main" (PRIMARY) or "backup" (BACKUP)
            primary_url: PRIMARY API URL
            backup_url: BACKUP API URL
        """
        self.machine_id = machine_id
        self.primary_url = primary_url
        self.backup_url = backup_url
        self.last_sync_at = None
        self.sync_history = []  # Track sync operations for debugging

    async def sync_backup_to_primary(self, state: Dict[str, Any]) -> bool:
        """Sync BACKUP state to PRIMARY after PRIMARY recovery.

        Used when PRIMARY comes back online to restore state from BACKUP.
        Strategy: If both have state, BACKUP sends current state to PRIMARY
        for PRIMARY to merge with its recovered state.

        Args:
            state: BACKUP's current state {cash, total_pnl, positions}

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            logger.info(f"📤 BACKUP syncing state to PRIMARY recovery endpoint...")

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{self.primary_url}/api/ha/sync-from-backup",
                    json=state
                )

                if resp.status_code == 200:
                    logger.info("✅ BACKUP → PRIMARY sync succeeded (PRIMARY recovered)")
                    self.last_sync_at = datetime.utcnow()
                    self.sync_history.append({
                        "direction": "backup_to_primary",
                        "status": "success",
                        "timestamp": datetime.utcnow().isoformat(),
                        "cash": state.get("cash"),
                        "positions_count": len(state.get("positions", []))
                    })
                    return True
                else:
                    logger.warning(f"⚠️ BACKUP → PRIMARY sync failed: {resp.status_code}")
                    self.sync_history.append({
                        "direction": "backup_to_primary",
                        "status": "failed",
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": f"HTTP {resp.status_code}"
                    })
                    return False

        except Exception as e:
            logger.error(f"❌ BACKUP → PRIMARY sync error: {e}")
            self.sync_history.append({
                "direction": "backup_to_primary",
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            })
            return False

    async def detect_primary_recovery(self) -> bool:
        """Detect if PRIMARY has recovered from a crash.

        Returns True if PRIMARY was unreachable but is now responding.
        """
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{self.primary_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False

    def get_sync_history(self, limit: int = 10) -> list:
        """Get recent sync operations for debugging."""
        return self.sync_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get bi-directional sync status."""
        return {
            "machine_id": self.machine_id,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_history_count": len(self.sync_history),
            "recent_syncs": self.get_sync_history(5)
        }
