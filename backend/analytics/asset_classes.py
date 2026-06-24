"""Asset class definitions and multi-asset support (refactored for quality)."""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import asdict, dataclass
import logging

from backend.config.asset_config import (
    AssetConfig,
    DEFAULT_ASSETS,
    CurrencyConfig,
    PortfolioOptimizationConfig,
)

logger = logging.getLogger(__name__)


class AssetClass(str, Enum):
    """Asset classes supported by the platform."""
    CRYPTO = "crypto"
    US_EQUITY = "us_equity"
    EU_EQUITY = "eu_equity"
    ASIA_EQUITY = "asia_equity"
    BOND_GOV = "bond_gov"
    BOND_CORP = "bond_corp"
    COMMODITY = "commodity"
    FX = "fx"
    INDEX = "index"


class Region(str, Enum):
    """Geographic regions."""
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    EMERGING_MARKETS = "emerging_markets"
    GLOBAL = "global"


class Sector(str, Enum):
    """Equity sectors."""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    ENERGY = "energy"
    MATERIALS = "materials"
    INDUSTRIALS = "industrials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    COMMUNICATION_SERVICES = "communication_services"
    CRYPTO = "crypto"


class InvalidAssetProfileError(ValueError):
    """Raised when AssetProfile is invalid."""
    pass


class DuplicateAssetError(ValueError):
    """Raised when attempting to register duplicate asset."""
    pass


