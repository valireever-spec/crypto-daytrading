"""Portfolio-level risk orchestration and coordination (Phase 3 Week 3)."""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from backend.execution.smart_executor import SmartExecutor
from backend.execution.exit_manager import ExitManager
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""

    total_position_value: float
    total_positions: int
    total_capital: float
    capital_utilization_pct: float
    max_single_position_pct: float
    sector_concentration: Dict[str, float] = field(default_factory=dict)
    average_holding_time_hours: float = 0.0
    portfolio_volatility_pct: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_pct: float = 0.0
    risk_score: float = 0.0  # 0-100, higher = riskier
    status: str = "HEALTHY"  # HEALTHY, CAUTION, WARNING, CRITICAL


@dataclass
class PortfolioAction:
    """Recommended portfolio action."""

    action_type: str  # REDUCE, REBALANCE, ENTER, EXIT, HOLD
    symbol: str
    quantity: float
    reason: str
    urgency: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL


class PortfolioOrchestrator:
    """Coordinate multi-position risk management at portfolio level."""

    def __init__(
        self,
        max_positions: int = 5,
        max_position_pct: float = 0.20,
        max_sector_pct: float = 0.40,
        max_correlation: float = 0.7,
    ):
        """Initialize portfolio orchestrator.

        Args:
            max_positions: Maximum concurrent positions
            max_position_pct: Maximum size for single position (% of capital)
            max_sector_pct: Maximum concentration in single sector
            max_correlation: Maximum correlation threshold for positions
        """
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_correlation = max_correlation

        self.executor = SmartExecutor(max_position_pct=max_position_pct)
        self.exit_manager = ExitManager()
        self.suggested_actions: List[PortfolioAction] = []

    def get_portfolio_metrics(
        self, current_prices: Dict[str, float]
    ) -> PortfolioRiskMetrics:
        """Calculate portfolio-level risk metrics.

        Args:
            current_prices: Dict mapping symbol to current price

        Returns:
            PortfolioRiskMetrics with health assessment
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return self._default_metrics()

            account = engine.get_account_state()
            total_capital = account.get("total_equity", 100000)
            available_cash = account.get("cash", 0)
            positions = engine.get_positions()

            # Calculate position metrics
            total_position_value = 0.0
            max_single_position_pct = 0.0
            position_values = {}

            for pos in positions:
                symbol = pos.get("symbol")
                qty = pos.get("quantity", 0)
                entry_price = pos.get("entry_price", 0)

                if symbol in current_prices:
                    current_price = current_prices[symbol]
                    position_value = qty * current_price
                    total_position_value += position_value
                    position_values[symbol] = position_value

                    position_pct = (position_value / total_capital) * 100
                    max_single_position_pct = max(max_single_position_pct, position_pct)

            # Calculate utilization
            capital_utilization = (total_position_value / total_capital) * 100

            # Calculate PnL
            total_pnl_usd = 0.0
            for pos in positions:
                symbol = pos.get("symbol")
                if symbol in current_prices:
                    qty = pos.get("quantity", 0)
                    entry_price = pos.get("entry_price", 0)
                    current_price = current_prices[symbol]
                    pnl = qty * (current_price - entry_price)
                    total_pnl_usd += pnl

            total_pnl_pct = (total_pnl_usd / total_capital) * 100

            # Calculate risk score (0-100)
            risk_score = self._calculate_risk_score(
                capital_utilization,
                len(positions),
                max_single_position_pct,
                total_pnl_pct,
            )

            # Determine status
            if risk_score >= 80:
                status = "CRITICAL"
            elif risk_score >= 60:
                status = "WARNING"
            elif risk_score >= 40:
                status = "CAUTION"
            else:
                status = "HEALTHY"

            return PortfolioRiskMetrics(
                total_position_value=round(total_position_value, 2),
                total_positions=len(positions),
                total_capital=round(total_capital, 2),
                capital_utilization_pct=round(capital_utilization, 2),
                max_single_position_pct=round(max_single_position_pct, 2),
                average_holding_time_hours=0.0,  # Would calculate from positions
                portfolio_volatility_pct=0.0,  # Would calculate from returns
                total_pnl_usd=round(total_pnl_usd, 2),
                total_pnl_pct=round(total_pnl_pct, 2),
                risk_score=round(risk_score, 1),
                status=status,
            )

        except Exception as e:
            logger.error(f"Portfolio metrics error: {e}")
            return self._default_metrics()

    def evaluate_new_entry(
        self,
        symbol: str,
        quantity: float,
        current_price: float,
        regime: str,
    ) -> Dict:
        """Evaluate if new position fits within portfolio constraints.

        Args:
            symbol: Trading symbol
            quantity: Proposed quantity
            current_price: Current price
            regime: Current market regime

        Returns:
            Dict with evaluation result and constraints violated
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return {"approved": False, "reason": "Trading engine not initialized"}

            account = engine.get_account_state()
            positions = engine.get_positions()
            total_capital = account.get("total_equity", 100000)

            constraints_violated = []

            # Check 1: Position count limit
            if len(positions) >= self.max_positions:
                constraints_violated.append(
                    f"Max positions ({self.max_positions}) already filled"
                )

            # Check 2: Position size limit
            position_value = quantity * current_price
            position_pct = (position_value / total_capital) * 100
            if position_pct > self.max_position_pct * 100:
                constraints_violated.append(
                    f"Position size {position_pct:.1f}% exceeds limit {self.max_position_pct*100:.1f}%"
                )

            # Check 3: Existing position
            existing = next((p for p in positions if p.get("symbol") == symbol), None)
            if existing:
                constraints_violated.append(f"Already have position in {symbol}")

            # Check 4: Capital available
            available_cash = account.get("cash", 0)
            if position_value > available_cash:
                constraints_violated.append(
                    f"Insufficient cash: need ${position_value:.2f}, have ${available_cash:.2f}"
                )

            if constraints_violated:
                return {
                    "approved": False,
                    "reason": "; ".join(constraints_violated),
                    "symbol": symbol,
                }

            return {
                "approved": True,
                "reason": "Entry approved",
                "symbol": symbol,
                "position_pct": round(position_pct, 2),
            }

        except Exception as e:
            logger.error(f"Entry evaluation error: {e}")
            return {"approved": False, "reason": str(e)}

    def check_portfolio_health(
        self, current_prices: Dict[str, float]
    ) -> List[PortfolioAction]:
        """Check portfolio health and generate recommended actions.

        Args:
            current_prices: Dict mapping symbol to current price

        Returns:
            List of recommended portfolio actions
        """
        try:
            metrics = self.get_portfolio_metrics(current_prices)
            actions = []

            # Check 1: High capital utilization
            if metrics.capital_utilization_pct > 90:
                actions.append(
                    PortfolioAction(
                        action_type="REDUCE",
                        symbol="*",  # Portfolio-wide
                        quantity=0.0,
                        reason=f"Capital utilization at {metrics.capital_utilization_pct:.1f}%",
                        urgency="HIGH",
                    )
                )

            # Check 2: Single position too large
            if metrics.max_single_position_pct > self.max_position_pct * 100:
                actions.append(
                    PortfolioAction(
                        action_type="REBALANCE",
                        symbol="*",
                        quantity=0.0,
                        reason=f"Largest position {metrics.max_single_position_pct:.1f}% exceeds limit",
                        urgency="MEDIUM",
                    )
                )

            # Check 3: Risk score critical
            if metrics.risk_score >= 80:
                actions.append(
                    PortfolioAction(
                        action_type="REDUCE",
                        symbol="*",
                        quantity=0.0,
                        reason=f"Portfolio risk score {metrics.risk_score:.1f} is CRITICAL",
                        urgency="CRITICAL",
                    )
                )

            # Check 4: High losses
            if metrics.total_pnl_pct < -5.0:
                actions.append(
                    PortfolioAction(
                        action_type="REBALANCE",
                        symbol="*",
                        quantity=0.0,
                        reason=f"Portfolio down {abs(metrics.total_pnl_pct):.1f}%",
                        urgency="HIGH",
                    )
                )

            self.suggested_actions = actions
            return actions

        except Exception as e:
            logger.error(f"Portfolio health check error: {e}")
            return []

    def get_recommended_rebalance(self, current_prices: Dict[str, float]) -> Dict:
        """Get recommended position rebalancing.

        Args:
            current_prices: Dict mapping symbol to current price

        Returns:
            Dict with rebalance suggestions
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return {"error": "Trading engine not initialized"}

            positions = engine.get_positions()
            if not positions:
                return {"error": "No positions to rebalance"}

            account = engine.get_account_state()
            total_capital = account.get("total_equity", 100000)

            # Calculate current allocations
            allocations = {}
            total_value = 0.0

            for pos in positions:
                symbol = pos.get("symbol")
                if symbol in current_prices:
                    qty = pos.get("quantity", 0)
                    price = current_prices[symbol]
                    value = qty * price
                    allocations[symbol] = {
                        "value": value,
                        "pct": (value / total_capital) * 100,
                        "quantity": qty,
                    }
                    total_value += value

            # Target: equal-weight across positions
            target_pct = 100.0 / max(len(allocations), 1)

            recommendations = {}
            for symbol, alloc in allocations.items():
                current_pct = alloc["pct"]
                diff_pct = current_pct - target_pct

                if abs(diff_pct) > 5.0:  # Only rebalance if >5% drift
                    recommendations[symbol] = {
                        "current_pct": round(current_pct, 2),
                        "target_pct": round(target_pct, 2),
                        "drift_pct": round(diff_pct, 2),
                        "action": "SELL" if diff_pct > 0 else "BUY",
                    }

            return {
                "total_positions": len(allocations),
                "target_allocation_pct": round(target_pct, 2),
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Rebalance suggestion error: {e}")
            return {"error": str(e)}

    def _calculate_risk_score(
        self,
        capital_utilization: float,
        position_count: int,
        max_position_pct: float,
        pnl_pct: float,
    ) -> float:
        """Calculate portfolio risk score (0-100).

        Args:
            capital_utilization: % of capital deployed
            position_count: Number of open positions
            max_position_pct: Size of largest position
            pnl_pct: Portfolio PnL %

        Returns:
            Risk score 0-100 (higher = riskier)
        """
        score = 0.0

        # Capital utilization risk (0-30 points)
        if capital_utilization > 90:
            score += 30
        elif capital_utilization > 70:
            score += 20
        elif capital_utilization > 50:
            score += 10

        # Position concentration risk (0-40 points)
        if max_position_pct > 30:
            score += 40
        elif max_position_pct > 20:
            score += 25
        elif max_position_pct > 15:
            score += 15
        else:
            score += 5

        # Drawdown risk (0-30 points)
        if pnl_pct < -10:
            score += 30
        elif pnl_pct < -5:
            score += 20
        elif pnl_pct < -2:
            score += 10

        return min(100.0, score)

    def _default_metrics(self) -> PortfolioRiskMetrics:
        """Return default metrics when error occurs."""
        return PortfolioRiskMetrics(
            total_position_value=0.0,
            total_positions=0,
            total_capital=100000.0,
            capital_utilization_pct=0.0,
            max_single_position_pct=0.0,
            status="UNKNOWN",
        )


# Global instance
_portfolio_orchestrator: Optional[PortfolioOrchestrator] = None


def init_portfolio_orchestrator(
    max_positions: int = 5,
    max_position_pct: float = 0.20,
    max_sector_pct: float = 0.40,
) -> PortfolioOrchestrator:
    """Initialize global portfolio orchestrator."""
    global _portfolio_orchestrator
    _portfolio_orchestrator = PortfolioOrchestrator(
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        max_sector_pct=max_sector_pct,
    )
    logger.info("Portfolio orchestrator initialized")
    return _portfolio_orchestrator


def get_portfolio_orchestrator() -> Optional[PortfolioOrchestrator]:
    """Get global portfolio orchestrator."""
    return _portfolio_orchestrator
