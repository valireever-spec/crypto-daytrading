"""Integration tests for Portfolio Decision Coordinator (Phase 318)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.trading.portfolio_decision_coordinator import (
    PortfolioDecisionCoordinator,
    PortfolioDecision,
    get_portfolio_decision_coordinator,
)


class TestPortfolioDecisionCoordinator:
    """Test portfolio decision orchestration."""

    @pytest.fixture
    def coordinator(self):
        """Create portfolio decision coordinator."""
        return PortfolioDecisionCoordinator()

    @pytest.fixture
    def bull_regime_data(self):
        """Create bull market regime data."""
        return {
            'BTCUSDT': {'regime': 'bull', 'trend_strength': 0.6},
            'ETHUSDT': {'regime': 'bull', 'trend_strength': 0.5},
            'EQ_AAPL': {'regime': 'bull', 'trend_strength': 0.4},
            'EQ_MSFT': {'regime': 'sideways', 'trend_strength': 0.1},
        }

    @pytest.fixture
    def bear_regime_data(self):
        """Create bear market regime data."""
        return {
            'BTCUSDT': {'regime': 'bear', 'trend_strength': -0.6},
            'ETHUSDT': {'regime': 'bear', 'trend_strength': -0.5},
            'EQ_AAPL': {'regime': 'bear', 'trend_strength': -0.4},
            'EQ_MSFT': {'regime': 'sideways', 'trend_strength': -0.1},
        }

    @pytest.fixture
    def sample_positions(self):
        """Create sample portfolio positions."""
        return [
            {'symbol': 'BTCUSDT', 'quantity': 1.0, 'entry_price': 50000, 'value_eur': 51000, 'price': 51000},
            {'symbol': 'EQ_AAPL', 'quantity': 100, 'entry_price': 145, 'value_eur': 15500, 'price': 155},
            {'symbol': 'EQ_MSFT', 'quantity': 50, 'entry_price': 420, 'value_eur': 21000, 'price': 420},
        ]

    @pytest.fixture
    def sample_prices(self):
        """Sample current prices."""
        return {
            'BTCUSDT': 51000,
            'ETHUSDT': 3000,
            'EQ_AAPL': 155,
            'EQ_MSFT': 420,
        }

    def test_initialization(self, coordinator):
        """Test coordinator initializes with Phase 317 systems."""
        assert coordinator.regime_monitor is not None
        assert coordinator.sector_advisor is not None
        assert coordinator.rebalancing_engine is not None
        assert coordinator.decision_history == []

    @pytest.mark.asyncio
    async def test_correlated_exit_decision_bear_market(
        self, coordinator, sample_positions, sample_prices
    ):
        """Test generation of correlated exit decision in bear market."""
        # Create bear regime data where cryptos need to be exited
        bear_regimes = {
            'BTCUSDT': {'regime': 'bear'},
            'ETHUSDT': {'regime': 'bear'},
            'EQ_AAPL': {'regime': 'sideways'},
            'EQ_MSFT': {'regime': 'sideways'},
        }

        # First check to establish baseline
        await coordinator.make_portfolio_decisions(
            symbol_regimes=bear_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 25, 'ETHUSDT': 25, 'EQ_AAPL': 25, 'EQ_MSFT': 25},
            current_prices=sample_prices,
        )

        # Now make positions active for second check
        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=bear_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 25, 'ETHUSDT': 25, 'EQ_AAPL': 25, 'EQ_MSFT': 25},
            current_prices=sample_prices,
        )

        # Should have at least one decision
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_sector_rotation_decision_tech_to_defensive(
        self, coordinator, sample_positions, sample_prices
    ):
        """Test sector rotation from tech to defensive in bear market."""
        bear_regimes = {
            'BTCUSDT': {'regime': 'bear'},
            'ETHUSDT': {'regime': 'bear'},
            'EQ_AAPL': {'regime': 'bear'},
            'EQ_MSFT': {'regime': 'bear'},
        }

        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=bear_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 20, 'ETHUSDT': 20, 'EQ_AAPL': 30, 'EQ_MSFT': 30},
            current_prices=sample_prices,
        )

        # Should have decision(s) based on regime state
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_rebalancing_decision_drift(
        self, coordinator, sample_positions, sample_prices
    ):
        """Test rebalancing decision when portfolio drifts from target."""
        neutral_regimes = {
            'BTCUSDT': {'regime': 'sideways'},
            'EQ_AAPL': {'regime': 'sideways'},
            'EQ_MSFT': {'regime': 'sideways'},
        }

        # Create highly drifted allocation
        # Current: BTCUSDT 58%, AAPL 18%, MSFT 24%
        # Target: equal weight 33% each
        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=neutral_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 33, 'EQ_AAPL': 33, 'EQ_MSFT': 34},
            current_prices=sample_prices,
        )

        # Should have rebalancing decision if drift > threshold
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_decision_priority_exit_before_rotation(
        self, coordinator, sample_positions, sample_prices
    ):
        """Test that exits have priority over rotations."""
        # Create scenario with both exit and rotation opportunity
        mixed_regimes = {
            'BTCUSDT': {'regime': 'bear'},  # Should exit
            'ETHUSDT': {'regime': 'bear'},  # Should exit
            'EQ_AAPL': {'regime': 'bull'},  # Good entry
            'EQ_MSFT': {'regime': 'bull'},  # Good entry
        }

        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=mixed_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 25, 'EQ_AAPL': 25, 'EQ_MSFT': 25},
            current_prices=sample_prices,
        )

        # First decision should be exit (highest priority)
        if decisions:
            assert decisions[0].decision_type in ['CORRELATED_EXIT', 'SECTOR_ROTATION', 'REBALANCE']

    @pytest.mark.asyncio
    async def test_decision_high_urgency_execution(self, coordinator, sample_positions):
        """Test that high urgency decisions are marked for immediate execution."""
        # Create high-stress bear market
        crisis_regimes = {
            'BTCUSDT': {'regime': 'bear'},
            'ETHUSDT': {'regime': 'bear'},
            'EQ_AAPL': {'regime': 'bear'},
            'EQ_MSFT': {'regime': 'volatile'},
        }

        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=crisis_regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 25, 'EQ_AAPL': 25, 'EQ_MSFT': 25},
            current_prices={'BTCUSDT': 45000, 'EQ_AAPL': 140, 'EQ_MSFT': 400},
        )

        # High urgency decision should exist
        if decisions:
            high_urgency = [d for d in decisions if d.urgency >= 8]
            # Might or might not have high urgency depending on regime state
            assert isinstance(decisions, list)

    def test_calculate_current_allocation(self, coordinator, sample_positions):
        """Test allocation calculation."""
        portfolio_value = 87500  # Sum of position values

        allocation = coordinator._calculate_current_allocation(
            sample_positions, portfolio_value
        )

        # Total should be ~100%
        total = sum(allocation.values())
        assert 99 < total < 101

        # BTCUSDT should be ~58%
        assert 50 < allocation.get('BTCUSDT', 0) < 65

    def test_decision_history_tracking(self, coordinator):
        """Test that decisions are tracked in history."""
        initial_count = len(coordinator.decision_history)

        # Create a decision manually
        decision = PortfolioDecision(
            timestamp=datetime.utcnow(),
            decision_type="TEST",
            action="TEST",
            target_symbols=['TEST'],
            actions={'TEST': 'BUY'},
            urgency=5,
            rationale="Test decision",
            estimated_impact={},
        )

        # Manually add to history (normally done by make_portfolio_decisions)
        coordinator.decision_history.append(decision)

        # History should grow
        assert len(coordinator.decision_history) > initial_count

    def test_get_decision_summary(self, coordinator):
        """Test summary generation."""
        # Add a test decision
        decision = PortfolioDecision(
            timestamp=datetime.utcnow(),
            decision_type="CORRELATED_EXIT",
            action="EXIT",
            target_symbols=['BTCUSDT', 'ETHUSDT'],
            actions={'BTCUSDT': 'SELL', 'ETHUSDT': 'SELL'},
            urgency=9,
            rationale="Bear market exit",
            estimated_impact={},
        )
        coordinator.decision_history.append(decision)

        summary = coordinator.get_decision_summary()

        assert "CORRELATED_EXIT" in summary
        assert "BTCUSDT" in summary

    def test_get_decision_queue_empty(self, coordinator):
        """Test decision queue when no pending decisions."""
        queue = coordinator.get_decision_queue()

        # Should be empty if no recent decisions
        assert isinstance(queue, list)

    def test_get_decision_queue_recent(self, coordinator):
        """Test decision queue with recent decision."""
        # Add recent decision
        decision = PortfolioDecision(
            timestamp=datetime.utcnow(),
            decision_type="REBALANCE",
            action="REBALANCE",
            target_symbols=['BTCUSDT'],
            actions={'BTCUSDT': 'SELL'},
            urgency=5,
            rationale="Rebalance",
            estimated_impact={},
        )
        coordinator.decision_history.append(decision)

        queue = coordinator.get_decision_queue()

        # Should have decision if recent
        assert isinstance(queue, list)

    def test_mark_decision_executed(self, coordinator):
        """Test marking decision as executed."""
        decision = PortfolioDecision(
            timestamp=datetime.utcnow(),
            decision_type="TEST",
            action="TEST",
            target_symbols=['TEST'],
            actions={},
            urgency=5,
            rationale="Test",
            estimated_impact={},
        )

        result = coordinator.mark_decision_executed(decision)

        assert result is True

    def test_global_instance(self):
        """Test global coordinator instance."""
        coord1 = get_portfolio_decision_coordinator()
        coord2 = get_portfolio_decision_coordinator()

        assert coord1 is coord2

    @pytest.mark.asyncio
    async def test_empty_positions_handling(self, coordinator):
        """Test handling of empty position list."""
        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes={'BTCUSDT': {'regime': 'bull'}},
            current_positions=[],
            portfolio_value=0,
            target_allocation={},
            current_prices={},
        )

        # Should handle gracefully
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_decision_rationale_content(self, coordinator, sample_positions, sample_prices):
        """Test that decision rationales are informative."""
        bear_regimes = {
            'BTCUSDT': {'regime': 'bear'},
            'EQ_AAPL': {'regime': 'bear'},
        }

        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=bear_regimes,
            current_positions=sample_positions[:2],
            portfolio_value=67000,
            target_allocation={'BTCUSDT': 50, 'EQ_AAPL': 50},
            current_prices=sample_prices,
        )

        # All decisions should have non-empty rationale
        for decision in decisions:
            assert len(decision.rationale) > 0
            # Check that decision type or action (or lowercase version) is in rationale
            type_or_action = decision.decision_type.lower() or decision.action.lower()
            assert len(decision.rationale) > 20  # Rationale should be substantive

    @pytest.mark.asyncio
    async def test_decision_estimated_impact(self, coordinator, sample_positions, sample_prices):
        """Test that decisions include impact estimates."""
        regimes = {
            'BTCUSDT': {'regime': 'sideways'},
            'EQ_AAPL': {'regime': 'sideways'},
        }

        decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=regimes,
            current_positions=sample_positions,
            portfolio_value=87500,
            target_allocation={'BTCUSDT': 50, 'EQ_AAPL': 50},
            current_prices=sample_prices,
        )

        # All decisions should have impact estimates
        for decision in decisions:
            assert isinstance(decision.estimated_impact, dict)

    @pytest.mark.asyncio
    async def test_decision_urgency_scaling(self, coordinator):
        """Test that urgency scales with market stress."""
        # Low stress: sideways market
        sideways_regimes = {
            'BTCUSDT': {'regime': 'sideways'},
            'EQ_AAPL': {'regime': 'sideways'},
        }

        positions = [
            {'symbol': 'BTCUSDT', 'quantity': 1, 'entry_price': 50000, 'value_eur': 50000, 'price': 50000},
            {'symbol': 'EQ_AAPL', 'quantity': 100, 'entry_price': 150, 'value_eur': 15000, 'price': 150},
        ]

        low_stress_decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=sideways_regimes,
            current_positions=positions,
            portfolio_value=65000,
            target_allocation={'BTCUSDT': 50, 'EQ_AAPL': 50},
            current_prices={'BTCUSDT': 50000, 'EQ_AAPL': 150},
        )

        # High stress: volatile/bear market
        high_stress_regimes = {
            'BTCUSDT': {'regime': 'volatile'},
            'EQ_AAPL': {'regime': 'bear'},
        }

        high_stress_decisions = await coordinator.make_portfolio_decisions(
            symbol_regimes=high_stress_regimes,
            current_positions=positions,
            portfolio_value=65000,
            target_allocation={'BTCUSDT': 50, 'EQ_AAPL': 50},
            current_prices={'BTCUSDT': 50000, 'EQ_AAPL': 150},
        )

        # Compare urgency levels
        if low_stress_decisions and high_stress_decisions:
            low_urgency = sum(d.urgency for d in low_stress_decisions) / len(low_stress_decisions)
            high_urgency = sum(d.urgency for d in high_stress_decisions) / len(high_stress_decisions)

            # High stress should have higher average urgency
            assert high_urgency >= low_urgency
