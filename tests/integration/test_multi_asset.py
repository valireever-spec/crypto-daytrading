"""Integration tests for Phase 336: Multi-Asset Support."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.analytics.asset_classes import (
    AssetRegistry,
    AssetClass,
    Region,
    AssetProfile,
    AssetClassWeights,
    SignalWeights
)
from backend.analytics.currency_risk import CurrencyRiskCalculator, CurrencyExposure
from backend.analytics.global_optimization import GlobalPortfolioOptimizer


class TestAssetRegistry:
    """Test asset registry functionality."""

    def test_asset_registry_initialization(self):
        """Test registry initializes with default assets."""
        registry = AssetRegistry()

        assert registry is not None
        all_assets = registry.get_all()
        assert len(all_assets) > 10  # Should have at least 10 default assets

    def test_list_symbols(self):
        """Test listing all symbols."""
        registry = AssetRegistry()

        symbols = registry.list_symbols()
        assert "BTC" in symbols
        assert "AAPL" in symbols
        assert "SPY" in symbols

    def test_get_asset(self):
        """Test getting asset by symbol."""
        registry = AssetRegistry()

        btc = registry.get("BTC")
        assert btc is not None
        assert btc.name == "Bitcoin"
        assert btc.asset_class == AssetClass.CRYPTO

    def test_get_assets_by_class(self):
        """Test filtering assets by class."""
        registry = AssetRegistry()

        crypto = registry.get_by_class(AssetClass.CRYPTO)
        assert len(crypto) > 0
        assert all(a.asset_class == AssetClass.CRYPTO for a in crypto)

        equities = registry.get_by_class(AssetClass.US_EQUITY)
        assert len(equities) > 0

    def test_get_assets_by_region(self):
        """Test filtering assets by region."""
        registry = AssetRegistry()

        na_assets = registry.get_by_region(Region.NORTH_AMERICA)
        assert len(na_assets) > 0

        eu_assets = registry.get_by_region(Region.EUROPE)
        assert len(eu_assets) > 0

    def test_register_new_asset(self):
        """Test registering a new asset."""
        registry = AssetRegistry()
        initial_count = len(registry.get_all())

        new_asset = AssetProfile(
            "TEST",
            "Test Asset",
            AssetClass.US_EQUITY,
            Region.NORTH_AMERICA
        )
        registry.register(new_asset)

        assert registry.get("TEST") == new_asset
        assert len(registry.get_all()) == initial_count + 1


class TestAssetClassWeights:
    """Test asset allocation weights."""

    def test_asset_class_weights_initialization(self):
        """Test weights initialize with defaults."""
        weights = AssetClassWeights()

        assert weights.get_weight(AssetClass.CRYPTO) == 0.05
        assert weights.get_weight(AssetClass.US_EQUITY) == 0.50

    def test_weights_validation(self):
        """Test weights validate to ~1.0."""
        weights = AssetClassWeights()

        assert weights.validate() is True

    def test_set_custom_weights(self):
        """Test setting custom weights."""
        weights = AssetClassWeights()

        weights.set_weight(AssetClass.CRYPTO, 0.10)
        assert weights.get_weight(AssetClass.CRYPTO) == 0.10

    def test_invalid_weight(self):
        """Test invalid weights are rejected."""
        weights = AssetClassWeights()

        with pytest.raises(ValueError):
            weights.set_weight(AssetClass.CRYPTO, 1.5)

        with pytest.raises(ValueError):
            weights.set_weight(AssetClass.CRYPTO, -0.1)


class TestSignalWeights:
    """Test signal component weights by asset class."""

    def test_signal_weights_crypto(self):
        """Test crypto signal weights."""
        weights = SignalWeights()

        crypto_weights = weights.get_weights(AssetClass.CRYPTO)
        assert "momentum" in crypto_weights
        assert "technical" in crypto_weights
        assert "sentiment" in crypto_weights

    def test_signal_weights_equity(self):
        """Test equity signal weights."""
        weights = SignalWeights()

        eq_weights = weights.get_weights(AssetClass.US_EQUITY)
        assert "momentum" in eq_weights
        assert "technical" in eq_weights
        assert "fundamentals" in eq_weights

    def test_signal_weights_sum(self):
        """Test signal weights sum to 1.0."""
        weights = SignalWeights()

        for asset_class in [AssetClass.CRYPTO, AssetClass.US_EQUITY, AssetClass.BOND_GOV]:
            w = weights.get_weights(asset_class)
            assert abs(sum(w.values()) - 1.0) < 0.01


class TestCurrencyRisk:
    """Test currency risk calculations."""

    def test_currency_conversion(self):
        """Test currency conversions."""
        calc = CurrencyRiskCalculator()

        usd_amount = calc.convert_to_usd(100, "EUR")
        assert usd_amount > 100  # EUR to USD should increase amount

        eur_amount = calc.convert_from_usd(100, "EUR")
        assert eur_amount < 100  # USD to EUR should decrease amount

    def test_currency_exposure(self):
        """Test calculating currency exposure."""
        calc = CurrencyRiskCalculator()

        positions = {
            "AAPL": {"currency": "USD", "value": 50000},
            "SAP": {"currency": "EUR", "value": 30000},
        }

        exposures = calc.calculate_currency_exposure(positions)
        assert "USD" in exposures
        assert "EUR" in exposures

    def test_currency_var(self):
        """Test currency VaR calculation."""
        calc = CurrencyRiskCalculator()

        var = calc.calculate_currency_var(100000, "EUR", confidence=0.95)
        assert var > 0

    def test_hedge_suggestions(self):
        """Test hedge recommendations."""
        calc = CurrencyRiskCalculator()

        exposures = {
            "EUR": CurrencyExposure("EUR", 100000, 50),
            "GBP": CurrencyExposure("GBP", 50000, 25),
        }

        suggestions = calc.suggest_hedges(exposures)
        assert len(suggestions) > 0

    def test_correlation_matrix(self):
        """Test FX correlation matrix."""
        calc = CurrencyRiskCalculator()

        currencies = ["EUR", "GBP", "JPY"]
        corr = calc.calculate_correlation_matrix(currencies)

        assert len(corr) == 9  # 3x3 matrix
        assert corr[("EUR", "EUR")] == 1.0
        assert corr[("EUR", "GBP")] > 0


class TestGlobalOptimization:
    """Test global portfolio optimization."""

    def test_optimizer_initialization(self):
        """Test optimizer initializes."""
        optimizer = GlobalPortfolioOptimizer()

        assert optimizer is not None

    def test_set_expected_returns(self):
        """Test setting expected returns."""
        optimizer = GlobalPortfolioOptimizer()

        returns = {
            "crypto": 0.25,
            "us_equity": 0.10,
            "bonds": 0.03
        }
        optimizer.set_expected_returns(returns)

        assert len(optimizer.expected_returns) == 3

    def test_set_volatilities(self):
        """Test setting volatilities."""
        optimizer = GlobalPortfolioOptimizer()

        vols = {
            "crypto": 0.70,
            "us_equity": 0.15,
            "bonds": 0.05
        }
        optimizer.set_volatilities(vols)

        assert len(optimizer.volatilities) == 3

    def test_add_constraint(self):
        """Test adding constraints."""
        from backend.analytics.global_optimization import OptimizationConstraint

        optimizer = GlobalPortfolioOptimizer()

        constraint = OptimizationConstraint("crypto", min_weight=0.0, max_weight=0.1)
        optimizer.add_constraint(constraint)

        assert len(optimizer.constraints) > 0

    def test_efficient_frontier(self):
        """Test efficient frontier calculation."""
        optimizer = GlobalPortfolioOptimizer()

        optimizer.set_expected_returns({
            "crypto": 0.25,
            "equity": 0.10,
            "bonds": 0.03
        })
        optimizer.set_volatilities({
            "crypto": 0.70,
            "equity": 0.15,
            "bonds": 0.05
        })

        frontier = optimizer.calculate_efficient_frontier(num_points=10)
        assert len(frontier) == 10

    def test_optimal_portfolio(self):
        """Test finding optimal portfolio."""
        optimizer = GlobalPortfolioOptimizer()

        optimizer.set_expected_returns({
            "crypto": 0.25,
            "equity": 0.10,
            "bonds": 0.03
        })
        optimizer.set_volatilities({
            "crypto": 0.70,
            "equity": 0.15,
            "bonds": 0.05
        })

        result = optimizer.find_optimal_portfolio()
        assert "weights" in result
        assert "expected_return" in result
        assert "risk" in result
        assert "sharpe_ratio" in result

    def test_rebalancing_plan(self):
        """Test rebalancing plan calculation."""
        optimizer = GlobalPortfolioOptimizer()

        current = {"crypto": 0.20, "equity": 0.50, "bonds": 0.30}
        target = {"crypto": 0.10, "equity": 0.60, "bonds": 0.30}

        plan = optimizer.calculate_rebalancing_plan(current, target, 100000)
        assert "trades" in plan
        assert "total_transaction_cost" in plan


class TestMultiAssetAPI:
    """Test multi-asset API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup multi-asset services."""
        AssetRegistry()
        CurrencyRiskCalculator()
        GlobalPortfolioOptimizer()
        yield

    def test_list_all_assets(self, client):
        """Test listing all assets."""
        response = client.get("/api/multi-asset/assets")
        assert response.status_code == 200
        data = response.json()

        assert 'total' in data
        assert 'assets' in data
        assert data['total'] > 0

    def test_list_assets_by_class(self, client):
        """Test filtering by asset class."""
        response = client.get("/api/multi-asset/assets/by-class/crypto")
        assert response.status_code == 200
        data = response.json()

        assert data['asset_class'] == 'crypto'
        assert 'assets' in data

    def test_list_assets_by_region(self, client):
        """Test filtering by region."""
        response = client.get("/api/multi-asset/assets/by-region/north_america")
        assert response.status_code == 200
        data = response.json()

        assert data['region'] == 'north_america'
        assert 'assets' in data

    def test_get_asset_details(self, client):
        """Test getting asset details."""
        response = client.get("/api/multi-asset/assets/BTC")
        assert response.status_code == 200
        data = response.json()

        assert data['symbol'] == 'BTC'
        assert 'name' in data
        assert 'asset_class' in data

    def test_recommended_allocation(self, client):
        """Test getting recommended allocation."""
        response = client.get("/api/multi-asset/allocation/recommended")
        assert response.status_code == 200
        data = response.json()

        assert 'allocation' in data
        assert 'valid' in data

    def test_signal_weights(self, client):
        """Test getting signal weights."""
        response = client.get("/api/multi-asset/allocation/signal-weights/crypto")
        assert response.status_code == 200
        data = response.json()

        assert data['asset_class'] == 'crypto'
        assert 'signal_weights' in data

    def test_currency_exposure(self, client):
        """Test currency exposure calculation."""
        response = client.get("/api/multi-asset/currency/exposure")
        assert response.status_code == 200
        data = response.json()

        assert 'exposures' in data

    def test_currency_var(self, client):
        """Test currency VaR calculation."""
        response = client.get("/api/multi-asset/currency/var?currency=EUR")
        assert response.status_code == 200
        data = response.json()

        assert 'currency' in data
        assert 'var_usd' in data

    def test_efficient_frontier(self, client):
        """Test efficient frontier calculation."""
        response = client.get("/api/multi-asset/optimization/efficient-frontier")
        assert response.status_code == 200
        data = response.json()

        assert 'frontier' in data
        assert 'points' in data

    def test_optimal_portfolio(self, client):
        """Test optimal portfolio calculation."""
        response = client.get("/api/multi-asset/optimization/optimal-portfolio")
        assert response.status_code == 200
        data = response.json()

        assert 'weights' in data
        assert 'expected_return' in data
        assert 'risk' in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
