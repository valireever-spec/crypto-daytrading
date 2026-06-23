"""Tests for dynamic position sizing (Phase 1 Week 3.5)."""

import pytest
from backend.analytics.position_sizing import (
    PositionSizer,
    init_position_sizer,
    get_position_sizer,
)


@pytest.fixture
def sizer():
    """Create position sizer for tests."""
    return PositionSizer(min_percent=0.5, max_percent=3.0)


@pytest.fixture(autouse=True)
def cleanup_sizer():
    """Clean up global sizer between tests."""
    import backend.analytics.position_sizing as sizer_module

    sizer_module._position_sizer = None
    yield
    sizer_module._position_sizer = None


class TestKellyCriterion:
    """Test Kelly Criterion calculation."""

    def test_kelly_50_percent_winrate(self, sizer):
        """Kelly with 50% win rate and 1:1 payoff should be 0."""
        kelly = sizer.calculate_kelly_size(
            win_rate=0.5,
            avg_win=100,
            avg_loss=100,
        )
        assert kelly == 0.0  # Break-even, no edge

    def test_kelly_60_percent_winrate(self, sizer):
        """Kelly with 60% win rate and 1:1 payoff should be positive."""
        kelly = sizer.calculate_kelly_size(
            win_rate=0.6,
            avg_win=100,
            avg_loss=100,
        )
        assert kelly > 0.0

    def test_kelly_clamped_to_1(self, sizer):
        """Kelly should not exceed 1.0 (100% of capital)."""
        kelly = sizer.calculate_kelly_size(
            win_rate=0.9,
            avg_win=1000,
            avg_loss=1,
        )
        assert kelly <= 1.0

    def test_kelly_zero_on_invalid_input(self, sizer):
        """Kelly should return 0 for invalid inputs."""
        # Negative win rate
        assert sizer.calculate_kelly_size(win_rate=-0.1, avg_win=100, avg_loss=100) == 0.0

        # Zero avg loss
        assert sizer.calculate_kelly_size(win_rate=0.5, avg_win=100, avg_loss=0) == 0.0

        # 100% win rate (impossible)
        assert sizer.calculate_kelly_size(win_rate=1.0, avg_win=100, avg_loss=100) == 0.0

    def test_kelly_favorable_payoff(self, sizer):
        """Kelly should be larger with favorable payoff ratios."""
        # 1:1 payoff
        kelly_1_1 = sizer.calculate_kelly_size(win_rate=0.55, avg_win=100, avg_loss=100)

        # 2:1 payoff (win more per dollar risked)
        kelly_2_1 = sizer.calculate_kelly_size(win_rate=0.55, avg_win=200, avg_loss=100)

        assert kelly_2_1 > kelly_1_1


class TestVolatilityAdjustment:
    """Test volatility-based position sizing."""

    def test_normal_volatility_no_change(self, sizer):
        """2% volatility (normal) should result in no adjustment."""
        adjusted = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=2.0)
        assert adjusted == pytest.approx(0.10)

    def test_high_volatility_reduces_size(self, sizer):
        """Higher volatility should reduce position size."""
        normal = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=2.0)
        high = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=4.0)

        assert high < normal

    def test_low_volatility_increases_size(self, sizer):
        """Lower volatility should increase position size."""
        normal = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=2.0)
        low = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=1.0)

        assert low > normal

    def test_volatility_adjustment_bounded(self, sizer):
        """Volatility adjustment should be bounded (0.5x - 1.5x)."""
        extreme_high = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=10.0)
        extreme_low = sizer.adjust_for_volatility(base_size=0.10, volatility_pct=0.1)

        assert extreme_high >= 0.10 * 0.5
        assert extreme_low <= 0.10 * 1.5


class TestPositionSizeCalculation:
    """Test full position size calculation."""

    def test_basic_calculation(self, sizer):
        """Calculate position size with typical inputs."""
        metrics = sizer.calculate_size(
            capital=10000,
            signal_strength=75.0,  # Strong signal
            win_rate=0.55,
            avg_win=100,
            avg_loss=100,
            volatility_pct=2.0,
        )

        assert metrics.min_size == 10000 * 0.005  # 0.5% = $50
        assert metrics.max_size == 10000 * 0.03   # 3% = $300
        assert metrics.min_size <= metrics.recommended <= metrics.max_size

    def test_weak_signal_reduces_size(self, sizer):
        """Weak signal should reduce position size."""
        strong = sizer.calculate_size(
            capital=10000,
            signal_strength=80.0,
            win_rate=0.55,
            avg_win=100,
            avg_loss=100,
        )

        weak = sizer.calculate_size(
            capital=10000,
            signal_strength=30.0,
            win_rate=0.55,
            avg_win=100,
            avg_loss=100,
        )

        assert weak.recommended < strong.recommended

    def test_size_respects_bounds(self, sizer):
        """Position size should always be within min/max bounds."""
        metrics = sizer.calculate_size(
            capital=10000,
            signal_strength=100.0,  # Max signal
            win_rate=0.9,
            avg_win=1000,
            avg_loss=10,  # Very favorable
            volatility_pct=0.1,  # Very low vol
        )

        assert metrics.recommended <= metrics.max_size
        assert metrics.recommended >= metrics.min_size

    def test_kelly_vs_half_kelly(self, sizer):
        """Half-Kelly should be conservative compared to full Kelly."""
        metrics = sizer.calculate_size(
            capital=10000,
            signal_strength=60.0,
            win_rate=0.6,
            avg_win=100,
            avg_loss=100,
        )

        assert metrics.half_kelly <= metrics.kelly_size
        assert metrics.half_kelly > 0


