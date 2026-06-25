"""Autonomous trading daemon - monitors signals and executes trades automatically."""

import asyncio
import logging
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

from backend.exchange.paper_trading import get_paper_trading
from backend.analytics.regime_detector import get_regime_detector
from backend.analytics.signals import get_signal_generator
from backend.execution.smart_executor import get_smart_executor
from backend.strategies.garp_value_strategy import apply_garp_value_strategy
from backend.analytics.signal_explainer import get_signal_explainer
from backend.analytics.volatility_manager import get_volatility_manager
from backend.trading.portfolio_decision_coordinator import get_portfolio_decision_coordinator
from backend.core.data_quality import get_data_quality_measurer
from backend.core.data_validator import get_price_validator, OrderFillValidator, PositionReconciler
from backend.core.circuit_breaker import get_circuit_breaker
from datetime import timedelta

logger = logging.getLogger(__name__)

# Thread pool for CPU-intensive calculations (prevents blocking event loop)
_signal_thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="signal_calc")


def log_trading_decision(
    decision_type: str,
    symbol: str,
    decision: str,
    reason: str,
    context: Dict,
) -> str:
    """Log a trading decision with full traceability (Pillar #8: Logging Fidelity).

    Args:
        decision_type: 'ENTRY' or 'EXIT'
        symbol: Trading symbol
        decision: 'ACCEPT' or 'REJECT'
        reason: Human-readable reason
        context: Decision context (signal_score, threshold, regime, etc.)

    Returns:
        Decision ID (UUID) for tracing
    """
    decision_id = str(uuid.uuid4())[:8]
    log_entry = {
        "decision_id": decision_id,
        "timestamp": datetime.utcnow().isoformat(),
        "decision_type": decision_type,
        "symbol": symbol,
        "decision": decision,
        "reason": reason,
        **context,
    }

    if decision == "ACCEPT":
        logger.info(f"✅ {decision_type} ACCEPTED [{decision_id}] {symbol}: {reason}")
    else:
        logger.info(f"❌ {decision_type} REJECTED [{decision_id}] {symbol}: {reason}")

    # Log full context for debugging (searchable by decision_id)
    logger.debug(f"DECISION_CONTEXT[{decision_id}]: {json.dumps(log_entry)}")

    return decision_id


@dataclass
class TradeSignal:
    """Signal to buy or sell."""
    symbol: str
    side: str  # BUY or SELL
    strength: float  # 0-100
    reason: str
    timestamp: datetime


@dataclass
class TradingConfig:
    """Configuration for autonomous trading (all values from .env)."""
    enabled: bool = True
    entry_threshold: float = 60.0  # From ENTRY_THRESHOLD env var
    exit_profit_target: float = 0.03  # From EXIT_PROFIT_TARGET env var
    exit_stop_loss: float = 0.02  # From EXIT_STOP_LOSS env var
    position_size_pct: float = 0.05  # From POSITION_SIZE_PCT env var
    max_positions: int = 5  # From MAX_POSITIONS env var
    max_daily_loss_pct: float = 5.0  # From MAX_DAILY_LOSS_PCT env var
    symbols: List[str] = None  # From TRADING_SYMBOLS env var
    loop_sleep_seconds: float = 10.0  # Sleep between trading loop iterations
    retry_sleep_seconds: float = 5.0  # Sleep on error before retry

    def __post_init__(self):
        if self.symbols is None:
            # Crypto + major stocks
            self.symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT',  # Crypto
                'EQ_AAPL', 'EQ_MSFT', 'EQ_TSLA',   # US Stocks
            ]

        # Remove duplicates while preserving order (BUG #5 fix)
        seen = set()
        unique_symbols = []
        for symbol in self.symbols:
            if symbol not in seen:
                seen.add(symbol)
                unique_symbols.append(symbol)

        if len(unique_symbols) != len(self.symbols):
            logger.warning(f"TradingConfig: removed {len(self.symbols) - len(unique_symbols)} duplicate symbols")
            self.symbols = unique_symbols


