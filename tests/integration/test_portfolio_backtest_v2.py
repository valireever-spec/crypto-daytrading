"""Integration tests for Portfolio Backtesting v2 (Phase 323)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.api.main import app
from backend.analytics.portfolio_backtest_engine_v2 import (
    PortfolioBacktestEngineV2,
    get_backtest_engine,
    BacktestResult,
)
from backend.analytics.backtest_analyzer import BacktestAnalyzer


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_returns():
    """Create sample daily returns."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
    returns = {
        "BTCUSDT": pd.Series(np.random.normal(0.08, 0.8, 252), index=dates),
        "EQ_AAPL": pd.Series(np.random.normal(0.05, 0.6, 252), index=dates),
        "EQ_MSFT": pd.Series(np.random.normal(0.06, 0.7, 252), index=dates),
    }
    return returns


@pytest.fixture
def sample_allocation():
    """Sample allocation."""
    return {"BTCUSDT": 40, "EQ_AAPL": 35, "EQ_MSFT": 25}


@pytest.fixture
def mock_historical_service():
    """Mock historical data service."""
    mock_service = MagicMock()

    def get_candles_side_effect(symbol, **kwargs):
        np.random.seed(hash(symbol) % 2**32)
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        prices = np.random.lognormal(mean=np.log(100), sigma=0.1, size=252)
        return pd.DataFrame({
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, 252),
        }, index=dates)

    mock_service.get_candles = MagicMock(side_effect=get_candles_side_effect)
    return mock_service


class TestPortfolioBacktestEngineV2:
    """Test backtest engine."""

    @pytest.fixture
    def engine(self):
        """Create backtest engine."""
        return PortfolioBacktestEngineV2()

    def test_initialization(self, engine):
        """Test engine initializes."""
        assert engine.risk_free_rate == 0.02

    def test_backtest_fixed_allocation(self, engine, sample_returns, sample_allocation):
        """Test fixed allocation backtest."""
        result = engine.backtest_allocation(
            historical_returns=sample_returns,
            allocation=sample_allocation,
            strategy_name="test_strategy",
        )

        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "test_strategy"
        assert result.period_days > 0
        assert isinstance(result.total_return_pct, float)
        assert isinstance(result.sharpe_ratio, float)

    def test_backtest_result_metrics(self, engine, sample_returns, sample_allocation):
        """Test backtest result has all metrics."""
        result = engine.backtest_allocation(
            historical_returns=sample_returns,
            allocation=sample_allocation,
        )

        # Returns
        assert hasattr(result, 'total_return_pct')
        assert hasattr(result, 'annualized_return_pct')

        # Risk
        assert hasattr(result, 'volatility_pct')
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'sortino_ratio')
        assert hasattr(result, 'max_drawdown_pct')

        # Win rate
        assert hasattr(result, 'win_rate_pct')
        assert 0 <= result.win_rate_pct <= 100

    def test_allocation_weights_in_result(self, engine, sample_returns, sample_allocation):
        """Test result contains allocation weights."""
        result = engine.backtest_allocation(
            historical_returns=sample_returns,
            allocation=sample_allocation,
        )

        # Weights should be normalized to ~100%
        total_weight = sum(result.allocation.values())
        assert abs(total_weight - 100.0) < 1.0

    def test_transaction_costs_calculated(self, engine, sample_returns, sample_allocation):
        """Test transaction costs are calculated."""
        result = engine.backtest_allocation(
            historical_returns=sample_returns,
            allocation=sample_allocation,
            transaction_cost_pct=0.001,
        )

        assert result.total_transaction_cost_pct >= 0

    def test_rolling_optimization(self, engine, sample_returns):
        """Test rolling optimization backtest."""
        result = engine.backtest_rolling_optimization(
            historical_returns=sample_returns,
            risk_level="balanced",
            rebalance_freq="monthly",
        )

        assert isinstance(result, BacktestResult)
        assert result.num_rebalances >= 0

    def test_multiple_allocations_comparison(self, engine, sample_returns):
        """Test comparing multiple allocations."""
        allocations = {
            "Conservative": {"BTCUSDT": 30, "EQ_AAPL": 40, "EQ_MSFT": 30},
            "Aggressive": {"BTCUSDT": 60, "EQ_AAPL": 20, "EQ_MSFT": 20},
        }

        comparison = engine.backtest_multiple_allocations(
            historical_returns=sample_returns,
            allocations=allocations,
        )

        assert len(comparison.results) == 2
        assert comparison.best_sharpe is not None
        assert comparison.best_return is not None

    def test_global_instance(self):
        """Test global engine instance."""
        eng1 = get_backtest_engine()
        eng2 = get_backtest_engine()

        assert eng1 is eng2


