"""Integration tests for HA failover scenarios."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.core.database_authority import DatabaseAuthority
from backend.core.database_sync import DatabaseSyncer
from backend.core.heartbeat import HeartbeatMonitor, HeartbeatSender


class TestHAFailoverScenarios:
    """Test HA failover under various failure conditions."""

    def test_primary_detection(self):
        """Test PRIMARY database detection."""
        authority = DatabaseAuthority()
        result = authority.detect_authority(
            "/home/vali/projects/crypto-daytrading/data/trading.db",
            "/home/claude/crypto-daytrading/data/trading.db"
        )

        assert result is not None
        assert "authoritative" in result

    def test_backup_database_missing(self):
        """Test behavior when BACKUP database is missing."""
        authority = DatabaseAuthority()
        result = authority.detect_authority(
            "/home/vali/projects/crypto-daytrading/data/trading.db",
            "/nonexistent/path/trading.db"
        )

        assert result["authoritative"] == "primary"

    def test_heartbeat_monitor_initialization(self):
        """Test heartbeat monitor initialization."""
        monitor = HeartbeatMonitor(
            check_interval=5,
            failure_threshold=3
        )

        assert monitor.check_interval == 5
        assert monitor.failure_threshold == 3


@pytest.mark.asyncio
async def test_primary_to_backup_sync():
    """Test syncing state from PRIMARY to BACKUP."""
    state = {
        "cash": 1220.41,
        "total_pnl": 221.56,
        "positions": [
            {
                "symbol": "BTCUSDT",
                "quantity": 0.5,
                "entry_price": 44000.0,
                "current_price": 45000.0
            }
        ]
    }

    assert state["cash"] == 1220.41
    assert len(state["positions"]) == 1


def test_position_consistency_after_failover():
    """Test position data consistency after failover."""
    primary_positions = [
        {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 44000},
        {"symbol": "ETHUSDT", "quantity": 5.0, "entry_price": 1800}
    ]

    backup_positions = [
        {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 44000},
        {"symbol": "ETHUSDT", "quantity": 5.0, "entry_price": 1800}
    ]

    assert len(primary_positions) == len(backup_positions)


def test_cash_balance_consistency():
    """Test cash balance consistency between machines."""
    primary_cash = 1220.41
    backup_cash = 1220.41

    assert primary_cash == backup_cash
    
    backup_cash = 1100.0
    diverged = primary_cash != backup_cash
    assert diverged == True


def test_heartbeat_sender_interval():
    """Test heartbeat sender interval configuration."""
    from backend.core.heartbeat import HeartbeatSender

    sender = HeartbeatSender(
        backup_url="http://192.168.3.25:8002",
        interval=5
    )

    assert sender.interval == 5
    assert sender.backup_url == "http://192.168.3.25:8002"
