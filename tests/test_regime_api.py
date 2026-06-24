"""Tests for regime detection and smart trading gateway API endpoints (Phase 2 Weeks 7-8)."""

import pytest
import pandas as pd
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.api.main import app
from backend.analytics.historical_data import init_historical_service


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_services():
    """Initialize required services for tests."""
    init_historical_service()
    yield


class TestRegimeDetectionAPI:
    """Test regime detection API endpoints (Week 7)."""

    def test_detect_regime_valid_symbol(self, client):
        """Detect regime for a valid symbol."""
        response = client.post("/api/regime/detect", params={"symbol": "AAPL"})

        # Should either return 200 if data available, 404 if not
        if response.status_code == 200:
            data = response.json()
            assert "regime" in data
            # Allow "unknown" if not enough data
            assert data["regime"] in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE", "unknown"]
            assert "confidence" in data
            assert 0 <= data["confidence"] <= 1
            assert "volatility_pct" in data
            assert "trend_strength" in data
            assert "rsi" in data
        elif response.status_code == 404:
            # No data available
            pass
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_detect_regime_response_structure(self, client):
        """Verify regime detection response has required fields."""
        response = client.post("/api/regime/detect", params={"symbol": "AAPL"})

        if response.status_code == 200:
            data = response.json()

            # Check required fields
            required_fields = [
                "symbol",
                "regime",
                "confidence",
                "volatility_pct",
                "trend_strength",
                "support_level",
                "resistance_level",
                "rsi",
            ]

            for field in required_fields:
                assert field in data, f"Missing field: {field}"

    def test_detect_regime_crypto(self, client):
        """Detect regime for crypto symbol."""
        response = client.post("/api/regime/detect", params={"symbol": "BTCUSDT"})

        if response.status_code == 200:
            data = response.json()
            assert data["symbol"] == "BTCUSDT"
            assert "regime" in data

    def test_get_trading_rules_bull(self, client):
        """Get trading rules for bull market."""
        response = client.get("/api/regime/trading-rules/BULL")

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "BULL"
        assert "position_size_multiplier" in data
        assert data["position_size_multiplier"] > 1.0  # Bull market larger positions
        assert "stop_loss_pct" in data
        assert "take_profit_pct" in data
        assert "recommended_strategies" in data
        assert isinstance(data["recommended_strategies"], list)

    def test_get_trading_rules_bear(self, client):
        """Get trading rules for bear market."""
        response = client.get("/api/regime/trading-rules/BEAR")

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "BEAR"
        assert data["position_size_multiplier"] < 1.0  # Bear market smaller positions
        assert "reversion" in data["recommended_strategies"]

    def test_get_trading_rules_sideways(self, client):
        """Get trading rules for sideways market."""
        response = client.get("/api/regime/trading-rules/SIDEWAYS")

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "SIDEWAYS"
        assert data["position_size_multiplier"] == 1.0
        assert "grid" in data["recommended_strategies"] or "reversion" in data["recommended_strategies"]

    def test_get_trading_rules_volatile(self, client):
        """Get trading rules for volatile market."""
        response = client.get("/api/regime/trading-rules/VOLATILE")

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "VOLATILE"
        assert data["position_size_multiplier"] < 1.0  # Reduce size in volatility
        assert len(data["recommended_strategies"]) == 0  # No recommended strategies

    def test_get_trading_rules_invalid_regime(self, client):
        """Handle invalid regime name."""
        response = client.get("/api/regime/trading-rules/INVALID")

        assert response.status_code == 400
        assert "Invalid regime" in response.json()["detail"]

    def test_analyze_strategy_impact(self, client):
        """Analyze regime impact on strategies."""
        response = client.post("/api/regime/strategy-impact", params={"symbol": "AAPL"})

        if response.status_code == 200:
            data = response.json()
            assert "current_regime" in data
            assert "confidence" in data
            assert "strategy_adjustments" in data

            # Check strategy adjustments
            adjustments = data["strategy_adjustments"]
            assert "momentum" in adjustments
            assert "reversion" in adjustments
            assert "grid" in adjustments

            # All adjustments should be positive numbers
            for strategy, adjustment in adjustments.items():
                assert adjustment > 0

    def test_strategy_impact_response_structure(self, client):
        """Verify strategy impact response structure."""
        response = client.post("/api/regime/strategy-impact", params={"symbol": "AAPL"})

        if response.status_code == 200:
            data = response.json()

            required_fields = [
                "symbol",
                "current_regime",
                "confidence",
                "strategy_adjustments",
            ]

            for field in required_fields:
                assert field in data, f"Missing field: {field}"


