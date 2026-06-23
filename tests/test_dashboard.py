"""Integration tests for dashboard and UI endpoints (FR-008)."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app, reset_trading_paused
from backend.exchange.paper_trading import init_paper_trading, get_paper_trading


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_engine():
    """Initialize paper trading engine for tests."""
    init_paper_trading(starting_capital=10000.0)
    reset_trading_paused()
    yield
    engine = get_paper_trading()
    if engine:
        engine.reset()
    reset_trading_paused()


class TestDashboardEndpoint:
    """Test dashboard data endpoint."""

    def test_dashboard_returns_200(self, client):
        """Dashboard should return 200."""
        response = client.get("/api/dashboard")
        assert response.status_code == 200

    def test_dashboard_has_required_fields(self, client):
        """Dashboard should include all required fields."""
        response = client.get("/api/dashboard")
        data = response.json()

        assert "account" in data
        assert "positions" in data
        assert "recent_trades" in data
        assert "metrics" in data
        assert "trading_paused" in data
        assert "timestamp" in data

    def test_dashboard_account_structure(self, client):
        """Dashboard account should have correct structure."""
        response = client.get("/api/dashboard")
        account = response.json()["account"]

        assert account["mode"] == "PAPER"
        assert account["cash"] == 10000.0
        assert account["total_equity"] == 10000.0
        assert account["active_positions"] == 0
        assert account["total_pnl"] == 0.0

    def test_dashboard_metrics_structure(self, client):
        """Dashboard metrics should have correct structure."""
        response = client.get("/api/dashboard")
        metrics = response.json()["metrics"]

        assert "total_trades" in metrics
        assert "winning_trades" in metrics
        assert "win_rate_pct" in metrics
        assert "avg_win" in metrics

        assert metrics["total_trades"] == 0
        assert metrics["winning_trades"] == 0
        assert metrics["win_rate_pct"] == 0
        assert metrics["avg_win"] == 0

    def test_dashboard_after_trade(self, client):
        """Dashboard should update after trades."""
        # Place a buy order
        client.post(
            "/api/paper/order",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 45000.0,
            },
        )

        # Check dashboard
        response = client.get("/api/dashboard")
        data = response.json()

        assert len(data["positions"]) == 1
        assert len(data["recent_trades"]) == 1
        assert data["metrics"]["total_trades"] == 1
        assert data["account"]["active_positions"] == 1

    def test_dashboard_positions_updated(self, client):
        """Dashboard positions should reflect open positions."""
        # Buy BTC
        client.post(
            "/api/paper/order",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 45000.0,
            },
        )

        # Buy ETH
        client.post(
            "/api/paper/order",
            params={
                "symbol": "ETHUSDT",
                "side": "BUY",
                "quantity": 1.0,
                "current_price": 2500.0,
            },
        )

        response = client.get("/api/dashboard")
        positions = response.json()["positions"]

        assert len(positions) == 2
        symbols = [p["symbol"] for p in positions]
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_dashboard_win_rate_calculation(self, client):
        """Dashboard should calculate win rate correctly."""
        engine = get_paper_trading()

        # Buy at 45000, sell at 46000 (profit)
        client.post(
            "/api/paper/order",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 45000.0,
            },
        )

        client.post(
            "/api/paper/order",
            params={
                "symbol": "BTCUSDT",
                "side": "SELL",
                "quantity": 0.1,
                "current_price": 46000.0,
            },
        )

        response = client.get("/api/dashboard")
        data = response.json()

        assert data["metrics"]["total_trades"] == 2
        assert data["metrics"]["winning_trades"] == 1
        assert data["metrics"]["win_rate_pct"] == 50.0

    def test_dashboard_empty_positions(self, client):
        """Dashboard should show empty positions list initially."""
        response = client.get("/api/dashboard")
        data = response.json()

        assert data["positions"] == []
        assert len(data["recent_trades"]) == 0

    def test_dashboard_trading_paused_flag(self, client):
        """Dashboard should reflect trading paused status."""
        # Initially not paused
        response = client.get("/api/dashboard")
        assert response.json()["trading_paused"] is False

        # Pause trading
        client.post("/api/trading/pause")

        response = client.get("/api/dashboard")
        assert response.json()["trading_paused"] is True

        # Resume
        client.post("/api/trading/resume")

        response = client.get("/api/dashboard")
        assert response.json()["trading_paused"] is False

    def test_dashboard_recent_trades_limit(self, client):
        """Dashboard should limit recent trades to 10."""
        engine = get_paper_trading()

        # Place 15 trades
        for i in range(15):
            client.post(
                "/api/paper/order",
                params={
                    "symbol": f"SYM{i % 5}",
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "quantity": 0.1,
                    "current_price": 1000.0 + i * 10,
                },
            )

        response = client.get("/api/dashboard")
        recent_trades = response.json()["recent_trades"]

        # Should limit to most recent 10
        assert len(recent_trades) <= 10


class TestTradingControlEndpoints:
    """Test trading control endpoints."""

    def test_pause_trading(self, client):
        """Pause endpoint should set trading_paused flag."""
        response = client.post("/api/trading/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_resume_trading(self, client):
        """Resume endpoint should clear trading_paused flag."""
        client.post("/api/trading/pause")
        response = client.post("/api/trading/resume")
        assert response.status_code == 200
        assert response.json()["status"] == "trading"

    def test_order_rejected_when_paused(self, client):
        """Orders should be rejected when trading is paused."""
        # Pause trading
        client.post("/api/trading/pause")

        # Try to place order
        response = client.post(
            "/api/order/manual",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 45000.0,
            },
        )

        assert response.status_code == 400
        assert "paused" in response.json()["reason"].lower()

    def test_order_accepted_when_trading(self, client):
        """Orders should be accepted when trading is active."""
        response = client.post(
            "/api/order/manual",
            params={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.1,
                "current_price": 45000.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "FILLED"

    def test_get_trading_status(self, client):
        """Should return current trading status."""
        response = client.get("/api/trading/status")
        data = response.json()

        assert "trading_paused" in data
        assert "mode" in data
        assert "account" in data
        assert data["trading_paused"] is False


class TestFrontendServing:
    """Test frontend HTML serving."""

    def test_root_serves_html(self, client):
        """Root endpoint should serve HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Crypto Daytrading" in response.text

    def test_html_contains_dashboard_sections(self, client):
        """HTML should contain all dashboard sections."""
        response = client.get("/")
        html = response.text

        # Check for key sections (unified dashboard)
        assert "Account Summary" in html
        assert "Open Positions" in html
        assert "Recent Trades" in html
        assert "Market Status" in html
        assert "Strategies" in html
        assert "Dashboard" in html

    def test_html_contains_api_calls(self, client):
        """HTML should have JavaScript for API calls."""
        response = client.get("/")
        html = response.text

        # Check for API endpoint references (unified dashboard uses const API)
        assert "const API" in html or "API_BASE" in html
        assert "/api/" in html
        assert "dashboard" in html.lower()
        assert "trading" in html.lower()
        assert "pause" in html.lower()
        assert "resume" in html.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
