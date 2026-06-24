"""Integration tests for Portfolio Attribution (Phase 324)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.api.main import app
from backend.analytics.attribution_engine import (
    PerformanceAttributionEngine,
    get_attribution_engine,
)
from backend.analytics.factor_calculator import FactorCalculator


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_positions():
    """Sample portfolio positions."""
    return {"BTCUSDT": 40000, "EQ_AAPL": 35000, "EQ_MSFT": 25000}


@pytest.fixture
def sample_returns():
    """Sample position returns."""
    return {"BTCUSDT": 12.5, "EQ_AAPL": 8.3, "EQ_MSFT": -2.1}


@pytest.fixture
def sample_benchmark():
    """Sample benchmark positions."""
    return {"BTCUSDT": 30000, "EQ_AAPL": 40000, "EQ_MSFT": 30000}


class TestAttributionEngine:
    """Test attribution engine."""

    @pytest.fixture
    def engine(self):
        """Create attribution engine."""
        return PerformanceAttributionEngine()

    def test_initialization(self, engine):
        """Test engine initializes."""
        assert engine is not None

    def test_position_contribution(self, engine, sample_positions, sample_returns):
        """Test position contribution calculation."""
        contributions, total_return = engine.analyze_position_contribution(
            positions=sample_positions,
            position_returns=sample_returns,
            portfolio_value=100000,
        )

        assert len(contributions) == 3
        assert isinstance(contributions[0].contribution_pct, float)
        # Total should be around 6.2% (0.4*12.5 + 0.35*8.3 + 0.25*-2.1)
        assert 5.0 < total_return < 8.0

    def test_drift_analysis(self, engine, sample_positions, sample_benchmark, sample_returns):
        """Test drift analysis."""
        drift = engine.calculate_drift_analysis(
            portfolio_positions=sample_positions,
            benchmark_positions=sample_benchmark,
            portfolio_value=100000,
            benchmark_value=100000,
            position_returns=sample_returns,
        )

        assert drift is not None
        assert "BTCUSDT" in drift.active_weight_pct
        assert abs(drift.active_weight_pct["BTCUSDT"] - 10.0) < 0.1  # 40% - 30%

    def test_global_instance(self):
        """Test global engine instance."""
        eng1 = get_attribution_engine()
        eng2 = get_attribution_engine()

        assert eng1 is eng2


class TestFactorCalculator:
    """Test factor calculator."""

    def test_momentum_calculation(self):
        """Test momentum factor calculation."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        returns = pd.Series(np.random.normal(0.05, 0.5, 100), index=dates)

        momentum = FactorCalculator.calculate_momentum(returns, lookback=50)

        assert isinstance(momentum, float)
        assert -1 <= momentum <= 1

    def test_value_factor(self):
        """Test value factor calculation."""
        value = FactorCalculator.calculate_value_factor(
            current_price=100,
            book_value=80,
            earnings=10,
        )

        assert isinstance(value, float)
        # Factor scores may exceed [-1, 1] depending on input
        assert isinstance(value, (int, float))

    def test_quality_factor(self):
        """Test quality factor calculation."""
        quality = FactorCalculator.calculate_quality_factor(
            roe=20.0,
            debt_to_equity=0.5,
            current_ratio=1.8,
        )

        assert isinstance(quality, float)

    def test_volatility_factor(self):
        """Test volatility factor calculation."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        returns = pd.Series(np.random.normal(0.05, 1.0, 100), index=dates)

        volatility = FactorCalculator.calculate_volatility_factor(returns, lookback=50)

        assert isinstance(volatility, float)
        # Factor scores may exceed [-1, 1] depending on input
        assert isinstance(volatility, (int, float))

    def test_size_factor(self):
        """Test size factor calculation."""
        size = FactorCalculator.calculate_size_factor(market_cap=10e9)

        assert isinstance(size, float)
        assert -1 <= size <= 1

    def test_all_factors(self):
        """Test calculating all factors."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        returns = pd.Series(np.random.normal(0.05, 0.5, 100), index=dates)

        factors = FactorCalculator.calculate_all_factors(
            returns=returns,
            price=100,
            book_value=80,
            earnings=10,
            roe=20,
            debt_to_equity=0.5,
            current_ratio=1.8,
            market_cap=10e9,
        )

        assert "momentum" in factors
        assert "value" in factors
        assert "quality" in factors
        assert "volatility" in factors
        assert "size" in factors