class TestBacktestAnalyzer:
    """Test backtest analyzer."""

    @pytest.fixture
    def sample_returns_series(self):
        """Sample returns series."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        return pd.Series(np.random.normal(0.05, 0.8, 252), index=dates)

    def test_calculate_metrics(self, sample_returns_series):
        """Test metrics calculation."""
        metrics = BacktestAnalyzer.calculate_metrics(sample_returns_series)

        assert "return_metrics" in metrics
        assert "risk_metrics" in metrics
        assert "distribution" in metrics

        # Check key fields
        assert "total_return_pct" in metrics["return_metrics"]
        assert "sharpe_ratio" in metrics["risk_metrics"]
        assert "skewness" in metrics["distribution"]

    def test_rolling_performance_monthly(self, sample_returns_series):
        """Test monthly rolling performance."""
        engine = PortfolioBacktestEngineV2()
        result = engine.backtest_allocation(
            historical_returns={"TEST": sample_returns_series},
            allocation={"TEST": 100},
        )

        perf = BacktestAnalyzer.analyze_rolling_performance(result, period="monthly")

        assert "period_type" in perf
        assert perf["period_type"] == "monthly"
        assert "positive_periods" in perf

    def test_rolling_performance_quarterly(self, sample_returns_series):
        """Test quarterly rolling performance."""
        engine = PortfolioBacktestEngineV2()
        result = engine.backtest_allocation(
            historical_returns={"TEST": sample_returns_series},
            allocation={"TEST": 100},
        )

        perf = BacktestAnalyzer.analyze_rolling_performance(result, period="quarterly")

        assert perf["period_type"] == "quarterly"

    def test_benchmark_comparison(self, sample_returns_series):
        """Test benchmark comparison."""
        engine = PortfolioBacktestEngineV2()
        result = engine.backtest_allocation(
            historical_returns={"TEST": sample_returns_series},
            allocation={"TEST": 100},
        )

        comp = BacktestAnalyzer.compare_to_benchmark(
            result,
            benchmark_return=5.0,
            benchmark_vol=10.0,
        )

        assert "excess_return_pct" in comp
        assert "information_ratio" in comp
        assert comp["outperformance"] in ["BETTER", "WORSE"]


class TestBacktestAllocationAPI:
    """Test backtest API endpoints."""

    def test_backtest_allocation_endpoint(self, client, mock_historical_service):
        """Test POST /api/backtest/allocation endpoint."""
        allocation = {"BTCUSDT": 40, "EQ_AAPL": 35, "EQ_MSFT": 25}

        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/allocation?strategy_name=test&lookback_days=100",
                json=allocation,
            )

            assert response.status_code == 200
            data = response.json()
            assert "result_id" in data
            assert "total_return_pct" in data
            assert "sharpe_ratio" in data

    def test_backtest_allocation_response_structure(self, client, mock_historical_service):
        """Test backtest response structure."""
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/allocation?strategy_name=test",
                json={"BTCUSDT": 50, "EQ_AAPL": 50},
            )

            assert response.status_code == 200
            data = response.json()

            # Check key fields
            assert data["total_return_pct"] is not None
            assert data["volatility_pct"] is not None
            assert data["win_rate_pct"] is not None

    def test_backtest_rolling_optimization(self, client, mock_historical_service):
        """Test POST /api/backtest/rolling-optimization endpoint."""
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/rolling-optimization",
                params={
                    "risk_level": "balanced",
                    "rebalance_freq": "monthly",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "result_id" in data
            assert "num_rebalances" in data

    def test_backtest_rolling_invalid_risk_level(self, client):
        """Test invalid risk level."""
        response = client.post(
            "/api/backtest/rolling-optimization",
            params={
                "risk_level": "invalid",
                "rebalance_freq": "monthly",
            },
        )
        assert response.status_code == 400

    def test_backtest_compare_allocations(self, client, mock_historical_service):
        """Test POST /api/backtest/compare endpoint."""
        allocations = {
            "Conservative": {"BTCUSDT": 30, "EQ_AAPL": 40, "EQ_MSFT": 30},
            "Aggressive": {"BTCUSDT": 60, "EQ_AAPL": 20, "EQ_MSFT": 20},
        }

        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/compare",
                json=allocations,
            )

            assert response.status_code == 200
            data = response.json()
            assert "best_sharpe" in data
            assert "rankings" in data
            assert "recommendations" in data

    def test_backtest_results_retrieval(self, client, mock_historical_service):
        """Test GET /api/backtest/results/{result_id} endpoint."""
        # First, create a backtest
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            create_response = client.post(
                "/api/backtest/allocation?strategy_name=test",
                json={"BTCUSDT": 50, "EQ_AAPL": 50},
            )

            assert create_response.status_code == 200
            result_id = create_response.json()["result_id"]

            # Get results
            get_response = client.get(f"/api/backtest/results/{result_id}")

            assert get_response.status_code == 200
            data = get_response.json()
            assert data["result_id"] == result_id
            assert "detailed_metrics" in data

    def test_backtest_results_not_found(self, client):
        """Test result not found."""
        response = client.get("/api/backtest/results/invalid_id")
        assert response.status_code == 404

    def test_backtest_analyze(self, client, mock_historical_service):
        """Test POST /api/backtest/analyze endpoint."""
        # First create a backtest
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            create_response = client.post(
                "/api/backtest/allocation?strategy_name=test",
                json={"BTCUSDT": 50, "EQ_AAPL": 50},
            )

            result_id = create_response.json()["result_id"]

            # Analyze
            response = client.post(
                "/api/backtest/analyze",
                params={
                    "result_id": result_id,
                    "benchmark_return_pct": 5.0,
                    "benchmark_volatility_pct": 10.0,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "metrics" in data
            assert "monthly_performance" in data
            assert "benchmark_comparison" in data

    def test_backtest_summary(self, client, mock_historical_service):
        """Test GET /api/backtest/summary endpoint."""
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            # Create a backtest
            client.post(
                "/api/backtest/allocation?strategy_name=test1",
                json={"BTCUSDT": 50, "EQ_AAPL": 50},
            )

            # Get summary
            response = client.get("/api/backtest/summary")

            assert response.status_code == 200
            data = response.json()
            assert "total_backtests" in data
            assert "results" in data
            assert data["total_backtests"] >= 0

    def test_allocation_weights_normalized(self, client, mock_historical_service):
        """Test allocation weights are normalized."""
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/allocation?strategy_name=test",
                json={"BTCUSDT": 40, "EQ_AAPL": 35, "EQ_MSFT": 25},
            )

            assert response.status_code == 200
            data = response.json()
            total_weight = sum(data["allocation"].values())
            assert abs(total_weight - 100.0) < 1.0

    def test_rolling_optimization_all_frequencies(self, client, mock_historical_service):
        """Test rolling optimization with all rebalance frequencies."""
        frequencies = ["monthly", "quarterly", "annual"]

        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            for freq in frequencies:
                response = client.post(
                    "/api/backtest/rolling-optimization",
                    params={
                        "risk_level": "balanced",
                        "rebalance_freq": freq,
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["rebalance_freq"] == freq

    def test_transaction_cost_parameter(self, client, mock_historical_service):
        """Test transaction cost parameter."""
        with patch("backend.api.routers.backtest_allocation.get_historical_service", return_value=mock_historical_service):
            response = client.post(
                "/api/backtest/allocation?strategy_name=test&transaction_cost_bps=20",
                json={"BTCUSDT": 50, "EQ_AAPL": 50},
            )

            assert response.status_code == 200
            data = response.json()
            assert "transaction_cost_pct" in data
