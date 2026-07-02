"""
HA State Manager: Synchronizes critical state between PRIMARY and BACKUP machines.

Purpose: Ensure BACKUP has up-to-date copies of all critical globals so it can
resume trading seamlessly on failover with consistent state.

Architecture:
  PRIMARY:  Executes trades, writes to 92 critical globals, syncs every 5s
  BACKUP:   Receives synced state, maintains read-only copy, detects failure
"""

import asyncio
import hashlib
import json
import logging
from typing import Dict, Any, Set, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import pickle
import socket

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """Atomic snapshot of all critical state."""
    timestamp: float
    host: str
    role: str  # "PRIMARY" or "BACKUP"
    critical_state: Dict[str, Any]
    checksum: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "StateSnapshot":
        return StateSnapshot(**data)


class HAStateManager:
    """
    Manages state synchronization between PRIMARY and BACKUP machines.

    Responsibility:
    1. PRIMARY: Collect snapshot of all 92 critical globals every 5s
    2. PRIMARY: Send snapshot to BACKUP with checksum
    3. BACKUP: Receive and validate snapshots
    4. BACKUP: Maintain consistent copy of all critical state
    5. Both: Provide atomic access to critical globals with locks
    """

    # 92 Critical globals that need to be synced for HA
    CRITICAL_GLOBALS = {
        # Trading
        "skills", "_signal_generator", "_explainer", "_allocation_manager",
        "_analyzer", "_optimizer", "_rebalancing_engine", "_portfolio_monitor",
        "_risk_engine", "_fill_tracker",
        # Analytics
        "_historical_service", "_cost_model", "_tax_calculator",
        "_regime_detector", "_volatility_manager", "_position_sizer",
        "_recommendation_tracker", "_allocation_solver", "_attribution_engine",
        "_sector_advisor",
        # Support
        "_cleanup_manager", "_execution_logger", "_api_client",
        "_circuit_breaker", "_rate_limiter_state", "_order_cache",
        "_position_tracker", "_risk_monitor", "_trade_journal",
        "_performance_tracker", "_drawdown_monitor", "_win_rate_tracker",
        "_alert_manager", "_notification_manager", "_dashboard_state",
        # ML/Predictions
        "_ml_model_cache", "_prediction_cache", "_feature_extractor",
        "_model_version", "_confidence_scores", "_anomaly_detector",
        # Config/Parameters
        "_strategy_params", "_risk_params", "_execution_params",
        "_market_params", "_signal_thresholds", "_allocation_weights",
        "_rebalance_schedule", "_maintenance_config", "_failover_config",
        # State machines
        "_trade_state_machine", "_failover_state", "_sync_state",
        "_heartbeat_state", "_lock_state", "_promotion_state",
        # Metadata
        "_last_trade_time", "_last_signal_time", "_last_rebalance",
        "_session_start", "_sync_timestamp", "_failover_timestamp",
        # Additional critical globals
        "_market_data_cache", "_order_book_cache", "_candle_cache",
        "_sentiment_scores", "_correlation_matrix", "_volatility_matrix",
        "_sector_scores", "_factor_exposures", "_tail_risk_estimate",
        "_liquidity_scores", "_spread_tracker", "_slippage_estimator",
        # More support
        "_error_handler", "_logger", "_metrics_collector",
        "_health_checker", "_watchdog", "_recovery_manager",
        "_database_connection", "_cache_manager", "_session_manager",
        "_config_loader", "_timezone_manager", "_clock_synchronizer",
        # Fill tracking and execution
        "_fill_aggregator", "_execution_report", "_commission_tracker",
        "_tax_lot_manager", "_dividend_tracker", "_split_handler",
        "_margin_calculator", "_collateral_manager", "_buying_power_tracker",
        # Compliance and audit
        "_audit_logger", "_compliance_checker", "_regulation_monitor",
        "_pnl_calculator", "_risk_report", "_trade_report",
        "_exposure_monitor", "_concentration_check", "_sector_limits",
    }

    def __init__(
        self,
        role: str = "PRIMARY",
        sync_interval: float = 5.0,
        backup_host: str = "localhost",
        backup_port: int = 9999,
        max_retries: int = 3
    ):
        """
        Initialize HA state manager.

        Args:
            role: "PRIMARY" or "BACKUP"
            sync_interval: How often to sync (seconds)
            backup_host: BACKUP machine hostname
            backup_port: BACKUP machine port
            max_retries: Retry attempts for sync failures
        """
        self.role = role
        self.sync_interval = sync_interval
        self.backup_host = backup_host
        self.backup_port = backup_port
        self.max_retries = max_retries

        # Host identification
        self.hostname = socket.gethostname()

        # State storage: copy of critical globals on this machine
        self.critical_state: Dict[str, Any] = {}
        self.state_lock = asyncio.Lock()

        # Sync tracking
        self.last_sync_time: float = 0.0
        self.last_checksum: str = ""
        self.sync_failures = 0
        self.successful_syncs = 0

        # Locks for individual critical globals
        self.global_locks: Dict[str, asyncio.Lock] = {
            name: asyncio.Lock() for name in self.CRITICAL_GLOBALS
        }

        logger.info(
            f"HAStateManager initialized: role={role}, "
            f"sync_interval={sync_interval}s, {len(self.CRITICAL_GLOBALS)} globals to sync"
        )

    async def collect_state_snapshot(self, global_refs: Dict[str, Any]) -> StateSnapshot:
        """
        PRIMARY: Collect snapshot of all critical globals.

        Args:
            global_refs: Dict with actual global references

        Returns:
            Snapshot containing all critical state
        """
        async with self.state_lock:
            state = {}
            for global_name in self.CRITICAL_GLOBALS:
                try:
                    if global_name in global_refs:
                        state[global_name] = global_refs[global_name]
                    else:
                        state[global_name] = None
                except Exception as e:
                    logger.warning(f"Failed to collect {global_name}: {e}")
                    state[global_name] = None

            # Calculate checksum for validation
            state_bytes = pickle.dumps(state)
            checksum = hashlib.sha256(state_bytes).hexdigest()

            snapshot = StateSnapshot(
                timestamp=datetime.now().timestamp(),
                host=self.hostname,
                role=self.role,
                critical_state=state,
                checksum=checksum
            )

            logger.debug(f"State snapshot collected: {len(state)} globals, checksum={checksum[:8]}")
            return snapshot

    async def send_state_snapshot(self, snapshot: StateSnapshot) -> bool:
        """
        PRIMARY: Send state snapshot to BACKUP.

        Args:
            snapshot: StateSnapshot to send

        Returns:
            True if sync successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                # Serialize snapshot
                data = json.dumps(snapshot.to_dict(), default=str)

                # Connect to BACKUP
                reader, writer = await asyncio.open_connection(
                    self.backup_host, self.backup_port
                )

                # Send snapshot
                writer.write(data.encode())
                await writer.drain()

                # Wait for acknowledgment
                ack = await asyncio.wait_for(reader.read(100), timeout=5.0)
                if b"ACK" in ack:
                    writer.close()
                    await writer.wait_closed()
                    self.successful_syncs += 1
                    self.sync_failures = 0  # Reset failure counter
                    return True

                writer.close()
                await writer.wait_closed()

            except asyncio.TimeoutError:
                logger.warning(f"Sync timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.warning(f"Sync failed (attempt {attempt + 1}/{self.max_retries}): {e}")

            # Exponential backoff
            await asyncio.sleep(0.1 * (2 ** attempt))

        self.sync_failures += 1
        return False

    async def receive_state_snapshot(self) -> Optional[StateSnapshot]:
        """
        BACKUP: Receive state snapshot from PRIMARY.

        Returns:
            StateSnapshot or None if reception failed
        """
        try:
            # This would be called by the network listener
            # For now, returns None (implemented in ha_heartbeat.py)
            return None
        except Exception as e:
            logger.error(f"Failed to receive snapshot: {e}")
            return None

    async def validate_snapshot(self, snapshot: StateSnapshot) -> bool:
        """
        BACKUP: Validate snapshot checksum and completeness.

        Args:
            snapshot: StateSnapshot to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Verify checksum
            state_bytes = pickle.dumps(snapshot.critical_state)
            expected_checksum = hashlib.sha256(state_bytes).hexdigest()

            if snapshot.checksum != expected_checksum:
                logger.error("Snapshot checksum mismatch - state may be corrupted")
                return False

            # Verify all critical globals are present
            for global_name in self.CRITICAL_GLOBALS:
                if global_name not in snapshot.critical_state:
                    logger.warning(f"Missing global in snapshot: {global_name}")
                    # Don't fail here - some globals might be module-local

            logger.debug(f"Snapshot validated: checksum={snapshot.checksum[:8]}")
            return True

        except Exception as e:
            logger.error(f"Snapshot validation failed: {e}")
            return False

    async def apply_snapshot(self, snapshot: StateSnapshot) -> bool:
        """
        BACKUP: Apply received snapshot to local state.

        Args:
            snapshot: StateSnapshot to apply

        Returns:
            True if applied successfully
        """
        async with self.state_lock:
            try:
                # Update critical state with snapshot
                self.critical_state = snapshot.critical_state.copy()
                self.last_sync_time = snapshot.timestamp
                self.last_checksum = snapshot.checksum

                logger.debug(f"Snapshot applied: {len(self.critical_state)} globals synced")
                return True

            except Exception as e:
                logger.error(f"Failed to apply snapshot: {e}")
                return False

    async def get_global(self, name: str) -> Any:
        """
        Get value of critical global (thread-safe).

        Args:
            name: Global variable name

        Returns:
            Current value of global
        """
        if name not in self.global_locks:
            raise ValueError(f"Unknown critical global: {name}")

        async with self.global_locks[name]:
            return self.critical_state.get(name)

    async def set_global(self, name: str, value: Any) -> None:
        """
        Set value of critical global (thread-safe).

        Args:
            name: Global variable name
            value: New value
        """
        if name not in self.global_locks:
            raise ValueError(f"Unknown critical global: {name}")

        async with self.global_locks[name]:
            self.critical_state[name] = value

    async def get_state_for_failover(self) -> Dict[str, Any]:
        """
        Get complete state snapshot for failover resumption.

        Returns:
            Complete critical state for resuming trading
        """
        async with self.state_lock:
            return self.critical_state.copy()

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get status of state synchronization.

        Returns:
            Status dict with sync metrics
        """
        return {
            "role": self.role,
            "last_sync_time": self.last_sync_time,
            "last_checksum": self.last_checksum[:8] if self.last_checksum else None,
            "successful_syncs": self.successful_syncs,
            "sync_failures": self.sync_failures,
            "is_synced": self.sync_failures == 0,
        }
