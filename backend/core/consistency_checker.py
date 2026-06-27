"""Platform-Wide Data Consistency Verification (NFR-010A)

Ensures PRIMARY, BACKUP, databases, and in-memory state are all synchronized.
This is critical for HA failover correctness.
"""

import logging
from typing import Dict, List, Tuple
import json

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """Verify state consistency across PRIMARY, BACKUP, and databases."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check_trade_consistency(self, primary_trades: List[Dict], backup_trades: List[Dict]) -> bool:
        """Verify trade lists are identical across PRIMARY and BACKUP.

        Args:
            primary_trades: Trade list from PRIMARY API
            backup_trades: Trade list from BACKUP API

        Returns:
            True if consistent, False otherwise
        """
        self.errors = []
        self.warnings = []

        # Check trade count
        if len(primary_trades) != len(backup_trades):
            self.errors.append(
                f"Trade count mismatch: PRIMARY={len(primary_trades)}, "
                f"BACKUP={len(backup_trades)}"
            )
            return False

        # Check each trade
        for i, (primary_trade, backup_trade) in enumerate(zip(primary_trades, backup_trades)):
            if not self._compare_trades(primary_trade, backup_trade, index=i):
                return False

        return True

    def _compare_trades(self, primary: Dict, backup: Dict, index: int) -> bool:
        """Compare individual trades from PRIMARY and BACKUP."""
        critical_fields = [
            "symbol", "side", "quantity", "price", "realized_pnl", "order_id", "status"
        ]

        for field in critical_fields:
            primary_val = primary.get(field)
            backup_val = backup.get(field)

            # Handle float comparison with tolerance
            if field in ["price", "realized_pnl"]:
                if abs(float(primary_val or 0) - float(backup_val or 0)) > 0.01:
                    self.errors.append(
                        f"Trade {index} {field} mismatch: "
                        f"PRIMARY={primary_val}, BACKUP={backup_val}"
                    )
                    return False
            else:
                if primary_val != backup_val:
                    self.errors.append(
                        f"Trade {index} {field} mismatch: "
                        f"PRIMARY={primary_val}, BACKUP={backup_val}"
                    )
                    return False

        return True

    def check_account_state_consistency(
        self, primary_state: Dict, backup_state: Dict
    ) -> bool:
        """Verify account state (cash, P&L) is identical."""
        self.errors = []

        fields = ["cash", "total_pnl", "daily_pnl"]

        for field in fields:
            primary_val = float(primary_state.get(field, 0))
            backup_val = float(backup_state.get(field, 0))

            if abs(primary_val - backup_val) > 0.01:
                self.errors.append(
                    f"{field} mismatch: PRIMARY={primary_val:.2f}, "
                    f"BACKUP={backup_val:.2f}"
                )
                return False

        return True

    def check_positions_consistency(
        self, primary_positions: List[Dict], backup_positions: List[Dict]
    ) -> bool:
        """Verify open positions are identical."""
        self.errors = []

        if len(primary_positions) != len(backup_positions):
            self.errors.append(
                f"Position count mismatch: PRIMARY={len(primary_positions)}, "
                f"BACKUP={len(backup_positions)}"
            )
            return False

        # Check each position
        primary_by_symbol = {p["symbol"]: p for p in primary_positions}
        backup_by_symbol = {p["symbol"]: p for p in backup_positions}

        if set(primary_by_symbol.keys()) != set(backup_by_symbol.keys()):
            self.errors.append(
                f"Position symbols mismatch: "
                f"PRIMARY={set(primary_by_symbol.keys())}, "
                f"BACKUP={set(backup_by_symbol.keys())}"
            )
            return False

        for symbol in primary_by_symbol:
            primary_pos = primary_by_symbol[symbol]
            backup_pos = backup_by_symbol[symbol]

            for field in ["quantity", "entry_price", "current_price"]:
                primary_val = float(primary_pos.get(field, 0))
                backup_val = float(backup_pos.get(field, 0))

                if abs(primary_val - backup_val) > 0.0001:
                    self.errors.append(
                        f"Position {symbol} {field} mismatch: "
                        f"PRIMARY={primary_val}, BACKUP={backup_val}"
                    )
                    return False

        return True

    def get_error_report(self) -> str:
        """Generate consistency report."""
        if not self.errors:
            return "✅ Platform consistency verified: All systems in sync"

        report = "❌ CONSISTENCY VIOLATIONS:\n"
        for error in self.errors:
            report += f"  - {error}\n"

        if self.warnings:
            report += "\n⚠️ WARNINGS:\n"
            for warning in self.warnings:
                report += f"  - {warning}\n"

        return report

    def log_errors(self):
        """Log all errors to application logger."""
        for error in self.errors:
            logger.error(f"🔴 {error}")

        for warning in self.warnings:
            logger.warning(f"⚠️ {warning}")


def verify_platform_consistency(
    primary_state: Dict, backup_state: Dict
) -> Tuple[bool, str]:
    """Verify entire platform is consistent.

    Args:
        primary_state: State from PRIMARY API
        backup_state: State from BACKUP API

    Returns:
        (is_consistent, error_report)
    """
    checker = ConsistencyChecker()

    # Check account state
    if not checker.check_account_state_consistency(
        primary_state.get("account", {}),
        backup_state.get("account", {})
    ):
        return False, checker.get_error_report()

    # Check trades
    if not checker.check_trade_consistency(
        primary_state.get("trades", []),
        backup_state.get("trades", [])
    ):
        return False, checker.get_error_report()

    # Check positions
    if not checker.check_positions_consistency(
        primary_state.get("positions", []),
        backup_state.get("positions", [])
    ):
        return False, checker.get_error_report()

    return True, checker.get_error_report()