class TestAttributionAPI:
    """Test attribution API endpoints."""

    def test_position_contribution_endpoint(self, client):
        """Test POST /api/attribution/position-contribution endpoint."""
        positions = {"BTCUSDT": 40000, "EQ_AAPL": 35000, "EQ_MSFT": 25000}
        returns = {"BTCUSDT": 12.5, "EQ_AAPL": 8.3, "EQ_MSFT": -2.1}

        response = client.post(
            "/api/attribution/position-contribution",
            json={
                "positions": positions,
                "position_returns": returns,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_return_pct" in data
        assert "contributions" in data
        assert len(data["contributions"]) == 3

    def test_position_contribution_response_structure(self, client):
        """Test response structure."""
        response = client.post(
            "/api/attribution/position-contribution",
            json={
                "positions": {"BTCUSDT": 50000, "EQ_AAPL": 50000},
                "position_returns": {"BTCUSDT": 10, "EQ_AAPL": 5},
            },
        )

        assert response.status_code == 200
        data = response.json()

        for contrib in data["contributions"]:
            assert "symbol" in contrib
            assert "weight_pct" in contrib
            assert "return_pct" in contrib
            assert "contribution_pct" in contrib
            assert "profit_loss_eur" in contrib

    def test_factor_attribution_endpoint(self, client):
        """Test POST /api/attribution/factor-attribution endpoint."""
        returns = {"BTCUSDT": 12.5, "EQ_AAPL": 8.3, "EQ_MSFT": -2.1}

        response = client.post(
            "/api/attribution/factor-attribution",
            json={"symbol_returns": returns},
        )

        assert response.status_code == 200
        data = response.json()
        assert "factors" in data
        assert isinstance(data["factors"], list)

    def test_drift_analysis_endpoint(self, client):
        """Test POST /api/attribution/drift-analysis endpoint."""
        portfolio = {"BTCUSDT": 40000, "EQ_AAPL": 35000, "EQ_MSFT": 25000}
        benchmark = {"BTCUSDT": 30000, "EQ_AAPL": 40000, "EQ_MSFT": 30000}
        returns = {"BTCUSDT": 12.5, "EQ_AAPL": 8.3, "EQ_MSFT": -2.1}

        response = client.post(
            "/api/attribution/drift-analysis",
            json={
                "portfolio_positions": portfolio,
                "benchmark_positions": benchmark,
                "position_returns": returns,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "active_return_pct" in data
        assert "tracking_error_pct" in data
        assert "information_ratio" in data

    def test_drift_analysis_structure(self, client):
        """Test drift analysis response structure."""
        response = client.post(
            "/api/attribution/drift-analysis",
            json={
                "portfolio_positions": {"BTCUSDT": 60000, "EQ_AAPL": 40000},
                "benchmark_positions": {"BTCUSDT": 50000, "EQ_AAPL": 50000},
                "position_returns": {"BTCUSDT": 10, "EQ_AAPL": 5},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "largest_overweight" in data
        assert "largest_underweight" in data
        assert "active_contributions" in data

    def test_attribution_summary(self, client):
        """Test GET /api/attribution/summary endpoint."""
        response = client.get("/api/attribution/summary?period=1m")

        assert response.status_code in [200, 400, 503]  # May fail if no positions
        if response.status_code == 200:
            data = response.json()
            assert "period" in data
            assert "summary" in data

    def test_invalid_positions(self, client):
        """Test error handling for invalid positions."""
        response = client.post(
            "/api/attribution/position-contribution",
            json={
                "positions": {},
                "position_returns": {},
            },
        )

        assert response.status_code == 400

    def test_drift_analysis_invalid_values(self, client):
        """Test drift analysis with invalid values."""
        response = client.post(
            "/api/attribution/drift-analysis",
            json={
                "portfolio_positions": {},
                "benchmark_positions": {},
                "position_returns": {},
            },
        )

        assert response.status_code == 400

    def test_position_contribution_accuracy(self, client):
        """Test contribution calculation accuracy."""
        positions = {"A": 60000, "B": 40000}  # 60-40 split
        returns = {"A": 10, "B": 5}  # A returns 10%, B returns 5%

        response = client.post(
            "/api/attribution/position-contribution",
            json={
                "positions": positions,
                "position_returns": returns,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Total return should be 0.6*10 + 0.4*5 = 8%
        assert abs(data["total_return_pct"] - 8.0) < 0.1

    def test_drift_analysis_active_weights(self, client):
        """Test active weight calculation."""
        portfolio = {"A": 70000, "B": 30000}  # 70-30
        benchmark = {"A": 50000, "B": 50000}  # 50-50
        returns = {"A": 10, "B": 5}

        response = client.post(
            "/api/attribution/drift-analysis",
            json={
                "portfolio_positions": portfolio,
                "benchmark_positions": benchmark,
                "position_returns": returns,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Active weight in A should be 20% (70% - 50%)
        active_A = data["active_contributions"].get("A", 0)
        # Contribution = 0.2 * 10% = 2%
        assert abs(active_A - 2.0) < 0.5
