"""Asset class definitions and multi-asset support."""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class AssetClass(str, Enum):
    """Asset classes supported by the platform."""
    CRYPTO = "crypto"           # Bitcoin, Ethereum, altcoins
    US_EQUITY = "us_equity"     # US stocks (large-cap, mid-cap, small-cap)
    EU_EQUITY = "eu_equity"     # European stocks
    ASIA_EQUITY = "asia_equity" # Asian stocks
    BOND_GOV = "bond_gov"       # Government bonds (treasury)
    BOND_CORP = "bond_corp"     # Corporate bonds
    COMMODITY = "commodity"     # Metals, energy, agriculture
    FX = "fx"                   # Currency pairs
    INDEX = "index"             # Stock indices (SPX, DAX, etc.)


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


@dataclass
class AssetProfile:
    """Asset metadata and characteristics."""
    symbol: str
    name: str
    asset_class: AssetClass
    region: Region
    sector: Optional[Sector] = None
    currency: str = "USD"
    exchange: Optional[str] = None
    liquidity_tier: str = "liquid"  # liquid, semi-liquid, illiquid
    volatility_rank: float = 0.5    # 0-1 scale, 0 = very stable, 1 = very volatile
    correlation_to_market: float = 0.5  # 0-1, correlation to broad market
    min_position_size: float = 100.0
    max_position_size: float = 1000000.0

    def to_dict(self) -> Dict:
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
            "correlation_to_market": self.correlation_to_market
        }


class AssetRegistry:
    """Registry of supported assets and their characteristics."""

    def __init__(self):
        self.assets: Dict[str, AssetProfile] = {}
        self._init_default_assets()

    def _init_default_assets(self):
        """Initialize default asset profiles."""
        # Crypto assets
        crypto_assets = [
            AssetProfile("BTC", "Bitcoin", AssetClass.CRYPTO, Region.GLOBAL, Sector.CRYPTO, "USD", "Binance", "liquid", 0.75, 0.7),
            AssetProfile("ETH", "Ethereum", AssetClass.CRYPTO, Region.GLOBAL, Sector.CRYPTO, "USD", "Binance", "liquid", 0.8, 0.75),
            AssetProfile("BNB", "Binance Coin", AssetClass.CRYPTO, Region.GLOBAL, Sector.CRYPTO, "USD", "Binance", "semi-liquid", 0.65, 0.65),
        ]

        # US Equities (large-cap)
        us_equities = [
            AssetProfile("AAPL", "Apple Inc.", AssetClass.US_EQUITY, Region.NORTH_AMERICA, Sector.TECHNOLOGY, "USD", "NASDAQ", "liquid", 0.3, 0.85),
            AssetProfile("MSFT", "Microsoft Corporation", AssetClass.US_EQUITY, Region.NORTH_AMERICA, Sector.TECHNOLOGY, "USD", "NASDAQ", "liquid", 0.3, 0.85),
            AssetProfile("GOOGL", "Alphabet Inc.", AssetClass.US_EQUITY, Region.NORTH_AMERICA, Sector.TECHNOLOGY, "USD", "NASDAQ", "liquid", 0.35, 0.85),
            AssetProfile("JPM", "JPMorgan Chase", AssetClass.US_EQUITY, Region.NORTH_AMERICA, Sector.FINANCIALS, "USD", "NYSE", "liquid", 0.25, 0.8),
            AssetProfile("JNJ", "Johnson & Johnson", AssetClass.US_EQUITY, Region.NORTH_AMERICA, Sector.HEALTHCARE, "USD", "NYSE", "liquid", 0.2, 0.75),
        ]

        # Indices
        indices = [
            AssetProfile("SPY", "S&P 500 ETF", AssetClass.INDEX, Region.NORTH_AMERICA, None, "USD", "NYSE", "liquid", 0.2, 1.0),
            AssetProfile("QQQ", "Nasdaq-100 ETF", AssetClass.INDEX, Region.NORTH_AMERICA, None, "USD", "NASDAQ", "liquid", 0.35, 1.2),
            AssetProfile("EWG", "iShares Germany ETF", AssetClass.EU_EQUITY, Region.EUROPE, None, "USD", "NYSE", "liquid", 0.3, 0.9),
        ]

        # Bonds
        bonds = [
            AssetProfile("TLT", "20+ Year Treasury ETF", AssetClass.BOND_GOV, Region.NORTH_AMERICA, None, "USD", "NASDAQ", "liquid", 0.15, 0.4),
            AssetProfile("BND", "Total Bond Market ETF", AssetClass.BOND_CORP, Region.NORTH_AMERICA, None, "USD", "NASDAQ", "liquid", 0.1, 0.3),
            AssetProfile("LQD", "Investment Grade Corporate", AssetClass.BOND_CORP, Region.NORTH_AMERICA, None, "USD", "NASDAQ", "liquid", 0.12, 0.35),
        ]

        # Commodities
        commodities = [
            AssetProfile("GLD", "SPDR Gold Shares", AssetClass.COMMODITY, Region.GLOBAL, None, "USD", "NYSE", "liquid", 0.25, 0.2),
            AssetProfile("USO", "U.S. Oil Fund", AssetClass.COMMODITY, Region.GLOBAL, None, "USD", "NYSE", "semi-liquid", 0.8, 0.5),
            AssetProfile("DBC", "Commodities Index", AssetClass.COMMODITY, Region.GLOBAL, None, "USD", "NYSE", "semi-liquid", 0.4, 0.4),
        ]

        all_assets = crypto_assets + us_equities + indices + bonds + commodities

        for asset in all_assets:
            self.register(asset)

    def register(self, profile: AssetProfile):
        """Register an asset profile."""
        self.assets[profile.symbol] = profile
        logger.debug(f"Registered asset: {profile.symbol} ({profile.asset_class.value})")

    def get(self, symbol: str) -> Optional[AssetProfile]:
        """Get asset profile by symbol."""
        return self.assets.get(symbol)

    def get_by_class(self, asset_class: AssetClass) -> List[AssetProfile]:
        """Get all assets of a specific class."""
        return [a for a in self.assets.values() if a.asset_class == asset_class]

    def get_by_region(self, region: Region) -> List[AssetProfile]:
        """Get all assets in a region."""
        return [a for a in self.assets.values() if a.region == region]

    def get_by_sector(self, sector: Sector) -> List[AssetProfile]:
        """Get all assets in a sector."""
        return [a for a in self.assets.values() if a.sector == sector]

    def get_all(self) -> List[AssetProfile]:
        """Get all registered assets."""
        return list(self.assets.values())

    def list_symbols(self) -> List[str]:
        """Get all registered symbols."""
        return list(self.assets.keys())


