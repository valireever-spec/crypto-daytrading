"""Configuration for multi-asset support (centralized, no hardcoded values)."""

from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class AssetConfig:
    """Configuration for an individual asset."""

    symbol: str
    name: str
    asset_class: str
    region: str
    sector: str | None
    currency: str
    exchange: str | None
    liquidity_tier: str
    volatility_rank: float
    correlation_to_market: float
    min_position_size_usd: float
    max_position_size_usd: float

    def validate(self) -> None:
        """Validate asset configuration.

        Raises:
            ValueError: If any field is invalid
        """
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError(f"Invalid symbol: {self.symbol}")
        if not self.name or not isinstance(self.name, str):
            raise ValueError(f"Invalid name: {self.name}")
        if not 0 <= self.volatility_rank <= 1:
            raise ValueError(f"Volatility rank must be 0-1, got {self.volatility_rank}")
        if not 0 <= self.correlation_to_market <= 1:
            raise ValueError(
                f"Correlation must be 0-1, got {self.correlation_to_market}"
            )
        if self.min_position_size_usd < 0:
            raise ValueError(
                f"Min position size cannot be negative: {self.min_position_size_usd}"
            )
        if self.max_position_size_usd < self.min_position_size_usd:
            raise ValueError(
                f"Max position {self.max_position_size_usd} < min {self.min_position_size_usd}"
            )
        if self.liquidity_tier not in ["liquid", "semi-liquid", "illiquid"]:
            raise ValueError(f"Invalid liquidity tier: {self.liquidity_tier}")


# Default asset configurations (loaded from here, not scattered in code)
DEFAULT_ASSETS: List[AssetConfig] = [
    # Crypto
    AssetConfig(
        "BTC",
        "Bitcoin",
        "crypto",
        "global",
        "crypto",
        "USD",
        "Binance",
        "liquid",
        0.75,
        0.7,
        100,
        1000000,
    ),
    AssetConfig(
        "ETH",
        "Ethereum",
        "crypto",
        "global",
        "crypto",
        "USD",
        "Binance",
        "liquid",
        0.8,
        0.75,
        100,
        1000000,
    ),
    AssetConfig(
        "BNB",
        "Binance Coin",
        "crypto",
        "global",
        "crypto",
        "USD",
        "Binance",
        "semi-liquid",
        0.65,
        0.65,
        100,
        500000,
    ),
    # US Equities
    AssetConfig(
        "AAPL",
        "Apple Inc.",
        "us_equity",
        "north_america",
        "technology",
        "USD",
        "NASDAQ",
        "liquid",
        0.3,
        0.85,
        100,
        1000000,
    ),
    AssetConfig(
        "MSFT",
        "Microsoft Corporation",
        "us_equity",
        "north_america",
        "technology",
        "USD",
        "NASDAQ",
        "liquid",
        0.3,
        0.85,
        100,
        1000000,
    ),
    AssetConfig(
        "GOOGL",
        "Alphabet Inc.",
        "us_equity",
        "north_america",
        "technology",
        "USD",
        "NASDAQ",
        "liquid",
        0.35,
        0.85,
        100,
        1000000,
    ),
    AssetConfig(
        "JPM",
        "JPMorgan Chase",
        "us_equity",
        "north_america",
        "financials",
        "USD",
        "NYSE",
        "liquid",
        0.25,
        0.8,
        100,
        500000,
    ),
    AssetConfig(
        "JNJ",
        "Johnson & Johnson",
        "us_equity",
        "north_america",
        "healthcare",
        "USD",
        "NYSE",
        "liquid",
        0.2,
        0.75,
        100,
        500000,
    ),
    # Indices
    AssetConfig(
        "SPY",
        "S&P 500 ETF",
        "index",
        "north_america",
        None,
        "USD",
        "NYSE",
        "liquid",
        0.2,
        1.0,
        100,
        1000000,
    ),
    AssetConfig(
        "QQQ",
        "Nasdaq-100 ETF",
        "index",
        "north_america",
        None,
        "USD",
        "NASDAQ",
        "liquid",
        0.35,
        0.95,
        100,
        1000000,
    ),
    AssetConfig(
        "EWG",
        "iShares Germany ETF",
        "index",
        "europe",
        None,
        "USD",
        "NYSE",
        "liquid",
        0.3,
        0.8,
        100,
        500000,
    ),
    # Bonds
    AssetConfig(
        "TLT",
        "20+ Year Treasury ETF",
        "bond_gov",
        "north_america",
        None,
        "USD",
        "NASDAQ",
        "liquid",
        0.15,
        0.4,
        100,
        1000000,
    ),
    AssetConfig(
        "BND",
        "Total Bond Market ETF",
        "bond_corp",
        "north_america",
        None,
        "USD",
        "NASDAQ",
        "liquid",
        0.1,
        0.3,
        100,
        1000000,
    ),
    AssetConfig(
        "LQD",
        "Investment Grade Corporate",
        "bond_corp",
        "north_america",
        None,
        "USD",
        "NASDAQ",
        "liquid",
        0.12,
        0.35,
        100,
        500000,
    ),
    # Commodities
    AssetConfig(
        "GLD",
        "SPDR Gold Shares",
        "commodity",
        "global",
        None,
        "USD",
        "NYSE",
        "liquid",
        0.25,
        0.2,
        100,
        500000,
    ),
    AssetConfig(
        "USO",
        "U.S. Oil Fund",
        "commodity",
        "global",
        None,
        "USD",
        "NYSE",
        "semi-liquid",
        0.8,
        0.5,
        100,
        250000,
    ),
    AssetConfig(
        "DBC",
        "Commodities Index",
        "commodity",
        "global",
        None,
        "USD",
        "NYSE",
        "semi-liquid",
        0.4,
        0.4,
        100,
        250000,
    ),
]


