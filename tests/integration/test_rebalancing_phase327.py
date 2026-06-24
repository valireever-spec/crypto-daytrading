"""Integration tests for Phase 327: Constrained Rebalancing Engine."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from backend.analytics.rebalancing_engine import (
    RebalancingEngine,
    get_rebalancing_engine,
)
from backend.analytics.rebalancing_stress_tester import (
    RebalancingStressTester,
    get_rebalancing_stress_tester,
)


@pytest.fixture
def current_allocation():
    """Current portfolio allocation."""
    return {
        "BTCUSDT": 35.0,
        "EQ_AAPL": 40.0,
        "EQ_MSFT": 25.0,
    }


@pytest.fixture
def target_allocation():
    """Target portfolio allocation."""
    return {
        "BTCUSDT": 40.0,
        "EQ_AAPL": 35.0,
        "EQ_MSFT": 25.0,
    }


@pytest.fixture
def scenario_params():
    """Scenario parameters for stress testing."""
    return {
        "returns": {"BTCUSDT": 5.0, "EQ_AAPL": 8.0, "EQ_MSFT": 7.0},
        "volatilities": {"BTCUSDT": 20.0, "EQ_AAPL": 15.0, "EQ_MSFT": 16.0},
        "correlations": np.array([
            [1.0, 0.3, 0.3],
            [0.3, 1.0, 0.7],
            [0.3, 0.7, 1.0],
        ]),
    }


class TestRebalancingEngine:
    """Test rebalancing engine functionality."""

    @pytest.fixture
    def engine(self):
        """Create engine."""
        return RebalancingEngine(drift_threshold_pct=5.0)

    def test_initialization(self, engine):
        """Test engine initializes."""
        assert engine is not None
        assert engine.drift_threshold_pct == 5.0

    def test_analyze_drift(self, engine, current_allocation, target_allocation):
        """Test drift analysis."""
        drift = engine.analyze_drift(current_allocation, target_allocation)

        assert drift is not None
        assert "BTCUSDT" in drift.drift_per_symbol
        assert drift.total_drift_pct > 0
        assert drift.requires_rebalancing

    def test_drift_no_rebalancing(self, engine):
        """Test drift when allocations match."""
        alloc = {"A": 50.0, "B": 50.0}
        drift = engine.analyze_drift(alloc, alloc)

        assert drift.total_drift_pct == 0.0
        assert not drift.requires_rebalancing

    def test_generate_rebalancing_plan(self, engine, current_allocation, target_allocation):
        """Test generating rebalancing plan."""
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=100000,
        )

        assert plan is not None
        assert len(plan.trades) > 0
        assert plan.total_cost_pct >= 0
        assert plan.estimated_slippage_pct >= 0

    def test_break_into_tranches(self, engine, current_allocation, target_allocation):
        """Test breaking into tranches."""
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=100000,
        )

        tranches = engine.break_into_tranches(plan, max_tranche_pct=2.0)

        assert len(tranches) > 0
        assert all(t.total_cost_pct >= 0 for t in tranches)

    def test_estimate_cost_breakdown(self, engine, current_allocation, target_allocation):
        """Test cost estimation."""
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=100000,
        )

        costs = engine.estimate_cost_breakdown(plan)

        assert "execution_cost_pct" in costs
        assert "slippage_cost_pct" in costs
        assert "tax_cost_pct" in costs
        assert "total_cost_pct" in costs

    def test_validate_feasibility(self, engine, current_allocation, target_allocation):
        """Test feasibility validation."""
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=100000,
        )

        is_feasible, issues = engine.validate_rebalancing_feasibility(plan, current_cash_pct=10.0)

        assert isinstance(is_feasible, bool)
        assert isinstance(issues, list)

    def test_record_rebalancing(self, engine, current_allocation, target_allocation):
        """Test recording rebalancing."""
        plan = engine.generate_rebalancing_plan(
            current_allocation=current_allocation,
            target_allocation=target_allocation,
            portfolio_value_eur=100000,
        )

        engine.record_rebalancing(plan)
        history = engine.get_rebalancing_history()

        assert len(history) >= 1

    def test_global_instance(self):
        """Test global singleton."""
        eng1 = get_rebalancing_engine()
        eng2 = get_rebalancing_engine()
        assert eng1 is eng2


class TestRebalancingStressTester:
    """Test stress testing functionality."""

    @pytest.fixture
    def tester(self):
        """Create stress tester."""
        return RebalancingStressTester()

    def test_initialization(self, tester):
        """Test tester initializes."""
        assert tester is not None
        assert len(tester.test_history) == 0

    def test_stress_test_allocation(self, tester, target_allocation, scenario_params):
        """Test stress testing allocation."""
        result = tester.stress_test_allocation(
            target_allocation=target_allocation,
            scenario_returns=scenario_params["returns"],
            scenario_volatilities=scenario_params["volatilities"],
            scenario_correlations=scenario_params["correlations"],
            scenario_name="Test Scenario",
        )

        assert result is not None
        assert result.scenario_name == "Test Scenario"
        assert result.portfolio_volatility_pct > 0
        assert isinstance(result.worst_case_drawdown_pct, float)

    def test_compare_allocations(self, tester):
        """Test comparing multiple allocations."""
        allocations = [
            {"A": 50.0, "B": 50.0},
            {"A": 40.0, "B": 60.0},
            {"A": 30.0, "B": 70.0},
        ]

        scenario_returns = {"A": 5.0, "B": 10.0}
        scenario_volatilities = {"A": 15.0, "B": 12.0}
        correlations = np.array([[1.0, 0.5], [0.5, 1.0]])

        results = tester.compare_allocations_under_stress(
            allocations=allocations,
            allocation_names=["High A", "Balanced", "Low A"],
            scenario_returns=scenario_returns,
            scenario_volatilities=scenario_volatilities,
            scenario_correlations=correlations,
        )

        assert len(results) == 3
        assert all(r.scenario_name for r in results)

    def test_get_robust_allocation(self, tester, scenario_params):
        """Test finding robust allocation."""
        allocations = [
            {"A": 60.0, "B": 40.0},
            {"A": 50.0, "B": 50.0},
            {"A": 40.0, "B": 60.0},
        ]

        scenarios = [
            {
                "name": "Scenario 1",
                "returns": {"A": 10.0, "B": 5.0},
                "volatilities": {"A": 15.0, "B": 10.0},
                "correlations": np.eye(2),
            },
        ]

        best_alloc, results = tester.get_robust_allocation(allocations, scenarios)

        assert best_alloc is not None
        assert isinstance(best_alloc, dict)

    def test_get_test_summary(self, tester, target_allocation, scenario_params):
        """Test getting summary."""
        # Run a test
        tester.stress_test_allocation(
            target_allocation=target_allocation,
            scenario_returns=scenario_params["returns"],
            scenario_volatilities=scenario_params["volatilities"],
            scenario_correlations=scenario_params["correlations"],
        )

        summary = tester.get_test_summary()

        assert "total_tests" in summary
        assert "recent_tests" in summary
        assert "avg_worst_drawdown_pct" in summary
        assert summary["total_tests"] >= 1

    def test_global_instance(self):
        """Test global singleton."""
        test1 = get_rebalancing_stress_tester()
        test2 = get_rebalancing_stress_tester()
        assert test1 is test2


class TestRebalancingIntegration:
    """Integration tests for rebalancing."""

    def test_full_rebalancing_workflow(self):
        """Test complete rebalancing workflow."""
        engine = RebalancingEngine()

        current = {"A": 40.0, "B": 60.0}
        target = {"A": 50.0, "B": 50.0}

        # 1. Analyze drift
        drift = engine.analyze_drift(current, target)
        assert drift.requires_rebalancing

        # 2. Generate plan
        plan = engine.generate_rebalancing_plan(current, target, 100000)
        assert plan.trades

        # 3. Break into tranches
        tranches = engine.break_into_tranches(plan)
        assert tranches

        # 4. Validate feasibility
        is_feasible, issues = engine.validate_rebalancing_feasibility(plan)
        assert isinstance(is_feasible, bool)

    def test_stress_and_rebalance(self):
        """Test stress testing then rebalancing."""
        tester = RebalancingStressTester()
        engine = RebalancingEngine()

        allocation = {"A": 60.0, "B": 40.0}

        # 1. Stress test
        result = tester.stress_test_allocation(
            target_allocation=allocation,
            scenario_returns={"A": 5.0, "B": 10.0},
            scenario_volatilities={"A": 20.0, "B": 15.0},
            scenario_correlations=np.array([[1.0, 0.5], [0.5, 1.0]]),
        )

        # 2. If needs adjustment, generate new plan
        if result.recommendation != "ACCEPTABLE":
            new_allocation = {"A": 50.0, "B": 50.0}
            plan = engine.generate_rebalancing_plan(
                allocation, new_allocation, 100000
            )
            assert plan is not None

    def test_multiple_rebalancings(self):
        """Test multiple consecutive rebalancings."""
        engine = RebalancingEngine()

        allocations = [
            ({"A": 30.0, "B": 70.0}, {"A": 50.0, "B": 50.0}),
            ({"A": 50.0, "B": 50.0}, {"A": 60.0, "B": 40.0}),
            ({"A": 60.0, "B": 40.0}, {"A": 50.0, "B": 50.0}),
        ]

        for current, target in allocations:
            plan = engine.generate_rebalancing_plan(current, target, 100000)
            engine.record_rebalancing(plan)

        history = engine.get_rebalancing_history()
        assert len(history) == 3
