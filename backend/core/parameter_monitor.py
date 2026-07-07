"""Real-time monitoring of critical trading parameters.

Tracks:
- Trend filter (1h RSI threshold for entry)
- Signals (generation rate, quality, filters passed)
- Stops (stop loss %, hits, effectiveness)
- Targets (profit target %, hits, effectiveness)
- Exit reasons (why positions closed)
- Entry reasons (why positions opened)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SignalParameter:
    """Tracks signal generation metrics."""
    timestamp: str
    symbol: str
    regime: str  # uptrend, downtrend, ranging
    rsi_1h: float
    rsi_5m: float
    trend_filter_passed: bool  # 1h RSI > 50?
    signal_strength: int  # 0-100
    entry_reason: str


@dataclass
class StopTargetParameter:
    """Tracks stop loss and profit target effectiveness."""
    timestamp: str
    symbol: str
    entry_price: float
    stop_loss_pct: float  # e.g., -0.5
    profit_target_pct: float  # e.g., +2.0
    current_price: float
    unrealized_pnl_pct: float


@dataclass
class ExitParameter:
    """Tracks exit decisions."""
    timestamp: str
    symbol: str
    exit_reason: str  # "Stop loss", "Profit target", "10-minute timeout"
    entry_price: float
    exit_price: float
    realized_pnl: float
    realized_pnl_pct: float
    hold_seconds: int


class ParameterMonitor:
    """Monitor critical trading parameters in real-time."""

    def __init__(self):
        self.signals: List[SignalParameter] = []
        self.stops_targets: List[StopTargetParameter] = []
        self.exits: List[ExitParameter] = []

        # Aggregates for quick stats
        self.signal_stats = defaultdict(int)  # {symbol: count}
        self.exit_reason_stats = defaultdict(int)  # {reason: count}
        self.entry_reason_stats = defaultdict(int)  # {reason: count}

    def record_signal(self, **kwargs) -> None:
        """Record signal generation."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        signal = SignalParameter(**kwargs)
        self.signals.append(signal)

        # Trim to last 1000
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:]

        # Update stats
        self.signal_stats[signal.symbol] += 1

    def record_stop_target(self, **kwargs) -> None:
        """Record stop loss and profit target state."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        st = StopTargetParameter(**kwargs)
        self.stops_targets.append(st)

        if len(self.stops_targets) > 500:
            self.stops_targets = self.stops_targets[-500:]

    def record_exit(self, **kwargs) -> None:
        """Record exit decision."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        exit_param = ExitParameter(**kwargs)
        self.exits.append(exit_param)

        if len(self.exits) > 500:
            self.exits = self.exits[-500:]

        # Update stats
        self.exit_reason_stats[exit_param.exit_reason] += 1

    def record_entry_reason(self, reason: str) -> None:
        """Track entry reason frequency."""
        self.entry_reason_stats[reason] += 1

    def get_trend_filter_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """Get trend filter (1h RSI > 50) effectiveness."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_signals = [
            s for s in self.signals
            if datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff
        ]

        if not recent_signals:
            return {
                "status": "NO_DATA",
                "total_signals": 0,
                "trend_filter_passed": 0,
                "pass_rate_pct": 0,
            }

        passed = sum(1 for s in recent_signals if s.trend_filter_passed)

        return {
            "status": "OK",
            "total_signals": len(recent_signals),
            "trend_filter_passed": passed,
            "trend_filter_failed": len(recent_signals) - passed,
            "pass_rate_pct": round((passed / len(recent_signals) * 100), 1),
            "recent_1h_rsi_range": {
                "min": round(min(s.rsi_1h for s in recent_signals), 1),
                "max": round(max(s.rsi_1h for s in recent_signals), 1),
                "current": round(recent_signals[-1].rsi_1h, 1) if recent_signals else 0,
            },
        }

    def get_signal_quality(self, minutes: int = 60) -> Dict[str, Any]:
        """Get signal quality metrics."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_signals = [
            s for s in self.signals
            if datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff
        ]

        if not recent_signals:
            return {"status": "NO_DATA", "total_signals": 0}

        avg_strength = sum(s.signal_strength for s in recent_signals) / len(recent_signals)
        regimes = defaultdict(int)
        for s in recent_signals:
            regimes[s.regime] += 1

        return {
            "status": "OK",
            "total_signals": len(recent_signals),
            "avg_strength": round(avg_strength, 1),
            "signal_strength_distribution": {
                "weak": sum(1 for s in recent_signals if s.signal_strength < 40),
                "medium": sum(1 for s in recent_signals if 40 <= s.signal_strength < 70),
                "strong": sum(1 for s in recent_signals if s.signal_strength >= 70),
            },
            "regime_distribution": dict(regimes),
            "signals_per_minute": round(len(recent_signals) / (minutes or 1), 2),
        }

    def get_stop_loss_stats(self, minutes: int = 120) -> Dict[str, Any]:
        """Get stop loss effectiveness."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_exits = [
            e for e in self.exits
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) > cutoff
            and e.exit_reason == "Stop loss"
        ]

        if not recent_exits:
            return {
                "status": "NO_DATA",
                "stop_loss_hits": 0,
                "avg_loss": 0,
            }

        _avg_loss = sum(e.realized_pnl for e in recent_exits) / len(recent_exits)
        avg_loss_pct = sum(e.realized_pnl_pct for e in recent_exits) / len(recent_exits)

        return {
            "status": "OK",
            "stop_loss_hits": len(recent_exits),
            "avg_loss_pct": round(avg_loss_pct, 3),
            "worst_loss_pct": round(min(e.realized_pnl_pct for e in recent_exits), 3),
            "best_loss_pct": round(max(e.realized_pnl_pct for e in recent_exits), 3),
            "avg_hold_seconds": round(sum(e.hold_seconds for e in recent_exits) / len(recent_exits), 0),
        }

    def get_profit_target_stats(self, minutes: int = 120) -> Dict[str, Any]:
        """Get profit target effectiveness."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_exits = [
            e for e in self.exits
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) > cutoff
            and e.exit_reason == "Profit target"
        ]

        if not recent_exits:
            return {
                "status": "NO_DATA",
                "profit_target_hits": 0,
                "avg_win": 0,
            }

        _avg_win = sum(e.realized_pnl for e in recent_exits) / len(recent_exits)
        avg_win_pct = sum(e.realized_pnl_pct for e in recent_exits) / len(recent_exits)

        return {
            "status": "OK",
            "profit_target_hits": len(recent_exits),
            "avg_win_pct": round(avg_win_pct, 3),
            "best_win_pct": round(max(e.realized_pnl_pct for e in recent_exits), 3),
            "worst_win_pct": round(min(e.realized_pnl_pct for e in recent_exits), 3),
            "avg_hold_seconds": round(sum(e.hold_seconds for e in recent_exits) / len(recent_exits), 0),
        }

    def get_exit_reason_distribution(self, minutes: int = 120) -> Dict[str, Any]:
        """Get breakdown of why positions closed."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_exits = [
            e for e in self.exits
            if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) > cutoff
        ]

        if not recent_exits:
            return {"status": "NO_DATA", "total_exits": 0}

        reason_dist = defaultdict(int)
        for exit_param in recent_exits:
            reason_dist[exit_param.exit_reason] += 1

        # Calculate P&L by exit reason
        reason_pnl = defaultdict(list)
        for exit_param in recent_exits:
            reason_pnl[exit_param.exit_reason].append(exit_param.realized_pnl_pct)

        reason_avg_pnl = {
            reason: round(sum(pnls) / len(pnls), 3)
            for reason, pnls in reason_pnl.items()
        }

        return {
            "status": "OK",
            "total_exits": len(recent_exits),
            "distribution": dict(reason_dist),
            "avg_pnl_by_reason": reason_avg_pnl,
            "most_common_exit": max(reason_dist, key=reason_dist.get) if reason_dist else None,
        }

    def get_entry_reason_distribution(self) -> Dict[str, Any]:
        """Get breakdown of why positions were opened."""
        if not self.entry_reason_stats:
            return {"status": "NO_DATA", "total_entries": 0}

        total = sum(self.entry_reason_stats.values())

        return {
            "status": "OK",
            "total_entries": total,
            "distribution": dict(self.entry_reason_stats),
            "most_common_entry": max(self.entry_reason_stats, key=self.entry_reason_stats.get),
        }

    def get_parameter_summary(self) -> Dict[str, Any]:
        """Get complete parameter monitoring summary."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trend_filter": self.get_trend_filter_stats(minutes=60),
            "signals": self.get_signal_quality(minutes=60),
            "stops": self.get_stop_loss_stats(minutes=120),
            "targets": self.get_profit_target_stats(minutes=120),
            "exit_reasons": self.get_exit_reason_distribution(minutes=120),
            "entry_reasons": self.get_entry_reason_distribution(),
        }


# Global instance
_parameter_monitor = ParameterMonitor()


def get_parameter_monitor() -> ParameterMonitor:
    """Get global parameter monitor instance."""
    return _parameter_monitor
