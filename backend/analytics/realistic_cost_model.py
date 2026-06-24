"""
Phase 328: Realistic Cost Model

Accurate execution cost estimation by symbol liquidity tier.
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
import json
from pathlib import Path

logger = logging.getLogger(__name__)

TIERS_CONFIG_FILE = Path("config/cost_model_tiers.json")


@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""
    execution_cost_pct: float  # Bid-ask spread
    slippage_cost_pct: float  # Volume impact
    tax_cost_pct: float  # Realized gains tax
    total_cost_pct: float
    cost_tier: str  # Crypto, Equity, Bond, etc.


class RealisticCostModel:
    """Calculate realistic execution costs by symbol type."""

    # Liquidity tiers: (execution_bps, slippage_basis_points_per_pct)
    LIQUIDITY_TIERS = {
        "crypto_major": (1.0, 0.5),  # BTC, ETH: 1 bp, 0.5 bp per % traded
        "crypto_alt": (5.0, 2.0),  # Altcoins: 5 bp, 2 bp per %
        "equity_large_cap": (2.0, 0.3),  # AAPL, MSFT: 2 bp, 0.3 bp per %
        "equity_mid_cap": (4.0, 0.8),  # Mid-caps: 4 bp, 0.8 bp per %
        "equity_small_cap": (8.0, 2.0),  # Small-caps: 8 bp, 2 bp per %
        "bond": (3.0, 0.5),  # Bonds: 3 bp, 0.5 bp per %
        "etf": (1.5, 0.4),  # ETFs: 1.5 bp, 0.4 bp per %
    }

    # Symbol to tier mapping
    SYMBOL_TIERS = {
        # Crypto
        "BTCUSDT": "crypto_major",
        "ETHUSDT": "crypto_major",
        "BNBUSDT": "crypto_alt",
        # Large-cap equities
        "EQ_AAPL": "equity_large_cap",
        "EQ_MSFT": "equity_large_cap",
        "EQ_GOOGL": "equity_large_cap",
        "EQ_AMZN": "equity_large_cap",
        "EQ_NVDA": "equity_large_cap",
        # Mid-cap equities
        "EQ_PYPL": "equity_mid_cap",
        "EQ_SQ": "equity_mid_cap",
        # Bonds (example)
        "BOND_US10Y": "bond",
        "BOND_EUROBUND": "bond",
        # ETFs (example)
        "ETF_SPY": "etf",
        "ETF_QQQ": "etf",
    }

    # Tax rates by jurisdiction (simplified)
    TAX_RATES = {
        "Germany": 0.27,  # Abgeltungsteuer
        "USA": 0.20,  # Long-term capital gains
        "EU": 0.19,  # Average across EU
    }

    def __init__(self, jurisdiction: str = "Germany", realized_gains_rate: float = 0.3):
        """
        Initialize cost model.

        Parameters:
        -----------
        jurisdiction : str
            Tax jurisdiction for cost calculation
        realized_gains_rate : float
            Proportion of sells that realize gains (0-1)
        """
        self.jurisdiction = jurisdiction
        self.realized_gains_rate = realized_gains_rate
        self.tax_rate = self.TAX_RATES.get(jurisdiction, 0.27)

        # Load symbol tiers from config if available
        custom_tiers = self._load_symbol_tiers_from_config()
        if custom_tiers:
            self.SYMBOL_TIERS.update(custom_tiers)
            logger.info(f"Loaded {len(custom_tiers)} custom symbol tiers from config")

    def get_symbol_tier(self, symbol: str) -> str:
        """Get liquidity tier for symbol."""
        tier = self.SYMBOL_TIERS.get(symbol, "equity_mid_cap")  # Default to mid-cap
        return tier

    def estimate_execution_cost(
        self,
        symbol: str,
        volume_pct: float,  # % of portfolio traded
    ) -> float:
        """
        Estimate execution cost (bid-ask + slippage).

        Parameters:
        -----------
        symbol : str
            Trading symbol
        volume_pct : float
            Volume as % of portfolio

        Returns:
        --------
        Execution cost as %
        """
        tier = self.get_symbol_tier(symbol)
        execution_bps, slippage_bps_per_pct = self.LIQUIDITY_TIERS.get(
            tier, (4.0, 0.8)
        )

        # Base execution cost + volume impact
        execution_cost = (execution_bps + slippage_bps_per_pct * volume_pct) / 10000

        return execution_cost * 100

    def estimate_tax_cost(
        self,
        sell_volume_pct: float,  # % of portfolio sold
    ) -> float:
        """
        Estimate tax cost from realized gains.

        Parameters:
        -----------
        sell_volume_pct : float
            Volume sold as % of portfolio

        Returns:
        --------
        Tax cost as %
        """
        # Tax applies to portion of sells that realize gains
        taxable_volume = sell_volume_pct * self.realized_gains_rate
        tax_cost = (taxable_volume * self.tax_rate) / 100

        return tax_cost

    def estimate_slippage(
        self,
        symbol: str,
        volume_pct: float,
    ) -> float:
        """
        Estimate slippage cost.

        Parameters:
        -----------
        symbol : str
            Trading symbol
        volume_pct : float
            Volume as % of portfolio

        Returns:
        --------
        Slippage cost as %
        """
        tier = self.get_symbol_tier(symbol)
        _, slippage_bps_per_pct = self.LIQUIDITY_TIERS.get(tier, (4.0, 0.8))

        slippage = (slippage_bps_per_pct * volume_pct) / 10000
        return slippage * 100

    def estimate_total_cost(
        self,
        trades: list,  # [(symbol, side, volume_pct)]
    ) -> Dict[str, CostBreakdown]:
        """
        Estimate total costs for a set of trades.

        Parameters:
        -----------
        trades : list
            List of (symbol, side, volume_pct) tuples

        Returns:
        --------
        {symbol: CostBreakdown}
        """
        results = {}

        for symbol, side, volume_pct in trades:
            tier = self.get_symbol_tier(symbol)

            # Execution + slippage
            execution_bps, slippage_bps_per_pct = self.LIQUIDITY_TIERS.get(
                tier, (4.0, 0.8)
            )
            exec_cost = (execution_bps + slippage_bps_per_pct * volume_pct) / 10000
            slippage_cost = (slippage_bps_per_pct * volume_pct) / 10000

            # Tax (only on sells)
            if side == "SELL":
                tax_cost = (volume_pct * self.realized_gains_rate * self.tax_rate) / 100
            else:
                tax_cost = 0.0

            total = (exec_cost + slippage_cost + tax_cost) * 100

            results[symbol] = CostBreakdown(
                execution_cost_pct=exec_cost * 100,
                slippage_cost_pct=slippage_cost * 100,
                tax_cost_pct=tax_cost,
                total_cost_pct=total,
                cost_tier=tier,
            )

        return results

    def adjust_for_market_conditions(
        self,
        base_execution_bps: float,
        volatility_pct: float,
        spread_pct: float = 0.0,
    ) -> float:
        """
        Adjust execution cost based on market conditions.

        Parameters:
        -----------
        base_execution_bps : float
            Base execution cost in bps
        volatility_pct : float
            Current market volatility (%)
        spread_pct : float
            Bid-ask spread increase (%)

        Returns:
        --------
        Adjusted execution cost
        """
        # Higher volatility = higher costs
        volatility_multiplier = 1.0 + (volatility_pct - 15.0) * 0.01  # 1x at 15% vol
        volatility_multiplier = max(0.8, min(2.0, volatility_multiplier))  # Clamp to [0.8, 2.0]

        # Direct spread impact
        spread_multiplier = 1.0 + spread_pct

        adjusted_cost = base_execution_bps * volatility_multiplier * spread_multiplier
        return adjusted_cost

    def _load_symbol_tiers_from_config(self) -> Dict[str, str]:
        """Load custom symbol-to-tier mappings from config file."""
        if not TIERS_CONFIG_FILE.exists():
            return {}

        try:
            data = json.loads(TIERS_CONFIG_FILE.read_text())
            return data.get("symbol_tiers", {})
        except Exception as e:
            logger.warning(f"Failed to load symbol tiers config: {e}")
            return {}


# Global instance
_cost_model: RealisticCostModel = None


def get_cost_model() -> RealisticCostModel:
    """Get or create cost model."""
    global _cost_model
    if _cost_model is None:
        _cost_model = RealisticCostModel()
    return _cost_model
