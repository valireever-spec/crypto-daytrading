"""
Phase 318: Portfolio Decision Coordinator

Orchestrates portfolio-level regime decisions from Phase 317 systems
(regime monitor, sector rotation, rebalancing) into coordinated trading
actions in the autonomous trader.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from backend.analytics.portfolio_regime_monitor import (
    get_portfolio_regime_monitor,
)
from backend.analytics.sector_rotation_advisor import (
    get_sector_rotation_advisor,
)
from backend.analytics.portfolio_rebalancing_engine import (
    get_portfolio_rebalancing_engine,
)

logger = logging.getLogger(__name__)


@dataclass
class PortfolioDecision:
    """Top-level portfolio decision from coordinator."""

    timestamp: datetime
    decision_type: str  # CORRELATED_EXIT, SECTOR_ROTATION, REBALANCE
    action: str  # EXIT, ROTATE, REBALANCE
    target_symbols: List[str]  # Symbols affected
    actions: Dict[str, str]  # symbol → action (SELL/BUY/HOLD)
    urgency: int  # 1-10
    rationale: str
    estimated_impact: Dict[str, Any]  # cost, time, improvement


class PortfolioDecisionCoordinator:
    """Orchestrates portfolio-level trading decisions."""

    def __init__(self):
        """Initialize portfolio decision coordinator."""
        self.regime_monitor = get_portfolio_regime_monitor()
        self.sector_advisor = get_sector_rotation_advisor()
        self.rebalancing_engine = get_portfolio_rebalancing_engine()
        self.decision_history: List[PortfolioDecision] = []
        self.last_rebalance_time = None

    async def make_portfolio_decisions(
        self,
        symbol_regimes: Dict[str, Any],  # symbol → regime_info
        current_positions: List[Dict],  # [{symbol, quantity, entry_price, value_eur}]
        portfolio_value: float,
        target_allocation: Dict[str, float],  # symbol → target % (0-100)
        current_prices: Dict[str, float],  # symbol → price
    ) -> List[PortfolioDecision]:
        """
        Generate portfolio-level decisions based on regime and drift.

        Orchestrates decision priority:
          1. Correlated exits (regime flips to bear/volatile)
          2. Sector rotations (overweight/underweight sectors)
          3. Rebalancing (drift from target allocation)

        Parameters:
        -----------
        symbol_regimes : dict
            Output from regime detector: {symbol: {regime, trend, vol, ...}}
        current_positions : list
            Current portfolio positions
        portfolio_value : float
            Total portfolio value in EUR
        target_allocation : dict
            Target allocation per symbol (%)
        current_prices : dict
            Current market prices

        Returns:
        --------
        List of PortfolioDecision (prioritized by urgency)
        """
        decisions: List[PortfolioDecision] = []

        try:
            # Extract symbol list from positions
            position_symbols = [p["symbol"] for p in current_positions]

            # 1. CHECK FOR CORRELATED EXITS (highest priority)
            exit_decision = await self._generate_correlated_exit_decision(
                symbol_regimes, position_symbols, current_prices
            )
            if exit_decision:
                decisions.append(exit_decision)
                logger.warning(
                    f"⚠️ Portfolio decision: {exit_decision.decision_type} "
                    f"(urgency {exit_decision.urgency}/10)"
                )

            # 2. CHECK FOR SECTOR ROTATIONS (medium priority)
            if not exit_decision:  # Only if no urgent exits
                rotation_decision = await self._generate_sector_rotation_decision(
                    symbol_regimes, position_symbols, current_positions, portfolio_value
                )
                if rotation_decision:
                    decisions.append(rotation_decision)
                    logger.info(
                        f"📊 Portfolio decision: {rotation_decision.decision_type} "
                        f"(urgency {rotation_decision.urgency}/10)"
                    )

            # 3. CHECK FOR REBALANCING (lower priority)
            if len(decisions) == 0:  # Only if no exits or rotations
                rebalance_decision = await self._generate_rebalancing_decision(
                    current_positions, portfolio_value, target_allocation
                )
                if rebalance_decision:
                    decisions.append(rebalance_decision)
                    logger.info(
                        f"🔄 Portfolio decision: {rebalance_decision.decision_type} "
                        f"(urgency {rebalance_decision.urgency}/10)"
                    )

            # Store decisions in history
            for decision in decisions:
                self.decision_history.append(decision)

            return decisions

        except Exception as e:
            logger.error(f"Error making portfolio decisions: {e}", exc_info=True)
            return []

    async def _generate_correlated_exit_decision(
        self,
        symbol_regimes: Dict[str, Any],
        current_positions: List[str],
        current_prices: Dict[str, float],
    ) -> Optional[PortfolioDecision]:
        """
        Generate correlated exit decision when regimes flip to bear/volatile.

        High urgency - exits should be executed immediately.
        """
        try:
            # Check portfolio regime state
            portfolio_state = self.regime_monitor.check_portfolio_regime(
                symbol_regimes, current_positions
            )

            if not portfolio_state.exit_signals:
                return None

            # Get stress level
            stress_level = self.regime_monitor.get_portfolio_stress_level(
                symbol_regimes
            )

            # Generate action dict (all exits are SELL)
            actions = {symbol: "SELL" for symbol in portfolio_state.exit_signals}

            # Calculate urgency (higher stress = higher urgency)
            urgency = min(int(stress_level * 10), 10)

            # Estimate impact (lost opportunity cost if don't exit)
            estimated_cost_if_delayed = (
                len(portfolio_state.exit_signals) * 2
            )  # Rough estimate: 2% loss/day in bear

            decision = PortfolioDecision(
                timestamp=datetime.utcnow(),
                decision_type="CORRELATED_EXIT",
                action="EXIT",
                target_symbols=portfolio_state.exit_signals,
                actions=actions,
                urgency=urgency,
                rationale=f"Regime flip to {portfolio_state.portfolio_regime}: "
                f"{len(portfolio_state.exit_signals)} positions at risk. "
                f"Stress level: {stress_level:.1%}",
                estimated_impact={
                    "symbols_to_exit": len(portfolio_state.exit_signals),
                    "stress_level": stress_level,
                    "portfolio_regime": portfolio_state.portfolio_regime,
                    "estimated_daily_loss_if_delayed": estimated_cost_if_delayed,
                    "execution_time_min": len(portfolio_state.exit_signals) * 2,
                },
            )

            logger.warning(
                f"⚠️ CORRELATED EXIT: {portfolio_state.exit_signals} "
                f"(stress: {stress_level:.1%}, regime: {portfolio_state.portfolio_regime})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error generating correlated exit decision: {e}")
            return None

    async def _generate_sector_rotation_decision(
        self,
        symbol_regimes: Dict[str, Any],
        current_positions: List[str],
        position_details: List[Dict],  # Full position objects
        portfolio_value: float,
    ) -> Optional[PortfolioDecision]:
        """
        Generate sector rotation decision.

        Medium urgency - recommend rotating overweight/underweight sectors.
        """
        try:
            # Calculate current allocation
            current_allocation = self._calculate_current_allocation(
                position_details, portfolio_value
            )

            # Get portfolio regime
            portfolio_state = self.regime_monitor.check_portfolio_regime(
                symbol_regimes, current_positions
            )
            portfolio_regime = portfolio_state.portfolio_regime

            # Get rotation recommendation
            rotation_rec = self.sector_advisor.get_sector_rotation_recommendation(
                portfolio_regime=portfolio_regime,
                current_allocation=current_allocation,
                symbol_regimes=symbol_regimes,
                symbol_prices={},
            )

            if not rotation_rec:
                return None

            # Extract actions from recommendation
            actions = rotation_rec.action_symbols

            # Calculate urgency based on confidence and drift
            urgency = min(int(rotation_rec.confidence * 10), 10)

            decision = PortfolioDecision(
                timestamp=datetime.utcnow(),
                decision_type="SECTOR_ROTATION",
                action="ROTATE",
                target_symbols=list(actions.keys()),
                actions=actions,
                urgency=urgency,
                rationale=f"Rotate from {rotation_rec.from_sector} to {rotation_rec.to_sector} "
                f"for {portfolio_regime} market. "
                f"Expected outperformance: {rotation_rec.expected_outperformance:.1f}%",
                estimated_impact={
                    "from_sector": rotation_rec.from_sector,
                    "to_sector": rotation_rec.to_sector,
                    "confidence": rotation_rec.confidence,
                    "expected_outperformance": rotation_rec.expected_outperformance,
                    "symbols_to_sell": sum(
                        1 for a in actions.values() if a in ["SELL", "REDUCE"]
                    ),
                    "symbols_to_buy": sum(1 for a in actions.values() if a == "BUY"),
                },
            )

            logger.info(
                f"📊 SECTOR ROTATION: {rotation_rec.from_sector} → {rotation_rec.to_sector} "
                f"(confidence: {rotation_rec.confidence:.1%})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error generating sector rotation decision: {e}")
            return None

    async def _generate_rebalancing_decision(
        self,
        current_positions: List[Dict],
        portfolio_value: float,
        target_allocation: Dict[str, float],
    ) -> Optional[PortfolioDecision]:
        """
        Generate rebalancing decision.

        Low urgency - execute on schedule when drift exceeds threshold.
        """
        try:
            # Calculate time since last rebalance
            if self.last_rebalance_time:
                days_since_rebalance = (
                    datetime.utcnow() - self.last_rebalance_time
                ).days
            else:
                days_since_rebalance = 30  # Force rebalance if never done

            # Convert position list to portfolio dict for engine
            portfolio_dict = {
                p["symbol"]: {
                    "value_eur": p.get("value_eur", 0),
                    "quantity": p.get("quantity", 0),
                    "price": p.get("price", 0),
                }
                for p in current_positions
            }

            # Generate rebalancing plan
            plan = self.rebalancing_engine.generate_rebalancing_plan(
                current_positions=portfolio_dict,
                portfolio_value=portfolio_value,
                target_allocation=target_allocation,
                regime="neutral",
            )

            if not plan:
                return None

            # Extract actions from plan
            actions = {action.symbol: action.action for action in plan.actions}

            # Calculate urgency based on drift and time
            urgency = plan.urgency

            decision = PortfolioDecision(
                timestamp=datetime.utcnow(),
                decision_type="REBALANCE",
                action="REBALANCE",
                target_symbols=list(actions.keys()),
                actions=actions,
                urgency=urgency,
                rationale=f"Rebalance portfolio: total drift {plan.total_drift:.1f}%. "
                f"Expected improvement: {plan.improvement_expected}. "
                f"Last rebalance: {days_since_rebalance} days ago.",
                estimated_impact={
                    "total_drift": plan.total_drift,
                    "total_cost": plan.total_rebalancing_cost,
                    "cost_pct_portfolio": (
                        plan.total_rebalancing_cost / portfolio_value * 100
                    )
                    if portfolio_value > 0
                    else 0,
                    "improvement_expected": plan.improvement_expected,
                    "execution_time_min": plan.estimated_execution_time_min,
                    "num_actions": len(plan.actions),
                },
            )

            logger.info(
                f"🔄 REBALANCING: {plan.total_drift:.1f}% drift, "
                f"{len(plan.actions)} actions, cost €{plan.total_rebalancing_cost:.2f}"
            )

            # Update last rebalance time if plan is accepted
            self.last_rebalance_time = datetime.utcnow()

            return decision

        except Exception as e:
            logger.error(f"Error generating rebalancing decision: {e}")
            return None

    def _calculate_current_allocation(
        self,
        positions: List[Dict],
        portfolio_value: float,
    ) -> Dict[str, float]:
        """Calculate current allocation as percentage per symbol."""
        if portfolio_value <= 0:
            return {}

        allocation = {}
        for pos in positions:
            symbol = pos.get("symbol")
            value = pos.get("value_eur", 0)
            pct = (value / portfolio_value) * 100
            allocation[symbol] = pct

        return allocation

    def get_decision_summary(self, limit: int = 5) -> str:
        """Get summary of recent portfolio decisions."""
        if not self.decision_history:
            return "📋 No portfolio decisions made yet"

        recent = self.decision_history[-limit:]
        summary = f"📋 Recent portfolio decisions ({len(recent)}):\n"

        for decision in recent:
            summary += (
                f"  • {decision.decision_type}: {', '.join(decision.target_symbols)} "
            )
            summary += f"(urgency: {decision.urgency}/10, time: {decision.timestamp.strftime('%H:%M:%S')})\n"

        return summary

    def get_decision_queue(self) -> List[PortfolioDecision]:
        """Get pending decisions (not yet executed)."""
        # In a real system, would track execution status
        # For now, return last decision if recent
        if self.decision_history:
            last_decision = self.decision_history[-1]
            age = (datetime.utcnow() - last_decision.timestamp).total_seconds()
            if age < 300:  # If less than 5 minutes old
                return [last_decision]

        return []

    def mark_decision_executed(self, decision: PortfolioDecision) -> bool:
        """Mark a decision as executed."""
        try:
            # In real system, would update decision status
            logger.info(
                f"✅ Decision executed: {decision.decision_type} "
                f"({len(decision.target_symbols)} symbols)"
            )
            return True
        except Exception as e:
            logger.error(f"Error marking decision executed: {e}")
            return False


# Global instance
_portfolio_coordinator: PortfolioDecisionCoordinator = None


def get_portfolio_decision_coordinator() -> PortfolioDecisionCoordinator:
    """Get or create portfolio decision coordinator instance."""
    global _portfolio_coordinator
    if _portfolio_coordinator is None:
        _portfolio_coordinator = PortfolioDecisionCoordinator()
    return _portfolio_coordinator
