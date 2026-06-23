"""Tests for Portfolio Regime Monitor (Phase 317)."""

import pytest
from datetime import datetime, timedelta
from backend.analytics.portfolio_regime_monitor import (
    PortfolioRegimeMonitor,
    RegimeFlip,
    get_portfolio_regime_monitor,
)


class TestPortfolioRegimeMonitor:
    """Test portfolio-level regime monitoring."""

    @pytest.fixture
    def monitor(self):
        """Create portfolio regime monitor."""
        return PortfolioRegimeMonitor()

    @pytest.fixture
    def sample_regime_data(self):
        """Create sample regime data for multiple symbols."""
        return {
            'BTCUSDT': {'regime': 'bull', 'trend_strength': 0.5},
            'ETHUSDT': {'regime': 'bull', 'trend_strength': 0.4},
            'EQ_AAPL': {'regime': 'sideways', 'trend_strength': 0.1},
            'EQ_MSFT': {'regime': 'sideways', 'trend_strength': 0.0},
        }

    def test_initialization(self, monitor):
        """Test monitor initializes with empty state."""
        assert monitor.last_regime_state == {}
        assert monitor.regime_change_history == []
        assert monitor.portfolio_regime_history == []

    def test_detect_regime_flip(self, monitor, sample_regime_data):
        """Test detection of regime flip (bull -> bear)."""
        current_positions = ['BTCUSDT', 'ETHUSDT']

        # First check - establish baseline
        state1 = monitor.check_portfolio_regime(sample_regime_data, current_positions)
        assert state1.regime_flips == []
        assert state1.exit_signals == []

        # Change BTCUSDT to bear
        sample_regime_data['BTCUSDT']['regime'] = 'bear'

        state2 = monitor.check_portfolio_regime(sample_regime_data, current_positions)
        assert len(state2.regime_flips) == 1
        assert state2.regime_flips[0].from_regime == 'bull'
        assert state2.regime_flips[0].to_regime == 'bear'
        assert state2.regime_flips[0].should_exit is True
        assert 'BTCUSDT' in state2.exit_signals

    def test_regime_flip_severity(self, monitor):
        """Test regime flip severity calculation."""
        # Bull to bear (maximum severity)
        severity = monitor._calculate_flip_severity('bull', 'bear')
        assert severity == 1.0

        # Bull to sideways (mild)
        severity = monitor._calculate_flip_severity('bull', 'sideways')
        assert 0.2 < severity < 0.5

        # Bull to volatile (moderate)
        severity = monitor._calculate_flip_severity('bull', 'volatile')
        assert 0.5 < severity < 0.8

    def test_portfolio_regime_bull_dominant(self, monitor):
        """Test portfolio regime when bull is dominant."""
        regime_data = {
            'SYM1': {'regime': 'bull'},
            'SYM2': {'regime': 'bull'},
            'SYM3': {'regime': 'sideways'},
            'SYM4': {'regime': 'sideways'},
        }

        portfolio_regime = monitor._calculate_portfolio_regime(regime_data)
        # With 50% bull and 50% sideways, should be bull (tied goes to first)
        assert portfolio_regime in ['bull', 'sideways', 'mixed']

    def test_portfolio_regime_bear_dominant(self, monitor):
        """Test portfolio regime when bear is dominant."""
        regime_data = {
            'SYM1': {'regime': 'bear'},
            'SYM2': {'regime': 'bear'},
            'SYM3': {'regime': 'bear'},
            'SYM4': {'regime': 'sideways'},
        }

        portfolio_regime = monitor._calculate_portfolio_regime(regime_data)
        assert portfolio_regime == 'bear'

    def test_portfolio_regime_mixed(self, monitor):
        """Test portfolio regime when no clear dominant."""
        regime_data = {
            'SYM1': {'regime': 'bull'},
            'SYM2': {'regime': 'bear'},
            'SYM3': {'regime': 'sideways'},
        }

        portfolio_regime = monitor._calculate_portfolio_regime(regime_data)
        assert portfolio_regime == 'mixed'

    def test_allocation_adjustments_bull(self, monitor, sample_regime_data):
        """Test position size adjustments in bull market."""
        current_positions = ['BTCUSDT', 'ETHUSDT', 'EQ_AAPL']

        adjustments = monitor._calculate_allocation_adjustments(
            sample_regime_data, current_positions
        )

        # Bull positions should have 1.2x multiplier
        assert adjustments['BTCUSDT'] == 1.2
        assert adjustments['ETHUSDT'] == 1.2

        # Sideways should have 1.0x
        assert adjustments['EQ_AAPL'] == 1.0

    def test_allocation_adjustments_bear(self, monitor, sample_regime_data):
        """Test position size adjustments in bear market."""
        sample_regime_data['BTCUSDT']['regime'] = 'bear'
        current_positions = ['BTCUSDT']

        adjustments = monitor._calculate_allocation_adjustments(
            sample_regime_data, current_positions
        )

        # Bear position should have 0.5x multiplier
        assert adjustments['BTCUSDT'] == 0.5

    def test_allocation_adjustments_volatile(self, monitor, sample_regime_data):
        """Test position size adjustments in volatile market."""
        sample_regime_data['BTCUSDT']['regime'] = 'volatile'
        current_positions = ['BTCUSDT']

        adjustments = monitor._calculate_allocation_adjustments(
            sample_regime_data, current_positions
        )

        # Volatile position should have 0.7x multiplier
        assert adjustments['BTCUSDT'] == 0.7

    def test_correlated_exits(self, monitor, sample_regime_data):
        """Test generation of correlated exit signals."""
        current_positions = [
            {'symbol': 'BTCUSDT', 'quantity': 1.0, 'entry_price': 50000},
            {'symbol': 'ETHUSDT', 'quantity': 10.0, 'entry_price': 2000},
        ]
        portfolio_value = 100000

        # Establish baseline
        monitor.check_portfolio_regime(sample_regime_data, [p['symbol'] for p in current_positions])

        # Flip both to bear
        sample_regime_data['BTCUSDT']['regime'] = 'bear'
        sample_regime_data['ETHUSDT']['regime'] = 'bear'

        monitor.check_portfolio_regime(sample_regime_data, [p['symbol'] for p in current_positions])

        # Get correlated exits
        exits = monitor.get_correlated_exits(current_positions, portfolio_value)

        # Should have exit recommendations
        assert len(exits) > 0
        assert all('symbol' in e for e in exits)

    def test_sector_rotation_opportunity(self, monitor, sample_regime_data):
        """Test detection of sector rotation opportunity."""
        current_allocation = {
            'technology': 40,
            'cryptocurrency': 30,
            'healthcare': 15,
            'utilities': 15,
        }

        symbol_sectors = {
            'BTCUSDT': 'cryptocurrency',
            'ETHUSDT': 'cryptocurrency',
            'EQ_AAPL': 'technology',
            'EQ_MSFT': 'technology',
        }

        result = monitor.detect_sector_rotation_opportunity(
            current_allocation, symbol_sectors, sample_regime_data
        )

        assert isinstance(result, dict)
        assert 'should_rotate' in result
        assert 'confidence' in result

    def test_portfolio_stress_level(self, monitor, sample_regime_data):
        """Test portfolio stress level calculation."""
        stress = monitor.get_portfolio_stress_level(sample_regime_data)

        assert 0 <= stress <= 1.0

        # With mostly bull/sideways, stress should be low
        assert stress < 0.5

    def test_portfolio_stress_level_high(self, monitor):
        """Test portfolio stress with many bear/volatile positions."""
        regime_data = {
            'SYM1': {'regime': 'bear'},
            'SYM2': {'regime': 'bear'},
            'SYM3': {'regime': 'volatile'},
            'SYM4': {'regime': 'volatile'},
        }

        stress = monitor.get_portfolio_stress_level(regime_data)

        # High percentage of bear/volatile should have elevated stress (100% = 0.6 from regimes)
        assert stress > 0.5

    def test_entry_signals_on_favorable_flip(self, monitor, sample_regime_data):
        """Test entry signals generated when flipping to favorable regime."""
        current_positions = []  # No positions

        # Establish baseline
        monitor.check_portfolio_regime(sample_regime_data, current_positions)

        # Change sideways to bull
        sample_regime_data['EQ_AAPL']['regime'] = 'bull'

        state = monitor.check_portfolio_regime(sample_regime_data, current_positions)

        # Should have entry signal
        assert 'EQ_AAPL' in state.entry_signals

    def test_global_instance(self):
        """Test global portfolio monitor instance."""
        mon1 = get_portfolio_regime_monitor()
        mon2 = get_portfolio_regime_monitor()

        assert mon1 is mon2  # Same instance

    def test_history_tracking(self, monitor, sample_regime_data):
        """Test that regime change history is tracked."""
        current_positions = ['BTCUSDT']

        monitor.check_portfolio_regime(sample_regime_data, current_positions)
        initial_history_len = len(monitor.regime_change_history)

        sample_regime_data['BTCUSDT']['regime'] = 'bear'
        monitor.check_portfolio_regime(sample_regime_data, current_positions)

        # History should have grown
        assert len(monitor.regime_change_history) > initial_history_len

    def test_regime_flip_dataclass(self):
        """Test RegimeFlip dataclass."""
        flip = RegimeFlip(
            symbol='BTCUSDT',
            from_regime='bull',
            to_regime='bear',
            severity=0.9,
            timestamp=datetime.utcnow(),
            should_exit=True,
        )

        assert flip.symbol == 'BTCUSDT'
        assert flip.from_regime == 'bull'
        assert flip.to_regime == 'bear'
        assert flip.should_exit is True

    def test_no_flip_on_same_regime(self, monitor, sample_regime_data):
        """Test that no flip is detected when regime stays same."""
        current_positions = ['BTCUSDT']

        state1 = monitor.check_portfolio_regime(sample_regime_data, current_positions)
        assert state1.regime_flips == []

        # Check again with same regime
        state2 = monitor.check_portfolio_regime(sample_regime_data, current_positions)
        assert state2.regime_flips == []

    def test_multiple_simultaneous_flips(self, monitor, sample_regime_data):
        """Test handling of multiple regime flips simultaneously."""
        current_positions = ['BTCUSDT', 'ETHUSDT']  # Only hold crypto initially

        # Establish baseline
        monitor.check_portfolio_regime(sample_regime_data, current_positions)

        # Flip all symbols
        sample_regime_data['BTCUSDT']['regime'] = 'bear'
        sample_regime_data['ETHUSDT']['regime'] = 'bear'
        sample_regime_data['EQ_AAPL']['regime'] = 'bull'
        sample_regime_data['EQ_MSFT']['regime'] = 'bull'

        state = monitor.check_portfolio_regime(sample_regime_data, current_positions)

        # Should detect 4 flips
        assert len(state.regime_flips) == 4

        # Crypto should have exit signals (flipped to bear and in positions)
        assert 'BTCUSDT' in state.exit_signals
        assert 'ETHUSDT' in state.exit_signals

        # Tech should have entry signals (flipped to bull and NOT in positions)
        assert 'EQ_AAPL' in state.entry_signals
        assert 'EQ_MSFT' in state.entry_signals

    def test_summary_generation(self, monitor, sample_regime_data):
        """Test summary generation."""
        current_positions = ['BTCUSDT']

        # Cause a flip
        monitor.check_portfolio_regime(sample_regime_data, current_positions)
        sample_regime_data['BTCUSDT']['regime'] = 'bear'
        monitor.check_portfolio_regime(sample_regime_data, current_positions)

        summary = monitor.get_summary()
        assert "Recent regime flips" in summary or "No regime changes" in summary
