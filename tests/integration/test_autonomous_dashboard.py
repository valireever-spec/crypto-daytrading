"""Integration tests for Phase 333: Autonomous Trading Dashboard."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.api.main import app
from backend.trading.autonomous_trader import init_autonomous_trader, TradingConfig
from backend.exchange.paper_trading import init_paper_trading
from backend.analytics.historical_data import init_historical_service


class TestAutonomousDashboardIntegration:
    """Test autonomous dashboard API endpoints integration."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup trading environment."""
        init_historical_service()
        init_paper_trading(starting_capital=10000)
        init_autonomous_trader(TradingConfig(
            enabled=False,
            entry_threshold=60.0,
            exit_profit_target=0.03,
            exit_stop_loss=0.02,
            position_size_pct=0.10,
            max_positions=5,
            symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        ))
        yield

    def test_autonomous_status_endpoint(self, client):
        """Test autonomous trading status endpoint."""
        response = client.get("/api/autonomous/status")
        assert response.status_code == 200
        data = response.json()
        assert 'running' in data or 'status' in data

    def test_autonomous_config_endpoint(self, client):
        """Test autonomous trading config endpoint."""
        response = client.get("/api/autonomous/config")
        assert response.status_code == 200
        data = response.json()
        assert 'entry_threshold' in data
        assert 'exit_profit_target' in data
        assert 'exit_stop_loss' in data
        assert 'position_size_pct' in data
        assert 'max_positions' in data
        assert 'symbols' in data
        assert isinstance(data['symbols'], list)

    def test_autonomous_trades_endpoint(self, client):
        """Test autonomous trades endpoint."""
        response = client.get("/api/autonomous/trades")
        assert response.status_code == 200
        data = response.json()
        assert 'total' in data
        assert 'recent' in data
        assert isinstance(data['recent'], list)

    def test_start_autonomous_trading(self, client):
        """Test starting autonomous trading."""
        response = client.post("/api/autonomous/start")
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert data['status'] in ['started', 'already_running']

    def test_stop_autonomous_trading(self, client):
        """Test stopping autonomous trading."""
        # First start
        client.post("/api/autonomous/start")

        # Then stop
        response = client.post("/api/autonomous/stop")
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert data['status'] == 'stopped'

    def test_update_config_entry_threshold(self, client):
        """Test updating entry threshold."""
        response = client.post(
            "/api/autonomous/config/update",
            json={"entry_threshold": 65.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['config']['entry_threshold'] == 65.0

    def test_update_config_position_size(self, client):
        """Test updating position size."""
        response = client.post(
            "/api/autonomous/config/update",
            json={"position_size_pct": 0.15}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['config']['position_size_pct'] == 0.15

    def test_update_config_symbols(self, client):
        """Test updating symbol list."""
        new_symbols = ['BTCUSDT', 'ETHUSDT']
        response = client.post(
            "/api/autonomous/config/update",
            json={"symbols": new_symbols}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['config']['symbols'] == new_symbols

    def test_update_multiple_config_params(self, client):
        """Test updating multiple config parameters at once."""
        response = client.post(
            "/api/autonomous/config/update",
            json={
                "entry_threshold": 70.0,
                "max_positions": 10,
                "exit_stop_loss": 0.03
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data['config']['entry_threshold'] == 70.0
        assert data['config']['max_positions'] == 10
        assert data['config']['exit_stop_loss'] == 0.03

    def test_paper_account_endpoint(self, client):
        """Test paper trading account endpoint."""
        response = client.get("/api/paper/account")
        assert response.status_code == 200
        data = response.json()
        assert 'total_equity' in data
        assert 'cash' in data
        assert 'positions_value' in data
        assert data['total_equity'] > 0

    def test_paper_trades_endpoint(self, client):
        """Test paper trading trades endpoint."""
        response = client.get("/api/paper/trades")
        assert response.status_code == 200
        data = response.json()
        assert 'trades' in data
        assert isinstance(data['trades'], list)

    def test_regime_detection_endpoint(self, client):
        """Test regime detection endpoint."""
        response = client.post("/api/regime/detect", params={"symbol": "BTCUSDT"})
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert 'regime' in data

    def test_signals_endpoint(self, client):
        """Test signals calculation endpoint."""
        # Signals endpoint requires prices data
        test_prices = [100.0, 101.0, 102.0, 101.5, 103.0]
        response = client.post(
            "/api/signals/calculate",
            params={"symbol": "BTCUSDT", "prices": test_prices}
        )
        assert response.status_code in [200, 404, 422]

    def test_dashboard_full_workflow(self, client):
        """Test complete dashboard workflow."""
        # 1. Get initial status
        status_resp = client.get("/api/autonomous/status")
        assert status_resp.status_code == 200

        # 2. Get config
        config_resp = client.get("/api/autonomous/config")
        assert config_resp.status_code == 200
        config = config_resp.json()

        # 3. Start trading
        start_resp = client.post("/api/autonomous/start")
        assert start_resp.status_code == 200

        # 4. Get account info
        account_resp = client.get("/api/paper/account")
        assert account_resp.status_code == 200

        # 5. Update config
        update_resp = client.post(
            "/api/autonomous/config/update",
            json={"entry_threshold": config['entry_threshold'] + 5}
        )
        assert update_resp.status_code == 200

        # 6. Get trades
        trades_resp = client.get("/api/autonomous/trades")
        assert trades_resp.status_code == 200

        # 7. Stop trading
        stop_resp = client.post("/api/autonomous/stop")
        assert stop_resp.status_code == 200

    def test_config_persistence(self, client):
        """Test that config changes persist."""
        new_threshold = 75.0

        # Update
        update_resp = client.post(
            "/api/autonomous/config/update",
            json={"entry_threshold": new_threshold}
        )
        assert update_resp.status_code == 200

        # Verify persistence
        config_resp = client.get("/api/autonomous/config")
        assert config_resp.status_code == 200
        assert config_resp.json()['entry_threshold'] == new_threshold

    def test_invalid_symbol_update(self, client):
        """Test updating with invalid symbols."""
        response = client.post(
            "/api/autonomous/config/update",
            json={"symbols": []}
        )
        # Should succeed (empty symbol list is technically valid)
        assert response.status_code == 200

    def test_config_value_ranges(self, client):
        """Test that config values are within reasonable ranges."""
        response = client.get("/api/autonomous/config")
        assert response.status_code == 200
        data = response.json()

        # Entry threshold should be 0-100
        assert 0 <= data['entry_threshold'] <= 100

        # Position size should be > 0
        assert data['position_size_pct'] > 0

        # Stop loss should be > 0
        assert data['exit_stop_loss'] > 0

        # Take profit should be > 0
        assert data['exit_profit_target'] > 0

        # Max positions should be > 0
        assert data['max_positions'] > 0


class TestDashboardUIAccess:
    """Test dashboard UI file access."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_autonomous_dashboard_accessible(self, client):
        """Test that autonomous dashboard HTML is accessible."""
        response = client.get("/static/autonomous-dashboard.html")
        assert response.status_code == 200
        assert b'Autonomous Trading Dashboard' in response.content

    def test_dashboard_contains_required_sections(self, client):
        """Test that dashboard contains all required sections."""
        response = client.get("/static/autonomous-dashboard.html")
        assert response.status_code == 200
        content = response.text

        # Check for required sections
        assert 'Overview' in content
        assert 'Signals' in content
        assert 'Positions' in content
        assert 'Trade History' in content
        assert 'Market Regime' in content
        assert 'Configuration' in content

    def test_dashboard_api_endpoints_referenced(self, client):
        """Test that dashboard references correct API endpoints."""
        response = client.get("/static/autonomous-dashboard.html")
        assert response.status_code == 200
        content = response.text

        # Check for API endpoint references
        assert '/api/autonomous/status' in content
        assert '/api/autonomous/start' in content
        assert '/api/autonomous/stop' in content
        assert '/api/autonomous/config' in content
        assert '/api/autonomous/trades' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
