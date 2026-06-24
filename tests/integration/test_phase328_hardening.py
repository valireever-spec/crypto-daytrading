"""Integration tests for Phase 328: Production Hardening."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.analytics.history_cleanup_manager import HistoryCleanupManager
from backend.analytics.realistic_cost_model import RealisticCostModel
from backend.analytics.feedback_loop_engine import FeedbackLoopEngine


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHistoryCleanupManager:
    """Test history cleanup functionality."""

    def test_initialization(self):
        """Test manager initializes."""
        manager = HistoryCleanupManager(retention_count=50)
        assert manager.retention_count == 50

    def test_cleanup_schedule(self):
        """Test cleanup schedule."""
        manager = HistoryCleanupManager()
        schedule = manager.get_cleanup_schedule()

        assert "retention_count" in schedule
        assert "cleanup_interval_days" in schedule
        assert "archive_location" in schedule

    def test_cleanup_empty_history(self):
        """Test cleanup on empty history."""
        manager = HistoryCleanupManager()
        result = manager.cleanup_rebalancing_history([])

        assert result.archived_count == 0
        assert result.remaining_count == 0

    def test_cleanup_within_retention(self):
        """Test no cleanup needed when within retention."""
        manager = HistoryCleanupManager(retention_count=100)

        class MockPlan:
            def __init__(self):
                self.trades = []
                self.total_cost_pct = 0.1
                self.feasible = True

        history = [MockPlan() for _ in range(50)]
        result = manager.cleanup_rebalancing_history(history)

        assert result.archived_count == 0
        assert result.next_cleanup_recommended is False


class TestRealisticCostModel:
    """Test realistic cost model."""

    def test_initialization(self):
        """Test model initializes."""
        model = RealisticCostModel(jurisdiction="Germany")
        assert model.jurisdiction == "Germany"

    def test_symbol_tier_mapping(self):
        """Test symbol to tier mapping."""
        model = RealisticCostModel()

        assert model.get_symbol_tier("BTCUSDT") == "crypto_major"
        assert model.get_symbol_tier("EQ_AAPL") == "equity_large_cap"
        assert model.get_symbol_tier("BOND_US10Y") == "bond"
        assert model.get_symbol_tier("UNKNOWN") == "equity_mid_cap"  # Default

    def test_execution_cost_estimation(self):
        """Test execution cost estimation."""
        model = RealisticCostModel()

        # High liquidity: low cost
        cost_btc = model.estimate_execution_cost("BTCUSDT", volume_pct=1.0)
        assert 0 < cost_btc < 0.05  # Should be < 0.05%

        # Low liquidity: high cost
        cost_small = model.estimate_execution_cost("EQ_UNKNOWN", volume_pct=2.0)
        assert cost_small > cost_btc  # Higher cost

    def test_tax_cost_estimation(self):
        """Test tax cost estimation."""
        model = RealisticCostModel(realized_gains_rate=0.5)

        tax_cost = model.estimate_tax_cost(sell_volume_pct=10.0)
        # 10% × 0.5 gain rate × 0.27 tax = 1.35% = 0.0135
        assert 0.01 < tax_cost < 0.02

    def test_total_cost_estimation(self):
        """Test total cost for trade set."""
        model = RealisticCostModel()

        trades = [
            ("BTCUSDT", "BUY", 1.0),
            ("EQ_AAPL", "SELL", 2.0),
        ]

        costs = model.estimate_total_cost(trades)

        assert "BTCUSDT" in costs
        assert "EQ_AAPL" in costs
        assert costs["BTCUSDT"].total_cost_pct > 0
        assert costs["EQ_AAPL"].total_cost_pct > 0

    def test_market_condition_adjustment(self):
        """Test cost adjustment for market conditions."""
        model = RealisticCostModel()

        # Normal vol (15%)
        base_cost = model.adjust_for_market_conditions(
            base_execution_bps=10.0, volatility_pct=15.0
        )
        assert base_cost == 10.0

        # High vol (30%)
        high_vol_cost = model.adjust_for_market_conditions(
            base_execution_bps=10.0, volatility_pct=30.0
        )
        assert high_vol_cost > base_cost


class TestFeedbackLoopEngine:
    """Test feedback loop engine."""

    def test_initialization(self):
        """Test engine initializes."""
        engine = FeedbackLoopEngine(min_samples_for_calibration=5)
        assert engine.min_samples == 5

    def test_insufficient_samples(self):
        """Test with insufficient samples."""
        engine = FeedbackLoopEngine(min_samples_for_calibration=10)

        accuracy, by_scenario = engine.analyze_recommendation_accuracy([], [])
        assert accuracy == 0.0
        assert by_scenario == {}

    def test_calibration_status(self):
        """Test calibration status."""
        engine = FeedbackLoopEngine()
        status = engine.get_recalibration_status()

        assert "status" in status
        assert status["status"] == "not_calibrated"

    def test_constraint_adjustment_suggestions(self):
        """Test constraint adjustment logic."""
        from backend.analytics.feedback_loop_engine import CalibrationReport

        engine = FeedbackLoopEngine()

        # Poor performance
        poor_report = CalibrationReport(
            scenario_accuracy_pct={"base": 20},
            recommendation_quality_score=25,
            constraint_effectiveness=40,
            suggested_adjustments={},
            is_healthy=False,
        )

        current_constraints = {"max_position_pct": 25.0}
        adjusted = engine.suggest_constraint_adjustments(poor_report, current_constraints)

        # Should tighten constraints
        assert adjusted["max_position_pct"] < current_constraints["max_position_pct"]

    def test_scenario_weight_suggestions(self):
        """Test scenario weight recommendations."""
        from backend.analytics.feedback_loop_engine import CalibrationReport

        engine = FeedbackLoopEngine()

        report = CalibrationReport(
            scenario_accuracy_pct={"upside": 80, "base": 60, "downside": 40},
            recommendation_quality_score=60,
            constraint_effectiveness=70,
            suggested_adjustments={},
            is_healthy=True,
        )

        weights = engine.suggest_scenario_weights(report)

        assert "upside" in weights
        assert "base" in weights
        assert "downside" in weights
        # Upside should have highest weight
        assert weights["upside"] > weights["downside"]
        # Sum should be ~1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestProductionHardeningAPI:
    """Test API endpoints."""

    def test_cleanup_status_endpoint(self, client):
        """Test cleanup status endpoint."""
        response = client.get("/api/hardening/cleanup/status")

        assert response.status_code == 200
        assert "status" in response.json()
        assert "archive_location" in response.json()

    def test_cleanup_execute_endpoint(self, client):
        """Test cleanup execution endpoint."""
        response = client.post(
            "/api/hardening/cleanup/execute-rebalancing",
            params={"history_size": 150},
        )

        assert response.status_code == 200
        assert "archived_count" in response.json()

    def test_cost_estimation_endpoint(self, client):
        """Test cost estimation endpoint."""
        trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "volume_pct": 1.0},
            {"symbol": "EQ_AAPL", "side": "SELL", "volume_pct": 2.0},
        ]

        response = client.post(
            "/api/hardening/costs/estimate",
            json=trades,
            params={"volatility_pct": 15.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_cost_pct" in data
        assert "costs_by_symbol" in data
        assert "BTCUSDT" in data["costs_by_symbol"]

    def test_calibration_report_endpoint(self, client):
        """Test calibration report endpoint."""
        response = client.get("/api/hardening/feedback/calibration-report")

        assert response.status_code == 200
        assert "recommendation_quality_score" in response.json()

    def test_recalibrate_endpoint(self, client):
        """Test recalibration endpoint."""
        response = client.post("/api/hardening/feedback/recalibrate")

        assert response.status_code == 200
        assert "status" in response.json()

    def test_production_readiness_endpoint(self, client):
        """Test production readiness assessment."""
        response = client.get("/api/hardening/health/production-readiness")

        assert response.status_code == 200
        data = response.json()
        assert "readiness_score" in data
        assert data["overall_status"] == "production_ready"
        assert "components" in data
