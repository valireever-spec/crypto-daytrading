"""NFR-010: Database Durability Tests
Verify that in-memory state syncs permanently with database.
Tests crash recovery: API restart must restore exact pre-crash state.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
import sys
import tempfile
import os
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.exchange.paper_trading import PaperTradingEngine
from backend.core.database import TradingDatabase


@pytest.fixture
def isolated_db():
    """Create isolated test database that doesn't interfere with production."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_trading.db"

        # Create fresh schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Exact schema from backend/core/database.py
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL CHECK(quantity > 0),
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                status TEXT DEFAULT 'OPEN',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                quantity REAL NOT NULL CHECK(quantity > 0),
                price REAL NOT NULL,
                trade_time TEXT NOT NULL,
                order_id TEXT UNIQUE,
                status TEXT DEFAULT 'FILLED',
                slippage_pct REAL,
                hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL DEFAULT 10000.0,
                total_pnl REAL DEFAULT 0.0,
                daily_pnl REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO account_state (id, cash, total_pnl, daily_pnl)
            VALUES (1, 10000.0, 0.0, 0.0)
        """)

        conn.commit()
        conn.close()

        yield db_path


@pytest.fixture
def mock_get_database(isolated_db):
    """Mock get_database to use isolated test database."""
    def _get_test_db():
        return TradingDatabase(db_path=str(isolated_db))

    with patch('backend.exchange.paper_trading.get_database', side_effect=_get_test_db):
        yield _get_test_db


class TestDatabaseDurability:
    """Test suite for NFR-010: Database Durability."""

    def test_trade_persists_to_database(self, mock_get_database, isolated_db):
        """Test: Trade written to DB immediately after execution."""
        # Create engine with mocked database
        engine = PaperTradingEngine(starting_capital=10000.0)
        initial_cash = engine.cash

        # Execute trade: BUY 0.01 BTC @ 45,000
        import asyncio
        result = asyncio.run(engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            current_price=45000.0,
            order_type="MARKET"
        ))

        assert result["status"] == "FILLED", f"Order failed: {result}"
        assert engine.cash < initial_cash, "Cash should decrease after buy"
        assert len(engine.trade_history) == 1, "Trade should be in memory"

        # Verify database has trade
        conn = sqlite3.connect(isolated_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        assert trade_count == 1, f"Expected 1 trade in DB, got {trade_count}"
        conn.close()

    def test_account_state_persists_after_trade(self, mock_get_database, isolated_db):
        """Test: Cash and P&L persisted to account_state table after trade."""
        engine = PaperTradingEngine(starting_capital=10000.0)

        # Execute BUY trade
        import asyncio
        asyncio.run(engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            current_price=45000.0,
            order_type="MARKET"
        ))

        in_memory_cash = engine.cash

        # Verify database has same cash value
        conn = sqlite3.connect(isolated_db)
        cursor = conn.cursor()
        cursor.execute("SELECT cash FROM account_state WHERE id = 1")
        db_cash = cursor.fetchone()[0]
        conn.close()

        assert abs(in_memory_cash - db_cash) < 0.01, \
            f"Cash mismatch after trade: in-memory={in_memory_cash}, db={db_cash}"

    def test_state_recovery_after_restart(self, mock_get_database, isolated_db):
        """Test: Execute trade, create new engine, verify state recovered."""
        import asyncio

        # PHASE 1: Create engine, execute trade
        engine1 = PaperTradingEngine(starting_capital=10000.0)

        # Trade 1: BUY BTC
        asyncio.run(engine1.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            current_price=45000.0,
            order_type="MARKET"
        ))

        # Trade 2: SELL BTC (close position)
        asyncio.run(engine1.place_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.01,
            current_price=46000.0,
            order_type="MARKET"
        ))

        # Save state before "restart"
        pre_restart_cash = engine1.cash
        pre_restart_pnl = engine1.total_pnl
        pre_restart_trades = len(engine1.trade_history)

        del engine1  # Simulate process crash

        # PHASE 2: Create new engine (simulates API restart)
        engine2 = PaperTradingEngine(starting_capital=10000.0)

        # Verify state recovered
        assert engine2.cash == pre_restart_cash, \
            f"Cash not recovered: expected {pre_restart_cash}, got {engine2.cash}"
        assert abs(engine2.total_pnl - pre_restart_pnl) < 0.01, \
            f"P&L not recovered: expected {pre_restart_pnl}, got {engine2.total_pnl}"
        assert len(engine2.trade_history) == pre_restart_trades, \
            f"Trades not recovered: expected {pre_restart_trades}, got {len(engine2.trade_history)}"

    def test_multiple_restarts_preserve_state(self, mock_get_database, isolated_db):
        """Test: Execute trades, restart 3 times, verify state preserved."""
        import asyncio

        trades_expected = 0

        for cycle in range(3):
            engine = PaperTradingEngine(starting_capital=10000.0)

            # Verify previous trades persisted
            assert len(engine.trade_history) == trades_expected, \
                f"Cycle {cycle}: Expected {trades_expected} trades, got {len(engine.trade_history)}"

            # Execute 1 new trade
            if cycle % 2 == 0:  # BUY
                result = asyncio.run(engine.place_order(
                    symbol="BTCUSDT",
                    side="BUY",
                    quantity=0.01,
                    current_price=45000.0 + (cycle * 100),
                    order_type="MARKET"
                ))
            else:  # SELL
                result = asyncio.run(engine.place_order(
                    symbol="BTCUSDT",
                    side="SELL",
                    quantity=0.01,
                    current_price=46000.0 + (cycle * 100),
                    order_type="MARKET"
                ))

            assert result["status"] == "FILLED"
            trades_expected += 1
            assert len(engine.trade_history) == trades_expected

            del engine  # Simulate restart

        # Final verification
        engine_final = PaperTradingEngine(starting_capital=10000.0)
        assert len(engine_final.trade_history) == 3, \
            f"Final state: Expected 3 trades, got {len(engine_final.trade_history)}"

    def test_database_matches_in_memory_exactly(self, mock_get_database, isolated_db):
        """Test: After 3 trades, DB state matches in-memory exactly."""
        import asyncio

        engine = PaperTradingEngine(starting_capital=10000.0)

        # Execute 3 trades
        prices = [45000, 46000, 45500]
        for i, price in enumerate(prices):
            side = "BUY" if i % 2 == 0 else "SELL"
            asyncio.run(engine.place_order(
                symbol="BTCUSDT",
                side=side,
                quantity=0.01,
                current_price=price,
                order_type="MARKET"
            ))

        # Compare with database
        conn = sqlite3.connect(isolated_db)
        cursor = conn.cursor()

        # Trade count
        cursor.execute("SELECT COUNT(*) FROM trades")
        db_trade_count = cursor.fetchone()[0]
        assert db_trade_count == len(engine.trade_history)

        # Account state
        cursor.execute("SELECT cash, total_pnl FROM account_state WHERE id = 1")
        db_cash, db_pnl = cursor.fetchone()

        assert abs(engine.cash - db_cash) < 0.01, \
            f"Cash mismatch: in-memory={engine.cash}, db={db_cash}"
        assert abs(engine.total_pnl - db_pnl) < 0.01, \
            f"P&L mismatch: in-memory={engine.total_pnl}, db={db_pnl}"

        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
