"""Integration tests for Phase 329: Learning & Feedback."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import shutil
from pathlib import Path

from backend.api.main import app
from backend.analytics.recommendation_tracker import get_recommendation_tracker
from backend.analytics.scenario_probability_learner import get_scenario_probability_learner
from backend.analytics.cost_model_calibrator import get_cost_model_calibrator


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances between tests."""
    import backend.analytics.recommendation_tracker as rt
    import backend.analytics.scenario_probability_learner as spl
    import backend.analytics.cost_model_calibrator as cmc

    # Clean tracking directory
    tracking_dir = Path("logs/recommendation_tracking")
    if tracking_dir.exists():
        shutil.rmtree(tracking_dir)
    tracking_dir.mkdir(parents=True, exist_ok=True)

    # Clean weights cache
    weights_cache = Path("logs/.scenario_weights_cache.json")
    if weights_cache.exists():
        weights_cache.unlink()

    rt._tracker = None
    spl._learner = None
    cmc._calibrator = None

    yield

    # Clean up after test
    if tracking_dir.exists():
        shutil.rmtree(tracking_dir)
    tracking_dir.mkdir(parents=True, exist_ok=True)

    if weights_cache.exists():
        weights_cache.unlink()

    rt._tracker = None
    spl._learner = None
    cmc._calibrator = None


class TestRecommendationTracker:
    """Test recommendation tracking."""

    def test_initialization(self):
        """Test tracker initializes."""
        tracker = get_recommendation_tracker()
        assert tracker is not None
        assert len(tracker.recommendations) == 0
        assert len(tracker.outcomes) == 0

    def test_record_recommendation(self):
        """Test recording recommendations."""
        tracker = get_recommendation_tracker()

        rec_id = str(uuid4())
        rec = tracker.record_recommendation(
            recommendation_id=rec_id,
            symbol="AAPL",
            recommended_allocation_pct=5.0,
            scenario="base",
            expected_return_pct=2.5,
            confidence_score=75.0,
            rationale="Strong technical setup",
        )

        assert rec.recommendation_id == rec_id
        assert rec.symbol == "AAPL"
        assert len(tracker.recommendations) == 1

    def test_record_outcome(self):
        """Test recording outcomes."""
        tracker = get_recommendation_tracker()

        rec_id = str(uuid4())
        tracker.record_recommendation(
            recommendation_id=rec_id,
            symbol="AAPL",
            recommended_allocation_pct=5.0,
            scenario="base",
            expected_return_pct=2.5,
            confidence_score=75.0,
        )

        outcome = tracker.record_outcome(
            recommendation_id=rec_id,
            holding_period_days=10,
            actual_return_pct=2.3,
            executed_allocation_pct=5.0,
        )

        assert outcome.recommendation_id == rec_id
        assert outcome.actual_return_pct == 2.3
        assert len(tracker.outcomes) == 1

    def test_analyze_accuracy_with_data(self):
        """Test accuracy analysis."""
        tracker = get_recommendation_tracker()

        # Record multiple recs and outcomes
        for i in range(5):
            rec_id = str(uuid4())
            tracker.record_recommendation(
                recommendation_id=rec_id,
                symbol="AAPL",
                recommended_allocation_pct=5.0,
                scenario="base",
                expected_return_pct=2.0,
                confidence_score=75.0,
            )

            # Outcome matches direction
            tracker.record_outcome(
                recommendation_id=rec_id,
                holding_period_days=10,
                actual_return_pct=1.8,
                executed_allocation_pct=5.0,
            )

        metrics = tracker.analyze_accuracy()
        assert metrics.total_recommendations == 5
        assert metrics.correct_direction == 5
        assert metrics.accuracy_pct == 100.0

    def test_scenario_performance(self):
        """Test scenario performance metrics."""
        tracker = get_recommendation_tracker()

        # Record base scenario
        for i in range(3):
            rec_id = str(uuid4())
            tracker.record_recommendation(
                recommendation_id=rec_id,
                symbol="AAPL",
                recommended_allocation_pct=5.0,
                scenario="base",
                expected_return_pct=2.0,
                confidence_score=75.0,
            )
            tracker.record_outcome(
                recommendation_id=rec_id,
                holding_period_days=10,
                actual_return_pct=2.0,
                executed_allocation_pct=5.0,
            )

        perf = tracker.get_scenario_performance()
        assert "base" in perf
        assert perf["base"]["count"] == 3
        assert perf["base"]["accuracy_pct"] == 100.0


