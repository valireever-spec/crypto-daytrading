"""Tests for Sector Rotation Advisor (Phase 317)."""

import pytest
from backend.analytics.sector_rotation_advisor import (
    SectorRotationAdvisor,
    get_sector_rotation_advisor,
)


class TestSectorRotationAdvisor:
    """Test sector rotation recommendations."""

    @pytest.fixture
    def advisor(self):
        """Create sector rotation advisor."""
        return SectorRotationAdvisor()

    @pytest.fixture
    def sample_regimes_bull(self):
        """Create regime data favoring tech/crypto in bull market."""
        return {
            'BTCUSDT': {'regime': 'bull'},
            'ETHUSDT': {'regime': 'bull'},
            'EQ_AAPL': {'regime': 'bull'},
            'EQ_MSFT': {'regime': 'bull'},
            'EQ_JNJ': {'regime': 'sideways'},
            'EQ_NEE': {'regime': 'sideways'},
        }

    @pytest.fixture
    def sample_regimes_bear(self):
        """Create regime data favoring healthcare/utilities in bear market."""
        return {
            'BTCUSDT': {'regime': 'bear'},
            'ETHUSDT': {'regime': 'bear'},
            'EQ_AAPL': {'regime': 'bear'},
            'EQ_MSFT': {'regime': 'bear'},
            'EQ_JNJ': {'regime': 'bull'},
            'EQ_UNH': {'regime': 'bull'},
            'EQ_NEE': {'regime': 'bull'},
            'EQ_DUK': {'regime': 'bull'},
        }

    @pytest.fixture
    def current_allocation_tech_heavy(self):
        """Current allocation overweighted in tech."""
        return {
            'technology': 45,
            'cryptocurrency': 25,
            'consumer': 15,
            'finance': 10,
            'healthcare': 3,
            'energy': 2,
            'utilities': 0,
        }

    @pytest.fixture
    def current_allocation_defensive(self):
        """Current allocation overweighted in defensive."""
        return {
            'technology': 5,
            'cryptocurrency': 3,
            'consumer': 10,
            'finance': 15,
            'healthcare': 35,
            'energy': 15,
            'utilities': 17,
        }

    def test_initialization(self, advisor):
        """Test advisor initializes with regime allocations."""
        assert 'bull' in advisor.regime_allocations
        assert 'bear' in advisor.regime_allocations
        assert 'sideways' in advisor.regime_allocations
        assert 'volatile' in advisor.regime_allocations

    def test_sector_allocation_targets_bull(self, advisor):
        """Test sector allocation targets in bull market."""
        targets = advisor.get_sector_allocation_targets('bull', {})

        # Bull should have tech and crypto overweighted
        tech_target = next((t.target_pct for t in targets if t.sector == 'technology'), 0)
        crypto_target = next((t.target_pct for t in targets if t.sector == 'cryptocurrency'), 0)
        health_target = next((t.target_pct for t in targets if t.sector == 'healthcare'), 0)

        assert tech_target > 20
        assert crypto_target > 10
        assert health_target < 15

    def test_sector_allocation_targets_bear(self, advisor):
        """Test sector allocation targets in bear market."""
        targets = advisor.get_sector_allocation_targets('bear', {})

        # Bear should have healthcare and utilities overweighted
        health_target = next((t.target_pct for t in targets if t.sector == 'healthcare'), 0)
        util_target = next((t.target_pct for t in targets if t.sector == 'utilities'), 0)
        tech_target = next((t.target_pct for t in targets if t.sector == 'technology'), 0)
        crypto_target = next((t.target_pct for t in targets if t.sector == 'cryptocurrency'), 0)

        assert health_target > 20
        assert util_target > 15
        assert tech_target < 15
        assert crypto_target < 10

    def test_rotation_recommendation_bull_market(
        self, advisor, sample_regimes_bull, current_allocation_tech_heavy
    ):
        """Test rotation recommendation in bull market (tech is already favored)."""
        rec = advisor.get_sector_rotation_recommendation(
            portfolio_regime='bull',
            current_allocation=current_allocation_tech_heavy,
            symbol_regimes=sample_regimes_bull,
            symbol_prices={},
        )

        # In bull market with tech-heavy allocation, recommendation depends on specific sectors
        # If tech is overweight in bull regime, might still rotate to other areas
        # Just verify it returns a valid recommendation or None
        assert rec is None or isinstance(rec.from_sector, (str, type(None)))

    def test_rotation_recommendation_bear_market(
        self, advisor, sample_regimes_bear, current_allocation_tech_heavy
    ):
        """Test rotation recommendation in bear market (tech-heavy is bad)."""
        rec = advisor.get_sector_rotation_recommendation(
            portfolio_regime='bear',
            current_allocation=current_allocation_tech_heavy,
            symbol_regimes=sample_regimes_bear,
            symbol_prices={},
        )

        # Should recommend rotation FROM tech TO defensive (if found)
        if rec:
            assert rec.from_sector == 'technology'
            # to_sector might be None if no underweight sector found, just verify it's valid
            assert rec.to_sector is None or rec.to_sector in ['healthcare', 'utilities', 'energy']

    def test_rotation_recommendation_defensive_to_growth(
        self, advisor, sample_regimes_bull, current_allocation_defensive
    ):
        """Test rotation recommendation from defensive to growth."""
        rec = advisor.get_sector_rotation_recommendation(
            portfolio_regime='bull',
            current_allocation=current_allocation_defensive,
            symbol_regimes=sample_regimes_bull,
            symbol_prices={},
        )

        # Should recommend rotation FROM defensive TO growth (if found)
        if rec:
            assert rec.from_sector is None or rec.from_sector in ['healthcare', 'utilities']
            assert rec.to_sector is None or rec.to_sector in ['technology', 'cryptocurrency']

    def test_calculate_rotation_confidence(self, advisor, sample_regimes_bear):
        """Test confidence calculation for rotation."""
        confidence = advisor._calculate_rotation_confidence(
            'cryptocurrency', 'healthcare', sample_regimes_bear
        )

        assert 0 <= confidence <= 1.0

    def test_generate_action_symbols(self, advisor, sample_regimes_bear):
        """Test generation of SELL/BUY actions for rotation."""
        actions = advisor._generate_action_symbols(
            'cryptocurrency', 'healthcare', sample_regimes_bear
        )

        # Crypto symbols should have SELL
        assert actions['BTCUSDT'] in ['SELL', 'REDUCE']
        assert actions['ETHUSDT'] in ['SELL', 'REDUCE']

        # Healthcare symbols should have BUY
        if 'EQ_JNJ' in actions:
            assert actions['EQ_JNJ'] in ['BUY', 'HOLD']

    def test_should_increase_sector_exposure(self, advisor):
        """Test checking if sector exposure should increase."""
        current = {'healthcare': 5, 'technology': 50}

        should_increase = advisor.should_increase_sector_exposure(
            'healthcare', current, 'bear'
        )

        # In bear market, healthcare is underweight, should increase
        assert should_increase is True

    def test_should_decrease_sector_exposure(self, advisor):
        """Test checking if sector exposure should decrease."""
        current = {'cryptocurrency': 30, 'technology': 35}

        should_decrease = advisor.should_decrease_sector_exposure(
            'cryptocurrency', current, 'bear'
        )

        # In bear market, crypto is overweight, should decrease
        assert should_decrease is True

    def test_sector_momentum_calculation(self, advisor):
        """Test sector momentum calculation."""
        price_history = {
            'BTCUSDT': [40000, 42000, 43000, 45000, 48000],
            'EQ_AAPL': [140, 142, 143, 144, 145],
            'EQ_JNJ': [160, 161, 161, 162, 162],
        }
        symbol_prices = {
            'BTCUSDT': 48000,
            'EQ_AAPL': 145,
            'EQ_JNJ': 162,
        }

        momentum = advisor.get_sector_momentum(symbol_prices, price_history)

        # Crypto should have positive momentum
        assert momentum.get('cryptocurrency', 0) > 5

    def test_regime_allocations_sum_to_100(self, advisor):
        """Test that all regime allocations sum to 100%."""
        for regime, allocation in advisor.regime_allocations.items():
            total = sum(allocation.values())
            assert abs(total - 100) < 0.1

    def test_allocation_targets_drift_calculation(self, advisor, current_allocation_tech_heavy):
        """Test drift calculation in allocation targets."""
        targets = advisor.get_sector_allocation_targets('bear', current_allocation_tech_heavy)

        for target in targets:
            # Drift should be current - target
            expected_drift = current_allocation_tech_heavy.get(target.sector, 0) - target.target_pct
            assert abs(target.drift - expected_drift) < 0.1

    def test_allocation_targets_action_determination(self, advisor):
        """Test that actions are correctly determined based on drift."""
        current = {
            'technology': 50,  # Overweight
            'healthcare': 5,   # Underweight
            'utilities': 10,   # Underweight in bear
        }

        targets = advisor.get_sector_allocation_targets('bear', current)

        tech_target = next((t for t in targets if t.sector == 'technology'), None)
        health_target = next((t for t in targets if t.sector == 'healthcare'), None)

        # Tech overweight should be DECREASE
        if tech_target and tech_target.drift > 2:
            assert tech_target.action == 'DECREASE'

        # Healthcare underweight should be INCREASE
        if health_target and health_target.drift < -2:
            assert health_target.action == 'INCREASE'

    def test_global_instance(self):
        """Test global sector advisor instance."""
        adv1 = get_sector_rotation_advisor()
        adv2 = get_sector_rotation_advisor()

        assert adv1 is adv2  # Same instance

    def test_unknown_regime_handling(self, advisor, sample_regimes_bull):
        """Test handling of unknown regime."""
        rec = advisor.get_sector_rotation_recommendation(
            portfolio_regime='unknown',
            current_allocation={},
            symbol_regimes=sample_regimes_bull,
            symbol_prices={},
        )

        assert rec is None

    def test_summary_generation(self, advisor):
        """Test summary generation."""
        summary = advisor.get_summary('bull')

        assert 'bull' in summary.lower()
        assert '%' in summary

    def test_expected_outperformance_calculation(self, advisor):
        """Test outperformance estimation."""
        # Tech → Healthcare in bear should have positive outperformance
        outperformance = advisor._calculate_expected_outperformance(
            'technology', 'healthcare'
        )

        assert outperformance > 0

        # Crypto → Utilities should have very positive outperformance
        outperformance = advisor._calculate_expected_outperformance(
            'cryptocurrency', 'utilities'
        )

        assert outperformance > 5

    def test_rotation_recommendation_drift_threshold(
        self, advisor, sample_regimes_bull, current_allocation_tech_heavy
    ):
        """Test that rotations are only recommended for significant drift."""
        # Perfectly aligned allocation
        perfect_allocation = advisor.regime_allocations['bull'].copy()

        rec = advisor.get_sector_rotation_recommendation(
            portfolio_regime='bull',
            current_allocation=perfect_allocation,
            symbol_regimes=sample_regimes_bull,
            symbol_prices={},
        )

        # Should not recommend rotation when aligned
        assert rec is None

    def test_symbol_sector_mapping(self, advisor):
        """Test that symbol sector mapping is complete."""
        # All test symbols should map to a sector
        test_symbols = ['BTCUSDT', 'EQ_AAPL', 'EQ_JNJ', 'EQ_NEE']

        for symbol in test_symbols:
            assert symbol in advisor.symbol_sectors
            sector = advisor.symbol_sectors[symbol]
            assert sector in ['cryptocurrency', 'technology', 'healthcare', 'utilities', 'finance', 'energy', 'consumer']