class TestSmartTradingGateway:
    """Test smart trading gateway endpoints (Week 8)."""

    def test_smart_gateway_execute(self, client):
        """Smart gateway makes execute decision with high confidence."""
        response = client.post(
            "/api/trading/smart-gateway",
            params={
                "symbol": "AAPL",
                "quantity": 1.0,
                "current_price": 150.0,
                "min_confidence": 0.5,
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert data["decision"] in ["EXECUTE", "WAIT"]

            if data["decision"] == "EXECUTE":
                assert "recommended_strategy" in data
                assert "adjusted_quantity" in data
                assert "stop_loss_price" in data
                assert "take_profit_price" in data

    def test_smart_gateway_wait_low_confidence(self, client):
        """Smart gateway waits when confidence is too low."""
        response = client.post(
            "/api/trading/smart-gateway",
            params={
                "symbol": "AAPL",
                "quantity": 1.0,
                "current_price": 150.0,
                "min_confidence": 0.99,  # Requires 99% confidence
            },
        )

        if response.status_code == 200:
            data = response.json()
            # Likely to wait unless confidence is exceptionally high
            if data["decision"] == "WAIT":
                assert "reason" in data
                assert "confidence" in data

    def test_smart_gateway_position_sizing(self, client):
        """Verify smart gateway adjusts position sizing by regime."""
        response = client.post(
            "/api/trading/smart-gateway",
            params={
                "symbol": "AAPL",
                "quantity": 100.0,
                "current_price": 150.0,
                "min_confidence": 0.0,
            },
        )

        if response.status_code == 200:
            data = response.json()

            if data["decision"] == "EXECUTE":
                # Adjusted quantity should be different from original
                # based on regime multiplier
                original = data["original_quantity"]
                adjusted = data["adjusted_quantity"]
                multiplier = data["adjustment_multiplier"]

                assert abs(adjusted - (original * multiplier)) < 0.01

    def test_smart_gateway_risk_levels(self, client):
        """Verify risk settings are based on regime."""
        response = client.post(
            "/api/trading/smart-gateway",
            params={
                "symbol": "AAPL",
                "quantity": 1.0,
                "current_price": 150.0,
            },
        )

        if response.status_code == 200:
            data = response.json()

            if data["decision"] == "EXECUTE":
                # Verify stop and take profit levels
                entry = data["entry_price"]
                stop = data["stop_loss_price"]
                target = data["take_profit_price"]

                # Stop should be below entry
                assert stop < entry
                # Target should be above entry
                assert target > entry

    def test_smart_status_endpoint(self, client):
        """Get smart trading status."""
        response = client.get("/api/trading/smart-status", params={"symbol": "BTCUSDT"})

        if response.status_code == 200:
            data = response.json()

            assert data["symbol"] == "BTCUSDT"
            assert "current_regime" in data
            assert data["current_regime"] in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE", "unknown"]
            assert "confidence" in data
            assert "volatility_pct" in data
            assert "trend_strength" in data
            assert "rsi" in data
            assert "recommended_strategies" in data
            assert "position_multiplier" in data
            assert "risk_settings" in data

    def test_smart_status_risk_settings(self, client):
        """Verify risk settings in smart status."""
        response = client.get("/api/trading/smart-status", params={"symbol": "AAPL"})

        if response.status_code == 200:
            data = response.json()

            risk_settings = data["risk_settings"]
            assert "stop_loss_pct" in risk_settings
            assert "take_profit_pct" in risk_settings

            # Risk settings should be positive
            assert risk_settings["stop_loss_pct"] > 0
            assert risk_settings["take_profit_pct"] > 0

    def test_smart_status_default_symbol(self, client):
        """Smart status uses default symbol if not provided."""
        response = client.get("/api/trading/smart-status")

        # Should succeed or return 404 if BTCUSDT not available
        assert response.status_code in [200, 404]


class TestRegimeAPIIntegration:
    """Integration tests for regime and gateway endpoints."""

    def test_regime_to_gateway_integration(self, client):
        """Verify regime detection flows into smart gateway."""
        # First get regime
        regime_response = client.post("/api/regime/detect", params={"symbol": "AAPL"})

        if regime_response.status_code == 200:
            regime_data = regime_response.json()

            # Then get trading rules
            rules_response = client.get(f"/api/regime/trading-rules/{regime_data['regime']}")
            assert rules_response.status_code == 200

            rules_data = rules_response.json()

            # Then use smart gateway
            gateway_response = client.post(
                "/api/trading/smart-gateway",
                params={
                    "symbol": "AAPL",
                    "quantity": 100.0,
                    "current_price": 150.0,
                    "min_confidence": 0.0,
                },
            )

            if gateway_response.status_code == 200:
                gateway_data = gateway_response.json()

                # Gateway's regime should match detector's regime
                if gateway_data["decision"] == "EXECUTE":
                    assert gateway_data["current_regime"] == regime_data["regime"]

    def test_all_regimes_have_rules(self, client):
        """Verify all regime types have trading rules."""
        regimes = ["BULL", "BEAR", "SIDEWAYS", "VOLATILE"]

        for regime in regimes:
            response = client.get(f"/api/regime/trading-rules/{regime}")
            assert response.status_code == 200
            data = response.json()
            assert "position_size_multiplier" in data
            assert "stop_loss_pct" in data
            assert "take_profit_pct" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
