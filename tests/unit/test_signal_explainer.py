"""Tests for Signal Explainer (Phase 313)."""

import pytest
from backend.analytics.signal_explainer import SignalExplainer, get_signal_explainer


class TestSignalExplainer:
    """Test signal explainer functionality."""

    @pytest.fixture
    def explainer(self):
        """Create signal explainer instance."""
        return SignalExplainer()

    def test_explainer_initialization(self, explainer):
        """Test explainer initializes with correct components."""
        assert "garp" in explainer.components
        assert "technical" in explainer.components
        assert explainer.components["garp"]["weight"] == 0.60
        assert explainer.components["technical"]["weight"] == 0.40

    def test_explain_strong_buy_signal(self, explainer):
        """Test explanation of strong buy signal."""
        explanation = explainer.explain_score(
            symbol="BTC",
            total_score=80.0,
            component_scores={"garp": 85.0, "technical": 70.0},
            asset_class="crypto"
        )

        assert explanation["symbol"] == "BTC"
        assert explanation["score"] == 80.0
        assert explanation["grade"] == "Strong Buy"
        assert explanation["emoji"] == "🚀"
        assert explanation["asset_class"] == "crypto"

    def test_explain_buy_signal(self, explainer):
        """Test explanation of buy signal."""
        explanation = explainer.explain_score(
            symbol="EQ_AAPL",
            total_score=65.0,
            component_scores={"garp": 70.0, "technical": 55.0},
            asset_class="stock"
        )

        assert explanation["grade"] == "Buy"
        assert explanation["emoji"] == "⭐⭐"
        assert explanation["score"] == 65.0

    def test_explain_enter_signal(self, explainer):
        """Test explanation of enter signal (just above threshold)."""
        explanation = explainer.explain_score(
            symbol="ETH",
            total_score=58.0,
            component_scores={"garp": 60.0, "technical": 55.0},
            asset_class="crypto"
        )

        assert explanation["grade"] == "Enter"
        assert explanation["emoji"] == "⭐"

    def test_explain_watch_signal(self, explainer):
        """Test explanation of watch signal."""
        explanation = explainer.explain_score(
            symbol="SOL",
            total_score=45.0,
            component_scores={"garp": 40.0, "technical": 50.0},
            asset_class="crypto"
        )

        assert explanation["grade"] == "Watch"
        assert explanation["emoji"] == "👁️"

    def test_explain_avoid_signal(self, explainer):
        """Test explanation of avoid signal."""
        explanation = explainer.explain_score(
            symbol="DOGE",
            total_score=15.0,
            component_scores={"garp": 10.0, "technical": 25.0},
            asset_class="crypto"
        )

        assert explanation["grade"] == "Avoid"
        assert explanation["emoji"] == "❌"

    def test_component_breakdown(self, explainer):
        """Test component breakdown calculation."""
        explanation = explainer.explain_score(
            symbol="BTC",
            total_score=100.0,
            component_scores={"garp": 100.0, "technical": 100.0},
            asset_class="crypto"
        )

        breakdown = explanation["breakdown"]
        assert len(breakdown) == 2

        # Check GARP component
        garp_comp = next((c for c in breakdown if c["component"] == "garp"), None)
        assert garp_comp is not None
        assert garp_comp["score"] == 100.0
        assert garp_comp["weight"] == "60%"
        assert garp_comp["contribution"] == 60.0

        # Check Technical component
        tech_comp = next((c for c in breakdown if c["component"] == "technical"), None)
        assert tech_comp is not None
        assert tech_comp["score"] == 100.0
        assert tech_comp["weight"] == "40%"
        assert tech_comp["contribution"] == 40.0

    def test_drivers_and_detractors(self, explainer):
        """Test identification of drivers and detractors."""
        explanation = explainer.explain_score(
            symbol="EQ_MSFT",
            total_score=70.0,
            component_scores={"garp": 90.0, "technical": 40.0},
            asset_class="stock"
        )

        # GARP should be driver (90)
        drivers = explanation["top_drivers"]
        assert len(drivers) > 0
        assert drivers[0]["component"] == "garp"

        # Technical should be detractor (40)
        detractors = explanation["detractors"]
        assert len(detractors) > 0
        assert detractors[0]["component"] == "technical"

    def test_reasoning_generation(self, explainer):
        """Test natural language reasoning generation."""
        explanation = explainer.explain_score(
            symbol="BTC",
            total_score=75.0,
            component_scores={"garp": 80.0, "technical": 65.0},
            asset_class="crypto"
        )

        reasoning = explanation["reasoning"]
        assert "Strong Buy" in reasoning
        assert "80.0" in reasoning or "80" in reasoning

    def test_zero_score_handling(self, explainer):
        """Test handling of zero scores."""
        explanation = explainer.explain_score(
            symbol="UNKNOWN",
            total_score=0.0,
            component_scores={"garp": 0.0, "technical": 0.0},
            asset_class="crypto"
        )

        assert explanation["score"] == 0.0
        assert explanation["grade"] == "Avoid"
        assert len(explanation["breakdown"]) == 2

    def test_mixed_component_scores(self, explainer):
        """Test with mixed strong/weak components."""
        explanation = explainer.explain_score(
            symbol="EQ_TSLA",
            total_score=62.0,
            component_scores={"garp": 95.0, "technical": 15.0},
            asset_class="stock"
        )

        breakdown = explanation["breakdown"]
        garp = next(c for c in breakdown if c["component"] == "garp")
        tech = next(c for c in breakdown if c["component"] == "technical")

        assert garp["status"] == "strong"
        assert tech["status"] == "weak"

    def test_get_signal_explainer(self):
        """Test global explainer instance."""
        explainer1 = get_signal_explainer()
        explainer2 = get_signal_explainer()

        # Should return same instance
        assert explainer1 is explainer2

    def test_asset_class_differentiation(self, explainer):
        """Test that asset class is preserved in explanation."""
        crypto_exp = explainer.explain_score(
            symbol="BTC",
            total_score=60.0,
            component_scores={"garp": 0.0, "technical": 60.0},
            asset_class="crypto"
        )

        stock_exp = explainer.explain_score(
            symbol="EQ_AAPL",
            total_score=60.0,
            component_scores={"garp": 70.0, "technical": 45.0},
            asset_class="stock"
        )

        assert crypto_exp["asset_class"] == "crypto"
        assert stock_exp["asset_class"] == "stock"

    def test_component_status_calculation(self, explainer):
        """Test status calculation (strong vs weak)."""
        explanation = explainer.explain_score(
            symbol="TEST",
            total_score=80.0,
            component_scores={"garp": 80.0, "technical": 75.0},
            asset_class="crypto"
        )

        for comp in explanation["breakdown"]:
            if comp["score"] > comp["max"] * 0.7:
                assert comp["status"] == "strong"
            else:
                assert comp["status"] == "weak"
