"""Tests for per-strategy analytics (Phase 1 Week 4)."""

import pytest
from datetime import datetime, timedelta
from backend.analytics.strategy_analytics import (
    StrategyStats,
    StrategyAnalytics,
    init_analytics,
    get_analytics,
)


@pytest.fixture
def analytics():
    """Create analytics instance for tests."""
    return StrategyAnalytics(lookback_days=30)


@pytest.fixture(autouse=True)
def cleanup_analytics():
    """Clean up global analytics between tests."""
    import backend.analytics.strategy_analytics as analytics_module

    analytics_module._analytics = None
    yield
    analytics_module._analytics = None


class TestStrategyStats:
    """Test StrategyStats dataclass."""

    def test_init(self):
        """Should initialize with default values."""
        stats = StrategyStats(strategy_name="momentum")
        assert stats.strategy_name == "momentum"
        assert stats.total_trades == 0
        assert stats.winning_trades == 0
        assert stats.losing_trades == 0

    def test_win_rate_zero_trades(self):
        """Win rate should be 0% with no trades."""
        stats = StrategyStats(strategy_name="momentum")
        assert stats.win_rate == 0.0

    def test_win_rate_50_percent(self):
        """Win rate should calculate correctly."""
        stats = StrategyStats(
            strategy_name="momentum",
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
        )
        assert stats.win_rate == pytest.approx(55.0)

    def test_expectancy_calculation(self):
        """Expectancy should be total_pnl / total_trades."""
        stats = StrategyStats(
            strategy_name="momentum",
            total_trades=10,
            total_pnl=500.0,
        )
        assert stats.expectancy == 50.0

    def test_profit_factor(self):
        """Profit factor should be gross_profit / gross_loss."""
        stats = StrategyStats(
            strategy_name="momentum",
            winning_trades=10,
            avg_win=100.0,
            losing_trades=5,
            avg_loss=50.0,
        )
        gross_profit = 10 * 100  # 1000
        gross_loss = 5 * 50      # 250
        assert stats.profit_factor == pytest.approx(gross_profit / gross_loss)


