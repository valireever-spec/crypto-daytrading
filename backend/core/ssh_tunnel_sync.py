"""SSH tunnel fallback for state sync (Phase 2 Component 4).

When HTTP sync fails (network isolation), fall back to SSH tunnel.
Enables sync even when PRIMARY and BACKUP are on different networks.
"""

import logging
import json
import subprocess
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SSHTunnelSync:
    """Sync state via SSH tunnel when HTTP fails."""

    def __init__(self, backup_host: str = "192.168.3.25", backup_user: str = "openhabian"):
        """Initialize SSH tunnel sync.

        Args:
            backup_host: BACKUP machine hostname/IP
            backup_user: SSH user on BACKUP machine
        """
        self.backup_host = backup_host
        self.backup_user = backup_user
        self.ssh_timeout = 10  # seconds

    async def sync_via_ssh_tunnel(self, state: Dict[str, Any]) -> bool:
        """Sync state to BACKUP via SSH tunnel.

        Fallback when HTTP sync fails due to network isolation.
        Uses SSH to run sync command on BACKUP targeting localhost:8002

        Args:
            state: State to sync {cash, total_pnl, positions}

        Returns:
            True if sync succeeded via SSH, False otherwise
        """
        try:
            logger.info("🌐 PRIMARY → BACKUP sync via SSH tunnel (HTTP fallback)...")

            # Build JSON payload
            payload = json.dumps(state)

            # SSH command: Use curl on BACKUP to POST to localhost:8002
            ssh_cmd = [
                "ssh",
                "-o", "ConnectTimeout=3",
                "-o", "StrictHostKeyChecking=no",
                f"{self.backup_user}@{self.backup_host}",
                f"curl -s -X POST http://127.0.0.1:8002/api/ha/sync-from-primary "
                f"-H 'Content-Type: application/json' "
                f"-d '{payload}' | grep -q '\"status\"' && echo 'SUCCESS' || echo 'FAILED'"
            ]

            # Execute SSH command with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *ssh_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=self.ssh_timeout
                )

                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=self.ssh_timeout
                )

                output = stdout.decode().strip()

                if result.returncode == 0 and "SUCCESS" in output:
                    logger.info("✅ PRIMARY → BACKUP sync via SSH succeeded")
                    return True
                else:
                    logger.warning(f"⚠️ SSH sync failed: {stderr.decode()}")
                    return False

            except asyncio.TimeoutError:
                logger.error(f"SSH sync timeout ({self.ssh_timeout}s)")
                return False

        except Exception as e:
            logger.error(f"❌ SSH tunnel sync error: {e}")
            return False

    async def check_ssh_connectivity(self) -> bool:
        """Test if SSH tunnel to BACKUP is available.

        Returns True if SSH connection succeeds, False otherwise.
        """
        try:
            ssh_cmd = [
                "ssh",
                "-o", "ConnectTimeout=2",
                "-o", "StrictHostKeyChecking=no",
                f"{self.backup_user}@{self.backup_host}",
                "echo 'ok'"
            ]

            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *ssh_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=3
            )

            await asyncio.wait_for(result.communicate(), timeout=3)
            return result.returncode == 0

        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get SSH tunnel status."""
        return {
            "backup_host": self.backup_host,
            "backup_user": self.backup_user,
            "ssh_timeout": self.ssh_timeout,
            "description": "Fallback sync channel when HTTP unreachable"
        }