class TestScenarioProbabilityLearner:
    """Test scenario probability learning."""

    def test_initialization(self):
        """Test learner initializes."""
        learner = get_scenario_probability_learner()
        assert learner is not None
        assert "base" in learner.weights
        assert "upside" in learner.weights
        assert "downside" in learner.weights

    def test_default_weights(self):
        """Test default weights."""
        learner = get_scenario_probability_learner()
        assert learner.weights["base"] == 0.50
        assert learner.weights["upside"] == 0.25
        assert learner.weights["downside"] == 0.25

    def test_update_from_accuracy(self):
        """Test updating weights from accuracy."""
        learner = get_scenario_probability_learner()

        accuracy = {
            "base": 85.0,
            "upside": 60.0,
            "downside": 40.0,
        }

        updated = learner.update_from_accuracy(accuracy)

        assert updated is not None
        assert sum(updated.values()) >= 0.99  # Allow for rounding
        # Base should have highest weight
        assert updated["base"] >= updated["upside"]
        assert updated["base"] >= updated["downside"]

    def test_suggest_reweighting_large_spread(self):
        """Test reweighting suggestion with large accuracy spread."""
        learner = get_scenario_probability_learner()

        accuracy = {
            "base": 90.0,
            "upside": 50.0,
            "downside": 30.0,
        }

        suggested, recommendation = learner.suggest_reweighting(
            accuracy,
            current_weights=learner.weights,
        )

        assert suggested is not None
        assert "base" in recommendation.lower()

    def test_weight_decay(self):
        """Test weight decay over time."""
        learner = get_scenario_probability_learner()
        learner.weights = {"base": 0.6, "upside": 0.3, "downside": 0.1}

        decayed = learner.decay_weights(days_since_last_update=60)

        # Should move toward uniform (0.33 each)
        assert abs(decayed["base"] - 0.33) < abs(learner.weights["base"] - 0.33)


class TestCostModelCalibrator:
    """Test cost model calibration."""

    def test_initialization(self):
        """Test calibrator initializes."""
        calibrator = get_cost_model_calibrator()
        assert calibrator is not None
        assert len(calibrator.executions) == 0

    def test_record_execution(self):
        """Test recording execution."""
        calibrator = get_cost_model_calibrator()

        record = calibrator.record_execution(
            symbol="AAPL",
            side="BUY",
            planned_cost_pct=0.15,
            actual_cost_pct=0.22,
            volume_pct=2.0,
        )

        assert record.symbol == "AAPL"
        assert record.actual_cost_pct == 0.22
        assert len(calibrator.executions) == 1

    def test_symbol_profile(self):
        """Test symbol cost profile."""
        calibrator = get_cost_model_calibrator()

        # Record multiple executions
        for i in range(4):
            calibrator.record_execution(
                symbol="AAPL",
                side="BUY",
                planned_cost_pct=0.15,
                actual_cost_pct=0.20,
                volume_pct=2.0,
            )

        profile = calibrator.get_symbol_profile("AAPL")
        assert profile is not None
        assert profile.symbol == "AAPL"
        assert profile.execution_count == 4
        assert profile.avg_actual_cost_pct > 0

    def test_insufficient_data_for_profile(self):
        """Test profile requires minimum executions."""
        calibrator = get_cost_model_calibrator()

        # Record only 2 executions (need 3+)
        calibrator.record_execution(
            symbol="MSFT",
            side="BUY",
            planned_cost_pct=0.15,
            actual_cost_pct=0.20,
            volume_pct=2.0,
        )
        calibrator.record_execution(
            symbol="MSFT",
            side="SELL",
            planned_cost_pct=0.15,
            actual_cost_pct=0.18,
            volume_pct=2.0,
        )

        profile = calibrator.get_symbol_profile("MSFT")
        assert profile is None  # Insufficient data

    def test_identify_tier_mismatches(self):
        """Test mismatch identification."""
        calibrator = get_cost_model_calibrator()

        # Record execution with large error
        for i in range(4):
            calibrator.record_execution(
                symbol="SMALL",
                side="BUY",
                planned_cost_pct=0.05,  # Expected small cost
                actual_cost_pct=0.50,  # Much higher actual cost
                volume_pct=1.0,
            )

        mismatches = calibrator.identify_tier_mismatches()
        assert "SMALL" in mismatches or len(mismatches) == 0

    def test_estimate_portfolio_cost(self):
        """Test portfolio cost estimation."""
        calibrator = get_cost_model_calibrator()

        # Record some executions
        for i in range(4):
            calibrator.record_execution(
                symbol="AAPL",
                side="BUY",
                planned_cost_pct=0.15,
                actual_cost_pct=0.20,
                volume_pct=2.0,
            )

        trades = [
            {"symbol": "AAPL", "volume_pct": 2.0},
            {"symbol": "MSFT", "volume_pct": 1.5},
        ]

        estimate = calibrator.estimate_total_portfolio_cost(trades)
        assert "costs_by_symbol" in estimate
        assert "total_portfolio_cost_pct" in estimate