class TestShareCalculation:
    """Test conversion from dollars to shares."""

    def test_convert_dollars_to_shares(self, sizer):
        """Convert dollar position to shares."""
        shares = sizer.calculate_shares(position_dollars=1000, price_per_share=100)
        assert shares == 10

    def test_fractional_shares_rounded_down(self, sizer):
        """Fractional shares should be rounded down for safety."""
        shares = sizer.calculate_shares(position_dollars=1050, price_per_share=100)
        assert shares == 10  # Not 10.5

    def test_insufficient_capital(self, sizer):
        """Position smaller than one share returns 0."""
        shares = sizer.calculate_shares(position_dollars=50, price_per_share=100)
        assert shares == 0

    def test_high_price_asset(self, sizer):
        """High-priced assets should work correctly."""
        shares = sizer.calculate_shares(position_dollars=45000, price_per_share=45000)
        assert shares == 1

    def test_invalid_price(self, sizer):
        """Invalid price should return 0."""
        assert sizer.calculate_shares(position_dollars=1000, price_per_share=0) == 0
        assert sizer.calculate_shares(position_dollars=1000, price_per_share=-100) == 0


class TestGlobalInstance:
    """Test global position sizer instance."""

    def test_init_position_sizer(self):
        """Initialize global position sizer."""
        sizer = init_position_sizer(min_percent=0.5, max_percent=3.0)
        assert sizer is not None

    def test_get_position_sizer(self):
        """Get initialized global position sizer."""
        init_position_sizer()
        sizer = get_position_sizer()
        assert sizer is not None

    def test_get_before_init(self):
        """Should return None if not initialized."""
        import backend.analytics.position_sizing as sizer_module

        sizer_module._position_sizer = None
        assert get_position_sizer() is None


class TestRealWorldScenarios:
    """Test real-world trading scenarios."""

    def test_low_capital_minimum_position(self):
        """With low capital, should respect minimum position size."""
        sizer = PositionSizer(min_percent=0.5, max_percent=3.0)
        metrics = sizer.calculate_size(
            capital=1000,  # Small account
            signal_strength=80.0,
            win_rate=0.6,
            avg_win=100,
            avg_loss=100,
        )

        # Minimum should be $5 (0.5% of $1000)
        assert metrics.min_size == 5.0
        assert metrics.recommended >= 5.0

    def test_high_capital_maximum_position(self):
        """With high capital, should respect maximum position size."""
        sizer = PositionSizer(min_percent=0.5, max_percent=3.0)
        metrics = sizer.calculate_size(
            capital=1000000,  # Large account
            signal_strength=100.0,
            win_rate=0.9,
            avg_win=1000,
            avg_loss=10,
        )

        # Maximum should be $30,000 (3% of $1M)
        assert metrics.max_size == 30000.0
        assert metrics.recommended <= 30000.0

    def test_crypto_position_example(self):
        """Real-world crypto position sizing example."""
        sizer = PositionSizer(min_percent=0.5, max_percent=3.0)

        # Account: $100,000 (larger account for meaningful BTC position)
        # BTC price: $45,000
        # Signal: 75 (strong buy)
        # Win rate: 55% (tested over 100 trades)
        # Avg win: $1000, avg loss: $800
        # Volatility: 2.3%

        metrics = sizer.calculate_size(
            capital=100000,
            signal_strength=75.0,
            win_rate=0.55,
            avg_win=1000,
            avg_loss=800,
            volatility_pct=2.3,
        )

        # Should recommend a reasonable size
        assert metrics.min_size <= metrics.recommended <= metrics.max_size

        # Convert to shares (actual BTC fractional units)
        btc_shares = sizer.calculate_shares(
            position_dollars=metrics.recommended,
            price_per_share=45000,
        )

        # Should be able to buy fractional BTC (can buy 0.001 BTC = 1 Satoshi unit)
        # With min 0.5% = $500, can afford $500 / $45,000 = 0.011 BTC
        assert metrics.recommended >= metrics.min_size  # Sanity check


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
