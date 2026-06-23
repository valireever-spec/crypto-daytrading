"""Integration tests for strategy analytics API endpoints (Phase 1 Week 4)."""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.analytics.strategy_analytics import init_analytics, get_analytics


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_analytics():
    """Initialize analytics for each test."""
    init_analytics(lookback_days=30)
    yield
    # Cleanup
    import backend.analytics.strategy_analytics as analytics_module
    analytics_module._analytics = None


class TestStrategyAnalyticsAPI:
    """Test strategy analytics API endpoints."""

    def test_record_trade_endpoint(self, client):
        """Record a trade via API."""
        response = client.post(
            "/api/strategies/record-trade",
            params={
                "strategy_name": "momentum",
                "pnl": 100.0,
                "quantity": 1.0,
                "entry_price": 45000,
                "exit_price": 45100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "momentum"
        assert data["total_trades"] == 1
        assert data["winning_trades"] == 1
        assert data["win_rate_pct"] == 100.0

    def test_get_strategy_stats_endpoint(self, client):
        """Get stats for a specific strategy."""
        # Record some trades first
        for _ in range(5):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )

        response = client.get("/api/strategies/stats/momentum")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "momentum"
        assert data["total_trades"] == 5
        assert data["winning_trades"] == 5
        assert data["win_rate_pct"] == 100.0

    def test_get_strategy_stats_not_found(self, client):
        """Get stats for non-existent strategy returns 404."""
        response = client.get("/api/strategies/stats/nonexistent")
        assert response.status_code == 404

    def test_get_all_stats_endpoint(self, client):
        """Get stats for all strategies."""
        # Record trades for multiple strategies
        for i in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )

        for i in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": 50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45050,
                },
            )

        response = client.get("/api/strategies/all-stats")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert "momentum" in data["strategies"]
        assert "reversion" in data["strategies"]

    def test_get_best_strategy_endpoint(self, client):
        """Get best-performing strategy."""
        # Record trades: momentum with 60% WR, reversion with 40% WR
        for _ in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )
        for _ in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": -50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 44950,
                },
            )

        for _ in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )
        for _ in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": -50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 44950,
                },
            )

        response = client.get("/api/strategies/best")

        assert response.status_code == 200
        data = response.json()
        assert data["best_strategy"] == "momentum"
        assert data["win_rate_pct"] == 60.0

    def test_get_allocation_endpoint(self, client):
        """Get optimal capital allocation."""
        # Record trades for momentum (60% WR) and reversion (40% WR)
        for _ in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )
        for _ in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": -50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 44950,
                },
            )

        for _ in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )
        for _ in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": -50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 44950,
                },
            )

        response = client.get("/api/strategies/allocation")

        assert response.status_code == 200
        data = response.json()
        assert data["total_pct"] == 100.0
        assert "allocation" in data
        # Momentum should get more allocation
        assert data["allocation"]["momentum"] > data["allocation"]["reversion"]

    def test_get_recent_stats_endpoint(self, client):
        """Get recent statistics for a strategy."""
        # Record some trades
        for _ in range(5):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )

        response = client.get("/api/strategies/recent-stats/momentum?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "momentum"
        assert data["period_days"] == 7
        assert data["total_trades"] == 5

    def test_reset_strategy_endpoint(self, client):
        """Reset a specific strategy."""
        # Record trades
        for _ in range(5):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )

        # Reset
        response = client.post("/api/strategies/reset/momentum")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reset"
        assert data["strategy"] == "momentum"

        # Verify reset
        stats_response = client.get("/api/strategies/stats/momentum")
        stats = stats_response.json()
        assert stats["total_trades"] == 0

    def test_reset_all_strategies_endpoint(self, client):
        """Reset all strategies."""
        # Record trades for multiple strategies
        for _ in range(3):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "momentum",
                    "pnl": 100.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45100,
                },
            )

        for _ in range(2):
            client.post(
                "/api/strategies/record-trade",
                params={
                    "strategy_name": "reversion",
                    "pnl": 50.0,
                    "quantity": 1.0,
                    "entry_price": 45000,
                    "exit_price": 45050,
                },
            )

        # Reset all
        response = client.post("/api/strategies/reset-all")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reset_all"
        assert data["strategies_reset"] == 2

        # Verify all reset
        all_stats = client.get("/api/strategies/all-stats")
        stats = all_stats.json()
        for strategy in stats["strategies"].values():
            assert strategy["total_trades"] == 0


class TestStrategyAnalyticsIntegration:
    """Integration tests with paper trading."""

    def test_trade_records_to_strategy_analytics(self, client):
        """Verify that strategy trades get recorded to analytics."""
        # This test would require mocking the paper trading engine
        # For now, we just test the direct API
        response = client.post(
            "/api/strategies/record-trade",
            params={
                "strategy_name": "momentum",
                "pnl": 250.0,
                "quantity": 1.0,
                "entry_price": 45000,
                "exit_price": 45250,
            },
        )

        assert response.status_code == 200

        # Verify via get_stats
        stats_response = client.get("/api/strategies/stats/momentum")
        data = stats_response.json()

        assert data["total_pnl"] == 250.0
        assert data["largest_win"] == 250.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
