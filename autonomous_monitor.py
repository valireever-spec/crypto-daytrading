#!/usr/bin/env python3
"""
Autonomous Trade Monitoring & Parameter Optimization System
Monitors trading performance and automatically adjusts parameters
Runs for 7 hours with 30-minute checkpoints
"""

import sys
sys.path.insert(0, '/home/vali/projects/crypto-daytrading')

from backend.exchange.paper_trading import init_paper_trading, get_paper_trading
from datetime import datetime, timezone, timedelta
import json
import logging
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutonomousTradeMonitor:
    """Monitor trades and optimize parameters autonomously."""

    def __init__(self):
        init_paper_trading()
        self.engine = get_paper_trading()

        # Load persistent checkpoint counter
        checkpoint_file = '/tmp/autonomous_monitor_checkpoint.txt'
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    self.checkpoint = int(f.read().strip())
            except:
                self.checkpoint = 0
        else:
            self.checkpoint = 0

        self.checkpoint_file = checkpoint_file
        self.start_time = datetime.now(timezone.utc)
        self.monitoring_log = []

    def analyze_performance(self, lookback_trades=100):
        """Analyze recent trading performance."""
        trades = self.engine.get_trades(limit=lookback_trades)
        account = self.engine.get_account_state()

        sell_trades = [t for t in trades if t['side'] == 'SELL']
        if not sell_trades:
            return None

        winning = [t for t in sell_trades if t.get('realized_pnl', 0) > 0]
        losing = [t for t in sell_trades if t.get('realized_pnl', 0) < 0]

        win_rate = (len(winning) / len(sell_trades) * 100) if sell_trades else 0
        total_pnl = sum(t.get('realized_pnl', 0) for t in sell_trades)
        avg_win = sum(t.get('realized_pnl', 0) for t in winning) / len(winning) if winning else 0
        avg_loss = abs(sum(t.get('realized_pnl', 0) for t in losing) / len(losing)) if losing else 0

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checkpoint': self.checkpoint,
            'win_rate': win_rate,
            'total_trades': len(sell_trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': avg_win / avg_loss if avg_loss > 0 else 0,
            'account_balance': account.get('cash', 0),
            'account_pnl': account.get('total_pnl', 0),
        }

    def recommend_parameter_changes(self, metrics):
        """Recommend parameter adjustments based on performance."""
        recommendations = []

        if metrics['win_rate'] < 35:
            recommendations.append({
                'action': 'CRITICAL: Tighten entry filters',
                'metric': f"Win rate {metrics['win_rate']:.1f}% (target: 45-55%)",
                'change': 'Increase entry_threshold from 60 to 75',
                'reason': 'Too many losing trades - entry signal too loose'
            })
        elif metrics['win_rate'] < 45:
            recommendations.append({
                'action': 'Tighten entry filters',
                'metric': f"Win rate {metrics['win_rate']:.1f}% (target: 45-55%)",
                'change': 'Increase entry_threshold by 5',
                'reason': 'Below target win rate'
            })
        elif metrics['win_rate'] > 60:
            recommendations.append({
                'action': 'Optimize position sizing',
                'metric': f"Win rate {metrics['win_rate']:.1f}% (above target)",
                'change': 'Increase max_positions and position_size',
                'reason': 'High win rate - can afford more risk'
            })

        if metrics['total_pnl'] < 0:
            recommendations.append({
                'action': 'Reduce risk',
                'metric': f"Negative P&L: €{metrics['total_pnl']:.2f}",
                'change': 'Reduce position_size_pct from 2.5% to 1.5%',
                'reason': 'Losing money - reduce per-trade risk'
            })

        if metrics['profit_factor'] < 1.0:
            recommendations.append({
                'action': 'Increase stop loss',
                'metric': f"Profit factor {metrics['profit_factor']:.2f}",
                'change': 'Increase exit_stop_loss from 0.5% to 0.75%',
                'reason': 'Losses larger than wins - stop too tight'
            })

        if metrics['win_rate'] >= 45 and metrics['win_rate'] <= 55 and metrics['profit_factor'] > 1.0:
            recommendations.append({
                'action': 'NO CHANGES NEEDED',
                'metric': 'Performance optimal',
                'reason': 'Win rate and profit factor within acceptable range'
            })

        return recommendations

    def print_checkpoint_report(self):
        """Print detailed checkpoint report."""
        metrics = self.analyze_performance()
        if not metrics:
            logger.warning("No trades found to analyze")
            return

        elapsed = datetime.now(timezone.utc) - self.start_time

        print("\n" + "=" * 90)
        print(f"AUTONOMOUS MONITORING CHECKPOINT #{self.checkpoint}")
        print(f"Elapsed: {elapsed} (7-hour window remaining)")
        print("=" * 90)
        print()

        print("📊 PERFORMANCE METRICS")
        print("-" * 90)
        print(f"Win Rate: {metrics['win_rate']:.1f}% (target: 45-55%)")
        print(f"Trades: {metrics['total_trades']} ({metrics['winning_trades']} wins, {metrics['losing_trades']} losses)")
        print(f"Recent P&L: €{metrics['total_pnl']:.2f}")
        print(f"Account Balance: €{metrics['account_balance']:.2f}")
        print(f"Total Account P&L: €{metrics['account_pnl']:.2f}")
        print(f"Avg Win: €{metrics['avg_win']:.2f} | Avg Loss: €{metrics['avg_loss']:.2f}")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print()

        recommendations = self.recommend_parameter_changes(metrics)
        if recommendations:
            print("🔧 PARAMETER RECOMMENDATIONS")
            print("-" * 90)
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec['action']}")
                print(f"   Metric: {rec['metric']}")
                if 'change' in rec:
                    print(f"   Change: {rec['change']}")
                print(f"   Reason: {rec['reason']}")
            print()

        # Log checkpoint
        self.monitoring_log.append({
            'checkpoint': self.checkpoint,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': metrics,
            'recommendations': recommendations
        })

        self.checkpoint += 1

        # Persist checkpoint counter for next run
        with open(self.checkpoint_file, 'w') as f:
            f.write(str(self.checkpoint))

        print("=" * 90)
        print()

    def generate_summary(self):
        """Generate monitoring session summary."""
        print("\n" + "=" * 90)
        print("🎯 AUTONOMOUS MONITORING SESSION COMPLETE")
        print("=" * 90)
        print()

        if self.monitoring_log:
            first = self.monitoring_log[0]['metrics']
            last = self.monitoring_log[-1]['metrics']

            print("📈 PERFORMANCE CHANGE")
            print("-" * 90)
            print(f"Win Rate: {first['win_rate']:.1f}% → {last['win_rate']:.1f}%")
            print(f"Account P&L: €{first['account_pnl']:.2f} → €{last['account_pnl']:.2f}")
            print(f"Trades Executed: {first['total_trades']} → {last['total_trades']}")
            print()

            print("📋 CHECKPOINTS COMPLETED")
            print("-" * 90)
            print(f"Total checkpoints: {len(self.monitoring_log)}")
            print(f"Monitoring duration: {datetime.now(timezone.utc) - self.start_time}")
            print()

        print("✅ MONITORING COMPLETE")
        print("=" * 90)

def main():
    """Run autonomous monitoring checkpoint."""
    monitor = AutonomousTradeMonitor()
    monitor.print_checkpoint_report()

if __name__ == "__main__":
    main()
