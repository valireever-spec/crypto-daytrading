"""Tests for smart entry execution (Phase 3 Week 1)."""

import pytest
from backend.execution.smart_executor import (
    SmartExecutor, ExecutionContext, ExecutionDecision,
    init_smart_executor, get_smart_executor
)
from backend.exchange.paper_trading import init_paper_trading, get_paper_trading
from backend.analytics.regime_detector import init_regime_detector


@pytest.fixture
def executor():
    """Create smart executor for tests."""
    return SmartExecutor(max_position_pct=0.05)


@pytest.fixture(autouse=True)
def setup_trading():
    """Initialize paper trading and regime detector for tests."""
    init_paper_trading(starting_capital=100000)
    init_regime_detector()
    yield


class TestSmartExecutor:
    """Test SmartExecutor class."""

    def test_init(self, executor):
        """Initialize executor."""
        assert executor.max_position_pct == 0.05

    def test_evaluate_entry_valid(self, executor):
        """Evaluate valid entry."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=0.1,
            current_price=50000,
            min_confidence=0.6,
        )

        decision = executor.evaluate_entry(context)

        # Should pass initial validation
        assert decision.symbol == "BTCUSDT"
        assert decision.quantity == 0.1
        assert decision.price == 50000

    def test_evaluate_entry_insufficient_cash(self, executor):
        """Reject entry with insufficient cash."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=100,  # 100 BTC = 5,000,000 USD
            current_price=50000,
        )

        decision = executor.evaluate_entry(context)

        assert decision.decision == "REJECT"
        assert "Insufficient cash" in decision.reason

    def test_evaluate_entry_position_too_large(self, executor):
        """Reject entry when position exceeds size limit."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=2.0,  # 2 BTC = 100,000 USD = 100% of capital
            current_price=50000,
            max_position_pct=0.05,  # Max 5%
        )

        decision = executor.evaluate_entry(context)

        # Insufficient cash takes precedence since 100K > available
        assert decision.decision == "REJECT"

    def test_evaluate_entry_within_limits(self, executor):
        """Accept entry within position limits."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=0.025,  # 0.025 BTC = 1,250 USD = 1.25% of capital
            current_price=50000,
            max_position_pct=0.05,  # Max 5%
        )

        decision = executor.evaluate_entry(context)

        # Should pass validation
        assert decision.symbol == "BTCUSDT"
        assert decision.quantity == 0.025

    def test_validate_position_fit_sufficient_cash(self, executor):
        """Position fits with sufficient cash."""
        # Get paper trading engine and ensure it has capital
        engine = get_paper_trading()
        if engine:
            # Initialize with capital
            account = engine.get_account_state()
            available = account.get("available_cash", 0)
            if available > 0:
                result = executor.validate_position_fit(
                    symbol="BTCUSDT",
                    quantity=0.1,  # Small position
                    price=50000,
                )
                assert result is True
            else:
                # If no capital, should fail
                result = executor.validate_position_fit(
                    symbol="BTCUSDT",
                    quantity=0.5,
                    price=50000,
                )
                assert result is False
        else:
            pytest.skip("Paper trading not initialized")

    def test_validate_position_fit_insufficient_cash(self, executor):
        """Position doesn't fit with insufficient cash."""
        result = executor.validate_position_fit(
            symbol="BTCUSDT",
            quantity=10,  # 10 BTC = 500,000 USD
            price=50000,
        )

        assert result is False

    def test_validate_position_fit_exceeds_size_limit(self, executor):
        """Position doesn't fit - size limit exceeded."""
        result = executor.validate_position_fit(
            symbol="BTCUSDT",
            quantity=2.0,  # 2 BTC = 100,000 USD = 100% of capital
            price=50000,
        )

        assert result is False

    def test_get_execution_summary(self, executor):
        """Generate execution summary."""
        summary = executor.get_execution_summary(
            symbol="BTCUSDT",
            quantity=0.1,
            price=50000,
            regime="BULL",
        )

        assert summary["symbol"] == "BTCUSDT"
        assert summary["quantity"] == 0.1
        assert summary["entry_price"] == 50000
        assert summary["position_value"] == 5000
        assert "stop_loss_price" in summary
        assert "take_profit_price" in summary
        assert "max_loss" in summary
        assert "max_gain" in summary

    def test_summary_position_percentage(self, executor):
        """Verify position percentage calculation in summary."""
        summary = executor.get_execution_summary(
            symbol="BTCUSDT",
            quantity=0.1,
            price=50000,  # 5,000 USD position
            regime="BULL",
        )

        # 5,000 / 100,000 = 5%
        assert summary["position_pct_of_capital"] == 5.0

    def test_summary_risk_metrics(self, executor):
        """Verify risk metrics in summary."""
        summary = executor.get_execution_summary(
            symbol="BTCUSDT",
            quantity=1.0,
            price=50000,
            regime="BULL",
        )

        # Max loss should be quantity * (entry - stop)
        # Max gain should be quantity * (target - entry)
        assert summary["max_loss"] > 0
        assert summary["max_gain"] > 0
        assert summary["max_loss"] < summary["max_gain"]  # Gain > loss in BULL


class TestExecutionContext:
    """Test ExecutionContext dataclass."""

    def test_context_creation(self):
        """Create execution context."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=1.0,
            current_price=50000,
            min_confidence=0.6,
        )

        assert context.symbol == "BTCUSDT"
        assert context.quantity == 1.0
        assert context.current_price == 50000
        assert context.min_confidence == 0.6

    def test_context_default_values(self):
        """Context has reasonable defaults."""
        context = ExecutionContext(
            symbol="BTCUSDT",
            quantity=1.0,
            current_price=50000,
        )

        assert context.min_confidence == 0.6
        assert context.max_position_pct == 0.05
        assert context.max_loss_pct == 2.0


class TestExecutionDecision:
    """Test ExecutionDecision dataclass."""

    def test_decision_creation(self):
        """Create execution decision."""
        decision = ExecutionDecision(
            decision="EXECUTE",
            symbol="BTCUSDT",
            quantity=1.0,
            price=50000,
            regime="BULL",
            confidence=0.8,
        )

        assert decision.decision == "EXECUTE"
        assert decision.symbol == "BTCUSDT"
        assert decision.regime == "BULL"

    def test_decision_with_order_id(self):
        """Decision includes order confirmation."""
        decision = ExecutionDecision(
            decision="EXECUTE",
            symbol="BTCUSDT",
            quantity=1.0,
            price=50000,
            regime="BULL",
            confidence=0.8,
            order_id="order_12345",
        )

        assert decision.order_id == "order_12345"
        assert decision.reason == ""


class TestGlobalInstance:
    """Test global executor instance."""

    def test_init_executor(self):
        """Initialize global executor."""
        executor = init_smart_executor(max_position_pct=0.08)
        assert executor is not None
        assert executor.max_position_pct == 0.08

    def test_get_executor(self):
        """Get initialized global executor."""
        init_smart_executor()
        executor = get_smart_executor()
        assert executor is not None

    def test_get_uninitialized(self):
        """Get uninitialized executor returns None."""
        import backend.execution.smart_executor as exec_module
        exec_module._smart_executor = None
        assert get_smart_executor() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
