"""Dynamic exit management with regime-aware risk controls (Phase 3 Week 2)."""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

from backend.analytics.regime_detector import get_regime_detector
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)


class ExitReason(str, Enum):
    """Reason for position exit."""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"
    RISK_LIMIT = "risk_limit"
    REBALANCE = "rebalance"
    MANUAL = "manual"


@dataclass
class ExitRule:
    """Exit rule for a position."""
    symbol: str
    regime: str
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float = 0.0  # Optional trailing stop
    max_holding_hours: float = 24.0  # Max time in position


@dataclass
class Position:
    """Active trading position."""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    regime: str
    strategy_name: str = "smart_gateway"
    max_loss_usd: float = 0.0
    max_gain_usd: float = 0.0
    high_water_mark: float = 0.0  # For trailing stops


@dataclass
class ExitSignal:
    """Signal to exit a position."""
    symbol: str
    quantity: float
    reason: ExitReason
    exit_price: float
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    holding_time_hours: float = 0.0
    regime: str = ""


class ExitManager:
    """Manage position exits with regime-aware rules."""

    def __init__(self):
        """Initialize exit manager."""
        self.positions: Dict[str, Position] = {}
        self.exit_history: List[ExitSignal] = []

    def add_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        regime: str,
        max_loss_usd: float = 0.0,
        max_gain_usd: float = 0.0,
    ) -> Position:
        """Add a new position to track.

        Args:
            symbol: Trading symbol
            quantity: Position quantity
            entry_price: Entry price
            regime: Current market regime
            max_loss_usd: Maximum loss in USD
            max_gain_usd: Maximum gain in USD

        Returns:
            Created Position object
        """
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            regime=regime,
            max_loss_usd=max_loss_usd,
            max_gain_usd=max_gain_usd,
            high_water_mark=entry_price,
        )

        self.positions[symbol] = position
        logger.info(f"Position added: {symbol} {quantity} @ ${entry_price:.2f} ({regime})")
        return position

    def get_exit_rule(self, symbol: str, regime: str) -> ExitRule:
        """Get exit rule for position based on regime.

        Args:
            symbol: Trading symbol
            regime: Current market regime

        Returns:
            ExitRule with stop loss, take profit, and trailing stop
        """
        detector = get_regime_detector()
        if not detector:
            # Default conservative rule
            return ExitRule(
                symbol=symbol,
                regime=regime,
                stop_loss_pct=2.0,
                take_profit_pct=3.0,
                trailing_stop_pct=1.0,
            )

        # Use get_adaptive_thresholds with regime info
        regime_info = {
            "regime": regime.lower(),
            "volatility_level": "medium",
            "rsi_value": 50.0,
        }
        thresholds = detector.get_adaptive_thresholds(regime_info)

        # Determine trailing stop based on regime
        trailing_stops = {
            "BULL": 1.5,  # Tight trailing in bull to protect gains
            "BEAR": 0.5,  # Loose trailing in bear (more volatility)
            "SIDEWAYS": 1.0,  # Medium trailing in sideways
            "VOLATILE": 0.0,  # No trailing in volatile (just use fixed stops)
        }

        trailing_stop = trailing_stops.get(regime, 1.0)

        return ExitRule(
            symbol=symbol,
            regime=regime,
            stop_loss_pct=thresholds.get("stop_loss", 0.02) * 100,  # Convert to percentage
            take_profit_pct=thresholds.get("profit_target", 0.05) * 100,  # Convert to percentage
            trailing_stop_pct=trailing_stop,
            max_holding_hours=12.0 if regime == "VOLATILE" else 24.0,
        )

    def check_exits(self, current_prices: Dict[str, float]) -> List[ExitSignal]:
        """Check all positions for exit signals.

        Args:
            current_prices: Dict mapping symbol to current price

        Returns:
            List of exit signals
        """
        signals = []

        for symbol, position in self.positions.items():
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            rule = self.get_exit_rule(symbol, position.regime)

            # Check exit conditions
            exit_signal = self._evaluate_exit(position, current_price, rule)

            if exit_signal:
                signals.append(exit_signal)
                logger.info(f"Exit signal: {symbol} - {exit_signal.reason.value}")

        return signals

    def _evaluate_exit(
        self, position: Position, current_price: float, rule: ExitRule
    ) -> Optional[ExitSignal]:
        """Evaluate exit conditions for a position.

        Args:
            position: Active position
            current_price: Current price
            rule: Exit rule for this regime

        Returns:
            ExitSignal if exit condition met, None otherwise
        """
        now = datetime.now()
        holding_time = (now - position.entry_time).total_seconds() / 3600

        # Check 1: Profit target hit
        gain_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        if gain_pct >= rule.take_profit_pct:
            pnl_usd = position.quantity * (current_price - position.entry_price)
            return ExitSignal(
                symbol=position.symbol,
                quantity=position.quantity,
                reason=ExitReason.PROFIT_TARGET,
                exit_price=current_price,
                pnl_usd=pnl_usd,
                pnl_pct=gain_pct,
                holding_time_hours=holding_time,
                regime=position.regime,
            )

        # Check 2: Stop loss hit
        loss_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        if loss_pct <= -rule.stop_loss_pct:
            pnl_usd = position.quantity * (current_price - position.entry_price)
            return ExitSignal(
                symbol=position.symbol,
                quantity=position.quantity,
                reason=ExitReason.STOP_LOSS,
                exit_price=current_price,
                pnl_usd=pnl_usd,
                pnl_pct=loss_pct,
                holding_time_hours=holding_time,
                regime=position.regime,
            )

        # Check 3: Trailing stop
        if rule.trailing_stop_pct > 0:
            position.high_water_mark = max(position.high_water_mark, current_price)
            drawdown_pct = (
                (position.high_water_mark - current_price) / position.high_water_mark * 100
            )
            if drawdown_pct >= rule.trailing_stop_pct and current_price < position.entry_price:
                pnl_usd = position.quantity * (current_price - position.entry_price)
                return ExitSignal(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    reason=ExitReason.TRAILING_STOP,
                    exit_price=current_price,
                    pnl_usd=pnl_usd,
                    pnl_pct=loss_pct,
                    holding_time_hours=holding_time,
                    regime=position.regime,
                )

        # Check 4: Time stop
        if holding_time >= rule.max_holding_hours:
            pnl_usd = position.quantity * (current_price - position.entry_price)
            return ExitSignal(
                symbol=position.symbol,
                quantity=position.quantity,
                reason=ExitReason.TIME_STOP,
                exit_price=current_price,
                pnl_usd=pnl_usd,
                pnl_pct=gain_pct,
                holding_time_hours=holding_time,
                regime=position.regime,
            )

        return None

    def execute_exit(self, signal: ExitSignal) -> bool:
        """Execute position exit.

        Args:
            signal: Exit signal

        Returns:
            True if exit executed, False otherwise
        """
        try:
            engine = get_paper_trading()
            if not engine:
                logger.error("Paper trading engine not initialized")
                return False

            position = self.positions.get(signal.symbol)
            if not position:
                logger.warning(f"Position {signal.symbol} not found")
                return False

            # Place sell order
            order_result = __import__("asyncio").run(
                engine.place_order(
                    symbol=signal.symbol,
                    side="SELL",
                    quantity=signal.quantity,
                    current_price=signal.exit_price,
                    order_type="MARKET",
                    strategy_name="exit_manager",
                )
            )

            if order_result.get("status") == "filled":
                # Record exit
                self.exit_history.append(signal)
                del self.positions[signal.symbol]

                logger.info(
                    f"Exit executed: {signal.symbol} {signal.quantity} @ "
                    f"${signal.exit_price:.2f} (PnL: ${signal.pnl_usd:.2f})"
                )
                return True
            else:
                logger.warning(f"Exit order rejected: {signal.symbol}")
                return False

        except Exception as e:
            logger.error(f"Exit execution error: {e}")
            return False

    def get_position_status(self, symbol: str, current_price: float) -> Dict:
        """Get current position status.

        Args:
            symbol: Trading symbol
            current_price: Current market price

        Returns:
            Dict with position metrics
        """
        position = self.positions.get(symbol)
        if not position:
            return {"error": f"No position for {symbol}"}

        gain_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        pnl_usd = position.quantity * (current_price - position.entry_price)
        holding_hours = (datetime.now() - position.entry_time).total_seconds() / 3600

        rule = self.get_exit_rule(symbol, position.regime)

        return {
            "symbol": symbol,
            "quantity": position.quantity,
            "entry_price": round(position.entry_price, 2),
            "current_price": round(current_price, 2),
            "gain_pct": round(gain_pct, 2),
            "pnl_usd": round(pnl_usd, 2),
            "holding_hours": round(holding_hours, 1),
            "regime": position.regime,
            "stop_loss_pct": rule.stop_loss_pct,
            "stop_loss_price": round(position.entry_price * (1 - rule.stop_loss_pct / 100), 2),
            "take_profit_pct": rule.take_profit_pct,
            "take_profit_price": round(
                position.entry_price * (1 + rule.take_profit_pct / 100), 2
            ),
            "trailing_stop_pct": rule.trailing_stop_pct,
            "max_holding_hours": rule.max_holding_hours,
        }

    def get_exit_history(self, limit: int = 100) -> List[Dict]:
        """Get recent exit history.

        Args:
            limit: Maximum number of exits to return

        Returns:
            List of exit signals
        """
        return [
            {
                "symbol": s.symbol,
                "quantity": s.quantity,
                "reason": s.reason.value,
                "exit_price": round(s.exit_price, 2),
                "pnl_usd": round(s.pnl_usd, 2),
                "pnl_pct": round(s.pnl_pct, 2),
                "holding_hours": round(s.holding_time_hours, 1),
            }
            for s in self.exit_history[-limit:]
        ]


# Global instance
_exit_manager: Optional[ExitManager] = None


def init_exit_manager() -> ExitManager:
    """Initialize global exit manager."""
    global _exit_manager
    _exit_manager = ExitManager()
    logger.info("Exit manager initialized")
    return _exit_manager


def get_exit_manager() -> Optional[ExitManager]:
    """Get global exit manager."""
    return _exit_manager
