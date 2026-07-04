"""
Main backtesting runner.
Executes full backtest and generates report.
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

from .backtest_engine import BacktestEngine, SignalCalculator, Candle
from .data_loader import DataLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestRunner:
    """Execute full backtest workflow"""

    def __init__(self):
        self.data_loader = DataLoader(cache_dir=Path("backtest_cache"))
        self.results = {}

    def run_single_symbol(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        use_real_data: bool = True,
    ) -> Dict:
        """Run backtest for single symbol"""

        logger.info(f"\n{'='*70}")
        logger.info(f"BACKTEST: {symbol}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"{'='*70}")

        # Load data for all timeframes
        if use_real_data:
            logger.info("📥 Loading real historical data from Binance...")
            data_5min = self.data_loader.fetch_data(symbol, '5m', start_date, end_date)
            data_1hr = self.data_loader.fetch_data(symbol, '1h', start_date, end_date)
            data_4hr = self.data_loader.fetch_data(symbol, '4h', start_date, end_date)
        else:
            logger.info("📊 Generating mock data...")
            days_ago = (datetime.utcnow() - start_date).days
            all_data = self.data_loader.generate_mock_data(symbol, days=max(days_ago, 30))
            data_5min = all_data['5m']
            data_1hr = all_data['1h']
            data_4hr = all_data['4h']

        if not data_5min:
            logger.error(f"❌ No data available for {symbol}")
            return {}

        logger.info(f"✅ Loaded data: {len(data_5min)} 5-min, {len(data_1hr)} 1-hr, {len(data_4hr)} 4-hr candles")

        # Initialize engine
        engine = BacktestEngine(symbol)

        # Track price history
        prices_5min = []
        prices_1hr = []
        prices_4hr = []
        volumes_5min = []

        # Main backtesting loop
        logger.info("▶️  Starting backtest simulation...")

        trades_executed = 0
        entries_attempted = 0

        for i, candle_5min in enumerate(data_5min):
            # Build price history (last 100 candles)
            prices_5min.append(candle_5min.close)
            volumes_5min.append(candle_5min.volume)
            prices_5min = prices_5min[-100:]
            volumes_5min = volumes_5min[-100:]

            # Find corresponding 1-hr candle
            closest_1hr = None
            for c in data_1hr:
                if c.timestamp.hour == candle_5min.timestamp.hour and \
                   c.timestamp.date() == candle_5min.timestamp.date():
                    closest_1hr = c
                    break

            if closest_1hr:
                prices_1hr.append(closest_1hr.close)
                prices_1hr = prices_1hr[-100:]

            # Find corresponding 4-hr candle
            hour_block = candle_5min.timestamp.hour // 4
            closest_4hr = None
            for c in data_4hr:
                if c.timestamp.date() == candle_5min.timestamp.date() and \
                   c.timestamp.hour // 4 == hour_block:
                    closest_4hr = c
                    break

            if closest_4hr:
                prices_4hr.append(closest_4hr.close)
                prices_4hr = prices_4hr[-100:]

            # Reset daily loss at midnight
            engine.reset_daily_loss(candle_5min.timestamp.date())

            # Check for new entries
            if len(prices_5min) >= 20 and closest_1hr and closest_4hr:
                signal_strength, reason = SignalCalculator.calculate_signal(
                    prices_5min=prices_5min,
                    prices_1hr=prices_1hr,
                    prices_4hr=prices_4hr,
                    volumes_5min=volumes_5min,
                )

                if signal_strength is not None:
                    entries_attempted += 1
                    entered = engine.enter_trade(
                        entry_time=candle_5min.timestamp,
                        entry_price=candle_5min.close,
                        signal_strength=signal_strength,
                        entry_reason=reason,
                    )
                    if entered:
                        trades_executed += 1

            # Check for exits on all active positions
            positions_to_exit = []
            for position_id, position in engine.positions.items():
                exit_reason, exit_price = SignalCalculator.check_exit_conditions(
                    entry_price=position['entry_price'],
                    current_price=candle_5min.close,
                    entry_time=position['entry_time'],
                    current_time=candle_5min.timestamp,
                    prices_5min=prices_5min,
                    daily_loss=engine.daily_loss,
                    daily_loss_limit=BacktestEngine.DAILY_LOSS_LIMIT,
                )

                if exit_reason:
                    positions_to_exit.append((position_id, exit_reason, exit_price))

            # Execute exits
            for position_id, exit_reason, exit_price in positions_to_exit:
                engine.exit_trade(
                    position_id=position_id,
                    exit_time=candle_5min.timestamp,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                )

            # Progress
            if (i + 1) % 1000 == 0:
                logger.info(f"  {i + 1}/{len(data_5min)} candles processed, "
                          f"trades: {len(engine.trades)}, "
                          f"cash: €{engine.cash:.2f}")

        logger.info(f"✅ Simulation complete: {trades_executed} entries attempted, {len(engine.trades)} trades executed")

        # Generate result
        result = engine.get_result()
        logger.info(f"\n📊 RESULTS FOR {symbol}:")
        logger.info(f"   Total Trades: {result.total_trades}")
        logger.info(f"   Win Rate: {result.win_rate:.1f}%")
        logger.info(f"   Profit Factor: {result.profit_factor:.2f}x")
        logger.info(f"   Total P&L: €{result.total_pnl:.2f} ({result.total_pnl_pct:.2f}%)")
        logger.info(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
        logger.info(f"   Max Drawdown: {result.max_drawdown_pct:.2f}%")

        # Check success criteria
        passes, failures = result.passes_criteria()
        if passes:
            logger.info(f"   ✅ PASSED all criteria")
        else:
            logger.warning(f"   ❌ FAILED criteria:")
            for failure in failures:
                logger.warning(f"      - {failure}")

        return result.to_dict()

    def run_all_symbols(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        use_real_data: bool = True,
    ) -> Dict:
        """Run backtest for all symbols"""

        all_results = {}

        for symbol in symbols:
            result = self.run_single_symbol(symbol, start_date, end_date, use_real_data)
            all_results[symbol] = result

        return all_results

    def save_results(self, results: Dict, output_file: Path):
        """Save backtest results to JSON"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"✅ Results saved to {output_file}")

    def generate_report(self, results: Dict) -> str:
        """Generate backtest report"""

        report = "\n" + "=" * 80 + "\n"
        report += "PHASE 2: BACKTEST RESULTS REPORT\n"
        report += f"Date: {datetime.utcnow().isoformat()}\n"
        report += "=" * 80 + "\n\n"

        # Summary table
        report += "SUMMARY\n"
        report += "-" * 80 + "\n"
        report += f"{'Symbol':<12} {'Trades':<8} {'Win%':<8} {'Profit':<12} {'Factor':<8} {'Status':<8}\n"
        report += "-" * 80 + "\n"

        all_passed = True
        for symbol, result in results.items():
            status = "✅ PASS" if result.get('win_rate', 0) >= 55 else "❌ FAIL"
            report += f"{symbol:<12} {result.get('total_trades', 0):<8} "
            report += f"{result.get('win_rate', 0):<8.1f} "
            report += f"€{result.get('total_pnl', 0):<11.2f} "
            report += f"{result.get('profit_factor', 0):<8.2f}x "
            report += f"{status:<8}\n"
            if "FAIL" in status:
                all_passed = False

        report += "-" * 80 + "\n"

        # Detailed results
        report += "\nDETAILED RESULTS\n"
        report += "-" * 80 + "\n"

        for symbol, result in results.items():
            report += f"\n{symbol}:\n"
            report += f"  Total Trades: {result.get('total_trades', 0)}\n"
            report += f"  Winning Trades: {result.get('winning_trades', 0)}\n"
            report += f"  Losing Trades: {result.get('losing_trades', 0)}\n"
            report += f"  Win Rate: {result.get('win_rate', 0):.1f}%\n"
            report += f"  Profit Factor: {result.get('profit_factor', 0):.2f}x\n"
            report += f"  Average Win: €{result.get('avg_win', 0):.2f}\n"
            report += f"  Average Loss: €{result.get('avg_loss', 0):.2f}\n"
            report += f"  Max Win: €{result.get('max_win', 0):.2f}\n"
            report += f"  Max Loss: €{result.get('max_loss', 0):.2f}\n"
            report += f"  Max Consecutive Losses: {result.get('max_consecutive_losses', 0)}\n"
            report += f"  Total P&L: €{result.get('total_pnl', 0):.2f} ({result.get('total_pnl_pct', 0):.2f}%)\n"
            report += f"  Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}\n"
            report += f"  Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%\n"
            report += f"  Avg Trade Duration: {result.get('avg_trade_duration_min', 0):.1f} min\n"
            report += f"  Starting Capital: €{result.get('starting_capital', 0):.2f}\n"
            report += f"  Ending Capital: €{result.get('ending_capital', 0):.2f}\n"

        # Success criteria
        report += "\n" + "=" * 80 + "\n"
        report += "SUCCESS CRITERIA\n"
        report += "=" * 80 + "\n"
        report += "✅ All symbols must pass:\n"
        report += "   - Win Rate ≥ 55%\n"
        report += "   - Profit Factor ≥ 1.5x\n"
        report += "   - Sharpe Ratio ≥ 1.0\n"
        report += "   - Max Consecutive Losses < 5\n"
        report += "   - Max Drawdown < 15%\n\n"

        if all_passed:
            report += "🎉 RESULT: ALL SYMBOLS PASSED - PROCEED TO PHASE 3\n"
        else:
            report += "⚠️  RESULT: SOME SYMBOLS FAILED - ADJUST PARAMETERS AND RETRY\n"

        report += "=" * 80 + "\n"

        return report


def main():
    """Main entry point"""

    logger.info("🚀 Starting Phase 2: Backtesting")

    # Configuration
    start_date = datetime(2025, 1, 4)  # 18 months ago
    end_date = datetime.utcnow()
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

    # Create runner
    runner = BacktestRunner()

    # Run backtest
    logger.info(f"Testing {len(symbols)} symbols from {start_date.date()} to {end_date.date()}")

    results = runner.run_all_symbols(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        use_real_data=True,  # Set to False to use mock data
    )

    # Save results
    output_file = Path("backtest_results.json")
    runner.save_results(results, output_file)

    # Generate report
    report = runner.generate_report(results)
    print(report)

    # Save report
    report_file = Path("PHASE_2_BACKTEST_REPORT.md")
    with open(report_file, 'w') as f:
        f.write(report)
    logger.info(f"✅ Report saved to {report_file}")

    logger.info("✅ Phase 2 complete")


if __name__ == "__main__":
    main()
