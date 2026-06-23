"""Autonomous trading daemon - monitors signals and executes trades automatically."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime

from backend.exchange.paper_trading import get_paper_trading
from backend.analytics.regime_detector import get_regime_detector
from backend.analytics.signals import get_signal_generator
from backend.execution.smart_executor import get_smart_executor

logger = logging.getLogger(__name__)


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
    """Configuration for autonomous trading."""
    enabled: bool = True
    entry_threshold: float = 60.0  # Signal score to trigger BUY
    exit_profit_target: float = 0.03  # 3% profit target
    exit_stop_loss: float = 0.02  # 2% stop loss
    position_size_pct: float = 0.10  # 10% of capital per position
    max_positions: int = 5
    symbols: List[str] = None  # Symbols to trade

    def __post_init__(self):
        if self.symbols is None:
            # Crypto + major stocks
            self.symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT',  # Crypto
                'EQ_AAPL', 'EQ_MSFT', 'EQ_TSLA',   # US Stocks
            ]


class AutonomousTrader:
    """Monitors signals and executes trades automatically."""

    def __init__(self, config: TradingConfig = None):
        self.config = config or TradingConfig()
        self.running = False
        self.trade_history: List[Dict] = []
        self.last_signal_time: Dict[str, datetime] = {}

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
        while self.running:
            try:
                loop_count += 1
                logger.debug(f"🔄 Trading loop iteration {loop_count}")

                # Get current prices - if empty, WebSocket hasn't connected yet
                prices = await self._get_current_prices()
                if not prices:
                    logger.debug("⏳ Waiting for Binance WebSocket prices...")
                    await asyncio.sleep(1)
                    continue

                # Monitor each symbol
                for symbol in self.config.symbols:
                    signal = await self._check_symbol(symbol)
                    if signal:
                        logger.info(f"✅ Signal generated for {symbol}: {signal.reason}")

                # Check exits for existing positions
                await self._check_exits()

                # Sleep briefly before next iteration (check every 5 seconds)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _check_symbol(self, symbol: str) -> Optional[TradeSignal]:
        """Check if a symbol should be bought."""
        if not self.config.enabled:
            return None

        try:
            engine = get_paper_trading()
            if not engine:
                logger.error(f"{symbol}: Paper trading engine not initialized")
                return None

            # Check if already have position
            positions = engine.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                logger.debug(f"{symbol}: Already have position, skipping")
                return None  # Already have position in this symbol

            # Calculate composite signal using real technical analysis (0-100)
            signal_score = await self._calculate_signal(symbol)
            logger.info(f"{symbol}: Signal score = {signal_score:.1f} (threshold: {self.config.entry_threshold})")

            if signal_score >= self.config.entry_threshold:
                # Generate entry signal
                signal = TradeSignal(
                    symbol=symbol,
                    side='BUY',
                    strength=signal_score,
                    reason=f'Composite signal {signal_score:.0f} >= {self.config.entry_threshold}',
                    timestamp=datetime.utcnow()
                )

                # Rate-limit: don't signal same symbol too frequently
                last_time = self.last_signal_time.get(symbol)
                if last_time and (datetime.utcnow() - last_time).total_seconds() < 60:
                    return None

                # Attempt to execute trade
                await self._execute_entry(signal)
                self.last_signal_time[symbol] = datetime.utcnow()
                return signal

        except Exception as e:
            logger.error(f"Error checking symbol {symbol}: {e}")

        return None

    async def _check_exits(self):
        """Check if any positions should be exited."""
        try:
            engine = get_paper_trading()
            if not engine:
                return

            positions = engine.get_positions()
            prices = await self._get_current_prices()

            for pos in positions:
                symbol = pos['symbol']
                current_price = prices.get(symbol)
                if not current_price:
                    continue

                entry_price = pos['entry_price']
                pnl_pct = (current_price - entry_price) / entry_price

                # Check profit target
                if pnl_pct >= self.config.exit_profit_target:
                    await self._execute_exit(
                        symbol,
                        current_price,
                        f'Profit target hit ({pnl_pct*100:.1f}%)'
                    )
                    continue

                # Check stop loss
                if pnl_pct <= -self.config.exit_stop_loss:
                    await self._execute_exit(
                        symbol,
                        current_price,
                        f'Stop loss hit ({pnl_pct*100:.1f}%)'
                    )
                    continue

        except Exception as e:
            logger.error(f"Error checking exits: {e}")

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

            # Calculate position size
            account = engine.get_account_state()
            capital = account['total_equity']
            position_value = capital * self.config.position_size_pct
            quantity = position_value / current_price

            logger.info(f"   Position: {quantity:.8f} {signal.symbol}")
            logger.info(f"   Cost: €{quantity * current_price:.2f}")

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
                logger.info(f"🚀 BUY EXECUTED: {quantity:.6f} {signal.symbol} @ ${current_price:.2f} - {signal.reason}")
                self.trade_history.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'symbol': signal.symbol,
                    'side': 'BUY',
                    'quantity': quantity,
                    'price': current_price,
                    'reason': signal.reason,
                    'signal_strength': signal.strength
                })
                return True
            else:
                logger.warning(f"BUY order failed for {signal.symbol}: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error executing entry for {signal.symbol}: {e}")
            return False

    async def _execute_exit(self, symbol: str, current_price: float, reason: str) -> bool:
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
                logger.info(f"SELL {quantity:.6f} {symbol} @ {current_price} - {reason} (PnL: €{pnl:.2f})")
                self.trade_history.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'symbol': symbol,
                    'side': 'SELL',
                    'quantity': quantity,
                    'price': current_price,
                    'reason': reason,
                    'pnl': pnl
                })
                return True
            else:
                logger.warning(f"SELL order failed for {symbol}: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error executing exit for {symbol}: {e}")
            return False

    async def _calculate_signal(self, symbol: str) -> float:
        """Calculate composite signal (0-100) for a symbol using real technical analysis."""
        try:
            from backend.analytics.historical_data import get_historical_service
            from datetime import datetime, timedelta

            hist_service = get_historical_service()
            if not hist_service:
                return 0.0

            # Get last 60 days of OHLCV data for technical analysis
            end = datetime.utcnow()
            start = end - timedelta(days=60)

            ohlcv = hist_service.fetch_ohlcv(symbol, start, end)
            if ohlcv is None or ohlcv.empty or len(ohlcv) < 14:
                # Not enough data for technical analysis
                return 0.0

            # Calculate technical indicators
            # Extract 'Close' prices, handling both flat and multi-level columns
            try:
                prices = ohlcv['Close']
                # If prices is a DataFrame (multi-level), extract the first column as Series
                if hasattr(prices, 'iloc'):
                    if len(prices.shape) > 1:
                        prices = prices.iloc[:, 0]
            except:
                return 0.0

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
            signal_score = max(0, min(100, signal_score))

            logger.debug(f"{symbol} signal: {signal_score:.1f} (RSI={rsi_value:.1f}, MACD={macd_value:.4f}, BB={bb_position:.2f})")
            return signal_score

        except Exception as e:
            logger.error(f"Error calculating signal for {symbol}: {e}")
            return 0.0

    async def _get_current_prices(self) -> Dict[str, float]:
        """Get current prices from Binance WebSocket."""
        try:
            from backend.exchange.binance_stream import get_stream_client
            client = get_stream_client()
            if not client:
                return {}

            # Get cached prices from WebSocket
            prices = client.get_prices(self.config.symbols)
            return prices
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}

    def get_status(self) -> Dict:
        """Get trader status."""
        return {
            'running': self.running,
            'enabled': self.config.enabled,
            'active_positions': 0,  # Would calculate
            'total_trades': len(self.trade_history),
            'recent_trades': self.trade_history[-10:] if self.trade_history else [],
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
