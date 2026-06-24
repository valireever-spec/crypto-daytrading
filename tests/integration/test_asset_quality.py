"""Comprehensive error case and quality tests for asset classes (Phase 336 QA)."""

import pytest
from backend.analytics.asset_classes import (
    AssetClass, Region, Sector, AssetProfile, AssetRegistry,
    InvalidAssetProfileError, DuplicateAssetError,
    AssetClassWeights, SignalWeights
)
from backend.config.asset_config import AssetConfig


class TestAssetProfileValidation:
    """Test AssetProfile validation and error cases."""

    def test_valid_profile_creation(self):
        """Test creating a valid asset profile."""
        profile = AssetProfile(
            symbol="TEST",
            name="Test Asset",
            asset_class=AssetClass.CRYPTO,
            region=Region.GLOBAL,
            volatility_rank=0.5,
            correlation_to_market=0.7
        )
        assert profile.symbol == "TEST"
        assert profile.volatility_rank == 0.5

    def test_invalid_symbol_empty(self):
        """Test that empty symbol is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL
            )

    def test_invalid_symbol_non_string(self):
        """Test that non-string symbol is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol=123,
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL
            )

    def test_invalid_name_empty(self):
        """Test that empty name is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL
            )

    def test_invalid_volatility_rank_negative(self):
        """Test that negative volatility is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                volatility_rank=-0.1
            )

    def test_invalid_volatility_rank_over_100(self):
        """Test that volatility > 1.0 is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                volatility_rank=1.5
            )

    def test_invalid_correlation_negative(self):
        """Test that negative correlation is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                correlation_to_market=-0.1
            )

    def test_invalid_position_size_negative(self):
        """Test that negative position size is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                min_position_size=-100
            )

    def test_invalid_position_size_max_less_than_min(self):
        """Test that max < min is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                min_position_size=1000,
                max_position_size=100
            )

    def test_invalid_liquidity_tier(self):
        """Test that invalid liquidity tier is rejected."""
        with pytest.raises(InvalidAssetProfileError):
            AssetProfile(
                symbol="TEST",
                name="Test",
                asset_class=AssetClass.CRYPTO,
                region=Region.GLOBAL,
                liquidity_tier="ultra-liquid"  # Invalid
            )

    def test_valid_sector_none(self):
        """Test that None sector is valid (for bonds, etc)."""
        profile = AssetProfile(
            symbol="TLT",
            name="Bond",
            asset_class=AssetClass.BOND_GOV,
            region=Region.NORTH_AMERICA,
            sector=None
        )
        assert profile.sector is None

    def test_valid_sector_provided(self):
        """Test that valid sector is accepted."""
        profile = AssetProfile(
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.US_EQUITY,
            region=Region.NORTH_AMERICA,
            sector=Sector.TECHNOLOGY
        )
        assert profile.sector == Sector.TECHNOLOGY


class TestAssetRegistryValidation:
    """Test AssetRegistry validation and error cases."""

    def test_registry_initialization(self):
        """Test registry initializes with default assets."""
        registry = AssetRegistry()
        assert len(registry) > 10
        assert registry.get("BTC") is not None

    def test_registry_custom_assets(self):
        """Test registry with custom assets."""
        configs = [
            AssetConfig(
                symbol="CUSTOM",
                name="Custom Asset",
                asset_class="crypto",
                region="global",
                sector=None,
                currency="USD",
                exchange=None,
                liquidity_tier="liquid",
                volatility_rank=0.5,
                correlation_to_market=0.5,
                min_position_size_usd=100,
                max_position_size_usd=100000
            )
        ]
        registry = AssetRegistry(assets=configs)
        assert registry.get("CUSTOM") is not None

    def test_duplicate_asset_error(self):
        """Test that duplicate registration is rejected."""
        registry = AssetRegistry()
        profile = AssetProfile(
            symbol="BTC",
            name="Bitcoin Duplicate",
            asset_class=AssetClass.CRYPTO,
            region=Region.GLOBAL
        )
        with pytest.raises(DuplicateAssetError):
            registry.register(profile)

    def test_invalid_profile_type_rejected(self):
        """Test that non-profile objects are rejected."""
        registry = AssetRegistry()
        with pytest.raises(InvalidAssetProfileError):
            registry.register({"symbol": "TEST"})

    def test_get_by_class_type_checking(self):
        """Test that get_by_class validates input type."""
        registry = AssetRegistry()
        with pytest.raises(TypeError):
            registry.get_by_class("crypto")  # String, not enum

    def test_get_by_region_type_checking(self):
        """Test that get_by_region validates input type."""
        registry = AssetRegistry()
        with pytest.raises(TypeError):
            registry.get_by_region("north_america")  # String, not enum

    def test_get_by_sector_type_checking(self):
        """Test that get_by_sector validates input type."""
        registry = AssetRegistry()
        with pytest.raises(TypeError):
            registry.get_by_sector("technology")  # String, not enum

    def test_get_symbol_case_insensitive(self):
        """Test that symbol lookup is case-insensitive."""
        registry = AssetRegistry()
        btc_upper = registry.get("BTC")
        btc_lower = registry.get("btc")
        assert btc_upper == btc_lower

    def test_get_nonexistent_returns_none(self):
        """Test that nonexistent symbols return None, not error."""
        registry = AssetRegistry()
        assert registry.get("NONEXISTENT") is None

    def test_get_invalid_symbol_type_returns_none(self):
        """Test that non-string symbol returns None safely."""
        registry = AssetRegistry()
        assert registry.get(123) is None

    def test_get_by_class_returns_correct_assets(self):
        """Test that filtering by class returns only matching assets."""
        registry = AssetRegistry()
        crypto_assets = registry.get_by_class(AssetClass.CRYPTO)
        assert all(a.asset_class == AssetClass.CRYPTO for a in crypto_assets)
        assert len(crypto_assets) > 0

    def test_empty_registry_operations(self):
        """Test operations on empty registry."""
        registry = AssetRegistry(assets=[])
        assert len(registry) == 0
        assert registry.get("BTC") is None
        assert registry.list_symbols() == []
        assert registry.get_by_class(AssetClass.CRYPTO) == []