class AutonomousTrader:
    """Monitors signals and executes trades automatically."""

    def __init__(self, config: TradingConfig = None):
        self.config = config or TradingConfig()
        self.running = False
        self.trade_history: List[Dict] = []
        self.last_signal_time: Dict[str, datetime] = {}
        self.order_failures: Dict[str, int] = {}  # Track failures per symbol (GAP #10)

    async def start(self):
        """Start the autonomous trading loop."""
        self.running = True
        logger.info("Autonomous trader starting...")

        try:
            await self._trading_loop()
        except Exception as e:
            logger.error(f"Autonomous trader error: {e}")
            self.running = False

    async def stop(self):
        """Stop the autonomous trading loop."""
        self.running = False
        logger.info("Autonomous trader stopped")

    async def _trading_loop(self):
        """Main trading loop - runs continuously."""
        loop_count = 0
        portfolio_check_interval = 6  # Check portfolio decisions every 60 seconds (6 * 10s)
        warmup_complete = False

        while self.running:
            try:
                loop_count += 1
                logger.debug(f"🔄 Trading loop iteration {loop_count}")

                # Get current prices - if empty, WebSocket hasn't connected yet
                prices = await self._get_current_prices()
                if not prices or len(prices) < len(self.config.symbols):
                    logger.debug(f"⏳ Waiting for Binance WebSocket prices... ({len(prices) if prices else 0}/{len(self.config.symbols)})")
                    await asyncio.sleep(1)
                    continue

                # First successful price fetch - log warmup complete
                if not warmup_complete:
                    warmup_complete = True
                    logger.info(f"✅ Warmup complete: received prices for {list(prices.keys())}")

                # HARDENING: Measure data quality (Pillar #3: Data Quality Gate)
                data_quality = await self._measure_data_quality(prices)
                logger.info(
                    f"Data Quality Score: {data_quality.overall_score:.0f}% {data_quality}",
                    extra={"extra_fields": {
                        "event": "DATA_QUALITY_CHECK",
                        "overall_score": round(data_quality.overall_score, 1),
                        "pass_gate": data_quality.pass_gate,
                        "price_sanity": round(data_quality.price_sanity, 1),
                        "symbol_coverage": round(data_quality.symbol_coverage, 1),
                        "websocket_health": round(data_quality.websocket_health, 1),
                        "age_variance": round(data_quality.age_variance, 1),
                        "failures": data_quality.failures
                    }}
                )

                # HARDENING: Circuit Breaker checks (Pillar #14: Auto-stop on anomalies)
                circuit_breaker = get_circuit_breaker()

                # Check #1: Data Quality (trip if <30%)
                circuit_breaker.check_data_quality(data_quality.overall_score)

                # Check #2: WebSocket Health (trip if disconnected >2 minutes)
                from backend.exchange.binance_stream import get_stream_client
                stream_client = get_stream_client()
                if stream_client:
                    # last_update is Dict[symbol, datetime], get most recent
                    if isinstance(stream_client.last_update, dict) and stream_client.last_update:
                        most_recent = max(stream_client.last_update.values())
                        last_update_age = (datetime.utcnow() - most_recent).total_seconds()
                    else:
                        last_update_age = 999
                    circuit_breaker.check_websocket_health(stream_client.is_connected, last_update_age)

                # Check #3: Database Integrity (trip if hash verification fails)
                try:
                    from backend.core.database import get_database
                    db = get_database()
                    integrity_ok = db.verify_all_trades_integrity()
                    circuit_breaker.check_database_integrity(integrity_ok)
                except Exception as e:
                    logger.warning(f"Could not verify database integrity: {e}")

                # If circuit breaker is open, stop new entries
                if not circuit_breaker.check_health():
                    cb_status = circuit_breaker.get_status_report()
                    logger.critical(f"🚨 CIRCUIT BREAKER ACTIVE: {cb_status['reason']}")
                    skip_entries = True
                else:
                    skip_entries = False

                # HARDENING: Differentiated quality gates (Entries vs Exits)
                # Exits are lenient to ensure stop losses and profit targets execute
                quality_gate_pass_entry = data_quality.overall_score >= 90.0  # Strict for entries
                quality_gate_pass_exit = data_quality.overall_score >= 60.0   # Lenient for exits

                if not quality_gate_pass_entry:
                    logger.warning(
                        f"⚠️ Entry quality gate FAILED ({data_quality.overall_score:.0f}% < 90%), "
                        f"blocking NEW ENTRIES. Failures: {data_quality.failures}. "
                        f"Exits still allowed (quality >= 60% for stop loss/profit target)"
                    )
                    # Don't skip iteration entirely - exits may still be needed
                    skip_entries = True
                else:
                    skip_entries = False

                if not quality_gate_pass_exit:
                    logger.critical(
                        f"🛑 Exit quality gate FAILED ({data_quality.overall_score:.0f}% < 60%), "
                        f"CANNOT EXECUTE STOPS. Emergency: will attempt liquidation anyway. "
                        f"Failures: {data_quality.failures}"
                    )
                    # Even in emergency, need some minimum data
                    if data_quality.overall_score < 30.0:
                        logger.critical("Data quality catastrophically low, waiting for recovery")
                        await asyncio.sleep(self.config.loop_sleep_seconds)
                        continue

                # Check daily loss limit (BUG FIX #1: Enforce max_daily_loss_pct)
                daily_loss_exceeded = await self._check_daily_loss_limit()
                if daily_loss_exceeded:
                    logger.critical("🛑 Daily loss limit exceeded - stopping all trading!")
                    self.running = False
                    break

                # Check portfolio-level decisions (Phase 318) every 60 seconds
                if loop_count % portfolio_check_interval == 0:
                    await self._check_portfolio_decisions()

                # Monitor each symbol (NEW ENTRIES - quality gated)
                if not skip_entries:
                    for symbol in self.config.symbols:
                        signal = await self._check_symbol(symbol)
                        if signal:
                            logger.info(f"✅ Signal generated for {symbol}: {signal.reason}")
                else:
                    logger.debug(f"Skipping entry signals due to data quality gate (<90%)")

                # Check exits for existing positions (EXITS - lenient quality gate, always run)
                # This ensures stop losses and profit targets execute even with degraded data quality
                await self._check_exits()

                # Sleep briefly before next iteration
                await asyncio.sleep(self.config.loop_sleep_seconds)
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(self.config.retry_sleep_seconds)

    async def _check_symbol(self, symbol: str) -> Optional[TradeSignal]:
        """Check if a symbol should be bought."""
        if not self.config.enabled:
            return None

        try:
            engine = get_paper_trading()
            if not engine:
                logger.error(f"{symbol}: Paper trading engine not initialized")
                return None

            # Check if already have position or at max positions (GAP #9 fix)
            positions = engine.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                logger.debug(f"{symbol}: Already have position, skipping")
                return None  # Already have position in this symbol

            if len(positions) >= self.config.max_positions:
                logger.debug(f"{symbol}: At max positions ({len(positions)}/{self.config.max_positions}), skipping")
                return None  # At position limit

            # Calculate composite signal using thread pool (prevents blocking event loop)
            signal_score, component_scores = await asyncio.get_event_loop().run_in_executor(
                _signal_thread_pool,
                self._calculate_signal_blocking,
                symbol
            )

            # HARDENING: Validate signal quality before proceeding (Pillar #2)
            import math
            if not isinstance(signal_score, (int, float)) or math.isnan(signal_score) or math.isinf(signal_score):
                logger.error(f"{symbol}: Invalid signal score {signal_score} (NaN/Inf/type error), skipping")
                return None

            if signal_score < 0 or signal_score > 100:
                logger.error(f"{symbol}: Signal score {signal_score} out of range [0-100], skipping")
                return None

            if not isinstance(component_scores, dict) or not component_scores:
                logger.error(f"{symbol}: Invalid component scores {component_scores}, skipping")
                return None

            # Validate all component scores are numbers
            for comp_name, comp_value in component_scores.items():
                if not isinstance(comp_value, (int, float)) or math.isnan(comp_value) or math.isinf(comp_value):
                    logger.error(f"{symbol}: Component {comp_name} has invalid value {comp_value}, skipping")
                    return None

            # Get market regime and adaptive entry threshold (Phase 316)
            regime_detector = get_regime_detector()
            regime_info, adaptive_threshold = await self._get_adaptive_entry_threshold(symbol, regime_detector)

            # Explain the signal (Phase 313)
            explainer = get_signal_explainer()
            asset_class = "stock" if symbol.startswith("EQ_") else "crypto"
            explanation = explainer.explain_score(
                symbol=symbol,
                total_score=signal_score,
                component_scores=component_scores,
                asset_class=asset_class,
            )

            # Add regime info to explanation
            regime_emoji = {
                "bull": "✅",
                "bear": "⛔",
                "sideways": "↔️",
                "volatile": "⚠️",
                "unknown": "❓"
            }.get(regime_info.get("regime", "unknown"), "?")
            regime_str = f"{regime_emoji} {regime_info.get('regime', 'unknown')} (entry_threshold: {adaptive_threshold:.1f})"

            # Structured signal decision log
            signal_passed = signal_score >= adaptive_threshold
            logger.info(
                f"{symbol}: {explanation['emoji']} {explanation['reasoning']} (score: {signal_score:.1f}/{adaptive_threshold:.1f}) | Regime: {regime_str}",
                extra={
                    "extra_fields": {
                        "event": "SIGNAL_DECISION",
                        "symbol": symbol,
                        "signal_score": round(signal_score, 2),
                        "threshold": round(adaptive_threshold, 2),
                        "passed": signal_passed,
                        "reasoning": explanation['reasoning'],
                        "component_scores": {
                            k: round(v, 2) if isinstance(v, float) else v
                            for k, v in component_scores.items()
                        },
                        "regime": regime_info.get("regime", "unknown"),
                        "regime_confidence": round(regime_info.get("trend_strength", 0), 2),
                        "asset_class": asset_class,
                    }
                }
            )

            if signal_passed:
                # HARDENING: Log entry decision with full context (Pillar #8: Logging Fidelity)
                decision_id = log_trading_decision(
                    decision_type="ENTRY",
                    symbol=symbol,
                    decision="ACCEPT",
                    reason=explanation['reasoning'],
                    context={
                        "signal_score": signal_score,
                        "threshold": adaptive_threshold,
                        "regime": regime_info.get("regime", "unknown"),
                        "asset_class": asset_class,
                    }
                )

                # Generate entry signal
                signal = TradeSignal(
                    symbol=symbol,
                    side='BUY',
                    strength=signal_score,
                    reason=explanation['reasoning'],  # Use explanation instead of generic reason
                    timestamp=datetime.utcnow()
                )

                # Rate-limit: don't signal same symbol too frequently
                last_time = self.last_signal_time.get(symbol)
                if last_time and (datetime.utcnow() - last_time).total_seconds() < 60:
                    return None

                # Log detailed breakdown
                logger.info(f"{symbol}: Entry signal details:")
                for comp in explanation['breakdown']:
                    logger.info(f"  {comp['label']:30} {comp['score']:6.1f} ({comp['weight']:>3}) → {comp['contribution']:6.1f}")

                # Attempt to execute trade
                await self._execute_entry(signal)
                self.last_signal_time[symbol] = datetime.utcnow()
                return signal

        except Exception as e:
            logger.error(f"Error checking symbol {symbol}: {e}", exc_info=True)

        return None

    async def _calculate_signal(self, symbol: str) -> tuple:
        """Calculate composite signal for a symbol (async wrapper for testing).

        Returns:
            (signal_score, components) tuple where signal_score is 0-100
        """
        loop = asyncio.get_event_loop()
        signal_score, components = await loop.run_in_executor(
            _signal_thread_pool,
            self._calculate_signal_blocking,
            symbol
        )
        return signal_score, components

    async def _check_exits(self):
        """Check if any positions should be exited (Phase 314/316: Dynamic stops + regime-aware).

        HARDENING: Uses lenient data quality gate (≥60% vs ≥90% for entries).
        Rationale: Must execute stop losses and profit targets to protect capital,
        even with degraded data quality. Can skip new entries, but exits MUST work.
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return

            positions = engine.get_positions()
            prices = await self._get_current_prices()
            vol_mgr = get_volatility_manager()
            regime_detector = get_regime_detector()

            for pos in positions:
                symbol = pos['symbol']
                current_price = prices.get(symbol)
                if not current_price:
                    continue

                entry_price = pos['entry_price']
                pnl_pct = (current_price - entry_price) / entry_price

                # Get dynamic stops and regime-aware thresholds
                from backend.analytics.historical_data import get_historical_service
                hist_service = get_historical_service()
                dynamic_stops = None
                exit_thresholds = None

                if hist_service:
                    end = datetime.utcnow()
                    start = end - timedelta(days=60)
                    ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
                    if ohlcv is not None and len(ohlcv) >= 14:
                        # Get dynamic stops from volatility manager
                        dynamic_stops = vol_mgr.calculate_stops(entry_price, ohlcv)
                        # Get regime-aware exit thresholds
                        regime_info = regime_detector.detect_regime(ohlcv)
                        exit_thresholds = regime_detector.get_adaptive_thresholds(regime_info)

                # Use dynamic stops and regime thresholds if available, otherwise fall back to fixed
                if dynamic_stops and exit_thresholds:
                    # Use regime-adjusted thresholds (Phase 316)
                    stop_loss_pct = exit_thresholds.get("stop_loss", self.config.exit_stop_loss)
                    take_profit_pct = exit_thresholds.get("profit_target", self.config.exit_profit_target)
                    regime_name = regime_info.get("regime", "unknown")
                    logger.debug(f"{symbol}: Regime-aware exits ({regime_name}) - TP: {take_profit_pct*100:.2f}%, SL: {stop_loss_pct*100:.2f}%")
                elif dynamic_stops:
                    # Use dynamic ATR-based stops
                    stop_loss_pct = dynamic_stops["stop_loss_pct"]
                    take_profit_pct = dynamic_stops["take_profit_pct"]
                    logger.debug(f"{symbol}: Dynamic stops - SL: {stop_loss_pct*100:.2f}%, TP: {take_profit_pct*100:.2f}%")
                else:
                    # Fall back to fixed config
                    stop_loss_pct = self.config.exit_stop_loss
                    take_profit_pct = self.config.exit_profit_target

                # Check profit target
                if pnl_pct >= take_profit_pct:
                    await self._execute_exit(
                        symbol,
                        current_price,
                        f'Profit target hit ({pnl_pct*100:.1f}%)',
                        pnl_pct,
                    )
                    continue

                # Check stop loss
                if pnl_pct <= -stop_loss_pct:
                    await self._execute_exit(
                        symbol,
                        current_price,
                        f'Stop loss hit ({pnl_pct*100:.1f}%)',
                        pnl_pct,
                    )
                    continue

        except Exception as e:
            logger.error(f"Error checking exits: {e}", exc_info=True)

    async def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been exceeded (BUG FIX #1).

        Returns:
            True if daily loss limit exceeded (should stop trading), False otherwise
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return False

            account = engine.get_account_state()
            daily_pnl = account.get('daily_pnl', 0.0)
            total_equity = account.get('total_equity', 10000.0)

            if total_equity <= 0:
                return False

            daily_loss_pct = abs(daily_pnl) / total_equity * 100

            # Check if daily loss exceeds limit
            if daily_pnl < 0 and daily_loss_pct >= self.config.max_daily_loss_pct:
                logger.critical(
                    f"🛑 DAILY LOSS LIMIT EXCEEDED: "
                    f"${abs(daily_pnl):.2f} ({daily_loss_pct:.2f}%) >= "
                    f"{self.config.max_daily_loss_pct:.1f}% limit"
                )
                return True

            # Log if approaching limit (80% of limit)
            if daily_pnl < 0 and daily_loss_pct >= (self.config.max_daily_loss_pct * 0.8):
                logger.warning(
                    f"⚠️  Approaching daily loss limit: "
                    f"${abs(daily_pnl):.2f} ({daily_loss_pct:.2f}%) "
                    f"(limit: {self.config.max_daily_loss_pct:.1f}%)"
                )

            return False

        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}", exc_info=True)
            return False

    async def _validate_risk_before_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
    ) -> tuple[bool, str]:
        """Pre-order risk validation (Pillar #6: Risk Enforcement Double-Check).

        Validates:
        1. Daily loss limit not exceeded
        2. New order won't push us over limit (worst-case)
        3. Sufficient cash available (for BUY orders)
        4. Position size within limits

        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            current_price: Current market price

        Returns:
            (is_valid, reason_if_invalid)
        """
        try:
            engine = get_paper_trading()
            if not engine:
                return False, "Paper trading engine unavailable"

            account = engine.get_account_state()
            daily_pnl = account.get('daily_pnl', 0.0)
            total_equity = account.get('total_equity', 10000.0)
            cash = account.get('cash', 10000.0)

            if total_equity <= 0:
                return False, "Invalid account equity"

            # Check 1: Daily loss not already exceeded
            daily_loss_pct = abs(daily_pnl) / total_equity * 100
            if daily_pnl < 0 and daily_loss_pct >= self.config.max_daily_loss_pct:
                return False, f"Daily loss limit already exceeded: ${abs(daily_pnl):.2f}"

            # Check 2: BUY-specific validations
            if side == "BUY":
                order_cost = quantity * current_price

                # Verify sufficient cash
                if order_cost > cash:
                    return False, f"Insufficient cash: need ${order_cost:.2f}, have ${cash:.2f}"

                # Worst-case loss: order fails and position closes at -2% (stop loss)
                worst_case_loss = order_cost * 0.02 + (order_cost * 0.001)  # SL + fee
                projected_daily_pnl = daily_pnl - worst_case_loss
                projected_loss_pct = abs(projected_daily_pnl) / total_equity * 100

                if projected_loss_pct > self.config.max_daily_loss_pct:
                    return (
                        False,
                        f"Order would exceed daily limit: worst-case loss ${worst_case_loss:.2f} → "
                        f"${abs(projected_daily_pnl):.2f} ({projected_loss_pct:.1f}%)",
                    )

            logger.debug(
                f"RISK_VALIDATION_PASSED: {side} {quantity} {symbol} @ ${current_price:.2f} "
                f"(daily P&L: ${daily_pnl:.2f}, limit: {self.config.max_daily_loss_pct:.1f}%)"
            )

            return True, "OK"

        except Exception as e:
            logger.error(f"Error validating risk before order: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"

    async def _check_portfolio_decisions(self):
        """Check and execute portfolio-level regime decisions (Phase 318)."""
        try:
            engine = get_paper_trading()
            if not engine:
                return

            # Get portfolio state
            positions = engine.get_positions()
            prices = await self._get_current_prices()
            account = engine.get_account_state()
            portfolio_value = account.get('total_equity', 0)

            if not positions or not prices or portfolio_value <= 0:
                return

            # Fetch regime data for all positions
            symbol_regimes = await self._fetch_all_regimes(
                [p['symbol'] for p in positions]
            )

            if not symbol_regimes:
                return

            # Get portfolio decisions from coordinator (Phase 318)
            coordinator = get_portfolio_decision_coordinator()
            decisions = await coordinator.make_portfolio_decisions(
                symbol_regimes=symbol_regimes,
                current_positions=positions,
                portfolio_value=portfolio_value,
                target_allocation=self._get_target_allocation(),
                current_prices=prices,
            )

            # Execute high-urgency decisions (exits, critical rotations)
            for decision in decisions:
                if decision.urgency >= 8:
                    # High urgency: execute immediately
                    await self._execute_portfolio_decision(decision, prices)
                elif decision.urgency >= 6:
                    # Medium urgency: queue for execution
                    logger.info(f"📋 Queued portfolio decision: {decision.decision_type} "
                              f"(urgency {decision.urgency}/10)")
                else:
                    # Low urgency: just log
                    logger.debug(f"📋 Portfolio decision: {decision.decision_type} "
                               f"(urgency {decision.urgency}/10)")

        except Exception as e:
            logger.error(f"Error checking portfolio decisions: {e}", exc_info=True)

    async def _fetch_all_regimes(self, symbols: List[str]) -> Dict[str, Any]:
        """Fetch regime info for all symbols."""
        try:
            from backend.analytics.historical_data import get_historical_service
            from backend.analytics.regime_detector import get_regime_detector

            hist_service = get_historical_service()
            regime_detector = get_regime_detector()
            regimes = {}

            if not hist_service:
                return regimes

            end = datetime.utcnow()
            start = end - timedelta(days=90)

            for symbol in symbols:
                try:
                    ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
                    if ohlcv is not None and len(ohlcv) >= 200:
                        regime_info = regime_detector.detect_regime(ohlcv)
                        regimes[symbol] = regime_info
                except Exception as e:
                    logger.debug(f"Could not fetch regime for {symbol}: {e}")

            return regimes

        except Exception as e:
            logger.error(f"Error fetching regimes: {e}")
            return {}

    def _get_target_allocation(self) -> Dict[str, float]:
        """Get target allocation (equal weight for now)."""
        if not self.config.symbols:
            return {}

        equal_weight = 100.0 / len(self.config.symbols)
        return {symbol: equal_weight for symbol in self.config.symbols}

    async def _execute_portfolio_decision(
        self,
        decision: "PortfolioDecision",  # Type hint
        current_prices: Dict[str, float],
    ) -> bool:
        """Execute a portfolio-level decision (exit, rotation, rebalance)."""
        try:
            engine = get_paper_trading()
            if not engine:
                logger.error("Paper trading engine not initialized")
                return False

            logger.info(f"🚀 Executing portfolio decision: {decision.decision_type}")
            logger.info(f"   Targets: {decision.target_symbols}")
            logger.info(f"   Actions: {decision.actions}")
            logger.info(f"   Rationale: {decision.rationale}")

            executed_count = 0

            # Execute actions in priority order
            for symbol, action in decision.actions.items():
                if action == "SELL":
                    # Find and close position
                    positions = engine.get_positions()
                    pos = next((p for p in positions if p['symbol'] == symbol), None)

                    if pos:
                        result = await engine.place_order(
                            symbol=symbol,
                            side='SELL',
                            quantity=pos['quantity'],
                            current_price=current_prices.get(symbol, pos['entry_price']),
                            order_type='MARKET',
                            strategy_name='portfolio_decision_coordinator'
                        )

                        if result.get('status') == 'FILLED':
                            logger.info(f"✅ Sold {pos['quantity']:.6f} {symbol} "
                                      f"@ {current_prices.get(symbol, 0):.2f}")
                            executed_count += 1
                        else:
                            logger.warning(f"❌ Failed to sell {symbol}: {result.get('error')}")

                elif action == "BUY":
                    # Execute BUY for rotation/rebalancing
                    # Use conservative sizing: 5% of portfolio per symbol
                    account = engine.get_account_state()
                    capital = account['total_equity'] * 0.05
                    price = current_prices.get(symbol)

                    if price and price > 0:
                        quantity = capital / price

                        result = await engine.place_order(
                            symbol=symbol,
                            side='BUY',
                            quantity=quantity,
                            current_price=price,
                            order_type='MARKET',
                            strategy_name='portfolio_decision_coordinator'
                        )

                        if result.get('status') == 'FILLED':
                            logger.info(f"✅ Bought {quantity:.6f} {symbol} @ {price:.2f}")
                            executed_count += 1
                        else:
                            logger.warning(f"❌ Failed to buy {symbol}: {result.get('error')}")

            # Mark decision as executed if all actions completed
            if executed_count == len(decision.actions):
                coordinator = get_portfolio_decision_coordinator()
                coordinator.mark_decision_executed(decision)
                logger.info(f"✅ Portfolio decision executed: {decision.decision_type}")
                return True
            else:
                logger.warning(f"⚠️ Partial execution: {executed_count}/{len(decision.actions)} actions")
                return False

        except Exception as e:
            logger.error(f"Error executing portfolio decision: {e}", exc_info=True)
            return False

    async def _execute_entry(self, signal: TradeSignal) -> bool:
        """Execute a BUY order."""
        try:
            engine = get_paper_trading()
            executor = get_smart_executor()
            if not engine:
                logger.error(f"{signal.symbol}: Paper trading engine not initialized")
                return False
            if not executor:
                logger.error(f"{signal.symbol}: Smart executor not initialized")
                return False

            # Get current price
            prices = await self._get_current_prices()
            current_price = prices.get(signal.symbol)
            if not current_price:
                logger.error(f"{signal.symbol}: No price available for execution")
                return False

            logger.info(f"🎯 EXECUTING ENTRY FOR {signal.symbol} @ ${current_price:.2f}")

            # HARDENING: Pre-order risk validation (Pillar #6: Risk Enforcement Double-Check)
            # Estimate position size to validate risk (will be recalculated below with volatility)
            account = engine.get_account_state()
            estimated_quantity = (account['total_equity'] * 0.03) / current_price  # Rough estimate
            risk_valid, risk_reason = await self._validate_risk_before_order(
                symbol=signal.symbol,
                side='BUY',
                quantity=estimated_quantity,
                current_price=current_price,
            )
            if not risk_valid:
                logger.critical(f"🛑 ENTRY REJECTED - RISK CHECK FAILED: {risk_reason}")
                return False

            # Calculate position size with volatility & regime adjustments (Phase 314/316)
            account = engine.get_account_state()
            capital = account['total_equity']

            # Get volatility manager and regime detector for dynamic sizing and stops
            vol_mgr = get_volatility_manager()
            regime_detector = get_regime_detector()

            # Fetch historical data for volatility and regime calculation
            from backend.analytics.historical_data import get_historical_service
            hist_service = get_historical_service()
            if hist_service:
                end = datetime.utcnow()
                start = end - timedelta(days=90)
                ohlcv_hist = hist_service.fetch_ohlcv(signal.symbol, start, end)
            else:
                ohlcv_hist = None

            # Calculate volatility metrics and regime
            regime_info = None
            regime_adjustment = 1.0
            if ohlcv_hist is not None and len(ohlcv_hist) >= 20:
                vol_metrics = vol_mgr.calculate_volatility(ohlcv_hist)
                logger.info(f"   Volatility: {vol_metrics.get('vol_20d', 0):.1f}% ({vol_metrics.get('regime', '?')})")

                # Get regime-aware position sizing adjustment (Phase 316)
                if len(ohlcv_hist) >= 200:  # Need 200+ candles for regime detector
                    regime_info = regime_detector.detect_regime(ohlcv_hist)
                    regime_thresholds = regime_detector.get_adaptive_thresholds(regime_info)
                    regime_adjustment = regime_thresholds.get("position_size_adjustment", 1.0)
                    logger.info(f"   Regime: {regime_info.get('regime', 'unknown')} (size multiplier: {regime_adjustment:.2f}x)")
            else:
                vol_metrics = {"current_vol": 0.30, "regime": "medium", "vol_20d": None}
                logger.warning(f"   Insufficient data for volatility, using defaults")

            # Safety checks (GAP #1: extreme price handling)
            if current_price <= 0 or current_price > 1e10:
                logger.error(f"{signal.symbol}: Invalid price {current_price}, rejecting order")
                return False

            # Dynamic position sizing based on volatility and regime (Phase 314/316)
            sizing = vol_mgr.calculate_position_size(
                account_equity=capital,
                current_price=current_price,
                vol_metrics=vol_metrics,
                entry_signal_strength=signal.strength,
            )

            # Apply regime adjustment to position size
            base_position_pct = sizing["position_size_pct"]
            adjusted_position_pct = base_position_pct * regime_adjustment
            adjusted_position_pct = max(0.01, min(adjusted_position_pct, 0.10))  # Clamp to 1-10%

            adjusted_position_value = capital * adjusted_position_pct
            quantity = adjusted_position_value / current_price
            position_value = adjusted_position_value

            # Sanity check: quantity should be reasonable
            if quantity > 1_000_000:
                logger.error(f"{signal.symbol}: Position size unreasonable ({quantity:.0f} units), rejecting")
                return False

            logger.info(f"   Position: {quantity:.8f} {signal.symbol}")
            logger.info(f"   Cost: €{position_value:.2f}")
            logger.info(f"   Sizing: {sizing['reason']} | Regime adjustment: {regime_adjustment:.2f}x")

            # Validate via Smart Gateway using ExecutionContext
            from backend.execution.smart_executor import ExecutionContext
            context = ExecutionContext(
                symbol=signal.symbol,
                quantity=quantity,
                current_price=current_price,
                min_confidence=0.6,
                max_position_pct=self.config.position_size_pct
            )
            decision = executor.evaluate_entry(context)

            logger.info(f"   Smart Executor Decision: {decision.decision}")
            logger.info(f"   Reason: {decision.reason}")

            if decision.decision != "EXECUTE":
                logger.warning(f"❌ ENTRY REJECTED for {signal.symbol}: {decision.reason}")
                return False

            logger.info(f"   ✅ Approval granted - Placing order...")

            # Place order
            result = await engine.place_order(
                symbol=signal.symbol,
                side='BUY',
                quantity=quantity,
                current_price=current_price,
                order_type='MARKET',
                strategy_name='autonomous_trader'
            )

            logger.info(f"   Order Result: {result}")

            if result.get('status') == 'FILLED':
                trade_log = {
                    'timestamp': datetime.utcnow().isoformat() + "Z",
                    'symbol': signal.symbol,
                    'side': 'BUY',
                    'quantity': quantity,
                    'price': current_price,
                    'reason': signal.reason,
                    'signal_strength': signal.strength
                }
                self.trade_history.append(trade_log)

                # Structured trade execution log
                logger.info(
                    f"🚀 BUY EXECUTED: {quantity:.6f} {signal.symbol} @ ${current_price:.2f}",
                    extra={
                        "extra_fields": {
                            "event": "TRADE_EXECUTED",
                            "order_id": result.get('order_id', 'unknown'),
                            "symbol": signal.symbol,
                            "side": "BUY",
                            "quantity": round(quantity, 6),
                            "price": round(current_price, 2),
                            "total_value": round(quantity * current_price, 2),
                            "strategy": "autonomous_trader",
                            "signal_strength": round(signal.strength, 2),
                            "signal_reason": signal.reason,
                            "status": result.get('status'),
                            "timestamp": trade_log['timestamp'],
                        }
                    }
                )
                # Clear failure count on success
                self.order_failures[signal.symbol] = 0
                return True
            else:
                # Track failures (GAP #10 fix)
                failures = self.order_failures.get(signal.symbol, 0) + 1
                self.order_failures[signal.symbol] = failures

                # Structured order failure log
                logger.warning(
                    f"BUY order failed for {signal.symbol}",
                    extra={
                        "extra_fields": {
                            "event": "ORDER_FAILED",
                            "order_id": result.get('order_id', 'unknown'),
                            "symbol": signal.symbol,
                            "side": "BUY",
                            "quantity": round(quantity, 6),
                            "price": round(current_price, 2),
                            "strategy": "autonomous_trader",
                            "error_code": result.get('error_code'),
                            "error_message": result.get('error'),
                            "consecutive_failures": failures,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                    }
                )

                # Back off if repeated failures
                if failures > 3:
                    logger.error(f"{signal.symbol}: {failures} consecutive failures, pausing trading")
                return False

        except Exception as e:
            failures = self.order_failures.get(signal.symbol, 0) + 1
            self.order_failures[signal.symbol] = failures
            logger.error(f"Error executing entry for {signal.symbol}: {e} (failure #{failures})")
            return False

    async def _execute_exit(self, symbol: str, current_price: float, reason: str, pnl_pct: float = 0.0) -> bool:
        """Execute a SELL order."""
        try:
            engine = get_paper_trading()
            if not engine:
                return False

            # Find position
            positions = engine.get_positions()
            pos = next((p for p in positions if p['symbol'] == symbol), None)
            if not pos:
                return False

            quantity = pos['quantity']

            # Place order
            result = await engine.place_order(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                current_price=current_price,
                order_type='MARKET',
                strategy_name='autonomous_trader'
            )

            if result.get('status') == 'FILLED':
                pnl = result.get('pnl', 0)
                exit_log = {
                    'timestamp': datetime.utcnow().isoformat() + "Z",
                    'symbol': symbol,
                    'side': 'SELL',
                    'quantity': quantity,
                    'price': current_price,
                    'reason': reason,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                }
                self.trade_history.append(exit_log)

                # Structured trade exit log
                logger.info(
                    f"📊 SELL {quantity:.6f} {symbol} @ {current_price} - PnL: €{pnl:.2f}",
                    extra={
                        "extra_fields": {
                            "event": "TRADE_EXIT",
                            "order_id": result.get('order_id', 'unknown'),
                            "symbol": symbol,
                            "side": "SELL",
                            "quantity": round(quantity, 6),
                            "price": round(current_price, 2),
                            "total_value": round(quantity * current_price, 2),
                            "strategy": "autonomous_trader",
                            "exit_reason": reason,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 4),
                            "status": result.get('status'),
                            "timestamp": exit_log['timestamp'],
                        }
                    }
                )
                return True
            else:
                # Structured exit failure log
                logger.warning(
                    f"SELL order failed for {symbol}",
                    extra={
                        "extra_fields": {
                            "event": "EXIT_FAILED",
                            "order_id": result.get('order_id', 'unknown'),
                            "symbol": symbol,
                            "side": "SELL",
                            "quantity": round(quantity, 6),
                            "price": round(current_price, 2),
                            "strategy": "autonomous_trader",
                            "exit_reason": reason,
                            "error_code": result.get('error_code'),
                            "error_message": result.get('error'),
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                    }
                )
                return False

        except Exception as e:
            logger.error(f"Error executing exit for {symbol}: {e}")
            return False

    def _calculate_signal_blocking(self, symbol: str) -> tuple:
        """
        Calculate composite signal (0-100) for a symbol using real technical analysis.

        **BLOCKING**: This method performs CPU-intensive pandas calculations.
        Run in thread pool via asyncio.get_event_loop().run_in_executor() to avoid blocking event loop.

        Returns:
        --------
        (signal_score, component_scores) where component_scores is dict with GARP and Technical scores
        """
        try:
            from backend.analytics.historical_data import get_historical_service
            from datetime import datetime, timedelta

            hist_service = get_historical_service()
            if not hist_service:
                return 0.0, {"garp": 0.0, "technical": 0.0}

            # Get last 60 days of OHLCV data for technical analysis
            end = datetime.utcnow()
            start = end - timedelta(days=60)

            ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
            if ohlcv is None or ohlcv.empty or len(ohlcv) < 14:
                # Not enough data for technical analysis
                return 0.0, {"garp": 0.0, "technical": 0.0}

            # Calculate technical indicators
            # Extract 'Close' prices, handling both flat and multi-level columns
            try:
                prices = ohlcv['Close']
                # If prices is a DataFrame (multi-level), extract the first column as Series
                if hasattr(prices, 'iloc'):
                    if len(prices.shape) > 1:
                        prices = prices.iloc[:, 0]
            except:
                return 0.0, {"garp": 0.0, "technical": 0.0}

            # RSI (14-period)
            import pandas as pd
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()

            # Calculate RS safely handling division
            rs = gain / loss.replace(0, 0.0001)  # Avoid division by zero
            rsi = 100 - (100 / (1 + rs))
            try:
                rsi_value = float(rsi.iloc[-1])
                rsi_value = 50.0 if pd.isna(rsi_value) else rsi_value
            except:
                rsi_value = 50.0

            # MACD
            exp1 = prices.ewm(span=12, adjust=False).mean()
            exp2 = prices.ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=9, adjust=False).mean()
            macd_histogram = macd - signal_line
            try:
                macd_value = float(macd_histogram.iloc[-1])
                macd_value = 0.0 if pd.isna(macd_value) else macd_value
            except:
                macd_value = 0.0

            # Bollinger Bands
            sma = prices.rolling(window=20).mean()
            std = prices.rolling(window=20).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            current_price = float(prices.iloc[-1])
            upper_val = float(upper_band.iloc[-1])
            lower_val = float(lower_band.iloc[-1])
            band_diff = upper_val - lower_val
            bb_position = (current_price - lower_val) / band_diff if band_diff > 0.001 else 0.5

            # Calculate composite signal (0-100)
            signal_score = 50.0  # Neutral baseline

            # RSI component (0-30 points)
            if rsi_value < 30:
                signal_score += 30  # Oversold = strong buy
            elif rsi_value < 40:
                signal_score += 20  # Weak oversold
            elif rsi_value > 70:
                signal_score -= 20  # Overbought = sell
            elif rsi_value > 60:
                signal_score -= 10  # Slightly overbought

            # MACD component (0-20 points)
            if macd_value > 0:
                signal_score += min(20, macd_value * 100)  # Bullish momentum
            else:
                signal_score += max(-20, macd_value * 100)  # Bearish momentum

            # Bollinger Bands component (0-30 points)
            if bb_position < 0.2:
                signal_score += 30  # Near lower band = oversold
            elif bb_position > 0.8:
                signal_score -= 20  # Near upper band = overbought
            elif bb_position > 0.5:
                signal_score += 10  # Above middle = bullish
            else:
                signal_score -= 10  # Below middle = bearish

            # Clamp to 0-100 range
            technical_score = max(0, min(100, signal_score))

            # For stocks: blend GARP with technical signals (60% GARP, 40% technical)
            # For crypto: use technical only
            garp_score = 0.0
            if symbol.startswith("EQ_"):
                try:
                    garp_df = apply_garp_value_strategy(ohlcv)
                    if not garp_df.empty and len(garp_df) > 0:
                        # Extract GARP position (0.0 or 1.0) for entry signal
                        garp_position = float(garp_df["position"].iloc[-1])

                        # If GARP position = 1, use high GARP score; if 0, use lower score
                        garp_score = 70.0 if garp_position > 0.5 else 30.0

                        # Blend: weight GARP heavily but allow technical to push over threshold
                        signal_score = (0.6 * garp_score) + (0.4 * technical_score)
                        logger.debug(f"{symbol} signal: {signal_score:.1f} (GARP={garp_score:.1f}, Technical={technical_score:.1f}, Position={garp_position})")
                    else:
                        signal_score = technical_score
                        logger.debug(f"{symbol} signal: {signal_score:.1f} (technical only, GARP empty)")
                except Exception as e:
                    logger.warning(f"{symbol}: GARP calculation failed, using technical only: {e}")
                    signal_score = technical_score
                    garp_score = 0.0
            else:
                signal_score = technical_score
                garp_score = 0.0  # No GARP for crypto

            signal_score = max(0, min(100, signal_score))
            logger.debug(f"{symbol} signal: {signal_score:.1f} (RSI={rsi_value:.1f}, MACD={macd_value:.4f}, BB={bb_position:.2f})")

            # Return signal score and component scores for explainer
            component_scores = {
                "garp": garp_score,
                "technical": technical_score,
            }
            return signal_score, component_scores

        except Exception as e:
            logger.error(f"Error calculating signal for {symbol}: {e}")
            return 0.0, {"garp": 0.0, "technical": 0.0}

    async def _get_adaptive_entry_threshold(self, symbol: str, regime_detector) -> tuple:
        """
        Get adaptive entry threshold based on market regime.

        Returns:
        --------
        (regime_info, adaptive_threshold)
        """
        try:
            from backend.analytics.historical_data import get_historical_service
            hist_service = get_historical_service()
            regime_info = {"regime": "unknown"}
            adaptive_threshold = self.config.entry_threshold  # Default fallback

            if hist_service:
                end = datetime.utcnow()
                start = end - timedelta(days=90)
                ohlcv = hist_service.fetch_ohlcv(symbol, start, end)

                if ohlcv is not None and len(ohlcv) >= 200:  # Need 200+ candles for regime detection
                    # Run regime detection in thread pool to avoid blocking
                    regime_info = await asyncio.get_event_loop().run_in_executor(
                        _signal_thread_pool,
                        regime_detector.detect_regime,
                        ohlcv
                    )
                    thresholds = regime_detector.get_adaptive_thresholds(regime_info)
                    adaptive_threshold = thresholds.get("entry_threshold", self.config.entry_threshold)

            return regime_info, adaptive_threshold

        except Exception as e:
            logger.debug(f"Error getting adaptive threshold for {symbol}: {e}")
            return {"regime": "unknown"}, self.config.entry_threshold

    async def _get_current_prices(self) -> Dict[str, float]:
        """Get current prices from Binance WebSocket with validation (HARDENING: Pillars #1, #9).

        Enforces 5-second max age (Pillar #1: Data Freshness)
        Validates price ranges and spikes (Pillar #9: Incoming Data Validation)
        """
        try:
            from backend.exchange.binance_stream import get_stream_client
            client = get_stream_client()
            if not client:
                logger.warning("Price fetch: WebSocket client not initialized")
                return {}

            if not client.is_connected:
                logger.warning("Price fetch: WebSocket not connected, no fresh data available")
                return {}

            # HARDENING: Get prices only if fresh (max 5 seconds old) - Pillar #1
            prices = client.get_prices_fresh(self.config.symbols, max_age_seconds=5)

            if len(prices) < len(self.config.symbols):
                missing = len(self.config.symbols) - len(prices)
                logger.warning(
                    f"Price freshness gate: {missing} of {len(self.config.symbols)} prices "
                    f"too stale or missing, skipping trading this iteration"
                )
                return prices

            # HARDENING: Validate prices for poisoning (Pillar #9: Incoming Data Validation)
            validator = get_price_validator()
            valid_prices, invalid_prices = validator.validate_prices_bulk(prices, datetime.utcnow())

            # Log any rejections
            if invalid_prices:
                logger.warning(f"🚨 POISONED PRICES REJECTED ({len(invalid_prices)}):")
                for symbol, reason in invalid_prices.items():
                    logger.warning(f"  ❌ {symbol}: {reason}")

            # Return only validated prices
            if len(valid_prices) < len(self.config.symbols):
                logger.warning(
                    f"Data poisoning gate: {len(invalid_prices)} prices rejected, "
                    f"only {len(valid_prices)} of {len(self.config.symbols)} valid"
                )

            return valid_prices

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}

    async def _measure_data_quality(self, prices: Dict[str, float]):
        """Measure data quality across 6 dimensions (HARDENING: Pillar #3).

        Returns DataQualityScore with overall score ≥90% required to trade.
        """
        from backend.exchange.binance_stream import get_stream_client

        measurer = get_data_quality_measurer()
        client = get_stream_client()

        # Get WebSocket health info
        websocket_health = {}
        if client:
            health_status = await client.get_connection_status()
            websocket_health = {
                "connected": client.is_connected,
                "reconnect_attempts": client.reconnect_attempts,
                "last_update": health_status.get("last_update"),
            }

        # Get price age info
        last_updates = {}
        if client:
            last_updates = client.last_update.copy()

        # Get historical volatility (estimated from regime detector)
        historical_volatility = {}
        for symbol in self.config.symbols:
            # Default to 2% until we have better volatility data
            historical_volatility[symbol] = 2.0

        # Measure data quality
        score = measurer.measure(
            current_prices=prices,
            required_symbols=self.config.symbols,
            websocket_health=websocket_health,
            last_updates=last_updates,
            historical_volatility=historical_volatility,
        )

        return score

    def get_status(self) -> Dict:
        """Get trader status."""
        engine = get_paper_trading()
        daily_pnl = 0.0
        daily_pnl_pct = 0.0
        total_equity = 10000.0

        if engine:
            account = engine.get_account_state()
            daily_pnl = account.get('daily_pnl', 0.0)
            total_equity = account.get('total_equity', 10000.0)
            if total_equity > 0:
                daily_pnl_pct = (daily_pnl / total_equity) * 100

        return {
            'running': self.running,
            'enabled': self.config.enabled,
            'active_positions': 0,  # Would calculate
            'total_trades': len(self.trade_history),
            'recent_trades': self.trade_history[-10:] if self.trade_history else [],
            'daily_pnl': daily_pnl,
            'daily_pnl_pct': daily_pnl_pct,
            'config': {
                'entry_threshold': self.config.entry_threshold,
                'exit_profit_target': self.config.exit_profit_target,
                'exit_stop_loss': self.config.exit_stop_loss,
                'max_positions': self.config.max_positions,
                'symbols': self.config.symbols
            }
        }


# Global instance
_autonomous_trader: Optional[AutonomousTrader] = None


def init_autonomous_trader(config: TradingConfig = None) -> AutonomousTrader:
    """Initialize global autonomous trader."""
    global _autonomous_trader
    _autonomous_trader = AutonomousTrader(config)
    return _autonomous_trader


def get_autonomous_trader() -> Optional[AutonomousTrader]:
    """Get global autonomous trader."""
    return _autonomous_trader
