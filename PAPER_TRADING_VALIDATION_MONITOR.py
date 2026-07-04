#!/usr/bin/env python3
"""
48-Hour Paper Trading Validation Monitor
Tracks metrics, alerts, and generates go/no-go decisions
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class ValidationMetrics:
    """Metrics snapshot from validation."""
    timestamp: str
    trades_total: int
    trades_won: int
    trades_lost: int
    win_rate_percent: float
    average_hold_time_seconds: float
    min_hold_time_seconds: float
    max_hold_time_seconds: float
    total_pnl_dollars: float
    max_single_loss_dollars: float
    data_quality_halts: int

    def meets_success_criteria(self) -> Dict[str, bool]:
        """Check if metrics meet success criteria."""
        return {
            "win_rate_target": self.win_rate_percent >= 15.0,
            "hold_time_target": 300 <= self.average_hold_time_seconds <= 600,
            "single_loss_target": -100 < self.max_single_loss_dollars,
            "data_quality_target": self.data_quality_halts < 10,
            "pnl_target": self.total_pnl_dollars >= -50,
        }


@dataclass
class Alert:
    """Alert event."""
    timestamp: str
    level: str  # CRITICAL, WARNING, INFO
    message: str
    metric: Optional[str] = None
    value: Optional[float] = None


class ValidationMonitor:
    """Monitors 48-hour paper trading validation."""

    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        self.metrics_file = self.logs_dir / "validation_metrics.jsonl"
        self.alerts_file = self.logs_dir / "validation_alerts.log"
        self.report_file = self.logs_dir / "validation_report.md"

        self.metrics_history: List[ValidationMetrics] = []
        self.alerts_history: List[Alert] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def initialize_validation(self, initial_capital: float = 1100.0):
        """Initialize validation run."""
        self.start_time = datetime.utcnow()
        self.end_time = self.start_time + timedelta(hours=48)

        print(f"\n{'=' * 80}")
        print(f"48-HOUR PAPER TRADING VALIDATION STARTED")
        print(f"{'=' * 80}")
        print(f"Start time: {self.start_time.isoformat()} UTC")
        print(f"End time:   {self.end_time.isoformat()} UTC")
        print(f"Duration:   48 hours")
        print(f"Capital:    ${initial_capital:.2f}")
        print(f"\nSuccess Criteria:")
        print(f"  • Win rate: >15%")
        print(f"  • Hold time: 300-600 seconds")
        print(f"  • Single loss: <$100 (hard limit)")
        print(f"  • Data quality halts: <10")
        print(f"  • Total P&L: >-$50")
        print(f"{'=' * 80}\n")

        # Write initialization marker
        with open(self.metrics_file, "w") as f:
            f.write(f"# Validation started: {self.start_time.isoformat()}\n")

        with open(self.alerts_file, "w") as f:
            f.write(f"# Validation started: {self.start_time.isoformat()}\n")

    def log_metrics(self, metrics: ValidationMetrics):
        """Log a metrics snapshot."""
        self.metrics_history.append(metrics)

        # Append to file
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")

        # Check for alerts
        criteria = metrics.meets_success_criteria()

        if not criteria["win_rate_target"] and metrics.trades_total >= 20:
            if metrics.trades_total % 20 == 0:  # Every 20 trades
                self.log_alert(Alert(
                    timestamp=datetime.utcnow().isoformat(),
                    level="WARNING",
                    message=f"Win rate {metrics.win_rate_percent:.1f}% < target 15%",
                    metric="win_rate",
                    value=metrics.win_rate_percent
                ))

        if not criteria["hold_time_target"]:
            self.log_alert(Alert(
                timestamp=datetime.utcnow().isoformat(),
                level="WARNING",
                message=f"Hold time {metrics.average_hold_time_seconds:.0f}s outside target 300-600s",
                metric="hold_time",
                value=metrics.average_hold_time_seconds
            ))

        if not criteria["single_loss_target"]:
            self.log_alert(Alert(
                timestamp=datetime.utcnow().isoformat(),
                level="CRITICAL",
                message=f"Single loss ${metrics.max_single_loss_dollars:.2f} exceeds -$100 limit - HALT",
                metric="single_loss",
                value=metrics.max_single_loss_dollars
            ))

        if not criteria["data_quality_target"]:
            self.log_alert(Alert(
                timestamp=datetime.utcnow().isoformat(),
                level="WARNING",
                message=f"{metrics.data_quality_halts} data quality halts (target <10)",
                metric="data_quality_halts",
                value=float(metrics.data_quality_halts)
            ))

        if not criteria["pnl_target"]:
            self.log_alert(Alert(
                timestamp=datetime.utcnow().isoformat(),
                level="WARNING",
                message=f"Total P&L ${metrics.total_pnl_dollars:.2f} below target ≥-$50",
                metric="total_pnl",
                value=metrics.total_pnl_dollars
            ))

    def log_alert(self, alert: Alert):
        """Log an alert."""
        self.alerts_history.append(alert)

        with open(self.alerts_file, "a") as f:
            f.write(f"[{alert.timestamp}] {alert.level}: {alert.message}\n")

        if alert.level == "CRITICAL":
            print(f"🔴 CRITICAL: {alert.message}")
        elif alert.level == "WARNING":
            print(f"🟡 WARNING: {alert.message}")

    def generate_report(self) -> str:
        """Generate final validation report."""
        if not self.metrics_history:
            return "No metrics collected"

        final_metrics = self.metrics_history[-1]
        criteria = final_metrics.meets_success_criteria()

        all_pass = all(criteria.values())

        report = f"""# 48-Hour Paper Trading Validation Report