class AssetClassWeights:
    """Asset allocation weights by class and region."""

    def __init__(self):
        self.weights: Dict[AssetClass, float] = {
            AssetClass.CRYPTO: 0.05,              # 5% crypto
            AssetClass.US_EQUITY: 0.50,           # 50% US stocks
            AssetClass.EU_EQUITY: 0.10,           # 10% European stocks
            AssetClass.ASIA_EQUITY: 0.10,         # 10% Asian stocks
            AssetClass.BOND_GOV: 0.15,            # 15% government bonds
            AssetClass.BOND_CORP: 0.05,           # 5% corporate bonds
            AssetClass.COMMODITY: 0.05,           # 5% commodities
            AssetClass.FX: 0.00,                  # 0% FX (hedges only)
            AssetClass.INDEX: 0.00,               # 0% indices (replaced by direct holdings)
        }

    def get_weight(self, asset_class: AssetClass) -> float:
        """Get target weight for asset class."""
        return self.weights.get(asset_class, 0.0)

    def set_weight(self, asset_class: AssetClass, weight: float):
        """Set target weight for asset class."""
        if weight < 0 or weight > 1:
            raise ValueError(f"Weight must be between 0 and 1, got {weight}")
        self.weights[asset_class] = weight

    def validate(self) -> bool:
        """Validate that weights sum to approximately 1.0."""
        total = sum(self.weights.values())
        return abs(total - 1.0) < 0.01

    def get_all_weights(self) -> Dict[str, float]:
        """Get all weights as dict."""
        return {k.value: v for k, v in self.weights.items()}


class SignalWeights:
    """Signal calculation weights by asset class."""

    # Default weights for different asset classes
    DEFAULT_WEIGHTS = {
        AssetClass.CRYPTO: {
            "momentum": 0.35,
            "mean_reversion": 0.20,
            "volatility": 0.15,
            "sentiment": 0.15,
            "technical": 0.15,
        },
        AssetClass.US_EQUITY: {
            "momentum": 0.25,
            "mean_reversion": 0.25,
            "volatility": 0.10,
            "sentiment": 0.10,
            "technical": 0.30,
            "fundamentals": 0.00,
        },
        AssetClass.BOND_GOV: {
            "momentum": 0.20,
            "mean_reversion": 0.30,
            "volatility": 0.20,
            "sentiment": 0.00,
            "technical": 0.20,
            "fundamentals": 0.10,
        },
        AssetClass.COMMODITY: {
            "momentum": 0.30,
            "mean_reversion": 0.15,
            "volatility": 0.25,
            "sentiment": 0.15,
            "technical": 0.15,
            "fundamentals": 0.00,
        },
    }

    def __init__(self):
        self.weights: Dict[AssetClass, Dict[str, float]] = {}
        self._init_defaults()

    def _init_defaults(self):
        """Initialize default weights."""
        self.weights = self.DEFAULT_WEIGHTS.copy()

    def get_weights(self, asset_class: AssetClass) -> Dict[str, float]:
        """Get signal component weights for asset class."""
        return self.weights.get(asset_class, self.DEFAULT_WEIGHTS.get(AssetClass.US_EQUITY, {}))

    def set_weights(self, asset_class: AssetClass, weights: Dict[str, float]):
        """Set custom weights for asset class."""
        if abs(sum(weights.values()) - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {sum(weights.values())}")
        self.weights[asset_class] = weights


# Global asset registry instance
_asset_registry: Optional[AssetRegistry] = None


def init_asset_registry() -> AssetRegistry:
    """Initialize global asset registry."""
    global _asset_registry
    if _asset_registry is None:
        _asset_registry = AssetRegistry()
        logger.info(f"Asset registry initialized with {len(_asset_registry.list_symbols())} assets")
    return _asset_registry


def get_asset_registry() -> Optional[AssetRegistry]:
    """Get global asset registry."""
    return _asset_registry
