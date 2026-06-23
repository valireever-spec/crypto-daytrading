"""Tests for portfolio risk orchestration (Phase 3 Week 3)."""

import pytest
from backend.execution.portfolio_orchestrator import (
    PortfolioOrchestrator, PortfolioRiskMetrics, PortfolioAction,
    init_portfolio_orchestrator, get_portfolio_orchestrator
)
from backend.exchange.paper_trading import init_paper_trading
from backend.analytics.regime_detector import init_regime_detector


@pytest.fixture
def orchestrator():
    """Create portfolio orchestrator for tests."""
    init_paper_trading(starting_capital=100000)
    init_regime_detector()
    return PortfolioOrchestrator(
        max_positions=5,
        max_position_pct=0.20,
        max_sector_pct=0.40,
    )


class TestPortfolioOrchestrator:
    """Test PortfolioOrchestrator class."""

    def test_init(self, orchestrator):
        """Initialize orchestrator."""
        assert orchestrator.max_positions == 5
        assert orchestrator.max_position_pct == 0.20
        assert orchestrator.max_sector_pct == 0.40

    def test_get_portfolio_metrics_no_positions(self, orchestrator):
        """Get metrics with no open positions."""
        metrics = orchestrator.get_portfolio_metrics({})

        assert metrics.total_positions == 0
        assert metrics.capital_utilization_pct == 0.0
        assert metrics.status == "HEALTHY"

    def test_get_portfolio_metrics_healthy(self, orchestrator):
        """Get metrics for healthy portfolio."""
        prices = {"BTC": 50000, "ETH": 2000}

        # Would need positions to be non-zero, but with no positions:
        metrics = orchestrator.get_portfolio_metrics(prices)

        assert isinstance(metrics, PortfolioRiskMetrics)
        assert metrics.total_capital > 0

    def test_evaluate_new_entry_valid(self, orchestrator):
        """Evaluate valid new entry."""
        result = orchestrator.evaluate_new_entry(
            symbol="BTCUSDT",
            quantity=0.1,
            current_price=50000,  # 5,000 = 5% of capital
            regime="BULL",
        )

        assert result["approved"] is True
        assert result["symbol"] == "BTCUSDT"

    def test_evaluate_new_entry_too_large(self, orchestrator):
        """Reject entry that's too large."""
        result = orchestrator.evaluate_new_entry(
            symbol="BTCUSDT",
            quantity=1.0,
            current_price=50000,  # 50,000 = 50% of capital (exceeds 20% limit)
            regime="BULL",
        )

        assert result["approved"] is False
        assert "exceeds limit" in result["reason"]

    def test_evaluate_new_entry_insufficient_cash(self, orchestrator):
        """Reject entry with insufficient cash."""
        result = orchestrator.evaluate_new_entry(
            symbol="BTCUSDT",
            quantity=10.0,
            current_price=50000,  # 500,000 = way more than available
            regime="BULL",
        )

        assert result["approved"] is False
        assert "Insufficient cash" in result["reason"]

    def test_check_portfolio_health_healthy(self, orchestrator):
        """Portfolio health check when healthy."""
        actions = orchestrator.check_portfolio_health({})

        assert isinstance(actions, list)
        # No positions, should be healthy
        assert len(actions) == 0 or all(a.urgency != "CRITICAL" for a in actions)

    def test_get_recommended_rebalance_no_positions(self, orchestrator):
        """Rebalance recommendation with no positions."""
        result = orchestrator.get_recommended_rebalance({})

        assert "error" in result or len(result.get("recommendations", {})) == 0

    def test_calculate_risk_score_low_risk(self, orchestrator):
        """Risk score calculation for low-risk portfolio."""
        score = orchestrator._calculate_risk_score(
            capital_utilization=30.0,
            position_count=2,
            max_position_pct=10.0,
            pnl_pct=2.0,
        )

        assert 0 <= score <= 100
        assert score < 20  # Should be low risk

    def test_calculate_risk_score_high_risk(self, orchestrator):
        """Risk score calculation for high-risk portfolio."""
        score = orchestrator._calculate_risk_score(
            capital_utilization=95.0,
            position_count=1,
            max_position_pct=95.0,
            pnl_pct=-10.0,
        )

        assert score > 60  # Should be high risk

    def test_calculate_risk_score_critical(self, orchestrator):
        """Risk score calculation for critical portfolio."""
        score = orchestrator._calculate_risk_score(
            capital_utilization=99.0,
            position_count=1,
            max_position_pct=99.0,
            pnl_pct=-15.0,
        )

        assert score >= 80  # Should be critical


class TestPortfolioRiskMetrics:
    """Test PortfolioRiskMetrics dataclass."""

    def test_metrics_creation(self):
        """Create portfolio risk metrics."""
        metrics = PortfolioRiskMetrics(
            total_position_value=10000,
            total_positions=2,
            total_capital=100000,
            capital_utilization_pct=10.0,
            max_single_position_pct=6.0,
            total_pnl_usd=500,
            total_pnl_pct=0.5,
            risk_score=15.0,
            status="HEALTHY",
        )

        assert metrics.total_positions == 2
        assert metrics.status == "HEALTHY"

    def test_metrics_status_values(self):
        """Verify all status values are valid."""
        statuses = ["HEALTHY", "CAUTION", "WARNING", "CRITICAL"]

        for status in statuses:
            metrics = PortfolioRiskMetrics(
                total_position_value=0,
                total_positions=0,
                total_capital=100000,
                capital_utilization_pct=0,
                max_single_position_pct=0,
                status=status,
            )
            assert metrics.status == status


class TestPortfolioAction:
    """Test PortfolioAction dataclass."""

    def test_action_creation(self):
        """Create portfolio action."""
        action = PortfolioAction(
            action_type="REDUCE",
            symbol="BTCUSDT",
            quantity=0.1,
            reason="High utilization",
            urgency="HIGH",
        )

        assert action.action_type == "REDUCE"
        assert action.urgency == "HIGH"

    def test_action_urgency_levels(self):
        """Verify all urgency levels."""
        for urgency in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            action = PortfolioAction(
                action_type="HOLD",
                symbol="TEST",
                quantity=0,
                reason="Test",
                urgency=urgency,
            )
            assert action.urgency == urgency


class TestGlobalInstance:
    """Test global orchestrator instance."""

    def test_init_orchestrator(self):
        """Initialize global orchestrator."""
        init_paper_trading()
        orchestrator = init_portfolio_orchestrator()
        assert orchestrator is not None

    def test_get_orchestrator(self):
        """Get initialized global orchestrator."""
        init_portfolio_orchestrator()
        orchestrator = get_portfolio_orchestrator()
        assert orchestrator is not None

    def test_get_uninitialized(self):
        """Get uninitialized orchestrator returns None."""
        import backend.execution.portfolio_orchestrator as orch_module
        orch_module._portfolio_orchestrator = None
        assert get_portfolio_orchestrator() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
