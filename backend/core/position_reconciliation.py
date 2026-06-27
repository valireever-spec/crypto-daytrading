"""Position Reconciliation: Catch & Alert on Position Mismatches

Prevents:
- Position tracking errors
- Untracked liquidations
- Wrong risk calculations
- Capital loss from silent mismatches
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionSnapshot:
    """Snapshot of position at a point in time."""
    symbol: str
    quantity: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "timestamp": self.timestamp,
        }


class PositionReconciliationManager:
    """Reconcile positions between local DB and Binance."""

    def __init__(self):
        """Initialize position reconciliation manager."""
        self.local_positions: Dict[str, PositionSnapshot] = {}
        self.last_reconciliation: Optional[datetime] = None
        self.reconciliation_interval = timedelta(hours=1)  # Every hour
        self.mismatch_history: List[Dict] = []

    async def reconcile(
        self,
        local_positions: Dict[str, Dict],
        binance_positions: Dict[str, Dict],
    ) -> Dict:
        """Reconcile local positions with Binance.

        Args:
            local_positions: {symbol: {quantity, entry_price}}
            binance_positions: {symbol: {quantity, entry_price}} from Binance API

        Returns:
            {
                "status": "OK" | "MISMATCH" | "CRITICAL",
                "matches": 3,
                "mismatches": 1,
                "issues": [...]
            }
        """
        logger.info("🔄 Starting position reconciliation with Binance...")

        issues = []
        matches = 0
        mismatches = 0

        # Check each local position against Binance
        for symbol, local_pos in local_positions.items():
            binance_pos = binance_positions.get(symbol, {})
            local_qty = local_pos.get("quantity", 0)
            binance_qty = binance_pos.get("quantity", 0)

            if abs(local_qty - binance_qty) < 0.00001:  # Allow float rounding
                matches += 1
                logger.debug(f"  ✅ {symbol}: {local_qty} (match)")
            else:
                mismatches += 1
                mismatch = {
                    "symbol": symbol,
                    "local_quantity": local_qty,
                    "binance_quantity": binance_qty,
                    "difference": binance_qty - local_qty,
                    "timestamp": datetime.utcnow().isoformat(),
                    "severity": "CRITICAL" if abs(binance_qty - local_qty) > 0.01 else "WARNING",
                }
                issues.append(mismatch)
                self.mismatch_history.append(mismatch)

                logger.warning(
                    f"  ⚠️  MISMATCH {symbol}: Local={local_qty}, Binance={binance_qty}, Diff={binance_qty - local_qty}"
                )

        # Check for Binance positions we don't know about
        for symbol, binance_pos in binance_positions.items():
            if symbol not in local_positions:
                binance_qty = binance_pos.get("quantity", 0)
                if binance_qty > 0:
                    issues.append({
                        "symbol": symbol,
                        "type": "POSITION_ON_BINANCE_UNKNOWN_LOCALLY",
                        "binance_quantity": binance_qty,
                        "severity": "CRITICAL",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    logger.error(f"  ❌ UNKNOWN POSITION: {symbol} ({binance_qty} on Binance, 0 local)")

        self.last_reconciliation = datetime.utcnow()

        # Determine overall status
        if not issues:
            status = "OK"
            logger.info(f"✅ Position reconciliation OK: {matches} matches")
        elif any(i.get("severity") == "CRITICAL" for i in issues):
            status = "CRITICAL"
            logger.critical(
                f"🚨 CRITICAL position mismatches: {sum(1 for i in issues if i.get('severity') == 'CRITICAL')}"
            )
        else:
            status = "MISMATCH"
            logger.warning(f"⚠️  Position mismatches found: {len(issues)}")

        return {
            "status": status,
            "matches": matches,
            "mismatches": mismatches,
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat(),
            "next_reconciliation": (
                self.last_reconciliation + self.reconciliation_interval
            ).isoformat(),
        }

    def should_reconcile(self) -> bool:
        """Check if reconciliation is due."""
        if self.last_reconciliation is None:
            return True  # First time

        time_since = datetime.utcnow() - self.last_reconciliation
        return time_since >= self.reconciliation_interval

    async def get_reconciliation_urgency(self) -> Dict:
        """Get whether reconciliation is urgent."""
        if not self.mismatch_history:
            return {"urgent": False, "reason": "No mismatches"}

        critical_mismatches = [
            m for m in self.mismatch_history[-24:]
            if m.get("severity") == "CRITICAL"
        ]

        if critical_mismatches:
            return {
                "urgent": True,
                "reason": f"CRITICAL mismatches: {len(critical_mismatches)}",
                "issues": critical_mismatches,
            }

        if len(self.mismatch_history) > 5:
            return {
                "urgent": True,
                "reason": f"Multiple mismatches: {len(self.mismatch_history)}",
            }

        return {"urgent": False, "reason": "Normal operation"}

    def get_mismatch_stats(self) -> Dict:
        """Get statistics on position mismatches."""
        if not self.mismatch_history:
            return {"total": 0, "critical": 0, "warning": 0}

        critical = len([m for m in self.mismatch_history if m.get("severity") == "CRITICAL"])
        warning = len(self.mismatch_history) - critical

        return {
            "total": len(self.mismatch_history),
            "critical": critical,
            "warning": warning,
            "last_mismatch": self.mismatch_history[-1] if self.mismatch_history else None,
        }


# Global instance
_position_reconciliation_manager: Optional[PositionReconciliationManager] = None


def init_position_reconciliation() -> PositionReconciliationManager:
    """Initialize global position reconciliation manager."""
    global _position_reconciliation_manager
    _position_reconciliation_manager = PositionReconciliationManager()
    logger.info("✅ Position Reconciliation Manager initialized")
    return _position_reconciliation_manager


def get_position_reconciliation() -> PositionReconciliationManager:
    """Get global position reconciliation manager."""
    global _position_reconciliation_manager
    if _position_reconciliation_manager is None:
        _position_reconciliation_manager = PositionReconciliationManager()
    return _position_reconciliation_manager
