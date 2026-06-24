"""Integration tests for Phase 326: Advanced Recommendation Features."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch

from backend.analytics.constraint_manager import (
    ConstraintManager,
    ConstraintSpec,
    get_constraint_manager,
)
from backend.analytics.scenario_customizer import (
    ScenarioCustomizer,
    get_scenario_customizer,
)
from backend.analytics.performance_tracker import (
    PerformanceTracker,
    get_performance_tracker,
)


@pytest.fixture
def sample_allocation():
    """Sample allocation."""
    return {
        "BTCUSDT": 40.0,
        "EQ_AAPL": 35.0,
        "EQ_MSFT": 25.0,
    }


@pytest.fixture
def sample_returns():
    """Sample historical returns."""
    dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
    return {
        "BTCUSDT": pd.Series(np.random.normal(0.1, 2.0, 252), index=dates),
        "EQ_AAPL": pd.Series(np.random.normal(0.05, 1.5, 252), index=dates),
        "EQ_MSFT": pd.Series(np.random.normal(0.08, 1.6, 252), index=dates),
    }


class TestConstraintManager:
    """Test constraint management."""

    @pytest.fixture
    def manager(self):
        """Create manager."""
        manager = ConstraintManager()
        manager.set_sector_map({
            "BTCUSDT": "Crypto",
            "EQ_AAPL": "Technology",
            "EQ_MSFT": "Technology",
        })
        manager.set_asset_class_map({
            "BTCUSDT": "crypto",
            "EQ_AAPL": "equities",
            "EQ_MSFT": "equities",
        })
        return manager

    def test_add_sector_limit(self, manager):
        """Test adding sector limit."""
        manager.add_sector_limit("Technology", 50.0)
        assert len(manager.constraints) == 1
        assert manager.constraints[0].constraint_type == "sector"

    def test_add_concentration_limit(self, manager):
        """Test adding concentration limit."""
        manager.add_concentration_limit(25.0)
        assert len(manager.constraints) == 1
        assert manager.constraints[0].constraint_type == "concentration"

    def test_add_position_bounds(self, manager):
        """Test adding position bounds."""
        manager.add_position_bounds("BTCUSDT", min_pct=10.0, max_pct=40.0)
        assert len(manager.constraints) == 2  # min + max

    def test_validate_valid_allocation(self, manager, sample_allocation):
        """Test validation of valid allocation."""
        manager.add_concentration_limit(40.0)
        is_valid, violations = manager.validate_allocation(sample_allocation)

        assert is_valid
        assert len(violations) == 0

    def test_validate_concentration_violation(self, manager):
        """Test validation catches concentration violations."""
        manager.add_concentration_limit(30.0)
        allocation = {"BTCUSDT": 50.0, "EQ_AAPL": 50.0}  # Invalid

        is_valid, violations = manager.validate_allocation(allocation)

        assert not is_valid
        assert len(violations) > 0

    def test_validate_sector_violation(self, manager):
        """Test validation catches sector violations."""
        manager.add_sector_limit("Technology", 40.0)
        allocation = {"BTCUSDT": 30.0, "EQ_AAPL": 40.0, "EQ_MSFT": 30.0}  # Tech = 70%

        is_valid, violations = manager.validate_allocation(allocation)

        assert not is_valid
        assert any("Technology" in v for v in violations)

    def test_clear_constraints(self, manager):
        """Test clearing constraints."""
        manager.add_concentration_limit(25.0)
        manager.add_sector_limit("Technology", 50.0)
        assert len(manager.constraints) == 2

        manager.clear_constraints()
        assert len(manager.constraints) == 0

    def test_global_instance(self):
        """Test global singleton."""
        mgr1 = get_constraint_manager()
        mgr2 = get_constraint_manager()
        assert mgr1 is mgr2


class TestScenarioCustomizer:
    """Test scenario customization."""

    @pytest.fixture
    def customizer(self):
        """Create customizer."""
        return ScenarioCustomizer()

    def test_list_predefined_scenarios(self, customizer):
        """Test listing predefined scenarios."""
        scenarios = customizer.list_predefined_scenarios()

        assert "bull_market" in scenarios
        assert "bear_market" in scenarios
        assert "high_volatility" in scenarios

    def test_get_predefined_scenario(self, customizer):
        """Test getting a predefined scenario."""
        scenario = customizer.get_predefined_scenario("bull_market")

        assert scenario is not None
        assert scenario.name == "Bull Market"
        assert scenario.return_multiplier == 1.5

    def test_create_custom_scenario(self, customizer):
        """Test creating custom scenario."""
        scenario = customizer.create_custom_scenario(
            name="Custom",
            return_multiplier=1.2,
            volatility_multiplier=0.9,
        )

        assert scenario.name == "Custom"
        assert scenario.return_multiplier == 1.2

    def test_apply_scenario_to_returns(self, customizer, sample_returns):
        """Test applying scenario to returns."""
        scenario = customizer.get_predefined_scenario("bear_market")
        adjusted = customizer.apply_scenario_to_returns(scenario, sample_returns)

        assert len(adjusted) == len(sample_returns)
        assert all(isinstance(v, pd.Series) for v in adjusted.values())

    def test_analyze_scenario(self, customizer, sample_returns, sample_allocation):
        """Test scenario analysis."""
        scenario = customizer.get_predefined_scenario("bull_market")
        base_metrics = {
            "expected_return_pct": 8.0,
            "volatility_pct": 12.0,
        }

        result = customizer.analyze_scenario(scenario, sample_returns, sample_allocation, base_metrics)

        assert result.scenario_name == "Bull Market"
        assert result.expected_return_pct is not None
        assert result.volatility_pct is not None
        assert result.sharpe_ratio is not None

    def test_global_instance(self):
        """Test global singleton."""
        cust1 = get_scenario_customizer()
        cust2 = get_scenario_customizer()
        assert cust1 is cust2


class TestPerformanceTracker:
    """Test performance tracking."""

    @pytest.fixture
    def tracker(self):
        """Create tracker."""
        return PerformanceTracker()

    def test_record_recommendation(self, tracker):
        """Test recording recommendation."""
        tracker.record_recommendation(
            allocation={"A": 60.0, "B": 40.0},
            expected_return_pct=10.0,
            expected_volatility_pct=12.0,
        )

        assert len(tracker.recommendations) == 1

    def test_record_outcome(self, tracker):
        """Test recording outcome."""
        tracker.record_outcome(
            actual_return_pct=8.5,
            actual_volatility_pct=11.5,
        )

        assert len(tracker.outcomes) == 1

    def test_get_performance_metrics(self, tracker):
        """Test getting performance metrics."""
        # Record recommendation and outcome at same timestamp
        tracker.record_recommendation(
            allocation={"A": 60.0, "B": 40.0},
            expected_return_pct=10.0,
            expected_volatility_pct=12.0,
            scenario_type="base",
        )

        rec_timestamp = tracker.recommendations[0].timestamp

        # Record outcome with matching timestamp
        tracker.record_outcome(
            actual_return_pct=9.5,
            actual_volatility_pct=11.5,
            recommendation_timestamp=rec_timestamp,
        )

        metrics = tracker.get_performance_metrics()

        assert metrics is not None
        assert metrics.total_recommendations >= 1
        assert isinstance(metrics.forecast_accuracy_pct, float)

    def test_scenario_performance(self, tracker):
        """Test scenario-specific performance."""
        tracker.record_recommendation(
            allocation={"A": 60.0, "B": 40.0},
            expected_return_pct=15.0,
            expected_volatility_pct=10.0,
            scenario_type="upside",
        )

        rec_timestamp = tracker.recommendations[0].timestamp

        tracker.record_outcome(
            actual_return_pct=14.0,
            actual_volatility_pct=10.5,
            recommendation_timestamp=rec_timestamp,
        )

        scenario_perf = tracker.get_scenario_performance("upside")

        assert scenario_perf is not None
        assert scenario_perf["scenario"] == "upside"
        assert scenario_perf["count"] == 1

    def test_clear_records(self, tracker):
        """Test clearing records."""
        tracker.record_recommendation(
            allocation={"A": 100.0},
            expected_return_pct=5.0,
            expected_volatility_pct=8.0,
        )
        assert len(tracker.recommendations) == 1

        tracker.clear_records()
        assert len(tracker.recommendations) == 0

    def test_get_summary(self, tracker):
        """Test getting summary."""
        tracker.record_recommendation(
            allocation={"A": 100.0},
            expected_return_pct=5.0,
            expected_volatility_pct=8.0,
        )

        summary = tracker.get_summary()

        assert "total_recommendations" in summary
        assert "total_outcomes" in summary
        assert summary["total_recommendations"] >= 1

    def test_global_instance(self):
        """Test global singleton."""
        trk1 = get_performance_tracker()
        trk2 = get_performance_tracker()
        assert trk1 is trk2


class TestConstraintIntegration:
    """Integration tests for constraints."""

    def test_multiple_constraints(self):
        """Test multiple constraint types."""
        manager = ConstraintManager()
        manager.set_sector_map({
            "A": "Tech",
            "B": "Finance",
            "C": "Energy",
        })

        manager.add_concentration_limit(35.0)
        manager.add_sector_limit("Tech", 45.0)
        manager.add_position_bounds("A", min_pct=5.0, max_pct=35.0)

        assert len(manager.constraints) == 4

    def test_scipy_constraint_generation(self):
        """Test generating scipy constraints."""
        manager = ConstraintManager()
        manager.add_concentration_limit(25.0)

        symbols = ["A", "B", "C"]
        scipy_constraints = manager.get_scipy_constraints(symbols)

        assert len(scipy_constraints) > 0


class TestScenarioIntegration:
    """Integration tests for scenarios."""

    def test_multiple_scenario_analysis(self):
        """Test analyzing multiple scenarios."""
        customizer = ScenarioCustomizer()

        scenarios = ["bull_market", "bear_market", "high_volatility"]
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        returns = {
            "A": pd.Series(np.random.normal(0.05, 1.0, 100), index=dates),
            "B": pd.Series(np.random.normal(0.08, 1.5, 100), index=dates),
        }

        allocation = {"A": 60.0, "B": 40.0}
        base_metrics = {"expected_return_pct": 6.5, "volatility_pct": 12.0}

        results = []
        for scenario_name in scenarios:
            scenario = customizer.get_predefined_scenario(scenario_name)
            result = customizer.analyze_scenario(scenario, returns, allocation, base_metrics)
            results.append(result)

        assert len(results) == 3
        assert all(r.scenario_name for r in results)
