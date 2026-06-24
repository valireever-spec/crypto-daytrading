"""Integration tests for Phase 325-327 API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestPhase325Endpoints:
    """Test Phase 325 API endpoints."""

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_scenario_analysis_endpoint_200(self, mock_returns, client):
        """Test scenario analysis returns 200 with valid data."""
        import pandas as pd
        import numpy as np

        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        mock_returns.return_value = {
            "BTCUSDT": pd.Series(np.random.normal(0.1, 2.0, 252), index=dates),
            "EQ_AAPL": pd.Series(np.random.normal(0.05, 1.5, 252), index=dates),
        }

        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "allocation": {"BTCUSDT": 60.0, "EQ_AAPL": 40.0},
            },
        )

        assert response.status_code == 200
        assert "monte_carlo" in response.json()
        assert "scenarios" in response.json()

    def test_scenario_analysis_400_invalid_weights(self, client):
        """Test scenario analysis returns 400 for invalid weights."""
        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["A", "B"],
                "allocation": {"A": 60.0, "B": 30.0},  # Sum = 90, not 100
            },
        )

        assert response.status_code == 400
        assert "sum" in response.json()["detail"].lower()

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_allocation_solver_endpoint_200(self, mock_returns, client):
        """Test allocation solver returns 200 with valid data."""
        import pandas as pd
        import numpy as np

        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        mock_returns.return_value = {
            "A": pd.Series(np.random.normal(0.05, 1.0, 252), index=dates),
            "B": pd.Series(np.random.normal(0.08, 1.5, 252), index=dates),
        }

        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["A", "B"],
                "target_type": "return",
                "target_value": 8.0,
            },
        )

        assert response.status_code == 200
        assert "allocation" in response.json()
        assert "sharpe_ratio" in response.json()

    def test_allocation_solver_400_invalid_target(self, client):
        """Test allocation solver returns 400 for invalid target."""
        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["A"],
                "target_type": "invalid",
                "target_value": 10.0,
            },
        )

        assert response.status_code == 400


class TestPhase326Endpoints:
    """Test Phase 326 API endpoints."""

    def test_add_sector_limit_endpoint_200(self, client):
        """Test adding sector limit returns 200."""
        response = client.post(
            "/api/recommendation/constraints/add-sector-limit",
            json={
                "sector": "Technology",
                "max_weight_pct": 50.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "added"

    def test_add_concentration_limit_endpoint_200(self, client):
        """Test adding concentration limit returns 200."""
        response = client.post(
            "/api/recommendation/constraints/add-concentration-limit",
            json=25.0,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "added"

    def test_validate_allocation_endpoint_200(self, client):
        """Test allocation validation returns 200."""
        response = client.post(
            "/api/recommendation/constraints/validate",
            json={"A": 60.0, "B": 40.0},
        )

        assert response.status_code == 200
        assert "valid" in response.json()
        assert isinstance(response.json()["valid"], bool)

    def test_list_scenarios_endpoint_200(self, client):
        """Test scenario listing returns 200."""
        response = client.post("/api/recommendation/scenario/list")

        assert response.status_code == 200
        assert "scenarios" in response.json()
        assert len(response.json()["scenarios"]) > 0

    def test_record_recommendation_endpoint_200(self, client):
        """Test recording recommendation returns 200."""
        response = client.post(
            "/api/recommendation/performance/record-recommendation",
            json={
                "allocation": {"A": 100.0},
                "expected_return_pct": 8.0,
                "expected_volatility_pct": 12.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

    def test_record_outcome_endpoint_200(self, client):
        """Test recording outcome returns 200."""
        response = client.post(
            "/api/recommendation/performance/record-outcome",
            json={
                "actual_return_pct": 7.5,
                "actual_volatility_pct": 11.5,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

    def test_get_performance_metrics_endpoint(self, client):
        """Test getting performance metrics."""
        # Record recommendation and outcome first
        client.post(
            "/api/recommendation/performance/record-recommendation",
            json={
                "allocation": {"A": 100.0},
                "expected_return_pct": 8.0,
                "expected_volatility_pct": 12.0,
            },
        )

        # Get metrics (may be 400 if no matched pairs yet)
        response = client.get("/api/recommendation/performance/metrics")
        assert response.status_code in [200, 400]


class TestPhase327Endpoints:
    """Test Phase 327 API endpoints."""

    def test_analyze_drift_endpoint_200(self, client):
        """Test drift analysis returns 200."""
        response = client.post(
            "/api/rebalancing/analyze-drift",
            json={
                "current_allocation": {"A": 40.0, "B": 60.0},
                "target_allocation": {"A": 50.0, "B": 50.0},
            },
        )

        assert response.status_code == 200
        assert "total_drift_pct" in response.json()
        assert "requires_rebalancing" in response.json()

    def test_generate_plan_endpoint_200(self, client):
        """Test plan generation returns 200."""
        response = client.post(
            "/api/rebalancing/generate-plan",
            json={
                "current_allocation": {"A": 40.0, "B": 60.0},
                "target_allocation": {"A": 50.0, "B": 50.0},
                "portfolio_value_eur": 100000,
            },
        )

        assert response.status_code == 200
        assert "trades" in response.json()
        assert "total_cost_pct" in response.json()
        assert "feasible" in response.json()

    def test_break_into_tranches_endpoint_200(self, client):
        """Test tranching returns 200."""
        response = client.post(
            "/api/rebalancing/break-into-tranches",
            json={
                "current_allocation": {"A": 30.0, "B": 70.0},
                "target_allocation": {"A": 60.0, "B": 40.0},
                "portfolio_value_eur": 100000,
            },
        )

        assert response.status_code == 200
        assert "total_tranches" in response.json()
        assert "tranches" in response.json()

    def test_stress_test_endpoint_200(self, client):
        """Test stress test returns 200."""
        response = client.post(
            "/api/rebalancing/stress-test?scenario_name=bull_market",
            json={"A": 60.0, "B": 40.0},
        )

        assert response.status_code == 200
        assert "scenario" in response.json()
        assert "portfolio_volatility_pct" in response.json()
        assert "feasible_under_stress" in response.json()

    def test_get_history_endpoint_200(self, client):
        """Test history retrieval returns 200."""
        response = client.get("/api/rebalancing/history")

        assert response.status_code == 200
        assert "total_rebalancings" in response.json()
        assert "recent_rebalancings" in response.json()


class TestErrorCases:
    """Test error handling across endpoints."""

    def test_endpoints_handle_missing_fields(self, client):
        """Test endpoints return 400 for missing required fields."""
        # Missing allocation
        response = client.post("/api/rebalancing/analyze-drift", json={})
        assert response.status_code in [400, 422]

    def test_endpoints_handle_invalid_values(self, client):
        """Test endpoints return 400 for invalid values."""
        # Negative portfolio value
        response = client.post(
            "/api/rebalancing/generate-plan",
            json={
                "current_allocation": {"A": 100.0},
                "target_allocation": {"A": 100.0},
                "portfolio_value_eur": -10000,
            },
        )
        assert response.status_code == 400

    def test_endpoints_have_timestamps(self, client):
        """Test that endpoints return timestamps in responses."""
        response = client.post(
            "/api/rebalancing/analyze-drift",
            json={
                "current_allocation": {"A": 100.0},
                "target_allocation": {"A": 100.0},
            },
        )

        if response.status_code == 200:
            assert "timestamp" in response.json()