class TestStrategyAnalytics:
    """Test StrategyAnalytics class."""

    def test_register_strategy(self, analytics):
        """Should register a new strategy."""
        analytics.register_strategy("momentum")
        assert "momentum" in analytics.strategies

    def test_register_multiple_strategies(self, analytics):
        """Should register multiple strategies."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")
        analytics.register_strategy("grid")

        assert len(analytics.strategies) == 3

    def test_record_trade_winning(self, analytics):
        """Should record a winning trade."""
        analytics.register_strategy("momentum")
        analytics.record_trade(
            strategy_name="momentum",
            pnl=100.0,
            quantity=1.0,
            entry_price=45000,
            exit_price=45100,
        )

        stats = analytics.get_strategy_stats("momentum")
        assert stats.total_trades == 1
        assert stats.winning_trades == 1
        assert stats.losing_trades == 0
        assert stats.total_pnl == 100.0
        assert stats.win_rate == 100.0

    def test_record_trade_losing(self, analytics):
        """Should record a losing trade."""
        analytics.register_strategy("momentum")
        analytics.record_trade(
            strategy_name="momentum",
            pnl=-50.0,
            quantity=1.0,
            entry_price=45000,
            exit_price=44950,
        )

        stats = analytics.get_strategy_stats("momentum")
        assert stats.total_trades == 1
        assert stats.winning_trades == 0
        assert stats.losing_trades == 1
        assert stats.total_pnl == -50.0
        assert stats.win_rate == 0.0

    def test_consecutive_wins(self, analytics):
        """Should track consecutive winning trades."""
        analytics.register_strategy("momentum")

        # 3 consecutive wins
        for i in range(3):
            analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.consecutive_wins == 3
        assert stats.consecutive_losses == 0

    def test_consecutive_losses(self, analytics):
        """Should track consecutive losing trades."""
        analytics.register_strategy("momentum")

        # Win then 2 losses
        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        analytics.record_trade("momentum", -50.0, 1.0, 45000, 44950)
        analytics.record_trade("momentum", -30.0, 1.0, 44950, 44920)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.consecutive_wins == 0
        assert stats.consecutive_losses == 2

    def test_average_win_tracking(self, analytics):
        """Should track average win amount."""
        analytics.register_strategy("momentum")

        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        analytics.record_trade("momentum", 150.0, 1.0, 45100, 45250)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.avg_win == pytest.approx(125.0)

    def test_average_loss_tracking(self, analytics):
        """Should track average loss amount."""
        analytics.register_strategy("momentum")

        analytics.record_trade("momentum", -50.0, 1.0, 45000, 44950)
        analytics.record_trade("momentum", -100.0, 1.0, 45000, 44900)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.avg_loss == pytest.approx(-75.0)

    def test_largest_win(self, analytics):
        """Should track largest winning trade."""
        analytics.register_strategy("momentum")

        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        analytics.record_trade("momentum", 500.0, 1.0, 45100, 45600)
        analytics.record_trade("momentum", 200.0, 1.0, 45600, 45800)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.largest_win == 500.0

    def test_largest_loss(self, analytics):
        """Should track largest losing trade."""
        analytics.register_strategy("momentum")

        analytics.record_trade("momentum", -50.0, 1.0, 45000, 44950)
        analytics.record_trade("momentum", -500.0, 1.0, 45000, 44500)
        analytics.record_trade("momentum", -200.0, 1.0, 45000, 44800)

        stats = analytics.get_strategy_stats("momentum")
        assert stats.largest_loss == -500.0

    def test_get_all_stats(self, analytics):
        """Should return all strategy statistics."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")
        analytics.register_strategy("grid")

        all_stats = analytics.get_all_stats()
        assert len(all_stats) == 3

    def test_get_best_strategy_empty(self, analytics):
        """Should return None for empty analytics."""
        best = analytics.get_best_strategy()
        assert best is None

    def test_get_best_strategy_minimum_trades(self, analytics):
        """Should ignore strategies with <5 trades."""
        analytics.register_strategy("momentum")
        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)

        best = analytics.get_best_strategy()
        assert best is None  # Only 1 trade, need minimum 5

    def test_get_best_strategy_qualified(self, analytics):
        """Should return best-performing strategy."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")

        # Momentum: 60% win rate (3 wins of 100 + 2 losses of 50)
        for _ in range(3):
            analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        for _ in range(2):
            analytics.record_trade("momentum", -50.0, 1.0, 45000, 44950)

        # Reversion: 40% win rate (2 wins of 100 + 3 losses of 50)
        for _ in range(2):
            analytics.record_trade("reversion", 100.0, 1.0, 45000, 45100)
        for _ in range(3):
            analytics.record_trade("reversion", -50.0, 1.0, 45000, 44950)

        best = analytics.get_best_strategy()
        assert best == "momentum"

    def test_calculate_allocation_equal(self, analytics):
        """Should allocate equally if no trades."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")

        allocation = analytics.calculate_allocation()
        assert allocation["momentum"] == pytest.approx(0.5)
        assert allocation["reversion"] == pytest.approx(0.5)

    def test_calculate_allocation_weighted(self, analytics):
        """Should weight allocation by performance."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")

        # Momentum: 60% WR, $300 total PNL
        for _ in range(3):
            analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        for _ in range(2):
            analytics.record_trade("momentum", -50.0, 1.0, 45000, 44950)

        # Reversion: 40% WR, -$50 total PNL
        for _ in range(2):
            analytics.record_trade("reversion", 100.0, 1.0, 45000, 45100)
        for _ in range(3):
            analytics.record_trade("reversion", -50.0, 1.0, 45000, 44950)

        allocation = analytics.calculate_allocation()

        # Momentum should get more allocation
        assert allocation["momentum"] > allocation["reversion"]
        assert sum(allocation.values()) == pytest.approx(1.0)

    def test_reset_strategy(self, analytics):
        """Should reset single strategy statistics."""
        analytics.register_strategy("momentum")
        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)

        stats_before = analytics.get_strategy_stats("momentum")
        assert stats_before.total_trades == 1

        analytics.reset_strategy("momentum")

        stats_after = analytics.get_strategy_stats("momentum")
        assert stats_after.total_trades == 0
        assert stats_after.total_pnl == 0.0

    def test_reset_all(self, analytics):
        """Should reset all strategy statistics."""
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")

        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        analytics.record_trade("reversion", 200.0, 1.0, 45000, 45200)

        analytics.reset_all()

        for stats in analytics.strategies.values():
            assert stats.total_trades == 0
            assert stats.total_pnl == 0.0

    def test_trade_history_stored(self, analytics):
        """Should store full trade history."""
        analytics.register_strategy("momentum")

        analytics.record_trade("momentum", 100.0, 1.0, 45000, 45100)
        analytics.record_trade("momentum", -50.0, 1.0, 45100, 45050)

        stats = analytics.get_strategy_stats("momentum")
        assert len(stats.trades) == 2
        assert stats.trades[0]["pnl"] == 100.0
        assert stats.trades[1]["pnl"] == -50.0

    def test_get_recent_stats_all_recent(self, analytics):
        """Should get stats for recent trades only."""
        analytics.register_strategy("momentum")

        now = datetime.utcnow()
        recent_time = now - timedelta(hours=1)

        # Recent trade
        analytics.record_trade(
            "momentum",
            100.0,
            1.0,
            45000,
            45100,
            timestamp=recent_time
        )

        recent_stats = analytics.get_recent_stats("momentum", days=7)
        assert recent_stats.total_trades == 1
        assert recent_stats.winning_trades == 1

    def test_get_recent_stats_excluding_old(self, analytics):
        """Should exclude old trades from recent stats."""
        analytics.register_strategy("momentum")

        # Old trade (30 days ago)
        old_time = datetime.utcnow() - timedelta(days=30)
        analytics.record_trade(
            "momentum",
            100.0,
            1.0,
            45000,
            45100,
            timestamp=old_time
        )

        # Recent trade (1 hour ago)
        recent_time = datetime.utcnow() - timedelta(hours=1)
        analytics.record_trade(
            "momentum",
            50.0,
            1.0,
            45000,
            45050,
            timestamp=recent_time
        )

        recent_stats = analytics.get_recent_stats("momentum", days=7)
        assert recent_stats.total_trades == 1  # Only recent trade
        assert recent_stats.winning_trades == 1


class TestStrategyAnalyticsGlobal:
    """Test global analytics instance."""

    def test_init_analytics(self):
        """Should initialize global analytics."""
        analytics = init_analytics(lookback_days=14)
        assert analytics is not None
        assert analytics.lookback_days == 14

    def test_get_analytics(self):
        """Should return global analytics instance."""
        init_analytics()
        analytics = get_analytics()
        assert analytics is not None

    def test_get_analytics_uninitialized(self):
        """Should return None if not initialized."""
        import backend.analytics.strategy_analytics as analytics_module

        analytics_module._analytics = None
        assert get_analytics() is None


class TestRealWorldScenarios:
    """Test real-world trading scenarios."""

    def test_momentum_vs_reversion_comparison(self):
        """Track performance of momentum vs reversion strategies."""
        analytics = StrategyAnalytics()

        # Momentum strategy: 55% win rate on 20 trades
        analytics.register_strategy("momentum")
        for i in range(11):  # 11 wins
            analytics.record_trade("momentum", 100.0, 1.0, 45000 + i*10, 45100 + i*10)
        for i in range(9):   # 9 losses
            analytics.record_trade("momentum", -80.0, 1.0, 45000 + i*10, 44920 + i*10)

        # Reversion strategy: 50% win rate on 20 trades
        analytics.register_strategy("reversion")
        for i in range(10):  # 10 wins
            analytics.record_trade("reversion", 120.0, 1.0, 45000 + i*10, 45120 + i*10)
        for i in range(10):  # 10 losses
            analytics.record_trade("reversion", -120.0, 1.0, 45000 + i*10, 44880 + i*10)

        momentum_stats = analytics.get_strategy_stats("momentum")
        reversion_stats = analytics.get_strategy_stats("reversion")

        assert momentum_stats.total_trades == 20
        assert momentum_stats.win_rate == pytest.approx(55.0)
        assert reversion_stats.total_trades == 20
        assert reversion_stats.win_rate == 50.0

        # Momentum should be best
        best = analytics.get_best_strategy()
        assert best == "momentum"

    def test_dynamic_allocation_after_performance(self):
        """Allocation should shift toward better-performing strategies."""
        analytics = StrategyAnalytics()

        # Day 1: Equal allocation
        analytics.register_strategy("momentum")
        analytics.register_strategy("reversion")
        analytics.register_strategy("grid")

        allocation_day1 = analytics.calculate_allocation()
        assert allocation_day1["momentum"] == pytest.approx(1/3, rel=0.1)

        # Add trades: momentum performs well
        for _ in range(10):
            analytics.record_trade("momentum", 150.0, 1.0, 45000, 45150)
        for _ in range(10):
            analytics.record_trade("momentum", -30.0, 1.0, 45000, 44970)

        # Reversion performs poorly
        for _ in range(10):
            analytics.record_trade("reversion", 50.0, 1.0, 45000, 45050)
        for _ in range(10):
            analytics.record_trade("reversion", -100.0, 1.0, 45000, 44900)

        allocation_day2 = analytics.calculate_allocation()

        # Momentum should get more capital
        assert allocation_day2["momentum"] > allocation_day1["momentum"]
        assert allocation_day2["reversion"] < allocation_day1["reversion"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