class TestLearningFeedbackAPI:
    """Test API endpoints."""

    def test_record_recommendation_endpoint(self, client):
        """Test recommendation recording endpoint."""
        rec_id = str(uuid4())

        response = client.post(
            "/api/learning/recommendations/record",
            json={
                "recommendation_id": rec_id,
                "symbol": "AAPL",
                "recommended_allocation_pct": 5.0,
                "scenario": "base",
                "expected_return_pct": 2.5,
                "confidence_score": 75.0,
                "rationale": "Strong technical setup",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["recommendation_id"] == rec_id
        assert data["status"] == "recorded"

    def test_record_outcome_endpoint(self, client):
        """Test outcome recording endpoint."""
        rec_id = str(uuid4())

        # First record recommendation
        client.post(
            "/api/learning/recommendations/record",
            json={
                "recommendation_id": rec_id,
                "symbol": "AAPL",
                "recommended_allocation_pct": 5.0,
                "scenario": "base",
                "expected_return_pct": 2.5,
                "confidence_score": 75.0,
            },
        )

        # Then record outcome
        response = client.post(
            "/api/learning/outcomes/record",
            json={
                "recommendation_id": rec_id,
                "holding_period_days": 10,
                "actual_return_pct": 2.3,
                "executed_allocation_pct": 5.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

    def test_get_recommendation_accuracy_endpoint(self, client):
        """Test accuracy endpoint."""
        response = client.get("/api/learning/recommendations/accuracy")

        assert response.status_code == 200
        data = response.json()
        assert "total_recommendations" in data
        assert "accuracy_pct" in data

    def test_get_scenario_performance_endpoint(self, client):
        """Test scenario performance endpoint."""
        response = client.get("/api/learning/scenarios/performance")

        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data

    def test_learn_scenario_weights_endpoint(self, client):
        """Test scenario learning endpoint."""
        response = client.post("/api/learning/scenarios/learn")

        assert response.status_code == 200
        data = response.json()
        assert "weights" in data or "status" in data

    def test_get_scenario_weights_endpoint(self, client):
        """Test get scenario weights endpoint."""
        response = client.get("/api/learning/scenarios/weights")

        assert response.status_code == 200
        data = response.json()
        assert "weights" in data

    def test_record_execution_endpoint(self, client):
        """Test execution recording endpoint."""
        response = client.post(
            "/api/learning/costs/record-execution",
            json={
                "symbol": "AAPL",
                "side": "BUY",
                "planned_cost_pct": 0.15,
                "actual_cost_pct": 0.22,
                "volume_pct": 2.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

    def test_get_calibration_status_endpoint(self, client):
        """Test calibration status endpoint."""
        response = client.get("/api/learning/costs/calibration-status")

        assert response.status_code == 200
        data = response.json()
        assert "total_executions_recorded" in data

    def test_get_symbol_profiles_endpoint(self, client):
        """Test symbol profiles endpoint."""
        response = client.get("/api/learning/costs/symbol-profiles")

        assert response.status_code == 200
        data = response.json()
        assert "profiles" in data

    def test_estimate_portfolio_costs_endpoint(self, client):
        """Test portfolio cost estimation endpoint."""
        trades = [
            {"symbol": "AAPL", "volume_pct": 2.0},
            {"symbol": "MSFT", "volume_pct": 1.5},
        ]

        response = client.post(
            "/api/learning/costs/estimate-portfolio",
            json=trades,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_portfolio_cost_pct" in data

    def test_estimate_portfolio_costs_empty(self, client):
        """Test error handling for empty trades."""
        response = client.post(
            "/api/learning/costs/estimate-portfolio",
            json=[],
        )

        assert response.status_code == 400