**Generated:** {datetime.utcnow().isoformat()} UTC

## 🎯 Executive Summary

**Status:** {'✅ GO (All criteria met)' if all_pass else '❌ NO-GO (Some criteria failed)'}

---

## 📊 Final Metrics (48-hour endpoint)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Win Rate** | >15% | {final_metrics.win_rate_percent:.2f}% | {'✅' if criteria['win_rate_target'] else '❌'} |
| **Hold Time** | 300-600s | {final_metrics.average_hold_time_seconds:.0f}s | {'✅' if criteria['hold_time_target'] else '❌'} |
| **Single Loss** | <$100 | ${final_metrics.max_single_loss_dollars:.2f} | {'✅' if criteria['single_loss_target'] else '❌'} |
| **Data Quality Halts** | <10 | {final_metrics.data_quality_halts} | {'✅' if criteria['data_quality_target'] else '❌'} |
| **Total P&L** | >-$50 | ${final_metrics.total_pnl_dollars:.2f} | {'✅' if criteria['pnl_target'] else '❌'} |

---

## 📈 Trade Performance

- **Total Trades:** {final_metrics.trades_total}
- **Winning Trades:** {final_metrics.trades_won}
- **Losing Trades:** {final_metrics.trades_lost}
- **Win Rate:** {final_metrics.win_rate_percent:.2f}%
- **Average Hold Time:** {final_metrics.average_hold_time_seconds:.0f} seconds
- **Min Hold Time:** {final_metrics.min_hold_time_seconds:.0f} seconds
- **Max Hold Time:** {final_metrics.max_hold_time_seconds:.0f} seconds

---

## 💰 Financial Results

- **Total P&L:** ${final_metrics.total_pnl_dollars:.2f}
- **Max Single Loss:** ${final_metrics.max_single_loss_dollars:.2f}
- **Largest Win:** TBD (from trade history)

---

## 🚨 Alerts & Issues

Total alerts: {len(self.alerts_history)}

### Critical Issues ({len([a for a in self.alerts_history if a.level == 'CRITICAL'])})
{self._format_alerts('CRITICAL')}

### Warnings ({len([a for a in self.alerts_history if a.level == 'WARNING'])})
{self._format_alerts('WARNING')}

---

## ✅ Decision Matrix

| Criterion | Required | Achieved | Decision |
|-----------|----------|----------|----------|
| Win rate >15% | YES | {final_metrics.win_rate_percent:.1f}% | {'✅' if criteria['win_rate_target'] else '❌'} |
| Hold time 300-600s | YES | {final_metrics.average_hold_time_seconds:.0f}s | {'✅' if criteria['hold_time_target'] else '❌'} |
| Single loss <$100 | YES | ${final_metrics.max_single_loss_dollars:.2f} | {'✅' if criteria['single_loss_target'] else '❌'} |
| Data quality halts <10 | YES | {final_metrics.data_quality_halts} | {'✅' if criteria['data_quality_target'] else '❌'} |
| P&L >-$50 | YES | ${final_metrics.total_pnl_dollars:.2f} | {'✅' if criteria['pnl_target'] else '❌'} |

---

## 🎯 Final Verdict

**{'✅ GO TO PRODUCTION' if all_pass else '❌ NO-GO (Needs More Work)'}**

"""
        if all_pass:
            report += """
### Next Steps (GO)
1. ✅ Code quality confirmed (validator: 0 bugs)
2. ✅ Business goals validated (all metrics met)
3. 🎯 Ready for production deployment
4. Deploy to live with real capital (start small: $100-500)
5. Monitor first 24h before scaling to full account

"""
        else:
            report += """
### Next Steps (NO-GO)
1. ❌ One or more criteria not met
2. Review failed metrics and root causes
3. Identify if it's a code bug or market conditions
4. If code bug: Fix, re-run validator, re-validate
5. If market conditions: Run another 48h validation cycle

"""

        return report

    def _format_alerts(self, level: str) -> str:
        """Format alerts by level."""
        alerts = [a for a in self.alerts_history if a.level == level]
        if not alerts:
            return "None"

        return "\n".join([f"- {a.message}" for a in alerts[:10]])


def main():
    """Example usage."""
    monitor = ValidationMonitor()

    # Initialize
    monitor.initialize_validation(initial_capital=1100.0)

    # Simulate metrics collection (would come from real trader)
    # In practice, these would be loaded from the metrics file

    # Print final report
    report = monitor.generate_report()
    print(report)

    # Save report
    with open(monitor.report_file, "w") as f:
        f.write(report)

    print(f"Report saved to: {monitor.report_file}")


if __name__ == "__main__":
    main()