class TestAssetClassWeights:
    """Test AssetClassWeights validation and error cases."""

    def test_default_weights_valid(self):
        """Test that default weights are valid."""
        weights = AssetClassWeights()
        assert weights.validate() is True

    def test_set_valid_weight(self):
        """Test setting a valid weight."""
        weights = AssetClassWeights()
        weights.set_weight(AssetClass.CRYPTO, 0.10)
        assert weights.get_weight(AssetClass.CRYPTO) == 0.10

    def test_set_weight_negative_rejected(self):
        """Test that negative weights are rejected."""
        weights = AssetClassWeights()
        with pytest.raises(ValueError):
            weights.set_weight(AssetClass.CRYPTO, -0.1)

    def test_set_weight_over_100_rejected(self):
        """Test that weights > 1.0 are rejected."""
        weights = AssetClassWeights()
        with pytest.raises(ValueError):
            weights.set_weight(AssetClass.CRYPTO, 1.5)

    def test_set_weight_type_checking(self):
        """Test that asset_class type is validated."""
        weights = AssetClassWeights()
        with pytest.raises(TypeError):
            weights.set_weight("crypto", 0.1)

    def test_get_weight_type_checking(self):
        """Test that asset_class type is validated in get."""
        weights = AssetClassWeights()
        with pytest.raises(TypeError):
            weights.get_weight("crypto")

    def test_get_nonexistent_weight_returns_zero(self):
        """Test that missing weights return 0.0."""
        weights = AssetClassWeights({})
        assert weights.get_weight(AssetClass.CRYPTO) == 0.0

    def test_custom_weights_initialization(self):
        """Test custom weights in constructor."""
        custom = {AssetClass.CRYPTO: 0.5, AssetClass.US_EQUITY: 0.5}
        weights = AssetClassWeights(weights=custom)
        assert weights.get_weight(AssetClass.CRYPTO) == 0.5
        assert weights.validate() is True


class TestSignalWeights:
    """Test SignalWeights validation and error cases."""

    def test_signal_weights_initialization(self):
        """Test signal weights initialize correctly."""
        weights = SignalWeights()
        crypto_weights = weights.get_weights(AssetClass.CRYPTO)
        assert "momentum" in crypto_weights
        assert abs(sum(crypto_weights.values()) - 1.0) < 0.01

    def test_get_weights_type_checking(self):
        """Test that asset_class type is validated."""
        weights = SignalWeights()
        with pytest.raises(TypeError):
            weights.get_weights("crypto")

    def test_get_weights_missing_class_error(self):
        """Test that missing asset class raises KeyError."""
        weights = SignalWeights(weights={})  # Empty weights dict
        with pytest.raises(KeyError):
            weights.get_weights(AssetClass.CRYPTO)  # crypto not in dict

    def test_set_weights_valid(self):
        """Test setting valid signal weights."""
        weights = SignalWeights()
        new_weights = {"momentum": 0.5, "technical": 0.5}
        weights.set_weights(AssetClass.CRYPTO, new_weights)
        assert weights.get_weights(AssetClass.CRYPTO) == new_weights

    def test_set_weights_sum_validation(self):
        """Test that weights must sum to 1.0."""
        weights = SignalWeights()
        invalid_weights = {"momentum": 0.5, "technical": 0.3}  # Sums to 0.8
        with pytest.raises(ValueError):
            weights.set_weights(AssetClass.CRYPTO, invalid_weights)

    def test_set_weights_allows_tolerance(self):
        """Test that weights allow ±1% tolerance."""
        weights = SignalWeights()
        # Sum to 1.005 (within 1% tolerance)
        valid_weights = {"momentum": 0.5, "technical": 0.505}
        weights.set_weights(AssetClass.CRYPTO, valid_weights)  # Should not raise
        assert weights.get_weights(AssetClass.CRYPTO) == valid_weights


class TestAssetConfigValidation:
    """Test AssetConfig validation."""

    def test_valid_config(self):
        """Test creating a valid asset config."""
        config = AssetConfig(
            symbol="TEST",
            name="Test",
            asset_class="crypto",
            region="global",
            sector=None,
            currency="USD",
            exchange=None,
            liquidity_tier="liquid",
            volatility_rank=0.5,
            correlation_to_market=0.5,
            min_position_size_usd=100,
            max_position_size_usd=100000
        )
        config.validate()  # Should not raise

    def test_invalid_symbol(self):
        """Test that invalid symbol is rejected."""
        config = AssetConfig(
            symbol="",
            name="Test",
            asset_class="crypto",
            region="global",
            sector=None,
            currency="USD",
            exchange=None,
            liquidity_tier="liquid",
            volatility_rank=0.5,
            correlation_to_market=0.5,
            min_position_size_usd=100,
            max_position_size_usd=100000
        )
        with pytest.raises(ValueError):
            config.validate()

    def test_invalid_volatility_range(self):
        """Test that volatility outside 0-1 is rejected."""
        config = AssetConfig(
            symbol="TEST",
            name="Test",
            asset_class="crypto",
            region="global",
            sector=None,
            currency="USD",
            exchange=None,
            liquidity_tier="liquid",
            volatility_rank=1.5,  # Invalid
            correlation_to_market=0.5,
            min_position_size_usd=100,
            max_position_size_usd=100000
        )
        with pytest.raises(ValueError):
            config.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
