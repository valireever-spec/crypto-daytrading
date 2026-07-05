"""HA Reverse SSH Tunnel Orchestrator - Three Scenario Logic.

Implements intelligent fallback:
1. Scenario A: Local network (192.168.3.25:22) → Use local IPs
2. Scenario B: Remote via DDNS (r33v3r.ddns.net:22) → Use DDNS if local fails
3. Scenario C: BACKUP offline → Proceed without failover, retry DDNS every 30-60s

Features:
- Parallel connectivity checks (1-2s timeout each)
- Binance API used for internet connectivity verification
- Bidirectional heartbeat (PRIMARY sends, BACKUP responds)
- Periodic DDNS retry during scenario C
- Detailed logging of scenario transitions
"""

import asyncio
import logging
import time
import socket
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


class HAScenario(Enum):
    """HA connectivity scenarios."""
    A_LOCAL = "local_network"        # 192.168.3.25:22 reachable
    B_REMOTE_DDNS = "remote_ddns"    # r33v3r.ddns.net:22 reachable
    C_OFFLINE = "backup_offline"     # BACKUP unreachable, PRIMARY has internet


@dataclass
class ScenarioConfig:
    """Configuration for HA scenarios."""
    # Scenario A: Local network
    backup_local_ip: str = "192.168.3.25"
    backup_local_port: int = 22

    # Scenario B: Remote via DDNS
    backup_ddns_hostname: str = "r33v3r.ddns.net"
    backup_ddns_port: int = 22

    # SSH credentials
    backup_ssh_user: str = "openhabian"

    # Timeouts (milliseconds)
    local_ping_timeout_ms: int = 1000      # 1s for local network
    ddns_resolve_timeout_ms: int = 2000    # 2s for DDNS resolution
    ddns_ping_timeout_ms: int = 1000       # 1s for DDNS IP ping
    internet_check_timeout_ms: int = 2000  # 2s for Binance API check

    # Retry strategy
    ddns_retry_interval_seconds: int = 45  # Retry DDNS every 45s in scenario C

    # Binance API endpoint for internet connectivity check
    binance_api_endpoint: str = "https://api.binance.com/api/v3/ping"


