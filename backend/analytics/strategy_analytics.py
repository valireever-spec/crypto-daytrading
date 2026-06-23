"""Per-strategy performance analytics and dynamic allocation (Phase 1 Week 4)."""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class StrategyStats:
    """Performance statistics for a single strategy."""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    last_trade_time: Optional[datetime] = None
    trades: List[Dict] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100.0

    @property
    def expectancy(self) -> float:
        """Calculate expected value per trade."""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        gross_profit = self.avg_win * self.winning_trades
        gross_loss = abs(self.avg_loss) * self.losing_trades

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        return gross_profit / gross_loss


class StrategyAnalytics:
    """Track and analyze performance by strategy."""

    def __init__(self, lookback_days: int = 30):
        """Initialize strategy analytics.

        Args:
            lookback_days: Days to track for recent performance (default 30)
        """
        self.lookback_days = lookback_days
        self.strategies: Dict[str, StrategyStats] = {}

    def register_strategy(self, strategy_name: str) -> None:
        """Register a new strategy for tracking.

        Args:
            strategy_name: Name of the strategy (e.g., "momentum", "reversion")
        """
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = StrategyStats(strategy_name=strategy_name)
            logger.info(f"Registered strategy: {strategy_name}")

    def record_trade(
        self,
        strategy_name: str,
        pnl: float,
        quantity: float,
        entry_price: float,
        exit_price: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a trade for a strategy.

        Args:
            strategy_name: Name of the strategy
            pnl: Profit/loss amount
            quantity: Trade quantity
            entry_price: Entry price
            exit_price: Exit price
            timestamp: Trade timestamp (default now)
        """
        if strategy_name not in self.strategies:
            self.register_strategy(strategy_name)

        stats = self.strategies[strategy_name]
        timestamp = timestamp or datetime.utcnow()

        # Update trade counts
        stats.total_trades += 1
        if pnl > 0:
            stats.winning_trades += 1
            stats.avg_win = (
                (stats.avg_win * (stats.winning_trades - 1) + pnl) / stats.winning_trades
            )
            stats.largest_win = max(stats.largest_win, pnl)
        else:
            stats.losing_trades += 1
            stats.avg_loss = (
                (stats.avg_loss * (stats.losing_trades - 1) + pnl) / stats.losing_trades
            )
            stats.largest_loss = min(stats.largest_loss, pnl)

        # Update consecutive wins/losses
        if pnl > 0:
            stats.consecutive_wins += 1
            stats.consecutive_losses = 0
        else:
            stats.consecutive_losses += 1
            stats.consecutive_wins = 0

        # Update totals
        stats.total_pnl += pnl
        stats.last_trade_time = timestamp

        # Record trade
        stats.trades.append({
            "pnl": pnl,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "timestamp": timestamp.isoformat() if timestamp else None,
        })

        logger.info(
            f"Recorded trade for {strategy_name}: "
            f"PNL=${pnl:.2f}, WR={stats.win_rate:.1f}%"
        )

    def get_strategy_stats(self, strategy_name: str) -> Optional[StrategyStats]:
        """Get statistics for a specific strategy.

        Args:
            strategy_name: Name of the strategy

        Returns:
            StrategyStats or None if not found
        """
        return self.strategies.get(strategy_name)

    def get_all_stats(self) -> Dict[str, StrategyStats]:
        """Get statistics for all strategies.

        Returns:
            Dict mapping strategy name to stats
        """
        return self.strategies.copy()

    def get_best_strategy(self) -> Optional[str]:
        """Find the best-performing strategy by win rate.

        Returns:
            Strategy name or None if no trades
        """
        if not self.strategies:
            return None

        # Filter strategies with at least 5 trades (statistical minimum)
        qualified = {
            name: stats
            for name, stats in self.strategies.items()
            if stats.total_trades >= 5
        }

        if not qualified:
            return None

        best = max(qualified.items(), key=lambda x: (x[1].win_rate, x[1].expectancy))
        return best[0]

    def get_recent_stats(self, strategy_name: str, days: int = 7) -> StrategyStats:
        """Get statistics for recent period only.

        Args:
            strategy_name: Name of the strategy
            days: Number of days to include

        Returns:
            StrategyStats for recent period
        """
        if strategy_name not in self.strategies:
            return StrategyStats(strategy_name=strategy_name)

        stats = self.strategies[strategy_name]
        cutoff = datetime.utcnow() - timedelta(days=days)

        recent_trades = [t for t in stats.trades if datetime.fromisoformat(t["timestamp"]) > cutoff]

        # Rebuild stats from recent trades
        recent_stats = StrategyStats(strategy_name=strategy_name, trades=recent_trades)
        for trade in recent_trades:
            pnl = trade["pnl"]
            recent_stats.total_trades += 1
            if pnl > 0:
                recent_stats.winning_trades += 1
                recent_stats.avg_win = (
                    (recent_stats.avg_win * (recent_stats.winning_trades - 1) + pnl)
                    / recent_stats.winning_trades
                )
            else:
                recent_stats.losing_trades += 1
                recent_stats.avg_loss = (
                    (recent_stats.avg_loss * (recent_stats.losing_trades - 1) + pnl)
                    / recent_stats.losing_trades
                )
            recent_stats.total_pnl += pnl

        return recent_stats

    def calculate_allocation(self) -> Dict[str, float]:
        """Calculate optimal capital allocation across strategies.

        Uses win rate and expectancy to weight allocation.
        Strategies with <5 trades get minimum allocation (1%).

        Returns:
            Dict mapping strategy name to allocation % (sums to 100)
        """
        if not self.strategies:
            return {}

        allocations = {}
        min_allocation = 0.01  # 1%

        # Calculate scores
        for name, stats in self.strategies.items():
            if stats.total_trades < 5:
                allocations[name] = min_allocation
            else:
                # Score = win_rate% * expectancy per trade
                # Normalize to 0-1 range
                score = (stats.win_rate / 100.0) * max(0, stats.expectancy)
                allocations[name] = score

        # Normalize to sum to 100%
        total_score = sum(allocations.values())
        if total_score == 0:
            # Equal allocation if no positive scores
            equal = 1.0 / len(allocations) if allocations else 0
            return {name: equal for name in allocations}

        normalized = {name: (score / total_score) for name, score in allocations.items()}
        return normalized

    def reset_strategy(self, strategy_name: str) -> None:
        """Reset statistics for a strategy.

        Args:
            strategy_name: Name of the strategy
        """
        if strategy_name in self.strategies:
            self.strategies[strategy_name] = StrategyStats(strategy_name=strategy_name)
            logger.info(f"Reset strategy: {strategy_name}")

    def reset_all(self) -> None:
        """Reset all statistics."""
        for name in self.strategies:
            self.strategies[name] = StrategyStats(strategy_name=name)
        logger.info("Reset all strategy statistics")


# Global analytics instance
_analytics: Optional[StrategyAnalytics] = None


def init_analytics(lookback_days: int = 30) -> StrategyAnalytics:
    """Initialize global analytics."""
    global _analytics
    _analytics = StrategyAnalytics(lookback_days=lookback_days)
    return _analytics


def get_analytics() -> Optional[StrategyAnalytics]:
    """Get global analytics."""
    return _analytics
