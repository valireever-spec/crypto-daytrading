"""Integration tests for Portfolio Allocation Optimizer (Phase 322)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.api.main import app
from backend.analytics.portfolio_optimizer import (
    PortfolioOptimizer,
    get_portfolio_optimizer,
    AllocationTarget,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_returns():
    """Create sample daily returns for multiple symbols."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
    # More realistic daily returns: 0.05-0.1% mean, 0.8-1.5% std
    returns = {
        "BTCUSDT": pd.Series(np.random.normal(0.08, 0.8, 252), index=dates),
        "EQ_AAPL": pd.Series(np.random.normal(0.05, 0.6, 252), index=dates),
        "EQ_MSFT": pd.Series(np.random.normal(0.06, 0.7, 252), index=dates),
        "EQ_GOOGL": pd.Series(np.random.normal(0.04, 0.65, 252), index=dates),
        "EQ_NVDA": pd.Series(np.random.normal(0.10, 1.0, 252), index=dates),
    }
    return returns


@pytest.fixture
def mock_paper_trading():
    """Mock paper trading engine."""
    mock_engine = MagicMock()
    mock_engine.get_positions = MagicMock(return_value=[
        {'symbol': 'BTCUSDT', 'quantity': 1.0, 'entry_price': 50000, 'value_eur': 51000, 'price': 51000},
        {'symbol': 'EQ_AAPL', 'quantity': 100, 'entry_price': 145, 'value_eur': 15500, 'price': 155},
        {'symbol': 'EQ_MSFT', 'quantity': 50, 'entry_price': 400, 'value_eur': 21000, 'price': 420},
    ])
    mock_engine.get_account_state = MagicMock(return_value={'total_equity': 100000})
    return mock_engine


@pytest.fixture
def mock_historical_service():
    """Mock historical data service."""
    mock_service = MagicMock()

    def get_candles_side_effect(symbol, **kwargs):
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        prices = np.random.lognormal(mean=np.log(100), sigma=0.15, size=252)
        return pd.DataFrame({
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, 252),
        }, index=dates)

    mock_service.get_candles = MagicMock(side_effect=get_candles_side_effect)
    return mock_service


