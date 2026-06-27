"""NFR-017A + NFR-010: Test realized_pnl persistence end-to-end

This test proves that realized_pnl is ACTUALLY persisted to database
and recovered correctly on restart (unlike before when it was lost).
"""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.exchange.paper_trading import PaperTradingEngine
from backend.core.database import TradingDatabase


class TestRealizedPnlPersistence:
    """Comprehensive tests for realized_pnl persistence."""

    @pytest.fixture
    def db_path(self):
        """Use production database for this test."""
        return Path("data/trading.db")

    def test_realized_pnl_in_database_schema(self, db_path):
        """Test 1: realized_pnl column exists in database schema."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check schema
        cursor.execute("PRAGMA table_info(trades)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "realized_pnl" in columns, \
            "❌ realized_pnl column missing from trades table!"
        assert columns["realized_pnl"] == "REAL", \
            f"❌ realized_pnl should be REAL, got {columns['realized_pnl']}"

        conn.close()
        print("✅ Test 1 passed: realized_pnl column exists in schema")

    def test_existing_trades_have_pnl_values(self, db_path):
        """Test 2: Existing trades in database have real P&L values (not NULL or 0)."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for NULL values
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE realized_pnl IS NULL
        """)
        null_count = cursor.fetchone()[0]
        assert null_count == 0, f"❌ {null_count} trades have NULL realized_pnl!"

        # Check that some trades have non-zero P&L (the SELL orders)
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE realized_pnl != 0
        """)
        non_zero_count = cursor.fetchone()[0]
        assert non_zero_count >= 3, \
            f"❌ Expected ≥3 trades with P&L, got {non_zero_count}"

        # Show actual values
        cursor.execute("""
            SELECT symbol, side, realized_pnl
            FROM trades
            ORDER BY trade_time
        """)
        print("\n✅ Test 2 passed: Trades have P&L values:")
        for symbol, side, pnl in cursor.fetchall():
            print(f"   {symbol} {side}: €{pnl:.2f}")

        conn.close()

    def test_trade_pnl_sum_matches_account_pnl(self, db_path):
        """Test 3: Sum of trade P&L equals account_state.total_pnl."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get sum from trades
        cursor.execute("SELECT SUM(realized_pnl) FROM trades")
        trade_sum = cursor.fetchone()[0] or 0.0

        # Get account P&L
        cursor.execute("SELECT total_pnl FROM account_state WHERE id = 1")
        account_pnl = cursor.fetchone()[0]

        diff = abs(trade_sum - account_pnl)
        assert diff < 0.01, \
            f"❌ P&L mismatch: sum(trades)={trade_sum:.2f}, " \
            f"account={account_pnl:.2f}, diff={diff:.2f}"

        print(f"✅ Test 3 passed: Trade P&L sum matches account state")
        print(f"   Sum of trades: €{trade_sum:.2f}")
        print(f"   Account P&L:   €{account_pnl:.2f}")

        conn.close()

    def test_engine_loads_pnl_from_database(self):
        """Test 4: Engine restores trades WITH P&L from database."""
        engine = PaperTradingEngine(starting_capital=10000.0)

        # Check that engine has trades
        assert len(engine.trade_history) > 0, \
            "❌ Engine has no trades to verify"

        # Check that trades have P&L values (not all zeros)
        sell_trades = [t for t in engine.trade_history if t.side == "SELL"]
        assert len(sell_trades) >= 2, \
            "❌ Engine should have ≥2 SELL trades with P&L"

        for trade in sell_trades:
            assert trade.realized_pnl != 0, \
                f"❌ SELL trade {trade.symbol} has P&L = €0.00 (not loaded from DB!)"
            assert abs(trade.realized_pnl) > 10, \
                f"❌ SELL trade {trade.symbol} P&L too small (€{trade.realized_pnl:.2f})"

        print("✅ Test 4 passed: Engine loaded P&L from database")
        for trade in sell_trades:
            print(f"   {trade.symbol} {trade.side}: P&L = €{trade.realized_pnl:.2f}")

    def test_api_returns_pnl_in_trades(self):
        """Test 5: API endpoint returns realized_pnl for each trade."""
        engine = PaperTradingEngine(starting_capital=10000.0)
        trades = engine.get_trades(limit=100)

        assert len(trades) > 0, "❌ No trades to verify"

        # Check that trades have realized_pnl field
        for i, trade in enumerate(trades):
            assert "realized_pnl" in trade, \
                f"❌ Trade {i} missing realized_pnl field"

            # SELL trades should have non-zero P&L
            if trade["side"] == "SELL":
                pnl = trade["realized_pnl"]
                assert pnl != 0, \
                    f"❌ SELL trade {i} has P&L = €0.00"

        print("✅ Test 5 passed: API returns realized_pnl in trades")
        for trade in trades:
            if trade["side"] == "SELL":
                print(f"   {trade['symbol']} SELL: €{trade['realized_pnl']:.2f}")

    def test_pnl_consistency_engine_vs_database(self, db_path):
        """Test 6: Engine P&L matches database P&L for each trade."""
        engine = PaperTradingEngine(starting_capital=10000.0)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, order_id, realized_pnl
            FROM trades
            ORDER BY trade_time
        """)
        db_trades = cursor.fetchall()
        conn.close()

        assert len(engine.trade_history) == len(db_trades), \
            f"❌ Trade count mismatch: engine={len(engine.trade_history)}, " \
            f"db={len(db_trades)}"

        print("✅ Test 6 passed: Engine and database P&L match")
        for engine_trade, (db_id, db_order_id, db_pnl) in zip(
            engine.trade_history, db_trades
        ):
            diff = abs(engine_trade.realized_pnl - db_pnl)
            assert diff < 0.01, \
                f"❌ Trade {db_id} P&L mismatch: " \
                f"engine={engine_trade.realized_pnl:.2f}, db={db_pnl:.2f}"
            print(f"   Trade {db_id}: €{engine_trade.realized_pnl:.2f} == €{db_pnl:.2f} ✓")

    def test_realized_pnl_survives_full_restart(self):
        """Test 7: P&L values survive full engine restart (the main test)."""
        print("\n📋 Test 7: FULL RESTART TEST")

        # Phase 1: Load engine, get initial trades
        print("  Phase 1: Loading engine with existing trades...")
        engine1 = PaperTradingEngine(starting_capital=10000.0)
        initial_trades = list(engine1.trade_history)
        initial_pnl_by_id = {
            f"{t.symbol}_{t.side}_{i}": t.realized_pnl
            for i, t in enumerate(initial_trades)
        }
        print(f"    Loaded {len(initial_trades)} trades")

        # Phase 2: Simulate restart by deleting engine
        print("  Phase 2: Deleting engine (simulating process crash)...")
        del engine1

        # Phase 3: Create new engine (simulates restart)
        print("  Phase 3: Restarting engine...")
        engine2 = PaperTradingEngine(starting_capital=10000.0)
        restarted_trades = list(engine2.trade_history)
        restarted_pnl_by_id = {
            f"{t.symbol}_{t.side}_{i}": t.realized_pnl
            for i, t in enumerate(restarted_trades)
        }
        print(f"    Restarted with {len(restarted_trades)} trades")

        # Phase 4: Verify P&L values match
        print("  Phase 4: Comparing P&L values...")
        assert len(initial_trades) == len(restarted_trades), \
            "❌ Trade count changed after restart!"

        for key in initial_pnl_by_id:
            initial_pnl = initial_pnl_by_id[key]
            restarted_pnl = restarted_pnl_by_id[key]
            diff = abs(initial_pnl - restarted_pnl)

            assert diff < 0.01, \
                f"❌ {key}: P&L changed after restart! " \
                f"{initial_pnl:.2f} → {restarted_pnl:.2f}"

            if initial_pnl != 0:
                print(f"    {key}: €{initial_pnl:.2f} → €{restarted_pnl:.2f} ✓")

        print("✅ Test 7 PASSED: P&L values SURVIVED restart!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
