"""Integration tests for Phase 325: Recommendation Engine."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.api.main import app
from backend.analytics.scenario_analyzer import (
    ScenarioAnalyzer,
    get_scenario_analyzer,
)
from backend.analytics.allocation_solver import (
    AllocationSolver,
    get_allocation_solver,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_returns():
    """Sample historical returns."""
    dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
    return {
        "BTCUSDT": pd.Series(np.random.normal(0.1, 2.0, 252), index=dates),
        "EQ_AAPL": pd.Series(np.random.normal(0.05, 1.5, 252), index=dates),
        "EQ_MSFT": pd.Series(np.random.normal(0.08, 1.6, 252), index=dates),
    }


@pytest.fixture
def sample_allocation():
    """Sample allocation."""
    return {"BTCUSDT": 40.0, "EQ_AAPL": 35.0, "EQ_MSFT": 25.0}


class TestScenarioAnalyzer:
    """Test scenario analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer."""
        return ScenarioAnalyzer()

    def test_initialization(self, analyzer):
        """Test analyzer initializes."""
        assert analyzer is not None
        assert analyzer.risk_free_rate == 0.02

    def test_monte_carlo_simulation(self, analyzer, sample_returns, sample_allocation):
        """Test Monte Carlo simulation."""
        result = analyzer.monte_carlo_simulation(
            historical_returns=sample_returns,
            allocation=sample_allocation,
            time_horizon_days=252,
            n_simulations=1000,
        )

        assert result is not None
        assert isinstance(result.expected_return_pct, float)
        assert isinstance(result.volatility_pct, float)
        assert result.probability_positive_pct >= 0
        assert result.probability_positive_pct <= 100

    def test_upside_scenario(self, analyzer, sample_returns, sample_allocation):
        """Test upside scenario analysis."""
        result = analyzer.analyze_upside_scenario(
            historical_returns=sample_returns,
            allocation=sample_allocation,
        )

        assert result.scenario_name == "Upside Scenario"
        assert result.probability_pct >= 0
        assert result.probability_pct <= 100

    def test_downside_scenario(self, analyzer, sample_returns, sample_allocation):
        """Test downside scenario analysis."""
        result = analyzer.analyze_downside_scenario(
            historical_returns=sample_returns,
            allocation=sample_allocation,
        )

        assert result.scenario_name == "Downside Scenario"
        assert result.probability_pct >= 0
        assert result.probability_pct <= 100

    def test_base_case_scenario(self, analyzer, sample_returns, sample_allocation):
        """Test base case scenario analysis."""
        result = analyzer.base_case_scenario(
            historical_returns=sample_returns,
            allocation=sample_allocation,
        )

        assert result.scenario_name == "Base Case Scenario"
        assert result.probability_pct == 50.0

    def test_empty_returns(self, analyzer, sample_allocation):
        """Test with empty returns."""
        result = analyzer.monte_carlo_simulation(
            historical_returns={},
            allocation=sample_allocation,
        )

        assert result.expected_return_pct == 0
        assert result.volatility_pct == 0

    def test_global_instance(self):
        """Test global singleton."""
        ana1 = get_scenario_analyzer()
        ana2 = get_scenario_analyzer()

        assert ana1 is ana2


class TestAllocationSolver:
    """Test allocation solver."""

    @pytest.fixture
    def solver(self):
        """Create solver."""
        return AllocationSolver()

    def test_initialization(self, solver):
        """Test solver initializes."""
        assert solver is not None
        assert solver.risk_free_rate == 0.02

    def test_solve_for_return(self, solver, sample_returns):
        """Test solving for return target."""
        result = solver.solve_for_return(
            historical_returns=sample_returns,
            target_return_pct=8.0,
            max_single_position_pct=25.0,
        )

        assert result is not None
        assert sum(result.allocation.values()) == pytest.approx(100.0, abs=2.0)
        # If feasible, should respect constraints
        if result.feasible:
            assert all(0 <= v <= 25.0 for v in result.allocation.values())

    def test_solve_for_volatility(self, solver, sample_returns):
        """Test solving for volatility target."""
        result = solver.solve_for_volatility(
            historical_returns=sample_returns,
            target_volatility_pct=10.0,
            max_single_position_pct=25.0,
        )

        assert result is not None
        assert sum(result.allocation.values()) == pytest.approx(100.0, abs=1.0)

    def test_allocation_constraints(self, solver, sample_returns):
        """Test allocation respects constraints."""
        result = solver.solve_for_return(
            historical_returns=sample_returns,
            target_return_pct=5.0,
            max_single_position_pct=30.0,
        )

        # Check sum is ~100%
        total = sum(result.allocation.values())
        assert total == pytest.approx(100.0, abs=2.0)

        # If feasible, check no position exceeds limit
        if result.feasible:
            assert all(v <= 30.0 for v in result.allocation.values())

    def test_global_instance(self):
        """Test global singleton."""
        sol1 = get_allocation_solver()
        sol2 = get_allocation_solver()

        assert sol1 is sol2

    def test_impossible_return_target(self, solver, sample_returns):
        """Test handling of infeasible target."""
        result = solver.solve_for_return(
            historical_returns=sample_returns,
            target_return_pct=1000.0,  # Unrealistic
        )

        assert result is not None
        assert not result.feasible


class TestRecommendationAPI:
    """Test recommendation API endpoints."""

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_scenario_analysis_endpoint(self, mock_returns, client, sample_returns, sample_allocation):
        """Test POST /api/recommendation/scenario-analysis endpoint."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL", "EQ_MSFT"],
                "allocation": sample_allocation,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "monte_carlo" in data
        assert "scenarios" in data
        assert len(data["scenarios"]) == 3

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_scenario_analysis_response_structure(self, mock_returns, client, sample_returns, sample_allocation):
        """Test scenario analysis response structure."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "allocation": {"BTCUSDT": 60.0, "EQ_AAPL": 40.0},
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check Monte Carlo structure
        assert "expected_return_pct" in data["monte_carlo"]
        assert "volatility_pct" in data["monte_carlo"]
        assert "percentile_5th_pct" in data["monte_carlo"]
        assert "percentile_95th_pct" in data["monte_carlo"]

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_scenario_analysis_custom_horizon(self, mock_returns, client, sample_returns, sample_allocation):
        """Test scenario analysis with custom time horizon."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT"],
                "allocation": {"BTCUSDT": 100.0},
            },
            params={
                "time_horizon_days": 126,
                "n_simulations": 5000,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_horizon_days"] == 126
        assert data["n_simulations"] == 5000

    def test_scenario_analysis_invalid_weights(self, client):
        """Test scenario analysis with invalid weights."""
        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "allocation": {"BTCUSDT": 60.0, "EQ_AAPL": 30.0},  # Sum=90, not 100
            },
        )

        assert response.status_code == 400

    def test_scenario_analysis_no_symbols(self, client):
        """Test scenario analysis with no symbols."""
        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": [],
                "allocation": {},
            },
        )

        assert response.status_code == 400

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_allocation_solver_return_endpoint(self, mock_returns, client, sample_returns):
        """Test POST /api/recommendation/allocation-solver for return target."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL", "EQ_MSFT"],
                "target_type": "return",
                "target_value": 10.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["target_type"] == "return"
        assert "allocation" in data
        assert "sharpe_ratio" in data

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_allocation_solver_volatility_endpoint(self, mock_returns, client, sample_returns):
        """Test POST /api/recommendation/allocation-solver for volatility target."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "target_type": "volatility",
                "target_value": 12.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["target_type"] == "volatility"

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_allocation_solver_response_structure(self, mock_returns, client, sample_returns):
        """Test allocation solver response structure."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "target_type": "return",
                "target_value": 8.0,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "allocation" in data
        assert "expected_return_pct" in data
        assert "expected_volatility_pct" in data
        assert "sharpe_ratio" in data
        assert "feasible" in data

    def test_allocation_solver_invalid_target_type(self, client):
        """Test allocation solver with invalid target type."""
        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT"],
                "target_type": "invalid",
                "target_value": 10.0,
            },
        )

        assert response.status_code == 400

    def test_allocation_solver_no_symbols(self, client):
        """Test allocation solver with no symbols."""
        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": [],
                "target_type": "return",
                "target_value": 10.0,
            },
        )

        assert response.status_code == 400

    def test_allocation_solver_negative_target(self, client):
        """Test allocation solver with negative target."""
        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT"],
                "target_type": "return",
                "target_value": -5.0,
            },
        )

        assert response.status_code == 400

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_allocation_solver_custom_max_position(self, mock_returns, client, sample_returns):
        """Test allocation solver with custom max position."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/allocation-solver",
            json={
                "symbols": ["BTCUSDT", "EQ_AAPL"],
                "target_type": "return",
                "target_value": 8.0,
            },
            params={"max_single_position_pct": 20.0},
        )

        assert response.status_code == 200
        data = response.json()
        # If feasible, all positions should respect the limit
        if data["feasible"]:
            assert all(v <= 20.0 for v in data["allocation"].values())

    @patch("backend.api.routers.recommendation._get_historical_returns")
    def test_scenario_analysis_probability_bounds(self, mock_returns, client, sample_returns, sample_allocation):
        """Test scenario analysis probability bounds."""
        mock_returns.return_value = sample_returns

        response = client.post(
            "/api/recommendation/scenario-analysis",
            json={
                "symbols": ["BTCUSDT"],
                "allocation": {"BTCUSDT": 100.0},
            },
        )

        assert response.status_code == 200
        data = response.json()

        for scenario in data["scenarios"]:
            assert 0 <= scenario["probability_pct"] <= 100
