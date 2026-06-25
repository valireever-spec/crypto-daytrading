"""
Phase 320: Stress Test Engine

Simulate portfolio behavior under extreme market conditions (crashes, volatility spikes,
correlation breakdowns, sector rotations).
"""

import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StressScenario(str, Enum):
    """Pre-defined stress test scenarios."""

    MARKET_CRASH = "market_crash"  # -20% across all assets
    VOLATILITY_SPIKE = "volatility_spike"  # 2x normal volatility
    CORRELATION_BREAKDOWN = "correlation_breakdown"  # All assets move together
    SECTOR_ROTATION = "sector_rotation"  # Growth crashes, defensive rises
    RATE_SHOCK = "rate_shock"  # Bond-like behavior disruption
    LIQUIDITY_CRISIS = "liquidity_crisis"  # Spreads widen significantly
    CRYPTO_CRASH = "crypto_crash"  # Crypto-specific crash (-50%)
    GEOPOLITICAL = "geopolitical"  # Black swan event


@dataclass
class StressTestResult:
    """Result of a stress test scenario."""

    scenario: StressScenario
    portfolio_loss_pct: float
    affected_symbols: Dict[str, float]  # symbol → loss %
    worst_affected: str
    worst_loss_pct: float
    recovery_days_estimate: int
    leverage_requirement: float  # Additional margin needed
    risk_classification: str