class TestPortfolioOptimizer:
    """Test portfolio optimizer functionality."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer."""
        return PortfolioOptimizer()

    def test_initialization(self, optimizer):
        """Test optimizer initializes correctly."""
        assert optimizer.risk_free_rate == 0.02

    def test_optimize_portfolio_balanced(self, optimizer, sample_returns):
        """Test portfolio optimization for balanced risk."""
        allocation = optimizer.optimize_portfolio(
            returns=sample_returns,
            risk_level="balanced",
        )

        assert isinstance(allocation, AllocationTarget)
        assert allocation.risk_level == "balanced"
        # Check that allocation is returned
        assert allocation.allocation is not None
        assert len(allocation.allocation) > 0
        assert abs(sum(allocation.allocation.values()) - 100.0) < 1.0  # Weights sum to 100%

    def test_optimize_portfolio_conservative(self, optimizer, sample_returns):
        """Test conservative allocation."""
        conservative = optimizer.optimize_portfolio(
            returns=sample_returns,
            risk_level="conservative",
        )

        assert conservative is not None
        assert conservative.risk_level == "conservative"
        assert conservative.allocation is not None

    def test_optimize_portfolio_aggressive(self, optimizer, sample_returns):
        """Test aggressive allocation."""
        aggressive = optimizer.optimize_portfolio(
            returns=sample_returns,
            risk_level="aggressive",
        )

        assert aggressive is not None
        assert aggressive.risk_level == "aggressive"
        assert aggressive.allocation is not None

    def test_allocation_weights_sum_to_100(self, optimizer, sample_returns):
        """Test allocation weights sum to 100%."""
        for risk_level in ["conservative", "moderate", "balanced", "aggressive", "extreme"]:
            allocation = optimizer.optimize_portfolio(
                returns=sample_returns,
                risk_level=risk_level,
            )
            total_weight = sum(allocation.allocation.values())
            assert abs(total_weight - 100.0) < 1.0

    def test_sharpe_ratio_calculated(self, optimizer, sample_returns):
        """Test Sharpe ratio is calculated."""
        allocation = optimizer.optimize_portfolio(
            returns=sample_returns,
            risk_level="balanced",
        )

        assert isinstance(allocation.sharpe_ratio, (int, float))
        assert allocation.sharpe_ratio > 0

    def test_diversification_ratio(self, optimizer, sample_returns):
        """Test diversification ratio is calculated."""
        allocation = optimizer.optimize_portfolio(
            returns=sample_returns,
            risk_level="balanced",
        )

        assert isinstance(allocation.diversification_ratio, (int, float))
        assert allocation.diversification_ratio > 1.0

    def test_efficient_frontier(self, optimizer, sample_returns):
        """Test efficient frontier calculation."""
        frontier = optimizer.efficient_frontier(returns=sample_returns, n_points=10)

        assert len(frontier) <= 10
        assert len(frontier) > 0

        # Check that volatility increases along frontier
        for i in range(1, len(frontier)):
            assert frontier[i].volatility_pct >= frontier[i - 1].volatility_pct

    def test_efficient_frontier_sharpe_variation(self, optimizer, sample_returns):
        """Test Sharpe ratio calculated for frontier."""
        frontier = optimizer.efficient_frontier(returns=sample_returns, n_points=15)

        sharpe_ratios = [p.sharpe_ratio for p in frontier]
        # All should be floats
        assert all(isinstance(s, (int, float)) for s in sharpe_ratios)
        assert len(frontier) > 0

    def test_rebalancing_plan_generation(self, optimizer):
        """Test rebalancing plan generation."""
        current_positions = {
            "BTCUSDT": 40000,
            "EQ_AAPL": 35000,
            "EQ_MSFT": 25000,
        }
        target_allocation = {
            "BTCUSDT": 35,
            "EQ_AAPL": 40,
            "EQ_MSFT": 25,
        }

        plan = optimizer.generate_rebalancing_plan(
            current_positions=current_positions,
            target_allocation=target_allocation,
            total_value=100000,
        )

        assert plan.trades is not None
        assert plan.total_trade_volume_eur >= 0
        assert plan.estimated_cost_eur >= 0
        assert plan.tax_impact_eur >= 0

    def test_rebalancing_plan_action_types(self, optimizer):
        """Test rebalancing trades are BUY/SELL."""
        current_positions = {
            "BTCUSDT": 60000,
            "EQ_AAPL": 40000,
        }
        target_allocation = {
            "BTCUSDT": 40,
            "EQ_AAPL": 60,
        }

        plan = optimizer.generate_rebalancing_plan(
            current_positions=current_positions,
            target_allocation=target_allocation,
            total_value=100000,
        )

        for trade in plan.trades:
            assert trade["action"] in ["BUY", "SELL"]

    def test_global_instance(self):
        """Test global optimizer instance."""
        opt1 = get_portfolio_optimizer()
        opt2 = get_portfolio_optimizer()

        assert opt1 is opt2


