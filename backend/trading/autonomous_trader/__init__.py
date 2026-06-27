"""Autonomous trader package - monitors signals and executes trades."""

from .core import (
    AutonomousTrader,
    TradingConfig,
    TradeSignal,
    log_trading_decision,
    init_autonomous_trader,
    get_autonomous_trader,
)

__all__ = [
    "AutonomousTrader",
    "TradingConfig",
    "TradeSignal",
    "log_trading_decision",
    "init_autonomous_trader",
    "get_autonomous_trader",
]