class HAScenarioOrchestrator:
    """Orchestrate HA failover across three scenarios."""

    def __init__(self, config: ScenarioConfig = None):
        self.config = config or ScenarioConfig()
        self.current_scenario: Optional[HAScenario] = None
        self.backup_endpoint: Optional[str] = None  # e.g., "192.168.3.25" or "r33v3r.ddns.net"

        # Scenario C retry tracking
        self.last_ddns_retry_time: float = 0
        self.scenario_transitions: list = []  # For observability
        self.consecutive_fails: Dict[HAScenario, int] = {s: 0 for s in HAScenario}

    async def determine_scenario(self) -> HAScenario:
        """Determine which scenario PRIMARY is in (A, B, or C).

        Runs checks in parallel for efficiency:
        1. Check local IP (1s timeout)
        2. Resolve DDNS (2s timeout)
        3. Check internet via Binance API (2s timeout)

        Returns:
            Current HA scenario
        """
        logger.debug("🔄 Determining HA scenario...")

        # Run connectivity checks in parallel
        local_ok, ddns_ok, internet_ok = await asyncio.gather(
            self._check_local_network(),
            self._check_ddns_resolution(),
            self._check_internet_connectivity(),
            return_exceptions=False
        )

        # Determine scenario based on results
        new_scenario: HAScenario

        if local_ok:
            new_scenario = HAScenario.A_LOCAL
            self.backup_endpoint = self.config.backup_local_ip
            logger.info("✅ Scenario A: BACKUP reachable on local network (192.168.3.25)")

        elif ddns_ok:
            new_scenario = HAScenario.B_REMOTE_DDNS
            self.backup_endpoint = self.config.backup_ddns_hostname
            logger.info(f"✅ Scenario B: BACKUP reachable via DDNS ({self.config.backup_ddns_hostname})")

        elif internet_ok:
            new_scenario = HAScenario.C_OFFLINE
            self.backup_endpoint = None
            logger.warning(
                "⚠️  Scenario C: BACKUP unreachable, but PRIMARY has internet connectivity. "
                "Proceeding without HA failover."
            )

        else:
            # PRIMARY itself offline - shouldn't happen
            logger.critical(
                "🔴 PRIMARY has no connectivity (not even internet). "
                "This shouldn't happen - check network cable."
            )
            new_scenario = HAScenario.C_OFFLINE

        # Log transitions
        if self.current_scenario != new_scenario:
            self._log_scenario_transition(self.current_scenario, new_scenario)

        self.current_scenario = new_scenario
        return new_scenario

    async def _check_local_network(self) -> bool:
        """Check if BACKUP is reachable on local network (192.168.3.25:22).

        Returns:
            True if reachable, False otherwise
        """
        try:
            # Ping local IP with 1s timeout
            await self._async_tcp_ping(
                self.config.backup_local_ip,
                self.config.backup_local_port,
                timeout_ms=self.config.local_ping_timeout_ms
            )
            logger.debug(f"✅ Local network check OK: {self.config.backup_local_ip}:{self.config.backup_local_port}")
            return True

        except asyncio.TimeoutError:
            logger.debug(f"⏱️  Local network timeout: {self.config.backup_local_ip}")
            return False
        except Exception as e:
            logger.debug(f"Local network check failed: {e}")
            return False

    async def _check_ddns_resolution(self) -> bool:
        """Check if DDNS hostname resolves and is reachable.

        Returns:
            True if resolves and reachable, False otherwise
        """
        try:
            # Resolve DDNS with 2s timeout
            ip = await asyncio.wait_for(
                asyncio.get_event_loop().getaddrinfo(
                    self.config.backup_ddns_hostname,
                    self.config.backup_ddns_port,
                    type=socket.SOCK_STREAM
                ),
                timeout=self.config.ddns_resolve_timeout_ms / 1000.0
            )

            if not ip:
                logger.debug(f"DDNS resolve failed: {self.config.backup_ddns_hostname}")
                return False

            # Verify resolved IP is reachable (1s timeout)
            resolved_ip = ip[0][4][0]
            await self._async_tcp_ping(
                resolved_ip,
                self.config.backup_ddns_port,
                timeout_ms=self.config.ddns_ping_timeout_ms
            )

            logger.debug(
                f"✅ DDNS check OK: {self.config.backup_ddns_hostname} "
                f"→ {resolved_ip}"
            )
            return True

        except asyncio.TimeoutError:
            logger.debug(f"⏱️  DDNS timeout: {self.config.backup_ddns_hostname}")
            return False
        except socket.gaierror:
            logger.debug(f"DDNS resolution failed: {self.config.backup_ddns_hostname}")
            return False
        except Exception as e:
            logger.debug(f"DDNS check failed: {e}")
            return False

    async def _check_internet_connectivity(self) -> bool:
        """Check if PRIMARY has internet by pinging Binance API.

        Uses Binance API endpoint (actual trading dependency) instead of
        generic internet connectivity tests.

        Returns:
            True if PRIMARY has internet, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.config.internet_check_timeout_ms / 1000.0) as client:
                resp = await client.get(self.config.binance_api_endpoint)

                if resp.status_code == 200:
                    logger.debug(f"✅ Internet check OK: Binance API reachable")
                    return True
                else:
                    logger.debug(f"Internet check failed: Binance returned {resp.status_code}")
                    return False

        except asyncio.TimeoutError:
            logger.debug("⏱️  Internet check timeout (Binance API unreachable)")
            return False
        except Exception as e:
            logger.debug(f"Internet check failed: {e}")
            return False

    async def _async_tcp_ping(self, host: str, port: int, timeout_ms: int) -> bool:
        """TCP ping to check if host:port is reachable.

        Args:
            host: Hostname or IP
            port: Port number
            timeout_ms: Timeout in milliseconds

        Returns:
            True if reachable, False otherwise

        Raises:
            asyncio.TimeoutError if timeout exceeded
        """
        try:
            await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout_ms / 1000.0
            )
            return True
        except asyncio.TimeoutError:
            raise
        except Exception:
            return False

    def should_retry_ddns(self) -> bool:
        """Check if PRIMARY should retry DDNS in scenario C.

        Returns:
            True if enough time has passed since last retry
        """
        if self.current_scenario != HAScenario.C_OFFLINE:
            return False

        now = time.time()
        if now - self.last_ddns_retry_time >= self.config.ddns_retry_interval_seconds:
            self.last_ddns_retry_time = now
            return True

        return False

    def get_backup_endpoint(self) -> Optional[str]:
        """Get current BACKUP endpoint based on scenario.

        Returns:
            IP/hostname for SSH tunnel, or None if BACKUP offline
        """
        return self.backup_endpoint

    def get_scenario_info(self) -> Dict[str, Any]:
        """Get current scenario information for logging/monitoring.

        Returns:
            Dict with scenario details
        """
        return {
            "current_scenario": self.current_scenario.value if self.current_scenario else None,
            "backup_endpoint": self.backup_endpoint,
            "last_transition": self.scenario_transitions[-1] if self.scenario_transitions else None,
            "consecutive_fails": {s.value: count for s, count in self.consecutive_fails.items()},
        }

    def _log_scenario_transition(
        self,
        from_scenario: Optional[HAScenario],
        to_scenario: HAScenario
    ) -> None:
        """Log scenario transition for observability.

        Args:
            from_scenario: Previous scenario
            to_scenario: New scenario
        """
        from_str = from_scenario.value if from_scenario else "INIT"
        to_str = to_scenario.value

        transition = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": from_str,
            "to": to_str,
        }

        self.scenario_transitions.append(transition)

        # Keep last 100 transitions
        if len(self.scenario_transitions) > 100:
            self.scenario_transitions = self.scenario_transitions[-100:]

        logger.critical(
            f"🔄 HA Scenario Transition: {from_str} → {to_str} "
            f"({datetime.utcnow().isoformat()})"
        )


# Global instance
_orchestrator: Optional[HAScenarioOrchestrator] = None


def get_ha_orchestrator(config: ScenarioConfig = None) -> HAScenarioOrchestrator:
    """Get or create global HA orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = HAScenarioOrchestrator(config or ScenarioConfig())
        logger.info("🎯 HA Scenario Orchestrator initialized")
    return _orchestrator


def init_ha_orchestrator(config: ScenarioConfig = None) -> HAScenarioOrchestrator:
    """Initialize HA orchestrator with custom config."""
    global _orchestrator
    _orchestrator = HAScenarioOrchestrator(config or ScenarioConfig())
    logger.info("🎯 HA Scenario Orchestrator initialized")
    return _orchestrator