class TestPortfolioAllocationAPI:
    """Test portfolio allocation API endpoints."""

    def test_get_optimal_allocation(self, client, mock_paper_trading, mock_historical_service):
        """Test GET /api/allocation/optimize endpoint."""
        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_paper_trading), \
             patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/optimize?risk_level=balanced")

            assert response.status_code == 200
            data = response.json()
            assert "risk_level" in data
            assert data["risk_level"] == "balanced"
            assert "target_return_pct" in data
            assert "target_volatility_pct" in data
            assert "allocation" in data
            assert "sharpe_ratio" in data

    def test_get_optimal_allocation_invalid_risk_level(self, client):
        """Test invalid risk level returns 400."""
        response = client.get("/api/allocation/optimize?risk_level=invalid")
        assert response.status_code == 400

    def test_get_optimal_allocation_all_levels(self, client, mock_historical_service):
        """Test optimization for all risk levels."""
        risk_levels = ["conservative", "moderate", "balanced", "aggressive", "extreme"]

        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            for risk_level in risk_levels:
                response = client.get(f"/api/allocation/optimize?risk_level={risk_level}")
                assert response.status_code == 200
                data = response.json()
                assert data["risk_level"] == risk_level

    def test_get_efficient_frontier(self, client, mock_historical_service):
        """Test GET /api/allocation/efficient-frontier endpoint."""
        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/efficient-frontier?n_points=10")

            assert response.status_code == 200
            data = response.json()
            assert "frontier" in data
            assert "optimal_point" in data
            assert len(data["frontier"]) > 0

    def test_get_current_allocation(self, client, mock_paper_trading):
        """Test GET /api/allocation/current-allocation endpoint."""
        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_paper_trading):
            response = client.get("/api/allocation/current-allocation")

            assert response.status_code == 200
            data = response.json()
            assert "total_value_eur" in data
            assert "allocation" in data
            assert "num_positions" in data
            assert data["total_value_eur"] == 100000
            assert data["num_positions"] == 3

    def test_get_current_allocation_structure(self, client, mock_paper_trading):
        """Test current allocation response structure."""
        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_paper_trading):
            response = client.get("/api/allocation/current-allocation")

            assert response.status_code == 200
            data = response.json()
            allocation = data["allocation"]

            for symbol, info in allocation.items():
                assert "value_eur" in info
                assert "weight_pct" in info
                assert "quantity" in info
                assert "entry_price" in info

    def test_get_recommended_rebalancing(self, client, mock_paper_trading, mock_historical_service):
        """Test GET /api/allocation/recommended-rebalancing endpoint."""
        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_paper_trading), \
             patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/recommended-rebalancing?risk_level=balanced")

            assert response.status_code == 200
            data = response.json()
            assert "current_allocation" in data
            assert "target_allocation" in data
            assert "trades" in data
            assert "total_trade_volume_eur" in data
            assert "estimated_cost_eur" in data

    def test_get_recommended_rebalancing_trades_structure(self, client, mock_paper_trading, mock_historical_service):
        """Test rebalancing trades structure."""
        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_paper_trading), \
             patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/recommended-rebalancing?risk_level=balanced")

            assert response.status_code == 200
            data = response.json()

            for trade in data["trades"]:
                assert "symbol" in trade
                assert "action" in trade
                assert trade["action"] in ["BUY", "SELL"]
                assert "current_value_eur" in trade
                assert "target_value_eur" in trade
                assert "trade_amount_eur" in trade

    def test_get_risk_return_profile(self, client, mock_historical_service):
        """Test GET /api/allocation/risk-return-profile endpoint."""
        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/risk-return-profile")

            assert response.status_code == 200
            data = response.json()
            assert "profiles" in data
            assert len(data["profiles"]) == 5  # 5 risk levels

    def test_risk_return_profile_completeness(self, client, mock_historical_service):
        """Test risk/return profiles have all fields."""
        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/risk-return-profile")

            assert response.status_code == 200
            data = response.json()

            expected_levels = ["conservative", "moderate", "balanced", "aggressive", "extreme"]
            actual_levels = [p["risk_level"] for p in data["profiles"]]
            assert actual_levels == expected_levels

            for profile in data["profiles"]:
                assert "target_return_pct" in profile
                assert "target_volatility_pct" in profile
                assert "sharpe_ratio" in profile
                assert "suitable_for" in profile

    def test_allocation_weights_sum_to_100(self, client, mock_historical_service):
        """Test allocation weights sum to ~100%."""
        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/optimize?risk_level=balanced")

            assert response.status_code == 200
            data = response.json()
            allocation = data["allocation"]
            total = sum(allocation.values())
            assert abs(total - 100.0) < 1.0

    def test_efficient_frontier_increasing_volatility(self, client, mock_historical_service):
        """Test efficient frontier volatility increases."""
        with patch("backend.api.routers.portfolio_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.get("/api/allocation/efficient-frontier?n_points=15")

            assert response.status_code == 200
            data = response.json()
            frontier = data["frontier"]

            for i in range(1, len(frontier)):
                assert frontier[i]["volatility_pct"] >= frontier[i - 1]["volatility_pct"]

    def test_rebalancing_plan_no_positions(self, client):
        """Test rebalancing with no positions."""
        mock_engine = MagicMock()
        mock_engine.get_positions = MagicMock(return_value=[])

        with patch("backend.api.routers.portfolio_allocation.get_paper_trading", return_value=mock_engine):
            response = client.get("/api/allocation/recommended-rebalancing?risk_level=balanced")
            assert response.status_code == 400
