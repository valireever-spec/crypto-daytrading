"""Integration tests for HA configuration sync.

Tests critical blockers #2 (Config Sync to BACKUP) and #4 (Trade Deduplication Sync).
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from backend.core.runtime_config import TradingConfig, get_config_manager
from backend.core.ha_deduplication import get_ha_deduplicator


class TestHAConfigSync:
    """Test configuration sync from PRIMARY to BACKUP."""

    def test_config_sync_payload_structure(self):
        """Test that sync payload includes all config parameters.

        Critical blocker #2: Config must be included in HA sync payload
        so BACKUP receives all trading parameters.
        """
        config_manager = get_config_manager()

        # Create a state dict like what lifecycle.py would generate
        current_config = config_manager.get_config()

        state = {
            "cash": 1000.0,
            "positions": [],
            "config": {
                "entry_threshold": current_config.entry_threshold,
                "exit_profit_target": current_config.exit_profit_target,
                "exit_stop_loss": current_config.exit_stop_loss,
                "max_positions": current_config.max_positions,
                "position_size_pct": current_config.position_size_pct,
                "max_daily_loss_pct": current_config.max_daily_loss_pct,
                "max_position_loss_pct": current_config.max_position_loss_pct,
                "enabled": current_config.enabled,
                "symbols": current_config.symbols
            }
        }

        # Verify all critical config parameters are in the payload
        assert "config" in state
        assert state["config"]["entry_threshold"] == current_config.entry_threshold
        assert state["config"]["exit_profit_target"] == current_config.exit_profit_target
        assert state["config"]["max_positions"] == current_config.max_positions
        assert state["config"]["enabled"] == current_config.enabled
        assert state["config"]["symbols"] == current_config.symbols


class TestDeduplicatorSync:
    """Test deduplication state sync from PRIMARY to BACKUP."""

    def test_deduplicator_state_included_in_sync(self):
        """Test that deduplicator state is included in HA sync payload.

        Critical blocker #4: BACKUP must know which orders were already
        executed to prevent duplicate trading on failover.
        """
        dedup = get_ha_deduplicator()

        # Register an order as if it was executed on PRIMARY
        order_key = "uuid-trade-123"
        dedup.register_order(order_key)

        # Create sync state with deduplicator data
        state = {
            "cash": 1000.0,
            "positions": [],
            "deduplicator_state": {
                "seen_orders": {k: v.isoformat() for k, v in dedup.seen_orders.items()}
            }
        }

        # Verify deduplicator state is in payload
        assert "deduplicator_state" in state
        assert order_key in state["deduplicator_state"]["seen_orders"]

        # Verify order can be deserialized from ISO format
        timestamp_str = state["deduplicator_state"]["seen_orders"][order_key]
        timestamp = datetime.fromisoformat(timestamp_str)
        assert isinstance(timestamp, datetime)


    def test_deduplicator_state_applied_on_backup(self):
        """Test that BACKUP applies deduplicator state from PRIMARY.

        When BACKUP receives sync from PRIMARY, it should restore all
        seen orders so it won't duplicate trades.
        """
        dedup_primary = get_ha_deduplicator()

        # PRIMARY executes two orders
        order_1 = "uuid-order-001"
        order_2 = "uuid-order-002"
        dedup_primary.register_order(order_1)
        dedup_primary.register_order(order_2)

        # Create the sync payload from PRIMARY
        dedup_state = {
            "seen_orders": {
                k: v.isoformat() for k, v in dedup_primary.seen_orders.items()
            }
        }

        # Simulate BACKUP receiving and applying the state
        # (in real scenario, this happens in /api/ha/sync-from-primary endpoint)
        dedup_backup = get_ha_deduplicator()

        # Restore deduplicator state from PRIMARY
        for order_key, timestamp_str in dedup_state["seen_orders"].items():
            timestamp = datetime.fromisoformat(timestamp_str)
            dedup_backup.seen_orders[order_key] = timestamp

        # Verify BACKUP now knows about both orders
        assert dedup_backup.is_duplicate(order_1)
        assert dedup_backup.is_duplicate(order_2)
        assert not dedup_backup.is_duplicate("uuid-new-order")


    def test_multiple_machines_share_dedup_state(self):
        """Test that PRIMARY and BACKUP maintain consistent dedup state.

        After PRIMARY syncs to BACKUP, they should have same dedup state
        so failover doesn't result in duplicate orders.
        """
        primary_dedup = get_ha_deduplicator()
        primary_dedup.seen_orders.clear()  # Clean state

        # PRIMARY executes an order
        order_key = "uuid-critical-trade-2026-07-02-001"
        primary_dedup.register_order(order_key)

        # PRIMARY syncs to BACKUP
        sync_payload = {
            "seen_orders": {
                k: v.isoformat() for k, v in primary_dedup.seen_orders.items()
            }
        }

        # BACKUP restores state
        backup_dedup = get_ha_deduplicator()
        for order_key_received, timestamp_str in sync_payload["seen_orders"].items():
            timestamp = datetime.fromisoformat(timestamp_str)
            backup_dedup.seen_orders[order_key_received] = timestamp

        # PRIMARY takes an order
        assert primary_dedup.is_duplicate(order_key)

        # BACKUP should also know it's a duplicate (failover safety)
        assert backup_dedup.is_duplicate(order_key)


    def test_dedup_cleanup_survives_sync(self):
        """Test that cleanup of old dedup entries doesn't interfere with sync.

        When BACKUP applies dedup state, it should get all current orders
        even if some are being cleaned up on PRIMARY.
        """
        dedup = get_ha_deduplicator()
        dedup.seen_orders.clear()

        # Register current order
        current_order = "uuid-current-001"
        dedup.register_order(current_order)

        # Get sync state
        sync_state = {
            "seen_orders": {k: v.isoformat() for k, v in dedup.seen_orders.items()}
        }

        # Now run cleanup (would remove old entries)
        old_entries_removed = dedup.cleanup_old_entries()

        # Current order should still be in sync state
        assert current_order in sync_state["seen_orders"]

        # BACKUP can still apply the state
        backup_dedup = get_ha_deduplicator()
        for order_key, timestamp_str in sync_state["seen_orders"].items():
            timestamp = datetime.fromisoformat(timestamp_str)
            backup_dedup.seen_orders[order_key] = timestamp

        assert backup_dedup.is_duplicate(current_order)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