class CurrencyConfig:
    """Currency configuration and rates."""

    # FX rates vs USD (loaded from config, not hardcoded in code)
    DEFAULT_RATES: Dict[str, float] = {
        "USD": 1.0,
        "EUR": 1.08,
        "GBP": 1.25,
        "JPY": 0.0067,
        "CHF": 1.10,
        "CAD": 0.74,
        "AUD": 0.67,
        "SGD": 0.75,
        "HKD": 0.128,
        "CNY": 0.138,
    }

    # Currency volatilities (annualized)
    DEFAULT_VOLATILITIES: Dict[str, float] = {
        "EUR": 0.10,
        "GBP": 0.12,
        "JPY": 0.08,
        "CHF": 0.09,
        "CAD": 0.07,
        "AUD": 0.13,
        "SGD": 0.06,
        "HKD": 0.05,
        "CNY": 0.08,
    }

    # FX pair correlations
    DEFAULT_CORRELATIONS: Dict[Tuple[str, str], float] = {
        ("EUR", "GBP"): 0.75,
        ("EUR", "JPY"): -0.30,
        ("EUR", "CHF"): 0.85,
        ("GBP", "JPY"): -0.25,
        ("GBP", "CHF"): 0.70,
        ("JPY", "CHF"): -0.20,
        ("USD", "JPY"): -0.10,
        ("USD", "EUR"): -0.80,
        ("USD", "GBP"): -0.70,
        ("USD", "CHF"): 0.50,
    }


class PortfolioOptimizationConfig:
    """Configuration for portfolio optimization."""

    # Risk-free rate (for Sharpe ratio calculation)
    RISK_FREE_RATE: float = 0.02

    # Transaction cost as percentage of notional (0.1% = 0.001)
    TRANSACTION_COST_PCT: float = 0.001

    # Default allocation weights by asset class
    DEFAULT_ALLOCATION_WEIGHTS: Dict[str, float] = {
        "crypto": 0.05,
        "us_equity": 0.50,
        "eu_equity": 0.10,
        "asia_equity": 0.10,
        "bond_gov": 0.15,
        "bond_corp": 0.05,
        "commodity": 0.05,
        "fx": 0.00,
        "index": 0.00,
    }

    # Signal component weights by asset class
    DEFAULT_SIGNAL_WEIGHTS: Dict[str, Dict[str, float]] = {
        "crypto": {
            "momentum": 0.35,
            "mean_reversion": 0.20,
            "volatility": 0.15,
            "sentiment": 0.15,
            "technical": 0.15,
        },
        "us_equity": {
            "momentum": 0.25,
            "mean_reversion": 0.25,
            "volatility": 0.10,
            "sentiment": 0.10,
            "technical": 0.30,
            "fundamentals": 0.00,
        },
        "bond_gov": {
            "momentum": 0.20,
            "mean_reversion": 0.30,
            "volatility": 0.20,
            "sentiment": 0.00,
            "technical": 0.20,
            "fundamentals": 0.10,
        },
        "commodity": {
            "momentum": 0.30,
            "mean_reversion": 0.15,
            "volatility": 0.25,
            "sentiment": 0.15,
            "technical": 0.15,
            "fundamentals": 0.00,
        },
    }