class StressTestEngine:
    """Simulate portfolio under extreme conditions."""

    def __init__(self):
        """Initialize stress test engine."""
        self.scenario_definitions = self._define_scenarios()

    def _define_scenarios(self) -> Dict[StressScenario, Dict[str, Any]]:
        """Define stress test scenarios with parameters."""
        return {
            StressScenario.MARKET_CRASH: {
                "description": "Global market crash (-20%)",
                "equity_shock": -0.20,
                "crypto_shock": -0.25,
                "volatility_multiplier": 2.0,
                "duration_days": 5,
            },
            StressScenario.VOLATILITY_SPIKE: {
                "description": "Volatility spike (2x normal)",
                "equity_shock": -0.05,
                "crypto_shock": -0.10,
                "volatility_multiplier": 2.5,
                "duration_days": 10,
            },
            StressScenario.CORRELATION_BREAKDOWN: {
                "description": "Correlation rises to 0.9 (diversification fails)",
                "equity_shock": -0.10,
                "crypto_shock": -0.15,
                "volatility_multiplier": 1.5,
                "duration_days": 20,
            },
            StressScenario.SECTOR_ROTATION: {
                "description": "Tech crashes -30%, Utilities +10%",
                "tech_shock": -0.30,
                "defensive_boost": 0.10,
                "volatility_multiplier": 1.3,
                "duration_days": 15,
            },
            StressScenario.RATE_SHOCK: {
                "description": "Interest rates +200bps (bonds fall)",
                "equity_shock": -0.08,
                "bond_shock": -0.05,
                "volatility_multiplier": 1.4,
                "duration_days": 10,
            },
            StressScenario.LIQUIDITY_CRISIS: {
                "description": "Bid-ask spreads widen 10x, illiquid positions gap",
                "equity_shock": -0.03,
                "crypto_shock": -0.15,
                "spread_multiplier": 10,
                "duration_days": 3,
            },
            StressScenario.CRYPTO_CRASH: {
                "description": "Crypto-specific crash (-50%)",
                "crypto_shock": -0.50,
                "equity_shock": -0.03,
                "volatility_multiplier": 3.0,
                "duration_days": 7,
            },
            StressScenario.GEOPOLITICAL: {
                "description": "Black swan event (geopolitical crisis)",
                "equity_shock": -0.15,
                "crypto_shock": -0.20,
                "volatility_multiplier": 2.0,
                "duration_days": 5,
            },
        }

    def run_stress_test(
        self,
        position_values: Dict[str, float],  # symbol → value in EUR
        current_prices: Dict[str, float],  # symbol → price
        symbol_sectors: Dict[str, str],  # symbol → sector
        scenario: StressScenario,
    ) -> StressTestResult:
        """
        Run stress test scenario on portfolio.

        Parameters:
        -----------
        position_values : dict
            Current position values
        current_prices : dict
            Current market prices
        symbol_sectors : dict
            Symbol to sector mapping
        scenario : StressScenario
            Scenario to test

        Returns:
        --------
        StressTestResult with simulated impact
        """
        params = self.scenario_definitions[scenario]
        affected_symbols = {}
        total_loss = 0

        for symbol, value in position_values.items():
            if value <= 0:
                continue

            shock = self._calculate_shock(symbol, symbol_sectors, params)
            loss = value * shock
            affected_symbols[symbol] = shock * 100
            total_loss += loss

        portfolio_total = sum(position_values.values())
        portfolio_loss_pct = (
            (total_loss / portfolio_total * 100) if portfolio_total > 0 else 0
        )

        # Find worst affected symbol
        worst_symbol = (
            min(affected_symbols, key=affected_symbols.get)
            if affected_symbols
            else "UNKNOWN"
        )
        worst_loss = affected_symbols.get(worst_symbol, 0)

        # Estimate recovery (assuming mean reversion)
        recovery_days = self._estimate_recovery(scenario, abs(portfolio_loss_pct))

        # Leverage requirement (margin call threshold)
        leverage_req = abs(portfolio_loss_pct) / 2  # Simplified

        # Risk classification
        risk_class = self._classify_stress_risk(abs(portfolio_loss_pct))

        return StressTestResult(
            scenario=scenario,
            portfolio_loss_pct=portfolio_loss_pct,
            affected_symbols=affected_symbols,
            worst_affected=worst_symbol,
            worst_loss_pct=worst_loss,
            recovery_days_estimate=recovery_days,
            leverage_requirement=leverage_req,
            risk_classification=risk_class,
        )

    def _calculate_shock(
        self,
        symbol: str,
        symbol_sectors: Dict[str, str],
        params: Dict[str, Any],
    ) -> float:
        """Calculate shock for a symbol given scenario parameters."""
        is_crypto = symbol.startswith(("BTC", "ETH", "BNB")) or "USDT" in symbol
        is_tech = symbol_sectors.get(symbol, "other") == "technology"
        is_defensive = symbol_sectors.get(symbol, "other") in [
            "healthcare",
            "utilities",
        ]

        # Base shock
        if is_crypto:
            shock = params.get("crypto_shock", params.get("equity_shock", 0))
        elif is_tech:
            shock = params.get("tech_shock", params.get("equity_shock", 0))
        elif is_defensive:
            shock = params.get("defensive_boost", params.get("equity_shock", 0))
        else:
            shock = params.get("equity_shock", 0)

        return shock

    def _estimate_recovery(
        self,
        scenario: StressScenario,
        portfolio_loss_pct: float,
    ) -> int:
        """Estimate days to recovery from scenario."""
        # Historical recovery patterns
        recovery_patterns = {
            StressScenario.MARKET_CRASH: 60,
            StressScenario.VOLATILITY_SPIKE: 20,
            StressScenario.CORRELATION_BREAKDOWN: 30,
            StressScenario.SECTOR_ROTATION: 45,
            StressScenario.RATE_SHOCK: 25,
            StressScenario.LIQUIDITY_CRISIS: 5,
            StressScenario.CRYPTO_CRASH: 90,
            StressScenario.GEOPOLITICAL: 40,
        }

        base_recovery = recovery_patterns.get(scenario, 30)

        # Scale by severity
        severity_multiplier = max(1.0, portfolio_loss_pct / 10)

        return int(base_recovery * severity_multiplier)

    def _classify_stress_risk(self, portfolio_loss_pct: float) -> str:
        """Classify stress test risk level."""
        if portfolio_loss_pct < 5:
            return "LOW"
        elif portfolio_loss_pct < 10:
            return "MODERATE"
        elif portfolio_loss_pct < 20:
            return "HIGH"
        else:
            return "CRITICAL"

    def run_all_scenarios(
        self,
        position_values: Dict[str, float],
        current_prices: Dict[str, float],
        symbol_sectors: Dict[str, str],
    ) -> Dict[StressScenario, StressTestResult]:
        """Run all stress test scenarios."""
        results = {}

        for scenario in StressScenario:
            try:
                result = self.run_stress_test(
                    position_values=position_values,
                    current_prices=current_prices,
                    symbol_sectors=symbol_sectors,
                    scenario=scenario,
                )
                results[scenario] = result
            except Exception as e:
                logger.error(f"Error running {scenario} stress test: {e}")

        return results

    def get_worst_case_scenario(
        self,
        results: Dict[StressScenario, StressTestResult],
    ) -> Tuple[StressScenario, StressTestResult]:
        """Get worst scenario by portfolio loss."""
        if not results:
            return None, None

        worst = min(results.items(), key=lambda x: x[1].portfolio_loss_pct)
        return worst[0], worst[1]

    def get_stress_summary(
        self, results: Dict[StressScenario, StressTestResult]
    ) -> str:
        """Get human-readable stress test summary."""
        summary = "⚠️ STRESS TEST RESULTS:\n\n"

        worst_scenario, worst_result = self.get_worst_case_scenario(results)

        summary += f"Worst Case: {worst_scenario.value}\n"
        summary += f"  Portfolio Loss: {worst_result.portfolio_loss_pct:.2f}%\n"
        summary += f"  Worst Symbol: {worst_result.worst_affected} ({worst_result.worst_loss_pct:.2f}%)\n"
        summary += f"  Recovery: ~{worst_result.recovery_days_estimate} days\n"
        summary += f"  Risk: {worst_result.risk_classification}\n\n"

        summary += "All Scenarios:\n"
        for scenario, result in sorted(
            results.items(), key=lambda x: x[1].portfolio_loss_pct
        ):
            summary += f"  • {scenario.value}: {result.portfolio_loss_pct:+.2f}%\n"

        return summary


# Global instance
_stress_engine: StressTestEngine = None


def get_stress_test_engine() -> StressTestEngine:
    """Get or create stress test engine."""
    global _stress_engine
    if _stress_engine is None:
        _stress_engine = StressTestEngine()
    return _stress_engine
