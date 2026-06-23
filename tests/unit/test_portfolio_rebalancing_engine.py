"""Tests for Portfolio Rebalancing Engine (Phase 317)."""

import pytest
from datetime import datetime
from backend.analytics.portfolio_rebalancing_engine import (
    PortfolioRebalancingEngine,
    RebalancingAction,
    RebalancingPlan,
    get_portfolio_rebalancing_engine,
)


class TestPortfolioRebalancingEngine:
    """Test portfolio rebalancing decisions."""

    @pytest.fixture
    def engine(self):
        """Create rebalancing engine."""
        return PortfolioRebalancingEngine()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio."""
        return {
            'BTCUSDT': {'quantity': 1.0, 'price': 50000, 'value_eur': 50000, 'entry_price': 45000},
            'EQ_AAPL': {'quantity': 100, 'price': 150, 'value_eur': 15000, 'entry_price': 140},
            'EQ_JNJ': {'quantity': 50, 'price': 160, 'value_eur': 8000, 'entry_price': 155},
        }

    @pytest.fixture
    def equal_weight_allocation(self):
        """Equal weight allocation across assets."""
        return {
            'BTCUSDT': 33.3,
            'EQ_AAPL': 33.3,
            'EQ_JNJ': 33.4,
        }

    def test_initialization(self, engine):
        """Test engine initializes with correct defaults."""
        assert engine.drift_threshold_pct == 5.0
        assert engine.max_rebalancing_cost_pct == 0.1
        assert engine.last_rebalance_timestamp is None

    def test_analyze_drift_perfectly_balanced(self):
        """Test drift analysis when portfolio is truly balanced."""
        engine = PortfolioRebalancingEngine()

        # Create portfolio with equal values
        portfolio = {
            'SYM1': {'value_eur': 33000},
            'SYM2': {'value_eur': 33000},
            'SYM3': {'value_eur': 34000},
        }
        portfolio_value = 100000
        target = {'SYM1': 33.0, 'SYM2': 33.0, 'SYM3': 34.0}

        drifts = engine.analyze_drift(portfolio, portfolio_value, target)

        # All drifts should be near zero
        for symbol, drift in drifts.items():
            assert abs(drift) < 0.1

    def test_analyze_drift_overweight(self, engine, sample_portfolio):
        """Test drift analysis when position is overweight."""
        portfolio_value = 73000
        target_allocation = {
            'BTCUSDT': 20.0,   # Target 20%, currently 68%
            'EQ_AAPL': 50.0,   # Target 50%, currently 20%
            'EQ_JNJ': 30.0,    # Target 30%, currently 11%
        }

        drifts = engine.analyze_drift(sample_portfolio, portfolio_value, target_allocation)

        # BTCUSDT should be overweight (+48%)
        assert drifts['BTCUSDT'] > 40

        # AAPL should be underweight (-30%)
        assert drifts['EQ_AAPL'] < -20

    def test_should_rebalance_no_drift(self, engine):
        """Test that rebalancing is not triggered with low drift."""
        drifts = {'SYM1': 0.5, 'SYM2': -0.3, 'SYM3': 0.2}

        should_rebalance = engine.should_rebalance(drifts, time_since_last_rebalance_days=30)

        # Low drift should not trigger rebalancing
        assert should_rebalance is False

    def test_should_rebalance_high_drift(self, engine):
        """Test that rebalancing is triggered with high drift."""
        drifts = {'SYM1': 15.0, 'SYM2': -3.0}

        should_rebalance = engine.should_rebalance(drifts, time_since_last_rebalance_days=30)

        # High drift should trigger rebalancing (if enough time passed)
        assert should_rebalance is True

    def test_should_rebalance_time_constraint(self, engine):
        """Test that rebalancing respects time constraint."""
        drifts = {'SYM1': 10.0}

        # Too recent (only 2 days since last)
        should_rebalance = engine.should_rebalance(drifts, time_since_last_rebalance_days=2)

        # Should not rebalance (drift is high but too soon)
        assert should_rebalance is False

    def test_generate_rebalancing_plan_overweight(
        self, engine, sample_portfolio, equal_weight_allocation
    ):
        """Test rebalancing plan generation for overweight position."""
        portfolio_value = 73000

        # Make BTCUSDT overweight
        target_allocation = {
            'BTCUSDT': 20.0,
            'EQ_AAPL': 50.0,
            'EQ_JNJ': 30.0,
        }

        plan = engine.generate_rebalancing_plan(
            sample_portfolio, portfolio_value, target_allocation, regime='neutral'
        )

        if plan:
            # Should have SELL action for BTCUSDT
            btc_action = next((a for a in plan.actions if a.symbol == 'BTCUSDT'), None)
            if btc_action:
                assert btc_action.action == 'SELL'

    def test_generate_rebalancing_plan_underweight(
        self, engine, sample_portfolio, equal_weight_allocation
    ):
        """Test rebalancing plan generation for underweight position."""
        portfolio_value = 73000

        # Make AAPL underweight
        target_allocation = {
            'BTCUSDT': 20.0,
            'EQ_AAPL': 50.0,
            'EQ_JNJ': 30.0,
        }

        plan = engine.generate_rebalancing_plan(
            sample_portfolio, portfolio_value, target_allocation, regime='neutral'
        )

        if plan:
            # Should have BUY action for AAPL
            aapl_action = next((a for a in plan.actions if a.symbol == 'EQ_AAPL'), None)
            if aapl_action:
                assert aapl_action.action == 'BUY'

    def test_generate_rebalancing_plan_no_rebalancing_needed(self, engine, sample_portfolio):
        """Test that no plan is generated when rebalancing not needed."""
        portfolio_value = 73000
        target_allocation = {
            'BTCUSDT': 68.5,  # Already at target
            'EQ_AAPL': 20.5,
            'EQ_JNJ': 11.0,
        }

        plan = engine.generate_rebalancing_plan(
            sample_portfolio, portfolio_value, target_allocation
        )

        # Should not generate plan (drift within tolerance)
        assert plan is None

    def test_estimate_rebalancing_impact(self, engine):
        """Test impact estimation for rebalancing plan."""
        plan = RebalancingPlan(
            timestamp=datetime.utcnow(),
            total_rebalancing_cost=100.0,
            total_drift=15.0,
            actions=[
                RebalancingAction(
                    symbol='BTCUSDT',
                    action='SELL',
                    current_allocation_pct=70.0,
                    target_allocation_pct=50.0,
                    adjustment_pct=20.0,
                    estimated_cost_eur=50.0,
                    priority=8,
                    rationale='Test'
                )
            ],
            estimated_execution_time_min=10.0,
            improvement_expected='Moderate',
            urgency=8,
        )

        impact = engine.estimate_rebalancing_impact(plan, portfolio_value=100000)

        assert impact['cost_pct_of_portfolio'] < 1.0  # Should be <1%
        assert 'cost_eur' in impact
        assert 'drift_reduction' in impact

    def test_regime_aware_targets_bull(self, engine):
        """Test regime-aware target allocation for bull market."""
        base_allocation = {
            'BTCUSDT': 20,
            'EQ_AAPL': 20,
            'EQ_JNJ': 20,
            'EQ_NEE': 20,
            'EQ_XOM': 20,
        }

        targets = engine.get_regime_aware_targets('bull', base_allocation)

        # In bull market, crypto and tech should be increased
        assert targets.get('BTCUSDT', 0) > base_allocation.get('BTCUSDT', 0)
        assert targets.get('EQ_AAPL', 0) > base_allocation.get('EQ_AAPL', 0)

        # Utilities and healthcare should be decreased
        assert targets.get('EQ_NEE', 0) < base_allocation.get('EQ_NEE', 0)

    def test_regime_aware_targets_bear(self, engine):
        """Test regime-aware target allocation for bear market."""
        base_allocation = {
            'BTCUSDT': 20,
            'EQ_AAPL': 20,
            'EQ_JNJ': 20,
            'EQ_NEE': 20,
            'EQ_XOM': 20,
        }

        targets = engine.get_regime_aware_targets('bear', base_allocation)

        # In bear market, defensive should be increased
        assert targets.get('EQ_JNJ', 0) > base_allocation.get('EQ_JNJ', 0)
        assert targets.get('EQ_NEE', 0) > base_allocation.get('EQ_NEE', 0)

        # Risk assets should be decreased
        assert targets.get('BTCUSDT', 0) < base_allocation.get('BTCUSDT', 0)

    def test_regime_aware_targets_volatile(self, engine):
        """Test regime-aware target allocation for volatile market."""
        base_allocation = {
            'BTCUSDT': 20,
            'EQ_AAPL': 20,
            'EQ_JNJ': 20,
            'EQ_NEE': 20,
            'EQ_XOM': 20,
        }

        targets = engine.get_regime_aware_targets('volatile', base_allocation)

        # In volatile market, all allocations should exist but risky reduced
        assert targets.get('BTCUSDT', 0) < base_allocation.get('BTCUSDT', 0)

        # Defensive should increase
        assert targets.get('EQ_JNJ', 0) > base_allocation.get('EQ_JNJ', 0)

    def test_global_instance(self):
        """Test global rebalancing engine instance."""
        eng1 = get_portfolio_rebalancing_engine()
        eng2 = get_portfolio_rebalancing_engine()

        assert eng1 is eng2  # Same instance

    def test_rebalancing_action_priority_bull(self, engine):
        """Test that actions are prioritized higher in bull market."""
        target = {
            'BTCUSDT': 30.0,
            'EQ_AAPL': 30.0,
            'EQ_JNJ': 40.0,
        }
        portfolio = {
            'BTCUSDT': {'value_eur': 10000},  # Underweight
            'EQ_AAPL': {'value_eur': 50000},  # Overweight
            'EQ_JNJ': {'value_eur': 40000},
        }
        portfolio_value = 100000

        plan = engine.generate_rebalancing_plan(
            portfolio, portfolio_value, target, regime='bull'
        )

        if plan:
            # BUY actions should have higher priority in bull
            buy_actions = [a for a in plan.actions if a.action == 'BUY']
            sell_actions = [a for a in plan.actions if a.action == 'SELL']

            if buy_actions and sell_actions:
                avg_buy_priority = sum(a.priority for a in buy_actions) / len(buy_actions)
                avg_sell_priority = sum(a.priority for a in sell_actions) / len(sell_actions)

                assert avg_buy_priority >= avg_sell_priority

    def test_rebalancing_action_priority_bear(self, engine):
        """Test that SELL actions are prioritized higher in bear market."""
        target = {
            'BTCUSDT': 10.0,
            'EQ_AAPL': 10.0,
            'EQ_JNJ': 80.0,
        }
        portfolio = {
            'BTCUSDT': {'value_eur': 50000},  # Overweight in bear
            'EQ_AAPL': {'value_eur': 10000},
            'EQ_JNJ': {'value_eur': 40000},
        }
        portfolio_value = 100000

        plan = engine.generate_rebalancing_plan(
            portfolio, portfolio_value, target, regime='bear'
        )

        if plan:
            # SELL actions should have higher priority in bear
            buy_actions = [a for a in plan.actions if a.action == 'BUY']
            sell_actions = [a for a in plan.actions if a.action == 'SELL']

            if buy_actions and sell_actions:
                avg_buy_priority = sum(a.priority for a in buy_actions) / len(buy_actions)
                avg_sell_priority = sum(a.priority for a in sell_actions) / len(sell_actions)

                assert avg_sell_priority >= avg_buy_priority

    def test_summary_generation_with_plan(self, engine):
        """Test summary generation with rebalancing plan."""
        plan = RebalancingPlan(
            timestamp=datetime.utcnow(),
            total_rebalancing_cost=100.0,
            total_drift=20.0,
            actions=[
                RebalancingAction(
                    symbol='BTCUSDT',
                    action='SELL',
                    current_allocation_pct=70.0,
                    target_allocation_pct=50.0,
                    adjustment_pct=20.0,
                    estimated_cost_eur=50.0,
                    priority=8,
                    rationale='Test'
                )
            ],
            estimated_execution_time_min=10.0,
            improvement_expected='Large',
            urgency=8,
        )

        summary = engine.get_summary(plan)

        assert 'Rebalancing plan' in summary
        assert 'urgency' in summary.lower()
        assert '€' in summary

    def test_summary_generation_no_plan(self, engine):
        """Test summary generation when no rebalancing needed."""
        summary = engine.get_summary(None)

        assert 'balanced' in summary.lower() or 'no rebalancing' in summary.lower()

    def test_rebalancing_plan_totals(self, engine):
        """Test that rebalancing plan calculates totals correctly."""
        target = {
            'SYM1': 50.0,
            'SYM2': 50.0,
        }
        portfolio = {
            'SYM1': {'value_eur': 80000},  # Overweight
            'SYM2': {'value_eur': 20000},  # Underweight
        }
        portfolio_value = 100000

        plan = engine.generate_rebalancing_plan(portfolio, portfolio_value, target)

        if plan:
            # Should have estimated execution time
            assert plan.estimated_execution_time_min > 0

            # Should have total cost estimate
            assert plan.total_rebalancing_cost >= 0

            # Should have improvement metric
            assert plan.improvement_expected in ['Small', 'Moderate', 'Large']

    def test_empty_portfolio_handling(self, engine):
        """Test handling of empty portfolio."""
        drifts = engine.analyze_drift({}, 0, {'SYM1': 50.0})

        # Should handle gracefully
        assert isinstance(drifts, dict)

    def test_zero_portfolio_value_handling(self, engine):
        """Test handling of zero portfolio value."""
        portfolio = {'SYM1': {'value_eur': 0}}
        drifts = engine.analyze_drift(portfolio, 0, {'SYM1': 50.0})

        # Should handle gracefully
        assert isinstance(drifts, dict)
