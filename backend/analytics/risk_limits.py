"""Risk limit enforcement and monitoring."""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels for position management."""
    GREEN = "green"      # Normal operations
    YELLOW = "yellow"    # Caution, reduce position size
    ORANGE = "orange"    # Warning, reduce positions
    RED = "red"          # Critical, stop trading


@dataclass
class RiskLimits:
    """Portfolio risk limits configuration."""
    max_drawdown_pct: float = 10.0           # Stop trading if down 10%
    max_daily_loss_pct: float = 5.0          # Stop if lose 5% in one day
    max_position_size_pct: float = 5.0       # Max per position
    max_sector_exposure_pct: float = 30.0    # Max per sector
    max_correlation: float = 0.8             # Warning if correlated >0.8
    max_var_95: float = 2.0                  # Max daily VaR at 95% confidence
    min_diversification: float = 0.05        # Minimum HHI (0.05 = well diversified)
    max_leverage: float = 1.0                # Max leverage ratio


@dataclass
class RiskMetrics:
    """Current portfolio risk metrics."""
    current_drawdown: float
    max_drawdown: float
    daily_loss: float
    portfolio_var: float
    concentration: float
    max_correlation: float
    portfolio_value: float
    timestamp: str


class RiskMonitor:
    """Monitor and enforce portfolio risk limits."""

    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self.initial_value: Optional[float] = None
        self.daily_start_value: Optional[float] = None
        self.last_day: Optional[str] = None
        self.alerts: List[Dict] = []
        self.violations: List[Dict] = []

    def update_portfolio_value(self, value: float) -> RiskLevel:
        """
        Update portfolio value and check limits.

        Returns:
            RiskLevel indicating current risk state
        """
        from datetime import date

        current_date = date.today().isoformat()

        # Initialize on first call
        if self.initial_value is None:
            self.initial_value = value
            self.daily_start_value = value
            self.last_day = current_date
            return RiskLevel.GREEN

        # Reset daily values on new day
        if current_date != self.last_day:
            self.daily_start_value = value
            self.last_day = current_date

        # Calculate drawdowns
        current_dd = (value - self.initial_value) / self.initial_value
        daily_loss = (value - self.daily_start_value) / self.daily_start_value

        # Check limits
        alerts = []

        if current_dd <= -self.limits.max_drawdown_pct / 100:
            alerts.append({
                "type": "max_drawdown_exceeded",
                "limit": self.limits.max_drawdown_pct,
                "current": current_dd * 100,
                "severity": "critical"
            })

        if daily_loss <= -self.limits.max_daily_loss_pct / 100:
            alerts.append({
                "type": "daily_loss_exceeded",
                "limit": self.limits.max_daily_loss_pct,
                "current": daily_loss * 100,
                "severity": "critical"
            })

        # Determine risk level
        risk_level = self._determine_risk_level(current_dd, daily_loss, len(alerts))

        # Log alerts
        for alert in alerts:
            logger.warning(f"Risk alert: {alert}")
            self.alerts.append({
                "timestamp": datetime.utcnow().isoformat(),
                **alert
            })

        return risk_level

    def _determine_risk_level(self, total_dd: float, daily_loss: float, alert_count: int) -> RiskLevel:
        """Determine overall risk level."""
        max_dd_limit = self.limits.max_drawdown_pct / 100
        daily_loss_limit = self.limits.max_daily_loss_pct / 100

        if alert_count > 0 or total_dd <= -max_dd_limit or daily_loss <= -daily_loss_limit:
            return RiskLevel.RED

        if total_dd <= -max_dd_limit * 0.8 or daily_loss <= -daily_loss_limit * 0.8:
            return RiskLevel.ORANGE

        if total_dd <= -max_dd_limit * 0.5 or daily_loss <= -daily_loss_limit * 0.5:
            return RiskLevel.YELLOW

        return RiskLevel.GREEN

    def check_position_size(self, position_value: float, portfolio_value: float) -> bool:
        """Check if position size is within limits."""
        if portfolio_value == 0:
            return True

        position_pct = (position_value / portfolio_value) * 100

        if position_pct > self.limits.max_position_size_pct:
            violation = {
                "type": "position_size_exceeded",
                "limit": self.limits.max_position_size_pct,
                "current": position_pct,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.violations.append(violation)
            logger.warning(f"Position size violation: {violation}")
            return False

        return True

    def check_correlation(self, correlation: float) -> bool:
        """Check if correlation is within acceptable limits."""
        if correlation > self.limits.max_correlation:
            violation = {
                "type": "high_correlation",
                "limit": self.limits.max_correlation,
                "current": correlation,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.violations.append(violation)
            logger.warning(f"Correlation violation: {violation}")
            return False

        return True

    def check_diversification(self, hhi: float) -> bool:
        """Check if portfolio is sufficiently diversified."""
        if hhi > 1.0 - self.limits.min_diversification:
            violation = {
                "type": "low_diversification",
                "limit": self.limits.min_diversification,
                "current": hhi,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.violations.append(violation)
            logger.warning(f"Diversification violation: {violation}")
            return False

        return True

    def check_var_limit(self, var_95: float) -> bool:
        """Check if VaR is within limits."""
        if var_95 > self.limits.max_var_95:
            violation = {
                "type": "var_exceeded",
                "limit": self.limits.max_var_95,
                "current": var_95,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.violations.append(violation)
            logger.warning(f"VaR violation: {violation}")
            return False

        return True

    def get_risk_score(self, metrics: RiskMetrics) -> float:
        """
        Calculate overall portfolio risk score (0-100).
        Higher = more risky.
        """
        score = 0.0

        # Drawdown component (0-30)
        dd_pct = -metrics.current_drawdown * 100
        if dd_pct > self.limits.max_drawdown_pct:
            score += 30
        elif dd_pct > self.limits.max_drawdown_pct * 0.5:
            score += 15
        else:
            score += min((dd_pct / (self.limits.max_drawdown_pct * 0.5)) * 15, 15)

        # Daily loss component (0-20)
        loss_pct = -metrics.daily_loss * 100
        if loss_pct > self.limits.max_daily_loss_pct:
            score += 20
        else:
            score += min((loss_pct / self.limits.max_daily_loss_pct) * 20, 20)

        # VaR component (0-20)
        if metrics.portfolio_var > self.limits.max_var_95:
            score += 20
        else:
            score += min((metrics.portfolio_var / self.limits.max_var_95) * 20, 20)

        # Concentration component (0-15)
        # HHI ranges from 1/N (diversified) to 1 (concentrated)
        if metrics.concentration > 0.25:
            score += 15
        else:
            score += (metrics.concentration / 0.25) * 15

        # Correlation component (0-15)
        if metrics.max_correlation > self.limits.max_correlation:
            score += 15
        else:
            score += min((metrics.max_correlation / self.limits.max_correlation) * 15, 15)

        return min(score, 100.0)

    def get_recommended_action(self, risk_level: RiskLevel) -> str:
        """Get recommended action based on risk level."""
        actions = {
            RiskLevel.GREEN: "Continue normal trading operations",
            RiskLevel.YELLOW: "Reduce position sizes by 25%, monitor closely",
            RiskLevel.ORANGE: "Reduce position sizes by 50%, consider liquidating largest positions",
            RiskLevel.RED: "STOP TRADING, liquidate positions to reduce exposure"
        }
        return actions.get(risk_level, "Unknown risk level")

    def get_status(self) -> Dict:
        """Get risk monitor status."""
        return {
            "limits": {
                "max_drawdown_pct": self.limits.max_drawdown_pct,
                "max_daily_loss_pct": self.limits.max_daily_loss_pct,
                "max_position_size_pct": self.limits.max_position_size_pct,
                "max_var_95": self.limits.max_var_95,
                "max_correlation": self.limits.max_correlation
            },
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "violations": self.violations[-10:],  # Last 10 violations
            "total_alerts": len(self.alerts),
            "total_violations": len(self.violations)
        }


# Global risk monitor instance
_risk_monitor: Optional[RiskMonitor] = None


def init_risk_monitor(limits: RiskLimits = None) -> RiskMonitor:
    """Initialize risk monitor."""
    global _risk_monitor
    if _risk_monitor is None:
        _risk_monitor = RiskMonitor(limits)
        logger.info("Risk monitor initialized")
    return _risk_monitor


def get_risk_monitor() -> Optional[RiskMonitor]:
    """Get risk monitor instance."""
    return _risk_monitor
