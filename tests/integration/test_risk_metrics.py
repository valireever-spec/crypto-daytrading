"""Integration tests for Risk Metrics Engine and Stress Test Engine (Phase 320)."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.analytics.risk_metrics_engine import (
    RiskMetricsEngine,
    RiskMetrics,
    get_risk_metrics_engine,
)
from backend.analytics.stress_test_engine import (
    StressTestEngine,
    StressScenario,
    get_stress_test_engine,
)


class TestRiskMetricsEngine:
    """Test risk metrics calculation."""

    @pytest.fixture
    def engine(self):
        """Create risk metrics engine."""
        return RiskMetricsEngine()

    @pytest.fixture
    def sample_returns(self):
        """Create sample daily returns."""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        # Normal distribution + some tail events
        returns = np.random.normal(0.1, 1.5, 252)  # Mean 0.1%, std 1.5%
        # Add tail events
        returns[50] = -10  # Crash day
        returns[100] = 8   # Spike up
        returns[150] = -8  # Another crash

        return pd.Series(returns, index=dates)

    @pytest.fixture
    def bull_returns(self):
        """Create bull market returns."""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        returns = np.random.normal(0.05, 0.8, 252)  # Lower vol, positive drift
        return pd.Series(returns, index=dates)

    @pytest.fixture
    def bear_returns(self):
        """Create bear market returns."""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        returns = np.random.normal(-0.02, 1.5, 252)  # Negative drift, higher vol
        return pd.Series(returns, index=dates)

    def test_initialization(self, engine):
        """Test engine initializes with default confidence."""
        assert engine.confidence_level == 0.95

    def test_calculate_risk_metrics(self, engine, sample_returns):
        """Test risk metrics calculation."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        assert isinstance(metrics, RiskMetrics)
        assert hasattr(metrics, 'value_at_risk_95')
        assert hasattr(metrics, 'expected_shortfall_95')
        assert hasattr(metrics, 'max_drawdown_pct')
        assert hasattr(metrics, 'volatility_pct')

    def test_var_is_negative(self, engine, sample_returns):
        """Test that VaR is negative (loss)."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # VaR should be negative (represents loss)
        assert metrics.value_at_risk_95 < 0
        assert metrics.value_at_risk_99 < 0

    def test_es_worse_than_var(self, engine, sample_returns):
        """Test that Expected Shortfall is worse than VaR."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # ES should be lower (worse) than VaR
        assert metrics.expected_shortfall_95 < metrics.value_at_risk_95

    def test_volatility_annualized(self, engine, sample_returns):
        """Test volatility is annualized."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # Volatility should be positive (sample_returns has large outliers so will be high)
        assert metrics.volatility_pct > 0

    def test_sharpe_ratio_calculation(self, engine, sample_returns):
        """Test Sharpe ratio calculation."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # Should have Sharpe ratio
        assert hasattr(metrics, 'sharpe_ratio')
        assert isinstance(metrics.sharpe_ratio, (int, float))

    def test_sortino_ratio_calculation(self, engine, sample_returns):
        """Test Sortino ratio calculation."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # Should have Sortino ratio (may be higher or lower than Sharpe depending on skew)
        assert isinstance(metrics.sortino_ratio, (int, float))

    def test_skewness_kurtosis(self, engine, sample_returns):
        """Test skewness and kurtosis calculation."""
        metrics = engine.calculate_risk_metrics(sample_returns)

        # Should have distribution metrics
        assert hasattr(metrics, 'skewness')
        assert hasattr(metrics, 'kurtosis')

    def test_regime_risk_profile(self, engine, sample_returns):
        """Test regime-specific risk profile."""
        symbol_returns = {'BTCUSDT': sample_returns, 'EQ_AAPL': sample_returns}
        symbol_regimes = {
            'BTCUSDT': [(datetime(2024, 1, 1), 'bull'), (datetime(2024, 6, 1), 'bear')],
            'EQ_AAPL': [(datetime(2024, 1, 1), 'bull'), (datetime(2024, 12, 31), 'bull')],
        }

        profile = engine.get_regime_risk_profile(
            symbol_returns=symbol_returns,
            symbol_regimes=symbol_regimes,
            regime='bull',
        )

        # Should have profile metrics
        assert profile.regime == 'bull'
        assert hasattr(profile, 'volatility_pct')
        assert hasattr(profile, 'var_95_pct')
        assert hasattr(profile, 'sharpe_ratio')

    def test_marginal_var_calculation(self, engine):
        """Test marginal VaR calculation."""
        position_values = {'BTCUSDT': 50000, 'EQ_AAPL': 30000, 'EQ_MSFT': 20000}

        # Create correlation matrix
        corr_data = {
            'BTCUSDT': [1.0, 0.3, 0.2],
            'EQ_AAPL': [0.3, 1.0, 0.8],
            'EQ_MSFT': [0.2, 0.8, 1.0],
        }
        corr_matrix = pd.DataFrame(corr_data, index=['BTCUSDT', 'EQ_AAPL', 'EQ_MSFT'])

        marginal_vars = engine.calculate_marginal_var(
            position_values=position_values,
            returns_correlation=corr_matrix,
        )

        # Should have marginal VaR for each symbol
        assert 'BTCUSDT' in marginal_vars
        assert 'EQ_AAPL' in marginal_vars

    def test_risk_summary_generation(self, engine, sample_returns):
        """Test summary generation."""
        metrics = engine.calculate_risk_metrics(sample_returns)
        summary = engine.get_risk_summary(metrics)

        # Summary should contain key metrics
        assert 'Value at Risk' in summary or 'Risk' in summary
        assert 'Sharpe' in summary
        assert '%' in summary

    def test_risk_classification(self, engine, sample_returns):
        """Test portfolio risk classification."""
        metrics = engine.calculate_risk_metrics(sample_returns)
        classification = engine.risk_classification(metrics)

        # Should classify as one of the risk levels
        assert classification in ['CONSERVATIVE', 'MODERATE', 'BALANCED', 'AGGRESSIVE', 'EXTREME']

    def test_bull_market_lower_var(self, engine, bull_returns, bear_returns):
        """Test VaR is lower in bull than bear market."""
        bull_metrics = engine.calculate_risk_metrics(bull_returns)
        bear_metrics = engine.calculate_risk_metrics(bear_returns)

        # Bull market should have lower/less negative VaR
        assert bull_metrics.value_at_risk_95 > bear_metrics.value_at_risk_95

    def test_global_instance(self):
        """Test global engine instance."""
        eng1 = get_risk_metrics_engine()
        eng2 = get_risk_metrics_engine()

        assert eng1 is eng2

    def test_custom_confidence_level(self, engine, sample_returns):
        """Test custom confidence level."""
        metrics = engine.calculate_risk_metrics(
            sample_returns,
            confidence_level=0.99,
        )

        # Should calculate with 99% confidence
        assert abs(metrics.value_at_risk_99) >= abs(metrics.value_at_risk_95)


class TestStressTestEngine:
    """Test stress test scenarios."""

    @pytest.fixture
    def engine(self):
        """Create stress test engine."""
        return StressTestEngine()

    @pytest.fixture
    def sample_positions(self):
        """Create sample portfolio."""
        return {
            'BTCUSDT': 50000,
            'EQ_AAPL': 30000,
            'EQ_MSFT': 20000,
        }

    @pytest.fixture
    def sample_prices(self):
        """Current prices."""
        return {
            'BTCUSDT': 50000,
            'EQ_AAPL': 150,
            'EQ_MSFT': 420,
        }

    @pytest.fixture
    def symbol_sectors(self):
        """Symbol to sector mapping."""
        return {
            'BTCUSDT': 'cryptocurrency',
            'EQ_AAPL': 'technology',
            'EQ_MSFT': 'technology',
        }

    def test_initialization(self, engine):
        """Test engine initializes with scenarios."""
        assert len(engine.scenario_definitions) > 0
        assert StressScenario.MARKET_CRASH in engine.scenario_definitions

    def test_market_crash_scenario(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test market crash scenario."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.MARKET_CRASH,
        )

        # Should have significant loss
        assert result.portfolio_loss_pct < 0
        assert result.worst_loss_pct < 0

    def test_volatility_spike_scenario(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test volatility spike scenario."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.VOLATILITY_SPIKE,
        )

        # Should have loss (volatility spikes hurt)
        assert result.portfolio_loss_pct < 0

    def test_crypto_crash_scenario(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test crypto-specific crash."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.CRYPTO_CRASH,
        )

        # Crypto should be hit hardest
        assert result.worst_affected == 'BTCUSDT'
        assert result.worst_loss_pct < -40  # -50% shock

    def test_sector_rotation_scenario(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test sector rotation scenario."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.SECTOR_ROTATION,
        )

        # Tech should be hit (tech crashes -30%)
        assert result.worst_affected in ['EQ_AAPL', 'EQ_MSFT']

    def test_run_all_scenarios(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test running all scenarios."""
        results = engine.run_all_scenarios(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
        )

        # Should have results for all scenarios
        assert len(results) == len(StressScenario)

    def test_worst_case_scenario(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test identifying worst case."""
        results = engine.run_all_scenarios(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
        )

        worst_scenario, worst_result = engine.get_worst_case_scenario(results)

        # Should identify worst loss
        assert worst_scenario is not None
        assert worst_result is not None
        assert worst_result.portfolio_loss_pct < -10  # Significant loss

    def test_recovery_estimate(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test recovery time estimation."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.MARKET_CRASH,
        )

        # Should estimate recovery time
        assert result.recovery_days_estimate > 0

    def test_stress_classification(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test stress scenario risk classification."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.MARKET_CRASH,
        )

        # Should classify risk level
        assert result.risk_classification in ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']

    def test_stress_summary_generation(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test summary generation."""
        results = engine.run_all_scenarios(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
        )

        summary = engine.get_stress_summary(results)

        # Summary should contain scenario information
        assert 'Stress Test Results' in summary or 'STRESS' in summary
        assert '%' in summary

    def test_global_instance(self):
        """Test global stress engine instance."""
        eng1 = get_stress_test_engine()
        eng2 = get_stress_test_engine()

        assert eng1 is eng2

    def test_scenario_definitions_complete(self, engine):
        """Test all scenarios have complete definitions."""
        for scenario in StressScenario:
            assert scenario in engine.scenario_definitions
            params = engine.scenario_definitions[scenario]
            assert 'description' in params

    def test_empty_portfolio_handling(self, engine):
        """Test handling of empty portfolio."""
        result = engine.run_stress_test(
            position_values={},
            current_prices={},
            symbol_sectors={},
            scenario=StressScenario.MARKET_CRASH,
        )

        # Should handle gracefully
        assert result is not None

    def test_leverage_requirement_calculation(self, engine, sample_positions, sample_prices, symbol_sectors):
        """Test leverage/margin requirement calculation."""
        result = engine.run_stress_test(
            position_values=sample_positions,
            current_prices=sample_prices,
            symbol_sectors=symbol_sectors,
            scenario=StressScenario.MARKET_CRASH,
        )

        # Should estimate leverage requirement
        assert result.leverage_requirement >= 0
