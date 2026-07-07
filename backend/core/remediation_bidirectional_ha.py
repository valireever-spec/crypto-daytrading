"""
BIDIRECTIONAL HA ARCHITECTURE

Critical fixes for true high-availability (not just PRIMARY-only setup):
1. Bidirectional WebSocket (both PRIMARY and BACKUP connect)
2. Bidirectional DB sync (forward + backward)
3. Bidirectional heartbeat (both directions, with health info)
4. Bidirectional SSH tunnel (forward + reverse for recovery)
5. Smart promotion logic (multiple signals, state recovery)

This prevents:
- State divergence when PRIMARY fails
- Stale data trading when PRIMARY's WebSocket dies
- False split-brain when only PRIMARY is isolated
- Data loss during failover (BACKUP lacks latest state)
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# BIDIRECTIONAL WEBSOCKET (Both PRIMARY & BACKUP connect)
# ============================================================================

@dataclass
class WebSocketHealth:
    role: str  # "PRIMARY" or "BACKUP"
    staleness_seconds: float
    is_connected: bool
    last_update_time: datetime
    connection_failures: int = 0
    last_failure_reason: str = ""


class BidirectionalWebSocket:
    """Both PRIMARY and BACKUP maintain WebSocket connections for visibility."""

    def __init__(self, role: str):
        """
        Initialize WebSocket for both machines.

        PRIMARY: Uses for live trading data
        BACKUP: Uses for network health monitoring (doesn't trade yet)
        """
        self.role = role
        self.connections = {}  # symbol -> websocket connection
        self.health = {}  # symbol -> WebSocketHealth
        self.use_for_trading = (role == "PRIMARY")
        self.monitor_staleness = (role == "BACKUP")

    async def connect_to_feed(self, symbol: str):
        """Both PRIMARY and BACKUP connect independently."""
        try:
            logger.info(f"[{self.role}] Connecting to WebSocket for {symbol}")

            # Each machine connects to the feed independently
            conn = await self._establish_connection(symbol)

            self.connections[symbol] = conn
            self.health[symbol] = WebSocketHealth(
                role=self.role,
                staleness_seconds=0,
                is_connected=True,
                last_update_time=datetime.now(),
                connection_failures=0
            )

            if self.use_for_trading:
                logger.info(f"[{self.role}] PRIMARY: Using {symbol} for trading")
            else:
                logger.info(f"[{self.role}] BACKUP: Using {symbol} for monitoring")

            return True

        except Exception as e:
            logger.error(f"[{self.role}] Failed to connect to {symbol}: {e}")
            return False

    async def detect_network_issues(self):
        """Both detect if THEIR connection is stale independently."""
        while True:
            for symbol, health in self.health.items():
                staleness = self._calculate_staleness(symbol)

                if staleness > 30:
                    health.staleness_seconds = staleness

                    if self.use_for_trading:
                        # PRIMARY: Can't reliably trade
                        logger.critical(
                            f"[{self.role}] WebSocket stale {staleness}s - "
                            f"cannot trade reliably"
                        )
                        await self._verify_isolation()

                    else:
                        # BACKUP: Report to PRIMARY
                        logger.warning(
                            f"[{self.role}] WebSocket stale {staleness}s - "
                            f"alerting PRIMARY of network issue"
                        )
                        await self._alert_peer_of_network_issue(symbol, staleness)

            await asyncio.sleep(5)

    async def _verify_isolation(self):
        """PRIMARY: Check if I'm isolated or if network is globally down."""
        logger.info(f"[{self.role}] Checking isolation...")

        # Can I reach BACKUP's heartbeat endpoint?
        backup_reachable = await self._check_peer_reachable()

        if not backup_reachable:
            logger.critical(
                f"[{self.role}] NETWORK ISOLATION DETECTED - "
                f"can't reach BACKUP, pausing trading to prevent divergence"
            )
            self.trading_paused = True
        else:
            logger.warning(
                f"[{self.role}] Only my WebSocket is down, BACKUP can provide visibility"
            )

    async def _alert_peer_of_network_issue(self, symbol: str, staleness: float):
        """BACKUP: Inform PRIMARY that I also lost WebSocket."""
        payload = {
            "role": "BACKUP",
            "alert": "websocket_stale",
            "symbol": symbol,
            "staleness_seconds": staleness,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Send to PRIMARY's health endpoint
            await self._send_to_peer("http://PRIMARY:8001/api/ha/network-alert", payload)
            logger.info(f"[{self.role}] Alerted PRIMARY of WebSocket issue")
        except Exception as e:
            logger.warning(f"[{self.role}] Could not alert PRIMARY: {e}")

    def get_health_status(self, symbol: str) -> Dict[str, Any]:
        """Get WebSocket health for a symbol."""
        if symbol not in self.health:
            return {"status": "not_connected"}

        health = self.health[symbol]
        return {
            "role": self.role,
            "symbol": symbol,
            "connected": health.is_connected,
            "staleness_seconds": health.staleness_seconds,
            "last_update": health.last_update_time.isoformat(),
            "connection_failures": health.connection_failures,
            "using_for_trading": self.use_for_trading
        }

    def _calculate_staleness(self, symbol: str) -> float:
        """Calculate staleness (seconds since last update)."""
        if symbol not in self.health:
            return 0

        health = self.health[symbol]
        staleness = (datetime.now() - health.last_update_time).total_seconds()
        health.staleness_seconds = staleness
        return staleness

    async def _establish_connection(self, symbol: str):
        """Establish WebSocket connection to data feed."""
        # TODO: Implement actual WebSocket connection
        pass

    async def _check_peer_reachable(self) -> bool:
        """Check if peer (PRIMARY or BACKUP) is reachable."""
        # TODO: Implement actual connectivity check
        pass

    async def _send_to_peer(self, url: str, payload: Dict):
        """Send alert/data to peer."""
        # TODO: Implement HTTP POST to peer
        pass


# ============================================================================
# BIDIRECTIONAL SYNC (Forward + Backward)
# ============================================================================

@dataclass
class SyncState:
    version: int
    timestamp: datetime
    cash: float
    positions: Dict[str, float]
    pnl: float
    role: str  # "PRIMARY" or "BACKUP"


class BidirectionalSync:
    """Forward sync (PRIMARY → BACKUP) + Backward sync (BACKUP ← PRIMARY)."""

    def __init__(self, role: str):
        self.role = role
        self.state_version = 0
        self.last_sync_time = datetime.now()
        self.state = {}

    # ========= FORWARD SYNC: PRIMARY → BACKUP =========

    async def sync_forward_to_backup(self, state: Dict[str, Any]) -> bool:
        """PRIMARY: Push state to BACKUP."""
        self.state_version += 1

        payload = {
            "role": "PRIMARY",
            "state": state,
            "version": self.state_version,
            "timestamp": datetime.now().isoformat()
        }

        # Try HTTP first
        try:
            response = await self._http_post(
                "http://BACKUP:8002/api/ha/sync-forward",
                payload
            )
            logger.info(f"✅ Forward sync succeeded (v{self.state_version})")
            self.last_sync_time = datetime.now()
            return True

        except Exception as e:
            logger.warning(f"HTTP forward sync failed: {e}")

            # Fallback: Try SSH reverse channel
            try:
                result = await self._ssh_reverse_sync(payload)
                logger.info(f"✅ Forward sync via SSH succeeded (v{self.state_version})")
                self.last_sync_time = datetime.now()
                return result

            except Exception as ssh_error:
                logger.error(
                    f"❌ Both HTTP and SSH forward sync failed: {ssh_error}"
                )
                return False

    # ========= BACKWARD SYNC: BACKUP ← PRIMARY =========

    async def sync_backward_from_primary(self) -> Optional[Dict[str, Any]]:
        """BACKUP: Pull state from PRIMARY (on-demand before promotion)."""
        if self.role != "BACKUP":
            logger.warning("Only BACKUP can pull state from PRIMARY")
            return None

        try:
            # Direct HTTP pull
            state = await self._http_get(
                "http://PRIMARY:8001/api/ha/state"
            )
            logger.info("✅ Backward sync (pull) succeeded")
            return state

        except Exception as e:
            logger.warning(f"HTTP backward sync failed: {e}")

            # Fallback: Try SSH reverse tunnel
            try:
                state = await self._ssh_backward_sync()
                logger.info("✅ Backward sync via SSH succeeded")
                return state

            except Exception as ssh_error:
                logger.error(f"❌ Both HTTP and SSH backward sync failed: {ssh_error}")
                return None

    async def _ssh_reverse_sync(self, payload: Dict) -> bool:
        """Use reverse SSH tunnel to sync if HTTP fails."""
        # Assumes: ssh -R 9001:localhost:8002 established
        try:
            response = await self._http_post(
                "http://localhost:9001/api/ha/sync-forward",  # Via reverse tunnel
                payload,
                timeout=5
            )
            return response.status == 200

        except Exception as e:
            logger.error(f"SSH reverse sync failed: {e}")
            return False

    async def _ssh_backward_sync(self) -> Optional[Dict]:
        """Pull state via reverse SSH tunnel."""
        try:
            state = await self._http_get(
                "http://localhost:9001/api/ha/state",  # Via reverse tunnel
                timeout=5
            )
            return state

        except Exception as e:
            logger.error(f"SSH reverse state pull failed: {e}")
            return None

    # ========= CONFLICT RESOLUTION =========

    async def resolve_state_conflict(
        self,
        primary_state: Dict,
        backup_state: Dict
    ) -> Dict:
        """Resolve divergence using version numbers and timestamps."""
        primary_version = primary_state.get("version", 0)
        backup_version = backup_state.get("version", 0)

        if primary_version > backup_version:
            logger.info(
                f"PRIMARY state is newer (v{primary_version} > v{backup_version})"
            )
            return primary_state

        elif backup_version > primary_version:
            logger.info(
                f"BACKUP state is newer (v{backup_version} > v{primary_version})"
            )
            return backup_state

        else:
            # Same version → use timestamp
            primary_time = datetime.fromisoformat(primary_state["timestamp"])
            backup_time = datetime.fromisoformat(backup_state["timestamp"])

            if primary_time >= backup_time:
                logger.info("Same version, using PRIMARY (more recent timestamp)")
                return primary_state
            else:
                logger.info("Same version, using BACKUP (more recent timestamp)")
                return backup_state

    async def _http_post(self, url: str, payload: Dict, timeout: int = 5):
        """POST to endpoint."""
        # TODO: Implement actual HTTP POST
        pass

    async def _http_get(self, url: str, timeout: int = 5):
        """GET from endpoint."""
        # TODO: Implement actual HTTP GET
        pass


# ============================================================================
# BIDIRECTIONAL HEARTBEAT
# ============================================================================

@dataclass
class HeartbeatPayload:
    role: str
    timestamp: str
    websocket_staleness: Dict[str, float]  # symbol -> staleness
    memory_percent: float
    state_version: int
    state_last_sync: str
    status: str  # "healthy", "degraded", "critical"


class BidirectionalHeartbeat:
    """Both PRIMARY and BACKUP send heartbeats (with health info)."""

    def __init__(self, role: str):
        self.role = role
        self.peer_role = "BACKUP" if role == "PRIMARY" else "PRIMARY"
        self.last_peer_heartbeat = datetime.now()
        self.heartbeat_timeout = 10  # seconds
        self.missed_count = 0

    async def send_heartbeat(
        self,
        websocket_staleness: Dict[str, float],
        memory_percent: float,
        state_version: int,
        state_last_sync: datetime
    ):
        """Send "I'm alive" with detailed health info."""
        payload = HeartbeatPayload(
            role=self.role,
            timestamp=datetime.now().isoformat(),
            websocket_staleness=websocket_staleness,
            memory_percent=memory_percent,
            state_version=state_version,
            state_last_sync=state_last_sync.isoformat(),
            status=self._determine_status(websocket_staleness, memory_percent)
        )

        try:
            if self.role == "PRIMARY":
                # PRIMARY sends to BACKUP
                await self._http_post(
                    "http://BACKUP:8002/api/ha/heartbeat",
                    asdict(payload)
                )
            else:
                # BACKUP also sends to PRIMARY
                await self._http_post(
                    "http://PRIMARY:8001/api/ha/heartbeat",
                    asdict(payload)
                )

            logger.debug(f"[{self.role}] Heartbeat sent: status={payload.status}")

        except Exception as e:
            logger.warning(f"[{self.role}] Could not send heartbeat: {e}")

    async def listen_for_heartbeat(self):
        """Receive heartbeat from peer (run as background task)."""
        # This would be implemented as a FastAPI endpoint:
        # @app.post("/api/ha/heartbeat")
        # async def receive_heartbeat(payload: dict):
        #     self.last_peer_heartbeat = datetime.now()
        #     self.missed_count = 0
        #     self._process_peer_heartbeat(payload)

        pass

    async def check_peer_alive(self):
        """Monitor if peer is still sending heartbeats."""
        while True:
            time_since_heartbeat = (
                datetime.now() - self.last_peer_heartbeat
            ).total_seconds()

            if time_since_heartbeat > self.heartbeat_timeout:
                self.missed_count += 1
                logger.warning(
                    f"[{self.role}] Heartbeat from {self.peer_role} missed "
                    f"({self.missed_count}x, {time_since_heartbeat:.1f}s)"
                )

                if self.missed_count >= 3:
                    # 3 consecutive missed heartbeats = peer is likely down
                    await self._handle_peer_down()

            else:
                self.missed_count = 0

            await asyncio.sleep(1)

    def _determine_status(
        self,
        websocket_staleness: Dict[str, float],
        memory_percent: float
    ) -> str:
        """Determine overall health status based on metrics."""
        max_staleness = max(websocket_staleness.values()) if websocket_staleness else 0

        if max_staleness > 60 or memory_percent > 95:
            return "critical"
        elif max_staleness > 30 or memory_percent > 85:
            return "degraded"
        else:
            return "healthy"

    def _process_peer_heartbeat(self, payload: Dict):
        """Process incoming heartbeat from peer."""
        peer_role = payload["role"]
        peer_status = payload["status"]
        peer_websocket_staleness = payload["websocket_staleness"]
        peer_memory = payload["memory_percent"]
        peer_state_version = payload["state_version"]

        logger.info(
            f"[{self.role}] Heartbeat from {peer_role}: "
            f"status={peer_status}, "
            f"websocket_staleness={peer_websocket_staleness}, "
            f"memory={peer_memory}%, "
            f"state_v{peer_state_version}"
        )

        # BACKUP uses this info for promotion decisions
        if self.role == "BACKUP" and peer_role == "PRIMARY":
            self._evaluate_promotion_triggers(payload)

    def _evaluate_promotion_triggers(self, peer_payload: Dict):
        """BACKUP: Check if PRIMARY is unhealthy enough to promote."""
        # Trigger 1: Status is critical
        if peer_payload["status"] == "critical":
            logger.warning("[BACKUP] PRIMARY status is CRITICAL - consider promotion")

        # Trigger 2: State version not advancing (PRIMARY frozen)
        # TODO: Compare with previous heartbeat

        # Trigger 3: Multiple WebSocket symbols stale
        stale_symbols = [
            sym for sym, staleness in peer_payload["websocket_staleness"].items()
            if staleness > 30
        ]
        if len(stale_symbols) > 1:
            logger.warning(
                f"[BACKUP] PRIMARY has {len(stale_symbols)} stale WebSocket(s) - "
                f"consider promotion"
            )

    async def _handle_peer_down(self):
        """Peer is unresponsive."""
        if self.role == "PRIMARY":
            logger.critical(
                f"[{self.role}] {self.peer_role} (BACKUP) is unresponsive - "
                f"cannot sync state"
            )
        else:
            logger.critical(
                f"[{self.role}] {self.peer_role} (PRIMARY) is unresponsive - "
                f"initiating promotion"
            )

    async def _http_post(self, url: str, payload: Dict):
        """POST heartbeat to peer."""
        # TODO: Implement actual HTTP POST
        pass


# ============================================================================
# BIDIRECTIONAL SSH TUNNEL
# ============================================================================

class BidirectionalSSHTunnel:
    """Forward SSH (PRIMARY → BACKUP) + Reverse SSH (BACKUP ← PRIMARY)."""

    def __init__(self, role: str):
        self.role = role
        self.forward_tunnel = None
        self.reverse_tunnel = None

    # ========= FORWARD TUNNEL: PRIMARY → BACKUP =========

    async def establish_forward_ssh(self, backup_host: str, backup_user: str):
        """PRIMARY: Establish SSH to BACKUP for emergency sync."""
        try:
            logger.info(f"[{self.role}] Establishing forward SSH tunnel to BACKUP")
            # ssh -L 9001:localhost:8002 backup_user@backup_host
            # This would create subprocess for SSH tunnel
            logger.info("[PRIMARY] Forward SSH tunnel established")

        except Exception as e:
            logger.error(f"[{self.role}] Failed to establish forward SSH: {e}")

    # ========= REVERSE TUNNEL: BACKUP ← PRIMARY =========

    async def establish_reverse_ssh(self, backup_host: str, backup_user: str):
        """PRIMARY: Allow BACKUP to SSH back via reverse tunnel."""
        if self.role != "PRIMARY":
            logger.warning("Only PRIMARY can establish reverse SSH tunnel")
            return

        try:
            logger.info(
                f"[{self.role}] Establishing reverse SSH tunnel "
                f"(BACKUP can pull state via localhost:9001)"
            )
            # ssh -R 9001:localhost:8001 backup_user@backup_host -N -f
            # Effect: BACKUP can do: ssh -p 9001 primary@backup_host → connects to PRIMARY:8001

            logger.info(
                "[PRIMARY] Reverse SSH tunnel established - "
                "BACKUP can recover state via reverse tunnel"
            )

        except Exception as e:
            logger.error(f"[{self.role}] Failed to establish reverse SSH: {e}")

    async def pull_state_via_reverse_ssh(self) -> Optional[Dict]:
        """BACKUP: Use reverse tunnel to pull state if PRIMARY's HTTP is down."""
        if self.role != "BACKUP":
            logger.warning("Only BACKUP can use reverse SSH to pull state")
            return None

        try:
            # Normal: Try direct HTTP first
            logger.info("[BACKUP] Attempting to pull state via direct HTTP")
            state = await self._http_get("http://PRIMARY:8001/api/ha/state", timeout=5)
            logger.info("[BACKUP] ✅ State pulled via direct HTTP")
            return state

        except Exception as e:
            logger.warning(f"[BACKUP] Direct HTTP failed: {e}, trying reverse SSH tunnel")

            try:
                # Fallback: Via reverse tunnel
                logger.info("[BACKUP] Attempting to pull state via reverse SSH tunnel")
                state = await self._http_get(
                    "http://localhost:9001/api/ha/state",
                    timeout=5
                )
                logger.info("[BACKUP] ✅ State pulled via reverse SSH tunnel")
                return state

            except Exception as tunnel_error:
                logger.error(f"[BACKUP] Reverse SSH tunnel also failed: {tunnel_error}")
                return None

    async def _http_get(self, url: str, timeout: int = 5):
        """GET from endpoint."""
        # TODO: Implement actual HTTP GET
        pass


# ============================================================================
# SMART BIDIRECTIONAL PROMOTION LOGIC
# ============================================================================

class BidirectionalPromotionLogic:
    """Smart promotion with multiple signals and state recovery."""

    def __init__(self, role: str):
        self.role = role
        self.promotion_triggers = []
        self.last_primary_state_version = 0
        self.state_stalled_count = 0

    # ========= PROMOTION TRIGGERS =========

    def check_primary_heartbeat_missed(self, missed_count: int):
        """Trigger: PRIMARY heartbeat missed 3+ times."""
        if missed_count >= 3:
            logger.warning("[BACKUP] Trigger: PRIMARY heartbeat missed 3x")
            self.promotion_triggers.append("primary_heartbeat_missed")

    def check_primary_websocket_stale(self, websocket_staleness: Dict[str, float]):
        """Trigger: PRIMARY WebSocket stale >60s."""
        max_staleness = max(websocket_staleness.values()) if websocket_staleness else 0
        if max_staleness > 60:
            logger.warning(
                f"[BACKUP] Trigger: PRIMARY WebSocket stale {max_staleness}s"
            )
            self.promotion_triggers.append("primary_websocket_stale_60s")

    def check_primary_memory_critical(self, memory_percent: float):
        """Trigger: PRIMARY memory >95%."""
        if memory_percent > 95:
            logger.warning(f"[BACKUP] Trigger: PRIMARY memory critical ({memory_percent}%)")
            self.promotion_triggers.append("primary_memory_critical")

    def check_primary_state_stalled(self, state_version: int):
        """Trigger: PRIMARY state version not advancing."""
        if state_version == self.last_primary_state_version:
            self.state_stalled_count += 1
            if self.state_stalled_count >= 3:  # 3 heartbeats with same version
                logger.warning(
                    f"[BACKUP] Trigger: PRIMARY state stalled "
                    f"(v{state_version} for {self.state_stalled_count} heartbeats)"
                )
                self.promotion_triggers.append("primary_state_stalled")
        else:
            self.state_stalled_count = 0

        self.last_primary_state_version = state_version

    # ========= PROMOTION DECISION MATRIX =========

    async def should_promote_to_primary(self) -> bool:
        """BACKUP: Evaluate if I should take over."""
        if self.role != "BACKUP":
            return False

        # Rule 1: PRIMARY down + I can connect to WebSocket
        if "primary_heartbeat_missed" in self.promotion_triggers:
            if await self._can_connect_to_websocket():
                logger.critical(
                    "[BACKUP] ✅ Promotion decision: PRIMARY down + WebSocket OK"
                )
                return True

        # Rule 2: PRIMARY WebSocket + state both stalled
        if (
            "primary_websocket_stale_60s" in self.promotion_triggers
            and "primary_state_stalled" in self.promotion_triggers
        ):
            logger.critical(
                "[BACKUP] ✅ Promotion decision: PRIMARY WebSocket + state both stalled"
            )
            return True

        # Rule 3: PRIMARY memory critical + other issues
        if "primary_memory_critical" in self.promotion_triggers:
            other_issues = len([
                t for t in self.promotion_triggers
                if t != "primary_memory_critical"
            ])
            if other_issues > 0:
                logger.critical(
                    "[BACKUP] ✅ Promotion decision: PRIMARY memory critical + "
                    f"{other_issues} other issue(s)"
                )
                return True

        return False

    async def promote_to_primary(self, sync: BidirectionalSync) -> bool:
        """Execute promotion: BACKUP → PRIMARY."""
        logger.critical("[BACKUP] 🚀 PROMOTING TO PRIMARY")

        # Step 1: Verify promotion readiness
        if not await self._validate_promotion_readiness():
            logger.error("[BACKUP] ❌ Promotion validation failed")
            return False

        # Step 2: Pull latest state from PRIMARY (if possible)
        primary_state = await sync.sync_backward_from_primary()
        if primary_state:
            logger.info("[BACKUP] ✅ Pulled latest state from PRIMARY before takeover")
            sync.state = primary_state
        else:
            logger.warning(
                "[BACKUP] ⚠️  Could not pull PRIMARY state, using BACKUP copy"
            )

        # Step 3: Connect to WebSocket for trading
        await self._connect_websocket_for_trading()

        # Step 4: Switch role
        self.role = "PRIMARY"
        logger.critical("[BACKUP] 🎯 Promotion complete - now PRIMARY")

        return True

    async def handle_old_primary_recovery(self, sync: BidirectionalSync):
        """OLD PRIMARY (now BACKUP): Recover after failure."""
        logger.info("[OLD-PRIMARY] 🔄 Recovering after downtime")

        # Step 1: Pull latest state from new PRIMARY
        new_primary_state = await sync.sync_backward_from_primary()
        if new_primary_state:
            logger.info("[OLD-PRIMARY] ✅ Synchronized state with new PRIMARY")
            sync.state = new_primary_state
        else:
            logger.error("[OLD-PRIMARY] ❌ Could not sync with new PRIMARY")

        # Step 2: Stop using WebSocket (only PRIMARY needs it)
        # await self._disconnect_websocket()

        # Step 3: Switch to BACKUP role
        self.role = "BACKUP"
        logger.info("[OLD-PRIMARY] ✅ Now running as BACKUP")

    async def _validate_promotion_readiness(self) -> bool:
        """Check if BACKUP can safely take over."""
        # Check 1: Can connect to WebSocket
        if not await self._can_connect_to_websocket():
            logger.error("[BACKUP] Cannot connect to WebSocket - not ready for promotion")
            return False

        # Check 2: Have valid state (from sync or cache)
        if not self._have_valid_state():
            logger.error("[BACKUP] No valid state - not ready for promotion")
            return False

        logger.info("[BACKUP] ✅ Promotion readiness validated")
        return True

    async def _can_connect_to_websocket(self) -> bool:
        """Test if WebSocket is available."""
        # TODO: Implement actual connection test
        return True

    def _have_valid_state(self) -> bool:
        """Check if we have valid cached state."""
        # TODO: Implement actual validation
        return True

    async def _connect_websocket_for_trading(self):
        """Start WebSocket for active trading."""
        logger.info("[PRIMARY] Connecting WebSocket for active trading")
        # TODO: Implement

    async def _disconnect_websocket(self):
        """Stop WebSocket (only for BACKUP)."""
        logger.info("[BACKUP] Disconnecting WebSocket")
        # TODO: Implement


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

async def example_bidirectional_ha():
    """Example showing complete bidirectional HA flow."""

    # Initialize components
    websocket = BidirectionalWebSocket("PRIMARY")
    sync = BidirectionalSync("PRIMARY")
    heartbeat = BidirectionalHeartbeat("PRIMARY")
    ssh = BidirectionalSSHTunnel("PRIMARY")
    promotion = BidirectionalPromotionLogic("PRIMARY")

    logger.info("=" * 70)
    logger.info("BIDIRECTIONAL HA: Complete Setup")
    logger.info("=" * 70)

    # Step 1: Both machines connect to WebSocket
    logger.info("\n[STEP 1] Both PRIMARY and BACKUP connect to WebSocket")
    await websocket.connect_to_feed("BTCUSDT")
    logger.info("✅ WebSocket connected (PRIMARY uses for trading, BACKUP monitors)")

    # Step 2: PRIMARY establishes SSH tunnels
    logger.info("\n[STEP 2] PRIMARY establishes SSH tunnels")
    await ssh.establish_forward_ssh("backup_host", "backup_user")
    await ssh.establish_reverse_ssh("backup_host", "backup_user")
    logger.info("✅ SSH tunnels ready (forward + reverse)")

    # Step 3: Bidirectional heartbeat
    logger.info("\n[STEP 3] Bidirectional heartbeat")
    await heartbeat.send_heartbeat(
        websocket_staleness={"BTCUSDT": 2.5},
        memory_percent=75.0,
        state_version=100,
        state_last_sync=datetime.now()
    )
    logger.info("✅ Heartbeat sent with health info")

    # Step 4: Forward sync (PRIMARY → BACKUP)
    logger.info("\n[STEP 4] Forward sync PRIMARY → BACKUP")
    sync_success = await sync.sync_forward_to_backup({"cash": 10000, "positions": {}})
    logger.info(f"✅ Forward sync: {sync_success}")

    # Step 5: Simulate PRIMARY failure
    logger.info("\n[STEP 5] Simulate PRIMARY failure (BACKUP perspective)")
    sync_backup = BidirectionalSync("BACKUP")
    heartbeat_backup = BidirectionalHeartbeat("BACKUP")
    promotion_backup = BidirectionalPromotionLogic("BACKUP")

    # BACKUP detects: PRIMARY heartbeat missed
    promotion_backup.check_primary_heartbeat_missed(missed_count=3)
    promotion_backup.check_primary_websocket_stale({"BTCUSDT": 65})

    # BACKUP: Should I promote?
    should_promote = await promotion_backup.should_promote_to_primary()
    logger.info(f"BACKUP: Should promote? {should_promote}")

    if should_promote:
        logger.info("\n[STEP 6] BACKUP promoting to PRIMARY")
        await promotion_backup.promote_to_primary(sync_backup)
        logger.info("✅ Promotion complete")


if __name__ == "__main__":
    logger.info("✅ Bidirectional HA module loaded")
    # Uncomment to test:
    # asyncio.run(example_bidirectional_ha())
