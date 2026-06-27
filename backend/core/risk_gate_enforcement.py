"""Risk Gate Enforcement: Actual trading halts, not just warnings

Prevents:
- Trades exceeding loss limits
- Over-leveraging
- Position size violations
- Cascade losses
"""

import logging
from typing import Dict, Tuple, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class RiskGateEnforcer:
    """Enforce risk gates with actual trading halts."""

    def __init__(
        self,
        max_daily_loss_pct: float = 5.0,
        max_position_size_pct: float = 10.0,
        max_positions: int = 10,
        max_leverage: float = 1.0,
    ):
        """Initialize risk gate enforcer.

        Args:
            max_daily_loss_pct: Max daily loss % (5% = halt)
            max_position_size_pct: Max single position size % (10% = halt)
            max_positions: Max concurrent positions
            max_leverage: Max leverage (1.0 = no leverage)
        """
        self.max_daily_loss_pct = Decimal(str(max_daily_loss_pct))
        self.max_position_size_pct = Decimal(str(max_position_size_pct))
        self.max_positions = max_positions
        self.max_leverage = Decimal(str(max_leverage))

    def check_daily_loss(
        self,
        daily_pnl: float,
        account_equity: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check if daily loss exceeds limit.

        Args:
            daily_pnl: Today's P&L
            account_equity: Total account equity

        Returns:
            (True if OK, error message if NOT OK)
        """
        if account_equity <= 0:
            return False, "Invalid account equity"

        pnl = Decimal(str(daily_pnl))
        equity = Decimal(str(account_equity))

        daily_loss_pct = (abs(pnl) / equity * 100).quantize(Decimal("0.01"))

        if pnl < 0 and daily_loss_pct >= self.max_daily_loss_pct:
            msg = f"❌ TRADING HALTED: Daily loss €{pnl:.2f} ({daily_loss_pct}%) exceeds limit {self.max_daily_loss_pct}%"
            logger.critical(msg)
            return False, msg

        return True, None

    def check_position_size(
        self,
        position_value: float,
        account_equity: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check if position exceeds max size.

        Args:
            position_value: Value of proposed position
            account_equity: Total account equity

        Returns:
            (True if OK, error message if NOT OK)
        """
        if account_equity <= 0:
            return False, "Invalid account equity"

        pos_value = Decimal(str(position_value))
        equity = Decimal(str(account_equity))

        position_pct = (pos_value / equity * 100).quantize(Decimal("0.01"))

        if position_pct > self.max_position_size_pct:
            msg = f"❌ POSITION TOO LARGE: €{pos_value:.2f} ({position_pct}%) exceeds limit {self.max_position_size_pct}%"
            logger.critical(msg)
            return False, msg

        return True, None

    def check_position_count(
        self,
        current_positions: int,
    ) -> Tuple[bool, Optional[str]]:
        """Check if too many positions open.

        Args:
            current_positions: Number of open positions

        Returns:
            (True if OK, error message if NOT OK)
        """
        if current_positions >= self.max_positions:
            msg = f"❌ TOO MANY POSITIONS: {current_positions} >= {self.max_positions}"
            logger.critical(msg)
            return False, msg

        return True, None

    def check_leverage(
        self,
        total_position_value: float,
        available_balance: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check if leverage exceeds limit.

        Args:
            total_position_value: Total value of all positions
            available_balance: Available cash balance

        Returns:
            (True if OK, error message if NOT OK)
        """
        if available_balance <= 0:
            return False, "No available balance"

        pos = Decimal(str(total_position_value))
        bal = Decimal(str(available_balance))

        leverage = pos / bal

        if leverage > self.max_leverage:
            msg = f"❌ EXCESSIVE LEVERAGE: {leverage}x exceeds {self.max_leverage}x limit"
            logger.critical(msg)
            return False, msg

        return True, None

    def enforce_all_gates(
        self,
        daily_pnl: float,
        account_equity: float,
        proposed_position_value: float,
        current_positions: int,
        total_position_value: float,
        available_balance: float,
    ) -> Tuple[bool, Optional[str]]:
        """Check all risk gates at once.

        Args:
            daily_pnl: Today's P&L
            account_equity: Total equity
            proposed_position_value: Value of new position
            current_positions: Number of open positions
            total_position_value: Value of all positions
            available_balance: Available cash

        Returns:
            (True if all gates pass, error message if any fails)
        """
        # Check daily loss
        ok, msg = self.check_daily_loss(daily_pnl, account_equity)
        if not ok:
            return False, msg

        # Check position size
        ok, msg = self.check_position_size(proposed_position_value, account_equity)
        if not ok:
            return False, msg

        # Check position count
        ok, msg = self.check_position_count(current_positions)
        if not ok:
            return False, msg

        # Check leverage
        ok, msg = self.check_leverage(total_position_value, available_balance)
        if not ok:
            return False, msg

        logger.info("✅ All risk gates PASSED")
        return True, None

    def get_status(self) -> Dict:
        """Get risk gate configuration."""
        return {
            "max_daily_loss_pct": float(self.max_daily_loss_pct),
            "max_position_size_pct": float(self.max_position_size_pct),
            "max_positions": self.max_positions,
            "max_leverage": float(self.max_leverage),
        }


# Global instance
_risk_gate_enforcer: Optional[RiskGateEnforcer] = None


def init_risk_gate_enforcer(
    max_daily_loss_pct: float = 5.0,
    max_position_size_pct: float = 10.0,
    max_positions: int = 10,
    max_leverage: float = 1.0,
) -> RiskGateEnforcer:
    """Initialize global risk gate enforcer."""
    global _risk_gate_enforcer
    _risk_gate_enforcer = RiskGateEnforcer(
        max_daily_loss_pct=max_daily_loss_pct,
        max_position_size_pct=max_position_size_pct,
        max_positions=max_positions,
        max_leverage=max_leverage,
    )
    logger.info("✅ Risk Gate Enforcer initialized")
    return _risk_gate_enforcer


def get_risk_gate_enforcer() -> RiskGateEnforcer:
    """Get global risk gate enforcer."""
    global _risk_gate_enforcer
    if _risk_gate_enforcer is None:
        _risk_gate_enforcer = RiskGateEnforcer()
    return _risk_gate_enforcer