@dataclass
class AssetProfile:
    """Asset metadata and characteristics (with validation).

    Attributes:
        symbol: Unique asset identifier (e.g., 'AAPL', 'BTC')
        name: Human-readable asset name
        asset_class: Asset classification
        region: Geographic region
        sector: Equity sector (None for bonds, commodities, etc.)
        currency: Quote currency (default: USD)
        exchange: Trading exchange or market
        liquidity_tier: Liquidity classification (liquid, semi-liquid, illiquid)
        volatility_rank: Annualized volatility (0.0-1.0)
        correlation_to_market: Correlation to broad market index (0.0-1.0)
        min_position_size: Minimum position value in USD
        max_position_size: Maximum position value in USD
    """
    symbol: str
    name: str
    asset_class: AssetClass
    region: Region
    sector: Optional[Sector] = None
    currency: str = "USD"
    exchange: Optional[str] = None
    liquidity_tier: str = "liquid"
    volatility_rank: float = 0.5
    correlation_to_market: float = 0.5
    min_position_size: float = 100.0
    max_position_size: float = 1000000.0

    def __post_init__(self) -> None:
        """Validate all fields after initialization.

        Raises:
            InvalidAssetProfileError: If any field is invalid
        """
        self.validate()

    def validate(self) -> None:
        """Validate asset profile constraints.

        Raises:
            InvalidAssetProfileError: If any field violates constraints
        """
        if not self.symbol or not isinstance(self.symbol, str):
            raise InvalidAssetProfileError(f"Invalid symbol: {self.symbol}")
        if not self.name or not isinstance(self.name, str):
            raise InvalidAssetProfileError(f"Invalid name: {self.name}")
        if not isinstance(self.asset_class, AssetClass):
            raise InvalidAssetProfileError(f"Invalid asset class: {self.asset_class}")
        if not isinstance(self.region, Region):
            raise InvalidAssetProfileError(f"Invalid region: {self.region}")
        if self.sector is not None and not isinstance(self.sector, Sector):
            raise InvalidAssetProfileError(f"Invalid sector: {self.sector}")
        if not 0 <= self.volatility_rank <= 1:
            raise InvalidAssetProfileError(f"Volatility rank must be 0-1, got {self.volatility_rank}")
        if not 0 <= self.correlation_to_market <= 1:
            raise InvalidAssetProfileError(f"Correlation must be 0-1, got {self.correlation_to_market}")
        if self.min_position_size < 0:
            raise InvalidAssetProfileError(f"Min position size cannot be negative: {self.min_position_size}")
        if self.max_position_size < self.min_position_size:
            raise InvalidAssetProfileError(
                f"Max position {self.max_position_size} < min {self.min_position_size}"
            )
        if self.liquidity_tier not in ["liquid", "semi-liquid", "illiquid"]:
            raise InvalidAssetProfileError(f"Invalid liquidity tier: {self.liquidity_tier}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert asset profile to dictionary.

        Returns:
            Dictionary representation with serialized enums
        """
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_class": self.asset_class.value,
            "region": self.region.value,
            "sector": self.sector.value if self.sector else None,
            "currency": self.currency,
            "exchange": self.exchange,
            "liquidity_tier": self.liquidity_tier,
            "volatility_rank": self.volatility_rank,
            "correlation_to_market": self.correlation_to_market,
            "min_position_size": self.min_position_size,
            "max_position_size": self.max_position_size,
        }


class AssetRegistry:
    """Registry of supported assets with validation and no global state.

    This class provides a safe, validated registry for asset profiles.
    It is instantiated explicitly - no global singleton pattern.

    Example:
        >>> registry = AssetRegistry()
        >>> btc = registry.get("BTC")
        >>> all_crypto = registry.get_by_class(AssetClass.CRYPTO)
    """

    def __init__(self, assets: Optional[List[AssetConfig]] = None) -> None:
        """Initialize asset registry.

        Args:
            assets: List of AssetConfigs. If None, uses DEFAULT_ASSETS.
                   Allows dependency injection for testing.

        Raises:
            InvalidAssetProfileError: If any default asset is invalid
        """
        self.assets: Dict[str, AssetProfile] = {}
        configs = assets if assets is not None else DEFAULT_ASSETS
        self._load_assets(configs)

    def _load_assets(self, configs: List[AssetConfig]) -> None:
        """Load and validate assets from configuration.

        Args:
            configs: List of asset configurations

        Raises:
            InvalidAssetProfileError: If any config is invalid
        """
        for config in configs:
            config.validate()
            profile = AssetProfile(
                symbol=config.symbol,
                name=config.name,
                asset_class=AssetClass(config.asset_class),
                region=Region(config.region),
                sector=Sector(config.sector) if config.sector else None,
                currency=config.currency,
                exchange=config.exchange,
                liquidity_tier=config.liquidity_tier,
                volatility_rank=config.volatility_rank,
                correlation_to_market=config.correlation_to_market,
                min_position_size=config.min_position_size_usd,
                max_position_size=config.max_position_size_usd,
            )
            self.register(profile)

    def register(self, profile: AssetProfile) -> None:
        """Register an asset profile.

        Args:
            profile: Asset profile to register

        Raises:
            DuplicateAssetError: If symbol already registered
            InvalidAssetProfileError: If profile is invalid
        """
        if not isinstance(profile, AssetProfile):
            raise InvalidAssetProfileError(f"Expected AssetProfile, got {type(profile)}")
        if profile.symbol in self.assets:
            raise DuplicateAssetError(f"Asset {profile.symbol} already registered")

        profile.validate()
        self.assets[profile.symbol] = profile
        logger.debug(f"Registered asset: {profile.symbol} ({profile.asset_class.value})")

    def get(self, symbol: str) -> Optional[AssetProfile]:
        """Get asset profile by symbol.

        Args:
            symbol: Asset symbol to look up

        Returns:
            AssetProfile if found, None otherwise
        """
        if not isinstance(symbol, str):
            logger.warning(f"Symbol must be string, got {type(symbol)}")
            return None
        return self.assets.get(symbol.upper())

    def get_by_class(self, asset_class: AssetClass) -> List[AssetProfile]:
        """Get all assets of a specific class.

        Args:
            asset_class: Asset class to filter by

        Returns:
            List of matching AssetProfiles

        Raises:
            TypeError: If asset_class is not AssetClass enum
        """
        if not isinstance(asset_class, AssetClass):
            raise TypeError(f"Expected AssetClass, got {type(asset_class)}")
        return [a for a in self.assets.values() if a.asset_class == asset_class]

    def get_by_region(self, region: Region) -> List[AssetProfile]:
        """Get all assets in a region.

        Args:
            region: Region to filter by

        Returns:
            List of matching AssetProfiles

        Raises:
            TypeError: If region is not Region enum
        """
        if not isinstance(region, Region):
            raise TypeError(f"Expected Region, got {type(region)}")
        return [a for a in self.assets.values() if a.region == region]

    def get_by_sector(self, sector: Sector) -> List[AssetProfile]:
        """Get all assets in a sector.

        Args:
            sector: Sector to filter by

        Returns:
            List of matching AssetProfiles

        Raises:
            TypeError: If sector is not Sector enum
        """
        if not isinstance(sector, Sector):
            raise TypeError(f"Expected Sector, got {type(sector)}")
        return [a for a in self.assets.values() if a.sector == sector]

    def get_all(self) -> List[AssetProfile]:
        """Get all registered assets.

        Returns:
            List of all AssetProfiles
        """
        return list(self.assets.values())

    def list_symbols(self) -> List[str]:
        """Get all registered symbols.

        Returns:
            List of asset symbols
        """
        return list(self.assets.keys())

    def __len__(self) -> int:
        """Get count of registered assets."""
        return len(self.assets)


class AssetClassWeights:
    """Asset allocation weights by class (config-driven, no global state).

    This class manages allocation targets across asset classes.
    Values loaded from configuration, not hardcoded.
    """

    def __init__(self, weights: Optional[Dict[AssetClass, float]] = None) -> None:
        """Initialize allocation weights.

        Args:
            weights: Custom weights dict. If None, uses DEFAULT_ALLOCATION_WEIGHTS.
                    Allows dependency injection for testing.
        """
        if weights is not None:
            self.weights = weights
        else:
            # Copy to avoid modifying shared config
            self.weights = {
                AssetClass(k): v
                for k, v in PortfolioOptimizationConfig.DEFAULT_ALLOCATION_WEIGHTS.items()
            }

    def get_weight(self, asset_class: AssetClass) -> float:
        """Get target weight for asset class.

        Args:
            asset_class: Asset class to look up

        Returns:
            Target weight (0.0-1.0)
        """
        if not isinstance(asset_class, AssetClass):
            raise TypeError(f"Expected AssetClass, got {type(asset_class)}")
        return self.weights.get(asset_class, 0.0)

    def set_weight(self, asset_class: AssetClass, weight: float) -> None:
        """Set target weight for asset class.

        Args:
            asset_class: Asset class to update
            weight: Target weight (0.0-1.0)

        Raises:
            TypeError: If asset_class is not AssetClass
            ValueError: If weight is outside valid range
        """
        if not isinstance(asset_class, AssetClass):
            raise TypeError(f"Expected AssetClass, got {type(asset_class)}")
        if not 0 <= weight <= 1:
            raise ValueError(f"Weight must be 0-1, got {weight}")
        self.weights[asset_class] = weight

    def validate(self) -> bool:
        """Validate that weights sum to approximately 1.0.

        Returns:
            True if valid, False otherwise
        """
        total = sum(self.weights.values())
        return abs(total - 1.0) < 0.01

    def get_all_weights(self) -> Dict[str, float]:
        """Get all weights as serializable dictionary.

        Returns:
            Dict with string keys (asset class names) and float values
        """
        return {k.value: v for k, v in self.weights.items()}


class SignalWeights:
    """Signal calculation weights by asset class (config-driven)."""

    def __init__(self, weights: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        """Initialize signal weights.

        Args:
            weights: Custom signal weights. If None, uses DEFAULT_SIGNAL_WEIGHTS.
                    Allows dependency injection for testing.
        """
        if weights is not None:
            self.weights: Dict[str, Dict[str, float]] = weights
        else:
            # Deep copy to avoid modifying shared config
            self.weights = {k: dict(v) for k, v in PortfolioOptimizationConfig.DEFAULT_SIGNAL_WEIGHTS.items()}

    def get_weights(self, asset_class: AssetClass) -> Dict[str, float]:
        """Get signal component weights for asset class.

        Args:
            asset_class: Asset class to look up

        Returns:
            Dict of signal component weights

        Raises:
            KeyError: If asset class not configured
        """
        if not isinstance(asset_class, AssetClass):
            raise TypeError(f"Expected AssetClass, got {type(asset_class)}")
        if asset_class.value not in self.weights:
            raise KeyError(f"No signal weights configured for {asset_class.value}")
        return self.weights[asset_class.value]

    def set_weights(self, asset_class: AssetClass, weights: Dict[str, float]) -> None:
        """Set custom weights for asset class.

        Args:
            asset_class: Asset class to update
            weights: Signal component weights (must sum to ~1.0)

        Raises:
            ValueError: If weights don't sum to 1.0
        """
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        self.weights[asset_class.value] = weights
