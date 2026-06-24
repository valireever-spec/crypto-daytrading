"""Integration tests for Phase 330: Learning Automation."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
import shutil
from pathlib import Path

from backend.api.main import app
from backend.analytics.recommendation_tracking_daemon import get_recommendation_tracking_daemon
from backend.analytics.scenario_auto_reweighting_scheduler import get_scenario_auto_reweighting_scheduler
from backend.analytics.recommendation_tracker import get_recommendation_tracker


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
    import backend.analytics.recommendation_tracking_daemon as rtd
    import backend.analytics.scenario_auto_reweighting_scheduler as sars

    # Clean tracking directory
    tracking_dir = Path("logs/recommendation_tracking")
    if tracking_dir.exists():
        shutil.rmtree(tracking_dir)
    tracking_dir.mkdir(parents=True, exist_ok=True)

    rt._tracker = None
    spl._learner = None
    cmc._calibrator = None
    rtd._daemon = None
    sars._scheduler = None

    yield

    if tracking_dir.exists():
        shutil.rmtree(tracking_dir)
    tracking_dir.mkdir(parents=True, exist_ok=True)

    rt._tracker = None
    spl._learner = None
    cmc._calibrator = None
    rtd._daemon = None
    sars._scheduler = None


class TestRecommendationTrackingDaemon:
    """Test recommendation tracking daemon."""

    def test_initialization(self):
        """Test daemon initializes."""
        daemon = get_recommendation_tracking_daemon()
        assert daemon is not None
        assert daemon.last_run is None

    def test_calculate_holding_outcome(self):
        """Test outcome calculation."""
        daemon = get_recommendation_tracking_daemon()

        now = datetime.now(timezone.utc)
        entry_time = now.isoformat()
        exit_time = (now + timedelta(days=5)).isoformat()

        outcome = daemon.calculate_holding_outcome(
            recommendation_id="rec-1",
            symbol="AAPL",
            entry_timestamp=entry_time,
            entry_price=150.0,
            entry_allocation_pct=5.0,
            exit_timestamp=exit_time,
            exit_price=160.0,
            exit_allocation_pct=5.0,
        )

        assert outcome.symbol == "AAPL"
        assert outcome.holding_period_days == 5
        # Price return: (160-150)/150 * 100 = 6.67%
        # Allocation-weighted: 6.67% * (5%/100) = 0.33%
        assert 0.3 < outcome.actual_return_pct < 0.4

    def test_match_recommendations_empty(self):
        """Test matching with empty data."""
        daemon = get_recommendation_tracking_daemon()

        outcomes = daemon.match_recommendations_to_executions([], [])
        assert len(outcomes) == 0

    def test_run_daily_sync_no_executions(self):
        """Test sync with no executions."""
        daemon = get_recommendation_tracking_daemon()

        result = daemon.run_daily_sync([])

        assert result["matched_count"] == 0
        assert result["recorded_count"] == 0


class TestScenarioAutoReweightingScheduler:
    """Test scenario auto-reweighting scheduler."""

    def test_initialization(self):
        """Test scheduler initializes."""
        scheduler = get_scenario_auto_reweighting_scheduler()
        assert scheduler is not None
        assert scheduler.last_reweight_timestamp is None

    def test_should_reweight_insufficient_data(self):
        """Test reweighting check with insufficient data."""
        scheduler = get_scenario_auto_reweighting_scheduler()

        # No recommendations, should not reweight
        assert not scheduler.should_reweight()

    def test_should_reweight_sufficient_data(self):
        """Test reweighting check with sufficient data."""
        scheduler = get_scenario_auto_reweighting_scheduler()
        tracker = get_recommendation_tracker()

        # Record recommendations with outcomes
        for i in range(5):
            for scenario in ["base", "upside", "downside"]:
                from uuid import uuid4
                rec_id = str(uuid4())
                tracker.record_recommendation(
                    recommendation_id=rec_id,
                    symbol="AAPL",
                    recommended_allocation_pct=5.0,
                    scenario=scenario,
                    expected_return_pct=2.0,
                    confidence_score=75.0,
                )
                tracker.record_outcome(
                    recommendation_id=rec_id,
                    holding_period_days=10,
                    actual_return_pct=2.0,
                    executed_allocation_pct=5.0,
                )

        # Should have enough data now
        assert scheduler.should_reweight()

    def test_get_status(self):
        """Test scheduler status."""
        scheduler = get_scenario_auto_reweighting_scheduler()
        status = scheduler.get_status()

        assert "last_reweight" in status
        assert "reweight_count" in status
        assert status["status"] == "ready"

    def test_reweight_history(self):
        """Test reweighting history tracking."""
        scheduler = get_scenario_auto_reweighting_scheduler()

        history = scheduler.get_reweighting_history()
        assert len(history) == 0


class TestLearningAutomationAPI:
    """Test automation API endpoints."""

    def test_sync_recommendations_endpoint(self, client):
        """Test recommendation sync endpoint."""
        now = datetime.now(timezone.utc).isoformat()

        executions = [
            {
                "symbol": "AAPL",
                "side": "BUY",
                "timestamp": now,
                "price": 150.0,
                "allocation_pct": 5.0,
                "quantity": 1.0,
            }
        ]

        response = client.post(
            "/api/automation/daemon/sync-recommendations",
            json=executions,
        )

        assert response.status_code == 200
        data = response.json()
        assert "matched_count" in data
        assert "recorded_count" in data

    def test_sync_empty_executions(self, client):
        """Test sync with empty executions."""
        response = client.post(
            "/api/automation/daemon/sync-recommendations",
            json=[],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matched_count"] == 0

    def test_daemon_last_run_endpoint(self, client):
        """Test daemon last run endpoint."""
        response = client.get("/api/automation/daemon/last-run")

        assert response.status_code == 200
        data = response.json()
        assert "last_run" in data
        assert "status" in data

    def test_reweight_scenarios_endpoint(self, client):
        """Test reweighting endpoint."""
        response = client.post("/api/automation/scheduler/reweight-scenarios")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_scheduler_status_endpoint(self, client):
        """Test scheduler status endpoint."""
        response = client.get("/api/automation/scheduler/status")

        assert response.status_code == 200
        data = response.json()
        assert "last_reweight" in data
        assert "reweight_count" in data

    def test_reweighting_history_endpoint(self, client):
        """Test reweighting history endpoint."""
        response = client.get("/api/automation/scheduler/history")

        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_learning_pipeline_health_endpoint(self, client):
        """Test learning pipeline health endpoint."""
        response = client.get("/api/automation/health/learning-pipeline")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "components" in data
        assert "metrics" in data

    def test_health_component_check(self, client):
        """Test all components present in health check."""
        response = client.get("/api/automation/health/learning-pipeline")

        data = response.json()
        components = data["components"]

        required_components = [
            "recommendation_tracker",
            "scenario_learner",
            "cost_calibrator",
            "tracking_daemon",
            "reweighting_scheduler",
        ]

        for component in required_components:
            assert component in components


class TestLearningDashboard:
    """Test learning metrics dashboard endpoints."""

    def test_accuracy_metrics_endpoint(self, client):
        """Test accuracy metrics dashboard endpoint."""
        response = client.get("/api/automation/dashboard/accuracy-metrics")

        assert response.status_code == 200
        data = response.json()
        assert "overall_accuracy_pct" in data
        assert "total_recommendations" in data
        assert "scenario_accuracy" in data
        assert "symbol_accuracy" in data

    def test_scenario_heatmap_endpoint(self, client):
        """Test scenario heatmap dashboard endpoint."""
        response = client.get("/api/automation/dashboard/scenario-heatmap")

        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert "matrix" in data

    def test_cost_calibration_endpoint(self, client):
        """Test cost calibration dashboard endpoint."""
        response = client.get("/api/automation/dashboard/cost-calibration")

        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data
        assert "symbols_learned" in data
        assert "avg_estimation_error" in data
        assert "readiness" in data


class TestLearningAutomationIntegration:
    """Test integration between components."""

    def test_daemon_to_tracker_integration(self):
        """Test daemon records outcomes in tracker."""
        daemon = get_recommendation_tracking_daemon()
        tracker = get_recommendation_tracker()

        # Record a recommendation
        from uuid import uuid4
        rec_id = str(uuid4())
        tracker.record_recommendation(
            recommendation_id=rec_id,
            symbol="AAPL",
            recommended_allocation_pct=5.0,
            scenario="base",
            expected_return_pct=2.0,
            confidence_score=75.0,
        )

        # No outcomes yet
        assert len(tracker.outcomes) == 0

        # Run sync (with empty executions, so nothing matches)
        result = daemon.run_daily_sync([])
        assert result["matched_count"] == 0

    def test_scheduler_requires_sufficient_data(self):
        """Test scheduler respects minimum data threshold."""
        scheduler = get_scenario_auto_reweighting_scheduler()
        tracker = get_recommendation_tracker()

        # Record just 1 recommendation (below min of 15)
        from uuid import uuid4
        rec_id = str(uuid4())
        tracker.record_recommendation(
            recommendation_id=rec_id,
            symbol="AAPL",
            recommended_allocation_pct=5.0,
            scenario="base",
            expected_return_pct=2.0,
            confidence_score=75.0,
        )

        # Should not reweight
        result = scheduler.run_reweighting()
        assert result["status"] == "skipped"
