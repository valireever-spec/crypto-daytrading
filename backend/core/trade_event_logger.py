"""Enhanced structured logging for trading events (Blocker #4 fix).

Provides rich context logging for all critical trading operations:
- Entry/exit decisions with full context
- State transitions with timestamps
- Performance metrics
- Risk gate evaluations
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TradeEvent:
    """Structured trade event for logging."""

    event_type: str  # "ENTRY", "EXIT", "SIGNAL", "RISK_GATE", "STATE_TRANSITION"
    timestamp: str
    symbol: Optional[str] = None
    side: Optional[str] = None  # BUY, SELL
    signal_strength: Optional[float] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    hold_time_seconds: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to loggable dict."""
        data = asdict(self)
        # Remove None values for cleaner logs
        return {k: v for k, v in data.items() if v is not None}


class TradeEventLogger:
    """Logs structured trade events with full context."""

    def __init__(self):
        """Initialize trade event logger."""
        self.logger = logging.getLogger("backend.trading.events")

    def log_entry_signal(
        self,
        symbol: str,
        signal_strength: float,
        reason: str,
        data_quality: float,
        websocket_age: float,
        entry_threshold: int,
    ) -> None:
        """Log entry signal evaluation."""
        event = TradeEvent(
            event_type="ENTRY_SIGNAL",
            timestamp=datetime.utcnow().isoformat() + "Z",
            symbol=symbol,
            signal_strength=signal_strength,
            reason=reason,
            context={
                "data_quality_pct": round(data_quality, 1),
                "websocket_age_seconds": round(websocket_age, 1),
                "entry_threshold": entry_threshold,
                "signal_passes_threshold": signal_strength >= entry_threshold,
            },
        )
        self.logger.info(
            f"ENTRY_SIGNAL: {symbol} strength={signal_strength:.0f} "
            f"(quality={data_quality:.0f}%, ws_age={websocket_age:.1f}s)",
            extra={"extra_fields": event.to_log_dict()},
        )

    def log_entry_execution(
        self,
        symbol: str,
        quantity: float,
        price: float,
        cash_before: float,
        cash_after: float,
    ) -> None:
        """Log entry order execution."""
        position_value = quantity * price
        event = TradeEvent(
            event_type="ENTRY_EXECUTION",
            timestamp=datetime.utcnow().isoformat() + "Z",
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            context={
                "position_value": round(position_value, 2),
                "cash_before": round(cash_before, 2),
                "cash_after": round(cash_after, 2),
                "cash_used": round(cash_before - cash_after, 2),
            },
        )
        self.logger.info(
            f"ENTRY_EXECUTION: {symbol} {quantity:.4f} @ ${price:.2f}",
            extra={"extra_fields": event.to_log_dict()},
        )

    def log_exit_decision(
        self,
        symbol: str,
        pnl: float,
        pnl_pct: float,
        reason: str,
        websocket_age: float,
        data_quality: float,
    ) -> None:
        """Log exit decision evaluation."""
        event = TradeEvent(
            event_type="EXIT_DECISION",
            timestamp=datetime.utcnow().isoformat() + "Z",
            symbol=symbol,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            reason=reason,
            context={
                "websocket_age_seconds": round(websocket_age, 1),
                "data_quality_pct": round(data_quality, 1),
            },
        )
        emoji = "✅" if pnl_pct > 0 else "❌"
        self.logger.info(
            f"EXIT_DECISION: {emoji} {symbol} P&L={pnl_pct:+.2f}% ({reason})",
            extra={"extra_fields": event.to_log_dict()},
        )

    def log_exit_execution(
        self,
        symbol: str,
        quantity: float,
        price: float,
        pnl: float,
        cash_after: float,
    ) -> None:
        """Log exit order execution."""
        event = TradeEvent(
            event_type="EXIT_EXECUTION",
            timestamp=datetime.utcnow().isoformat() + "Z",
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=price,
            pnl=round(pnl, 2),
            context={
                "exit_value": round(quantity * price, 2),
                "cash_after": round(cash_after, 2),
            },
        )
        self.logger.info(
            f"EXIT_EXECUTION: {symbol} {quantity:.4f} @ ${price:.2f}, P&L=${pnl:.2f}",
            extra={"extra_fields": event.to_log_dict()},
        )

    def log_risk_gate_evaluation(
        self,
        gate_name: str,
        passed: bool,
        data_quality: float,
        websocket_stale: bool,
        circuit_breaker_open: bool,
    ) -> None:
        """Log risk gate evaluation."""
        event = TradeEvent(
            event_type="RISK_GATE_EVAL",
            timestamp=datetime.utcnow().isoformat() + "Z",
            reason=gate_name,
            context={
                "passed": passed,
                "data_quality_pct": round(data_quality, 1),
                "websocket_stale": websocket_stale,
                "circuit_breaker_open": circuit_breaker_open,
            },
        )
        status = "PASS" if passed else "FAIL"
        self.logger.info(
            f"RISK_GATE: {status} {gate_name} (quality={data_quality:.0f}%)",
            extra={"extra_fields": event.to_log_dict()},
        )

    def log_state_transition(
        self,
        from_state: str,
        to_state: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log state machine transition."""
        event = TradeEvent(
            event_type="STATE_TRANSITION",
            timestamp=datetime.utcnow().isoformat() + "Z",
            reason=reason,
            context={
                "from_state": from_state,
                "to_state": to_state,
                **(context or {}),
            },
        )
        self.logger.info(
            f"STATE_TRANSITION: {from_state} → {to_state} ({reason})",
            extra={"extra_fields": event.to_log_dict()},
        )


# Global instance
_trade_event_logger: Optional[TradeEventLogger] = None


def get_trade_event_logger() -> TradeEventLogger:
    """Get or create global trade event logger."""
    global _trade_event_logger
    if _trade_event_logger is None:
        _trade_event_logger = TradeEventLogger()
    return _trade_event_logger


def init_trade_event_logger() -> TradeEventLogger:
    """Initialize trade event logger."""
    global _trade_event_logger
    _trade_event_logger = TradeEventLogger()
    logger.info("Trade event logger initialized")
    return _trade_event_logger
