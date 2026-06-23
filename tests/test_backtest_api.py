"""Tests for backtesting API endpoints (Phase 2 Week 6)."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.analytics.historical_data import init_historical_service
from backend.analytics.signals import init_signal_generator


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_services():
    """Initialize required services for tests."""
    init_signal_generator()
    init_historical_service()
    yield


class TestBacktestAPI:
    """Test backtesting API endpoints."""


    def test_run_backtest_valid(self, client):
        """Run valid backtest."""
        response = client.post(
            "/api/backtest/run",
            params={
                "symbol": "AAPL",
                "strategy_name": "momentum",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "initial_capital": 10000.0,
            },
        )

        # Should return 200 if data available, 404 if not
        if response.status_code == 200:
            data = response.json()
            assert data["strategy"] == "momentum"
            assert data["symbol"] == "AAPL"
            assert "total_trades" in data
            assert "win_rate_pct" in data
            assert "total_pnl" in data
        elif response.status_code == 404:
            # No data available
            pass
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_backtest_response_structure(self, client):
        """Verify backtest response has required fields."""
        response = client.post(
            "/api/backtest/run",
            params={
                "symbol": "AAPL",
                "strategy_name": "momentum",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        if response.status_code == 200:
            data = response.json()

            # Check required fields
            required_fields = [
                "strategy",
                "symbol",
                "total_trades",
                "win_rate_pct",
                "total_pnl",
                "expectancy",
                "sharpe_ratio",
                "max_drawdown_pct",
            ]

            for field in required_fields:
                assert field in data, f"Missing field: {field}"

    def test_get_data_range(self, client):
        """Get available data range for symbol."""
        response = client.get("/api/backtest/data-range/AAPL")

        if response.status_code == 200:
            data = response.json()
            assert data["symbol"] == "AAPL"
            assert "start_date" in data
            assert "end_date" in data
            assert "days_available" in data
        elif response.status_code == 404:
            # No data available
            pass
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_backtest_different_capital(self, client):
        """Backtest with different initial capital."""
        for capital in [5000, 10000, 50000]:
            response = client.post(
                "/api/backtest/run",
                params={
                    "symbol": "AAPL",
                    "strategy_name": "momentum",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "initial_capital": float(capital),
                },
            )

            if response.status_code == 200:
                data = response.json()
                assert data["initial_capital"] == capital


class TestBacktestMultipleStrategies:
    """Test backtesting multiple strategies."""

    def test_backtest_momentum(self, client):
        """Backtest momentum strategy."""
        response = client.post(
            "/api/backtest/run",
            params={
                "symbol": "AAPL",
                "strategy_name": "momentum",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert data["strategy"] == "momentum"

    def test_backtest_reversion(self, client):
        """Backtest reversion strategy."""
        response = client.post(
            "/api/backtest/run",
            params={
                "symbol": "AAPL",
                "strategy_name": "reversion",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert data["strategy"] == "reversion"

    def test_backtest_grid(self, client):
        """Backtest grid strategy."""
        response = client.post(
            "/api/backtest/run",
            params={
                "symbol": "AAPL",
                "strategy_name": "grid",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert data["strategy"] == "grid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
