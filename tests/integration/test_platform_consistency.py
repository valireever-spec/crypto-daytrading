"""NFR-010A: Platform-Wide Data Consistency Tests

Verify PRIMARY, BACKUP, and databases are all synchronized.
"""

import pytest
import requests
import json
from backend.core.consistency_checker import ConsistencyChecker, verify_platform_consistency


class TestPlatformConsistency:
    """Test suite for NFR-010A: Platform-wide consistency."""

    @pytest.fixture
    def primary_url(self):
        return "http://127.0.0.1:8001"

    @pytest.fixture
    def backup_url(self):
        return "http://192.168.3.25:8002"

    def test_account_state_matches_across_machines(self, primary_url, backup_url):
        """Test: Account state (cash, P&L) identical on PRIMARY and BACKUP."""
        # Get PRIMARY state
        primary_account = requests.get(f"{primary_url}/api/paper/account").json()

        # Get BACKUP state
        backup_account = requests.get(f"{backup_url}/api/paper/account").json()

        # Compare critical fields
        assert abs(primary_account["cash"] - backup_account["cash"]) < 0.01, \
            f"Cash mismatch: PRIMARY={primary_account['cash']}, BACKUP={backup_account['cash']}"
        assert abs(primary_account["total_pnl"] - backup_account["total_pnl"]) < 0.01, \
            f"P&L mismatch: PRIMARY={primary_account['total_pnl']}, BACKUP={backup_account['total_pnl']}"
        assert primary_account["trades_today"] == backup_account["trades_today"], \
            f"Trade count mismatch: PRIMARY={primary_account['trades_today']}, BACKUP={backup_account['trades_today']}"

    def test_trade_details_match_across_machines(self, primary_url, backup_url):
        """Test: Every trade detail (P&L, price, qty) identical on PRIMARY and BACKUP."""
        # Get PRIMARY trades
        primary_resp = requests.get(f"{primary_url}/api/paper/trades").json()
        primary_trades = primary_resp.get("trades", [])

        # Get BACKUP trades
        backup_resp = requests.get(f"{backup_url}/api/paper/trades").json()
        backup_trades = backup_resp.get("trades", [])

        assert len(primary_trades) == len(backup_trades), \
            f"Trade count: PRIMARY={len(primary_trades)}, BACKUP={len(backup_trades)}"

        # Compare each trade
        for i, (primary_trade, backup_trade) in enumerate(zip(primary_trades, backup_trades)):
            assert primary_trade["symbol"] == backup_trade["symbol"], \
                f"Trade {i} symbol mismatch"
            assert primary_trade["side"] == backup_trade["side"], \
                f"Trade {i} side mismatch"
            assert abs(primary_trade["quantity"] - backup_trade["quantity"]) < 0.0001, \
                f"Trade {i} qty mismatch"
            assert abs(primary_trade["price"] - backup_trade["price"]) < 0.01, \
                f"Trade {i} price mismatch"
            assert abs(primary_trade["realized_pnl"] - backup_trade["realized_pnl"]) < 0.01, \
                f"Trade {i} P&L mismatch: PRIMARY={primary_trade['realized_pnl']}, " \
                f"BACKUP={backup_trade['realized_pnl']}"

    def test_positions_match_across_machines(self, primary_url, backup_url):
        """Test: Open positions identical on PRIMARY and BACKUP."""
        # Get PRIMARY positions
        primary_resp = requests.get(f"{primary_url}/api/paper/positions").json()
        primary_positions = primary_resp.get("positions", [])

        # Get BACKUP positions
        backup_resp = requests.get(f"{backup_url}/api/paper/positions").json()
        backup_positions = backup_resp.get("positions", [])

        assert len(primary_positions) == len(backup_positions), \
            f"Position count: PRIMARY={len(primary_positions)}, BACKUP={len(backup_positions)}"

        # Compare each position
        primary_by_symbol = {p["symbol"]: p for p in primary_positions}
        backup_by_symbol = {p["symbol"]: p for p in backup_positions}

        assert set(primary_by_symbol.keys()) == set(backup_by_symbol.keys()), \
            f"Position symbols mismatch"

        for symbol in primary_by_symbol:
            primary_pos = primary_by_symbol[symbol]
            backup_pos = backup_by_symbol[symbol]

            assert abs(primary_pos["quantity"] - backup_pos["quantity"]) < 0.0001, \
                f"Position {symbol} qty mismatch"
            assert abs(primary_pos["entry_price"] - backup_pos["entry_price"]) < 0.01, \
                f"Position {symbol} entry price mismatch"

    def test_consistency_checker_validates_state(self, primary_url, backup_url):
        """Test: ConsistencyChecker correctly identifies mismatches."""
        # Get PRIMARY state
        primary_account = requests.get(f"{primary_url}/api/paper/account").json()
        primary_trades = requests.get(f"{primary_url}/api/paper/trades").json()["trades"]

        # Get BACKUP state
        backup_account = requests.get(f"{backup_url}/api/paper/account").json()
        backup_trades = requests.get(f"{backup_url}/api/paper/trades").json()["trades"]

        # Verify consistency
        checker = ConsistencyChecker()

        # Account state check
        is_consistent = checker.check_account_state_consistency(
            primary_account, backup_account
        )
        assert is_consistent, f"Account mismatch: {checker.get_error_report()}"

        # Trade check
        is_consistent = checker.check_trade_consistency(primary_trades, backup_trades)
        assert is_consistent, f"Trade mismatch: {checker.get_error_report()}"

    def test_full_platform_consistency(self, primary_url, backup_url):
        """Test: Full platform consistency check passes."""
        # Get combined state
        primary_account = requests.get(f"{primary_url}/api/paper/account").json()
        primary_trades = requests.get(f"{primary_url}/api/paper/trades").json()["trades"]
        primary_positions = requests.get(f"{primary_url}/api/paper/positions").json()["positions"]

        backup_account = requests.get(f"{backup_url}/api/paper/account").json()
        backup_trades = requests.get(f"{backup_url}/api/paper/trades").json()["trades"]
        backup_positions = requests.get(f"{backup_url}/api/paper/positions").json()["positions"]

        primary_state = {
            "account": primary_account,
            "trades": primary_trades,
            "positions": primary_positions,
        }
        backup_state = {
            "account": backup_account,
            "trades": backup_trades,
            "positions": backup_positions,
        }

        # Verify
        is_consistent, report = verify_platform_consistency(primary_state, backup_state)
        assert is_consistent, f"Platform not consistent:\n{report}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
