"""
Portfolio Analysis Service - Runs on backup trader during standby
Provides P&L, risk metrics, backtesting, and performance reporting
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import statistics
import asyncio


class PortfolioAnalyzer:
    """Analyze portfolio performance and risk metrics"""

    def __init__(self):
        self.trades_history = []
        self.positions = {}
        self.account_state = {}

    def set_account_state(self, account_data: Dict[str, Any]) -> None:
        """Update account state from primary"""
        self.account_state = account_data
        self.positions = account_data.get("positions", {})

    def set_trades_history(self, trades: List[Dict[str, Any]]) -> None:
        """Update trade history from primary"""
        self.trades_history = trades

    def calculate_daily_pnl(self) -> Dict[str, Any]:
        """Calculate daily P&L breakdown"""
        today = datetime.now().date()
        today_trades = [
            t for t in self.trades_history
            if datetime.fromisoformat(t["timestamp"]).date() == today
        ]

        realized_pnl = sum(
            t.get("pnl", 0) for t in today_trades if t.get("status") == "closed"
        )
        unrealized_pnl = sum(
            (p.get("current_price", 0) - p.get("entry_price", 0)) * p.get("quantity", 0)
            for p in self.positions.values()
        )

        return {
            "date": str(today),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_pnl": round(realized_pnl + unrealized_pnl, 2),
            "trades_count": len(today_trades),
            "win_rate": self._calculate_win_rate(today_trades),
        }

    def calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate VaR, drawdown, Sharpe ratio"""
        if not self.trades_history:
            return {}

        # Calculate returns
        returns = self._calculate_returns()
        if not returns:
            return {}

        # Sharpe ratio (annualized, assuming 252 trading days)
        mean_return = statistics.mean(returns) if returns else 0
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0
        sharpe = (mean_return * 252) / (std_dev * (252 ** 0.5)) if std_dev > 0 else 0

        # Maximum drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Value at Risk (95% confidence)
        returns_sorted = sorted(returns)
        var_idx = max(0, int(len(returns_sorted) * 0.05) - 1)
        var_95 = returns_sorted[var_idx] if returns_sorted else 0

        return {
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 4),
            "value_at_risk_95": round(var_95, 4),
            "volatility": round(std_dev, 4),
            "total_return": round(sum(returns), 4),
        }

    def calculate_portfolio_drift(self, targets: Dict[str, float] = None) -> Dict[str, Any]:
        """Detect portfolio drift from target allocation"""
        if not self.account_state:
            return {}

        total_equity = self.account_state.get("total_equity", 0)
        positions_value = self.account_state.get("positions_value", 0)

        # Current allocation
        current = {}
        for symbol, pos in self.positions.items():
            value = pos.get("quantity", 0) * pos.get("current_price", 0)
            pct = (value / total_equity * 100) if total_equity > 0 else 0
            current[symbol] = round(pct, 2)

        # Default targets (equal weight)
        if targets is None:
            n = len(self.positions)
            targets = {s: 100 / n for s in self.positions} if n > 0 else {}

        # Calculate drift
        drift = {}
        for symbol in current:
            target = targets.get(symbol, 0)
            drift[symbol] = round(current[symbol] - target, 2)

        return {
            "current_allocation": current,
            "target_allocation": targets,
            "drift": drift,
            "rebalance_needed": any(abs(d) > 5 for d in drift.values()),
        }

    def calculate_signal_quality(self) -> Dict[str, Any]:
        """Analyze signal quality by entry method"""
        if not self.trades_history:
            return {}

        by_signal = {}
        for trade in self.trades_history:
            signal_type = trade.get("signal_type", "unknown")
            if signal_type not in by_signal:
                by_signal[signal_type] = {"count": 0, "wins": 0, "pnl": 0}

            by_signal[signal_type]["count"] += 1
            if trade.get("pnl", 0) > 0:
                by_signal[signal_type]["wins"] += 1
            by_signal[signal_type]["pnl"] += trade.get("pnl", 0)

        result = {}
        for signal_type, data in by_signal.items():
            win_rate = (data["wins"] / data["count"] * 100) if data["count"] > 0 else 0
            result[signal_type] = {
                "count": data["count"],
                "win_rate": round(win_rate, 2),
                "avg_pnl": round(data["pnl"] / data["count"], 2),
                "total_pnl": round(data["pnl"], 2),
            }

        return result

    def generate_daily_report(self) -> Dict[str, Any]:
        """Generate comprehensive daily report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "account": self.account_state,
            "pnl": self.calculate_daily_pnl(),
            "risk_metrics": self.calculate_risk_metrics(),
            "portfolio_drift": self.calculate_portfolio_drift(),
            "signal_quality": self.calculate_signal_quality(),
            "positions": len(self.positions),
        }

    # Helper methods
    def _calculate_returns(self) -> List[float]:
        """Calculate daily returns"""
        if not self.trades_history:
            return []

        daily_pnl = {}
        for trade in self.trades_history:
            date = datetime.fromisoformat(trade["timestamp"]).date()
            if date not in daily_pnl:
                daily_pnl[date] = 0
            daily_pnl[date] += trade.get("pnl", 0)

        # Convert to returns (pnl / starting equity)
        starting_equity = self.account_state.get("total_equity", 1) + sum(daily_pnl.values())
        return [pnl / starting_equity for pnl in daily_pnl.values()]

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.trades_history:
            return 0

        cumulative_returns = [0]
        for trade in self.trades_history:
            cumulative_returns.append(
                cumulative_returns[-1] + trade.get("pnl", 0)
            )

        peak = max(cumulative_returns)
        max_dd = max(peak - val for val in cumulative_returns)
        return -max_dd / peak if peak != 0 else 0

    def _calculate_win_rate(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate win rate for trades"""
        if not trades:
            return 0
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return round((wins / len(trades)) * 100, 2)


# Singleton instance
_analyzer = PortfolioAnalyzer()


def get_portfolio_analyzer() -> PortfolioAnalyzer:
    """Get analyzer instance"""
    return _analyzer


def init_portfolio_analyzer() -> None:
    """Initialize analyzer"""
    global _analyzer
    _analyzer = PortfolioAnalyzer()
