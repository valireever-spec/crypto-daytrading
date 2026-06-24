"""Integration tests for Risk Metrics API endpoints (Phase 321)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from backend.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_paper_trading():
    """Mock paper trading engine."""
    mock_engine = MagicMock()
    mock_engine.get_positions = MagicMock(return_value=[
        {'symbol': 'BTCUSDT', 'quantity': 1.0, 'entry_price': 50000, 'value_eur': 51000, 'price': 51000},
        {'symbol': 'EQ_AAPL', 'quantity': 100, 'entry_price': 145, 'value_eur': 15500, 'price': 155},
    ])
    mock_engine.get_account_state = MagicMock(return_value={'total_equity': 100000})
    return mock_engine


class TestRiskMetricsAPI:
    """Test risk metrics API endpoints."""

    def test_get_risk_metrics(self, client, mock_paper_trading):
        """Test GET /api/risk/metrics endpoint."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/metrics?lookback_days=90")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "value_at_risk_95" in data
            assert "expected_shortfall_95" in data
            assert "volatility_pct" in data
            assert "classification" in data

    def test_get_risk_metrics_valid_lookback(self, client, mock_paper_trading):
        """Test lookback_days parameter validation."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            # Valid range: 30-365
            response = client.get("/api/risk/metrics?lookback_days=180")
            assert response.status_code == 200

    def test_get_risk_metrics_invalid_lookback(self, client, mock_paper_trading):
        """Test invalid lookback_days parameter."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            # Invalid: too low
            response = client.get("/api/risk/metrics?lookback_days=10")
            assert response.status_code == 422

            # Invalid: too high
            response = client.get("/api/risk/metrics?lookback_days=400")
            assert response.status_code == 422

    def test_get_risk_metrics_no_positions(self, client):
        """Test risk metrics with empty portfolio."""
        mock_engine = MagicMock()
        mock_engine.get_positions = MagicMock(return_value=[])

        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_engine):
            response = client.get("/api/risk/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "error" in data

    def test_get_regime_risk_profile_bull(self, client):
        """Test GET /api/risk/regime-profile/bull endpoint."""
        response = client.get("/api/risk/regime-profile/bull")

        assert response.status_code == 200
        data = response.json()
        assert data["regime"] == "bull"
        assert "volatility_pct" in data
        assert "var_95_pct" in data
        assert "sharpe_ratio" in data
        assert "guidance" in data

    def test_get_regime_risk_profile_bear(self, client):
        """Test bear regime profile."""
        response = client.get("/api/risk/regime-profile/bear")

        assert response.status_code == 200
        data = response.json()
        assert data["regime"] == "bear"
        # Bear should have higher risk metrics than bull
        assert data["volatility_pct"] > 20

    def test_get_regime_risk_profile_sideways(self, client):
        """Test sideways regime profile."""
        response = client.get("/api/risk/regime-profile/sideways")

        assert response.status_code == 200
        data = response.json()
        assert data["regime"] == "sideways"

    def test_get_regime_risk_profile_volatile(self, client):
        """Test volatile regime profile."""
        response = client.get("/api/risk/regime-profile/volatile")

        assert response.status_code == 200
        data = response.json()
        assert data["regime"] == "volatile"
        assert data["volatility_pct"] > 30

    def test_get_regime_risk_profile_invalid(self, client):
        """Test invalid regime."""
        response = client.get("/api/risk/regime-profile/invalid")

        assert response.status_code == 400

    def test_get_stress_tests(self, client, mock_paper_trading):
        """Test GET /api/risk/stress-tests endpoint."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/stress-tests")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "scenarios" in data
            assert "worst_case" in data
            assert len(data["scenarios"]) > 0

    def test_get_stress_tests_no_positions(self, client):
        """Test stress tests with no positions."""
        mock_engine = MagicMock()
        mock_engine.get_positions = MagicMock(return_value=[])

        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_engine):
            response = client.get("/api/risk/stress-tests")
            assert response.status_code == 400

    def test_get_single_stress_test(self, client, mock_paper_trading):
        """Test GET /api/risk/stress-tests/{scenario} endpoint."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/stress-tests/market_crash")

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "market_crash"
            assert "portfolio_loss_pct" in data
            assert "affected_symbols" in data
            assert "recovery_days" in data

    def test_get_single_stress_test_volatility_spike(self, client, mock_paper_trading):
        """Test volatility spike scenario."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/stress-tests/volatility_spike")

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "volatility_spike"

    def test_get_single_stress_test_crypto_crash(self, client, mock_paper_trading):
        """Test crypto crash scenario."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/stress-tests/crypto_crash")

            assert response.status_code == 200
            data = response.json()
            assert data["scenario"] == "crypto_crash"

    def test_get_single_stress_test_invalid(self, client, mock_paper_trading):
        """Test invalid scenario."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/stress-tests/invalid_scenario")

            assert response.status_code == 400

    def test_set_risk_alert_thresholds(self, client):
        """Test POST /api/risk/alerts/thresholds endpoint."""
        response = client.post(
            "/api/risk/alerts/thresholds",
            params={
                "var_95_threshold": -3.5,
                "volatility_threshold": 25.0,
                "max_drawdown_threshold": -20.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["thresholds"]["var_95"] == -3.5
        assert data["thresholds"]["volatility"] == 25.0

    def test_set_risk_alert_thresholds_invalid_var(self, client):
        """Test invalid VaR threshold."""
        response = client.post(
            "/api/risk/alerts/thresholds",
            params={
                "var_95_threshold": 3.5,  # Should be negative
                "volatility_threshold": 25.0,
                "max_drawdown_threshold": -20.0,
            },
        )

        assert response.status_code == 400

    def test_set_risk_alert_thresholds_invalid_volatility(self, client):
        """Test invalid volatility threshold."""
        response = client.post(
            "/api/risk/alerts/thresholds",
            params={
                "var_95_threshold": -3.5,
                "volatility_threshold": -25.0,  # Should be positive
                "max_drawdown_threshold": -20.0,
            },
        )

        assert response.status_code == 400

    def test_get_risk_alert_status(self, client, mock_paper_trading):
        """Test GET /api/risk/alerts/status endpoint."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/alerts/status")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "current_metrics" in data
            assert "thresholds" in data
            assert "alerts" in data
            assert "critical_alerts" in data
            assert "status" in data

    def test_get_risk_alert_status_structure(self, client, mock_paper_trading):
        """Test alert status response structure."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/alerts/status")

            assert response.status_code == 200
            data = response.json()
            # Status should be OK or CRITICAL
            assert data["status"] in ["OK", "CRITICAL"]

    def test_get_risk_dashboard_summary(self, client, mock_paper_trading):
        """Test GET /api/risk/dashboard/summary endpoint."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert "timestamp" in data
            assert "portfolio_value" in data
            assert "risk_level" in data
            assert "summary" in data
            assert "regime" in data
            assert "worst_stress" in data
            assert "alerts" in data

    def test_get_risk_dashboard_summary_completeness(self, client, mock_paper_trading):
        """Test dashboard includes all risk components."""
        with patch('backend.api.routers.risk_metrics.get_paper_trading', return_value=mock_paper_trading):
            response = client.get("/api/risk/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            # Verify all components are present
            assert "var_95_pct" in data["summary"]
            assert "volatility_pct" in data["summary"]
            assert "sharpe_ratio" in data["summary"]
            assert data["regime"]["current"] in ["bull", "bear", "sideways", "volatile"]
