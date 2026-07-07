"""Trading metrics collection for real-time monitoring.

Tracks:
- Signal generation (regime, entry reason, filters)
- Trade execution (entry, exit, P&L)
- System health (CB state, WebSocket, sync)
- Performance (win rate, hold time, slippage)
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

@dataclass
class SignalMetric:
    """Signal generation metric."""
    timestamp: str
    symbol: str
    regime: str  # uptrend, downtrend, ranging
    entry_reason: str  # full entry description
    filters_passed: Dict[str, bool]  # {filter_name: passed}
    rsi_5m: float
    rsi_1h: float
    bb_width_pct: float
    macd_histogram: float
    volume_ratio: float
    signal_strength: int  # 0-100
    decision: str  # "ENTER" or rejection reason

@dataclass
class TradeMetric:
    """Trade execution metric."""
    timestamp: str
    symbol: str
    side: str  # BUY or SELL
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    hold_seconds: Optional[int] = None
    exit_reason: Optional[str] = None  # profit_target, stop_loss, timeout
    slippage_pct: Optional[float] = None

@dataclass
class SystemMetric:
    """System health metric."""
    timestamp: str
    cb_state: str  # OPEN, CLOSED
    cb_halted: bool
    websocket_healthy: bool
    websocket_stale_seconds: int
    sync_lag_seconds: int
    memory_percent: float
    trades_today: int
    open_positions: int
    daily_pnl: float
    cash: float

class MetricsCollector:
    """Collects trading metrics for monitoring."""

    def __init__(self):
        self.signals: List[SignalMetric] = []
        self.trades: List[TradeMetric] = []
        self.system: List[SystemMetric] = []
        self.start_time = datetime.now(timezone.utc)

    def record_signal(self, **kwargs) -> None:
        """Record signal generation."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        self.signals.append(SignalMetric(**kwargs))
        # Keep only last 1000 signals (rolling window)
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:]

    def record_trade(self, **kwargs) -> None:
        """Record trade execution."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        self.trades.append(TradeMetric(**kwargs))
        # Keep only last 500 trades
        if len(self.trades) > 500:
            self.trades = self.trades[-500:]

    def record_system(self, **kwargs) -> None:
        """Record system health."""
        kwargs['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        self.system.append(SystemMetric(**kwargs))
        # Keep only last 1440 (24 hours of minute-by-minute samples)
        if len(self.system) > 1440:
            self.system = self.system[-1440:]

    def get_signals_since(self, minutes: int = 60) -> List[Dict]:
        """Get signals from last N minutes."""
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = []
        for sig in self.signals:
            sig_time = datetime.fromisoformat(sig.timestamp.replace('Z', '+00:00'))
            if sig_time > cutoff:
                result.append(asdict(sig))
        return result

    def get_trades_since(self, minutes: int = 60) -> List[Dict]:
        """Get trades from last N minutes."""
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = []
        for trade in self.trades:
            trade_time = datetime.fromisoformat(trade.timestamp.replace('Z', '+00:00'))
            if trade_time > cutoff:
                result.append(asdict(trade))
        return result

    def get_win_rate(self, trades: Optional[List[TradeMetric]] = None) -> float:
        """Calculate win rate from SELL exits only."""
        if trades is None:
            trades = self.trades
        
        exits = [t for t in trades if t.side == 'SELL' and t.realized_pnl is not None]
        if not exits:
            return 0.0
        
        winners = sum(1 for t in exits if t.realized_pnl > 0)
        return (winners / len(exits) * 100) if exits else 0.0

    def get_statistics(self) -> Dict:
        """Get current statistics."""
        from datetime import timezone
        recent_trades = self.get_trades_since(minutes=120)
        all_trades = [t for t in recent_trades if t.side == 'SELL']

        return {
            'total_signals': len(self.signals),
            'total_trades': len(self.trades),
            'recent_trades_2h': len(recent_trades),
            'recent_exits_2h': len(all_trades),
            'win_rate_2h': self.get_win_rate([TradeMetric(**t) for t in all_trades]) if all_trades else 0,
            'recent_signals_2h': len(self.get_signals_since(minutes=120)),
            'uptime_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds(),
        }

    def get_dashboard_metrics(self) -> Dict:
        """Get comprehensive metrics for dashboard display."""
        from datetime import timezone

        # Get today's trades (all trades in last 24 hours)
        trades_24h = self.get_trades_since(minutes=1440)
        exits_24h = [TradeMetric(**t) for t in trades_24h if t['side'] == 'SELL']
        entries_24h = [TradeMetric(**t) for t in trades_24h if t['side'] == 'BUY']

        # Calculate P&L metrics
        total_pnl = sum(t.realized_pnl or 0 for t in exits_24h)
        winners = [t for t in exits_24h if (t.realized_pnl or 0) > 0]
        losers = [t for t in exits_24h if (t.realized_pnl or 0) <= 0]

        avg_win = sum(t.realized_pnl or 0 for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t.realized_pnl or 0 for t in losers) / len(losers) if losers else 0

        win_rate = (len(winners) / len(exits_24h) * 100) if exits_24h else 0

        # Risk/reward ratio
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        # Consecutive losses
        consecutive_losses = 0
        for trade in reversed(exits_24h):
            if (trade.realized_pnl or 0) <= 0:
                consecutive_losses += 1
            else:
                break

        # Get last 5 trades
        last_5 = exits_24h[-5:] if exits_24h else []
        last_5_display = []
        for trade in reversed(last_5):
            pnl = trade.realized_pnl or 0
            pnl_pct = trade.realized_pnl_pct or 0
            status = "✅" if pnl > 0 else "❌"
            last_5_display.append({
                'status': status,
                'symbol': trade.symbol,
                'pnl': round(pnl, 4),
                'pnl_pct': round(pnl_pct, 2),
                'hold_seconds': trade.hold_seconds or 0,
                'exit_reason': trade.exit_reason or 'unknown'
            })

        return {
            'summary': {
                'trades_today': len(entries_24h),
                'exits_today': len(exits_24h),
                'total_pnl': round(total_pnl, 2),
                'win_rate_pct': round(win_rate, 1),
                'wins': len(winners),
                'losses': len(losers),
            },
            'performance': {
                'avg_win': round(avg_win, 4),
                'avg_loss': round(avg_loss, 4),
                'risk_reward_ratio': round(risk_reward, 2),
                'consecutive_losses': consecutive_losses,
            },
            'recent_trades': last_5_display,
        }

# Global instance
_metrics = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics
