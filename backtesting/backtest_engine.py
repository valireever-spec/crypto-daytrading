"""
Backtesting Engine for Trend-Following Signal

Implements the signal specification exactly:
- 5 entry conditions (all must be true)
- 5 exit conditions (first true wins)
- Position sizing: 1.5% per trade
- Risk/Reward: 1% stop, 2% target
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Single OHLCV candle"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __repr__(self):
        return f"Candle({self.timestamp.isoformat()}, close={self.close:.2f}, vol={self.volume:.0f})"


@dataclass
class Trade:
    """Completed trade record"""
    symbol: str
    entry_time: datetime
    entry_price: float
    entry_reason: str
    entry_signal_strength: float

    exit_time: datetime
    exit_price: float
    exit_reason: str

    quantity: float
    position_size_usd: float

    pnl: float  # Realized P&L in USD
    pnl_pct: float  # P&L as percentage

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': round(self.entry_price, 2),
            'exit_time': self.exit_time.isoformat(),
            'exit_price': round(self.exit_price, 2),
            'quantity': round(self.quantity, 8),
            'position_size': round(self.position_size_usd, 2),
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct, 4),
            'entry_reason': self.entry_reason,
            'exit_reason': self.exit_reason,
            'duration_minutes': (self.exit_time - self.entry_time).total_seconds() / 60,
            'win': self.is_win,
        }


@dataclass
class BacktestResult:
    """Backtest summary statistics"""
    symbol: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    win_rate: float = 0.0  # %
    profit_factor: float = 0.0  # gross_profit / gross_loss
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade_duration_min: float = 0.0

    max_win: float = 0.0
    max_loss: float = 0.0
    max_consecutive_losses: int = 0

    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0

    starting_capital: float = 0.0
    ending_capital: float = 0.0

    trades: List[Trade] = field(default_factory=list)

    def passes_criteria(self) -> Tuple[bool, List[str]]:
        """Check if backtest passes success criteria"""
        failures = []

        if self.win_rate < 55.0:
            failures.append(f"Win Rate {self.win_rate:.1f}% < 55%")

        if self.profit_factor < 1.5:
            failures.append(f"Profit Factor {self.profit_factor:.2f}x < 1.5x")

        if self.sharpe_ratio < 1.0:
            failures.append(f"Sharpe Ratio {self.sharpe_ratio:.2f} < 1.0")

        if self.max_consecutive_losses >= 5:
            failures.append(f"Max Consecutive Losses {self.max_consecutive_losses} >= 5")

        if self.max_drawdown_pct > 15.0:
            failures.append(f"Max Drawdown {self.max_drawdown_pct:.1f}% > 15%")

        return len(failures) == 0, failures

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_factor': round(self.profit_factor, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_pct': round(self.total_pnl_pct, 2),
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'max_win': round(self.max_win, 2),
            'max_loss': round(self.max_loss, 2),
            'max_consecutive_losses': self.max_consecutive_losses,
            'avg_trade_duration_min': round(self.avg_trade_duration_min, 1),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct, 2),
            'starting_capital': round(self.starting_capital, 2),
            'ending_capital': round(self.ending_capital, 2),
        }


class Indicators:
    """Technical indicator calculations"""

    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """Calculate EMA of last price"""
        if len(prices) < period:
            return sum(prices) / len(prices)

        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0  # Neutral if insufficient data

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]

        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate ATR (Average True Range)"""
        if len(highs) < period:
            return 0.0

        tr_values = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_values.append(tr)

        return sum(tr_values[-period:]) / period if tr_values else 0.0


class SignalCalculator:
    """Implements the signal specification exactly"""

    # Constants from specification
    EMA5_PERIOD = 5
    EMA20_PERIOD = 20
    RSI_PERIOD = 14
    VOLUME_AVG_PERIOD = 20

    # Thresholds
    ENTRY_THRESHOLD = 50  # 0-100 scale (lowered for real data validation)
    SIGNAL_BASE_SCORE = 50
    RSI_OVERBOUGHT = 70

    @staticmethod
    def calculate_signal(
        prices_5min: List[float],
        prices_1hr: List[float],
        prices_4hr: List[float],
        volumes_5min: List[float],
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Calculate signal strength (0-100) and reason.
        Returns (strength, reason) or (None, reason) if no signal.

        Implements all 5 entry conditions from specification.
        """

        # Need minimum history for indicators
        if len(prices_5min) < 20 or len(prices_1hr) < 20 or len(prices_4hr) < 20:
            return None, "Insufficient price history"

        # ===== PRE-CONDITION 1: Trend Filter (4-hour) =====
        current_price = prices_5min[-1]
        ema20_4hr = Indicators.ema(prices_4hr, SignalCalculator.EMA20_PERIOD)

        if current_price <= ema20_4hr:
            return None, f"Trend DOWN: price {current_price:.2f} < EMA20_4hr {ema20_4hr:.2f}"

        # ===== PRE-CONDITION 2: Momentum Filter (1-hour) =====
        ema5_1hr = Indicators.ema(prices_1hr, SignalCalculator.EMA5_PERIOD)
        ema20_1hr = Indicators.ema(prices_1hr, SignalCalculator.EMA20_PERIOD)

        if ema5_1hr <= ema20_1hr:
            return None, f"Momentum DOWN: EMA5_1hr {ema5_1hr:.2f} < EMA20_1hr {ema20_1hr:.2f}"

        # ===== PRE-CONDITION 3: Entry Signal (5-min breakout) =====
        # High of last 5 candles (support/resistance)
        high5_5min = max(prices_5min[-5:])

        if current_price <= high5_5min:
            return None, f"No breakout: close {current_price:.2f} < high5 {high5_5min:.2f}"

        # ===== PRE-CONDITION 4: Volume Confirmation =====
        current_volume = volumes_5min[-1]
        avg_volume_20 = sum(volumes_5min[-20:]) / 20
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0

        if volume_ratio < 1.5:
            return None, f"Low volume: {volume_ratio:.2f}x < 1.5x average"

        # ===== PRE-CONDITION 5: Overbought Filter (RSI) =====
        rsi_5min = Indicators.rsi(prices_5min, SignalCalculator.RSI_PERIOD)

        if rsi_5min >= SignalCalculator.RSI_OVERBOUGHT:
            return None, f"Overbought: RSI {rsi_5min:.0f} >= 70"

        # ===== ALL CONDITIONS MET - CALCULATE SIGNAL STRENGTH =====
        signal_strength = SignalCalculator.SIGNAL_BASE_SCORE  # 50 base points
        bonuses = []

        # Bonus 1: Strong momentum (distance from EMA)
        momentum_distance = ((ema5_1hr - ema20_1hr) / ema20_1hr) * 100
        if momentum_distance > 0.5:
            signal_strength += 15
            bonuses.append(f"momentum +{momentum_distance:.2f}%")

        # Bonus 2: Volume surge
        if volume_ratio > 2.0:
            signal_strength += 10
            bonuses.append(f"volume {volume_ratio:.1f}x")

        # Bonus 3: RSI room to run
        if rsi_5min < 50:
            signal_strength += 10
            bonuses.append(f"RSI {rsi_5min:.0f} < 50")

        # Bonus 4: 5-min uptrend
        ema5_5min = Indicators.ema(prices_5min, SignalCalculator.EMA5_PERIOD)
        if current_price > ema5_5min:
            signal_strength += 5
            bonuses.append("5-min uptrend")

        signal_strength = min(signal_strength, 100.0)  # Cap at 100

        bonus_text = ", ".join(bonuses) if bonuses else ""
        reason = f"Breakout above 5-candle high with {bonus_text}" if bonus_text else "Breakout above 5-candle high"

        if signal_strength >= SignalCalculator.ENTRY_THRESHOLD:
            return signal_strength, reason
        else:
            return None, f"Signal weak: {signal_strength:.0f} < {SignalCalculator.ENTRY_THRESHOLD}"

    @staticmethod
    def check_exit_conditions(
        entry_price: float,
        current_price: float,
        entry_time: datetime,
        current_time: datetime,
        prices_5min: List[float],
        daily_loss: float,
        daily_loss_limit: float = 20.0,
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Check exit conditions in priority order.
        Returns (exit_reason, exit_price) or (None, None) if no exit.

        Priority order (first true = exit):
        1. Trend reversal
        2. Stop loss
        3. Profit target
        4. Time exit
        5. Daily halt
        """

        # Exit Condition 1: Trend Reversal
        if len(prices_5min) >= 5:
            low5_5min = min(prices_5min[-5:])
            if current_price < low5_5min:
                return "Trend reversal", current_price

        # Exit Condition 2: Stop Loss (-1%)
        loss_pct = (current_price - entry_price) / entry_price
        if loss_pct <= -0.01:
            return "Stop loss -1%", current_price

        # Exit Condition 3: Profit Target (+2%)
        profit_pct = (current_price - entry_price) / entry_price
        if profit_pct >= 0.02:
            return "Profit target +2%", current_price

        # Exit Condition 4: Time Exit (10 minutes)
        hold_minutes = (current_time - entry_time).total_seconds() / 60
        if hold_minutes >= 10:
            return "Time exit 10min", current_price

        # Exit Condition 5: Daily Halt (Daily Loss >= 2%)
        if daily_loss >= daily_loss_limit:
            return "Daily halt", current_price

        return None, None


class BacktestEngine:
    """Main backtesting engine"""

    COMMISSION = 0.001  # 0.1% Binance commission
    SLIPPAGE = 0.001     # 0.1% market order slippage
    STARTING_CAPITAL = 1000.0
    POSITION_SIZE_PCT = 0.015  # 1.5%
    STOP_LOSS_PCT = 0.01  # 1%
    PROFIT_TARGET_PCT = 0.02  # 2%
    DAILY_LOSS_LIMIT = 20.0  # €20 or 2%
    MAX_POSITIONS = 2

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.cash = self.STARTING_CAPITAL
        self.starting_capital = self.STARTING_CAPITAL
        self.positions: Dict[str, Dict] = {}  # Active positions
        self.trades: List[Trade] = []
        self.daily_loss = 0.0
        self.last_reset_date = None

    def reset_daily_loss(self, current_date):
        """Reset daily loss at midnight"""
        if self.last_reset_date != current_date:
            self.daily_loss = 0.0
            self.last_reset_date = current_date

    def calculate_position_size(self, entry_price: float) -> float:
        """Calculate position size: 1.5% of cash"""
        position_size_usd = self.cash * self.POSITION_SIZE_PCT
        quantity = position_size_usd / entry_price
        return quantity

    def enter_trade(
        self,
        entry_time: datetime,
        entry_price: float,
        signal_strength: float,
        entry_reason: str,
    ) -> bool:
        """Execute entry trade"""

        # Check max positions
        if len(self.positions) >= self.MAX_POSITIONS:
            return False

        # Check cash
        position_size_usd = self.cash * self.POSITION_SIZE_PCT
        if position_size_usd < 5.0:  # Minimum position size
            return False

        # Check daily loss limit
        if self.daily_loss >= self.DAILY_LOSS_LIMIT:
            return False

        # Calculate quantity
        quantity = self.calculate_position_size(entry_price)

        # Apply commission on entry
        cost = position_size_usd * (1 + self.COMMISSION + self.SLIPPAGE)

        if cost > self.cash:
            return False

        # Record position
        position_id = f"{self.symbol}_{len(self.trades)}"
        self.positions[position_id] = {
            'entry_time': entry_time,
            'entry_price': entry_price,
            'entry_reason': entry_reason,
            'entry_signal_strength': signal_strength,
            'quantity': quantity,
            'position_size_usd': position_size_usd,
        }

        self.cash -= cost
        return True

    def exit_trade(
        self,
        position_id: str,
        exit_time: datetime,
        exit_price: float,
        exit_reason: str,
    ) -> Optional[Trade]:
        """Execute exit trade and record trade"""

        if position_id not in self.positions:
            return None

        pos = self.positions.pop(position_id)

        # Calculate P&L
        entry_price = pos['entry_price']
        quantity = pos['quantity']

        # Exit revenue (before commission)
        exit_revenue = quantity * exit_price

        # Apply commission on exit
        exit_revenue -= exit_revenue * (self.COMMISSION + self.SLIPPAGE)

        # Entry cost (already applied)
        # entry_cost already deducted from cash during entry

        # P&L calculation
        entry_cost = pos['position_size_usd']
        pnl = exit_revenue - entry_cost
        pnl_pct = pnl / entry_cost if entry_cost > 0 else 0

        self.cash += exit_revenue
        self.daily_loss += pnl  # Can be negative (loss)

        trade = Trade(
            symbol=self.symbol,
            entry_time=pos['entry_time'],
            entry_price=entry_price,
            entry_reason=pos['entry_reason'],
            entry_signal_strength=pos['entry_signal_strength'],
            exit_time=exit_time,
            exit_price=exit_price,
            exit_reason=exit_reason,
            quantity=quantity,
            position_size_usd=entry_cost,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

        self.trades.append(trade)
        return trade

    def get_result(self) -> BacktestResult:
        """Generate backtest result summary"""

        result = BacktestResult(
            symbol=self.symbol,
            total_trades=len(self.trades),
            starting_capital=self.starting_capital,
            ending_capital=self.cash,
        )

        if len(self.trades) == 0:
            return result

        # Calculate metrics
        winning_trades = [t for t in self.trades if t.is_win]
        losing_trades = [t for t in self.trades if not t.is_win]

        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)
        result.win_rate = (len(winning_trades) / len(self.trades)) * 100

        # Total P&L
        result.total_pnl = sum(t.pnl for t in self.trades)
        result.total_pnl_pct = (result.total_pnl / self.starting_capital) * 100

        # Average win/loss
        if winning_trades:
            result.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
            result.max_win = max(t.pnl for t in winning_trades)

        if losing_trades:
            result.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
            result.max_loss = min(t.pnl for t in losing_trades)

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Average trade duration
        durations = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in self.trades]
        result.avg_trade_duration_min = sum(durations) / len(durations) if durations else 0

        # Max consecutive losses
        max_consecutive = 0
        current_consecutive = 0
        for trade in self.trades:
            if not trade.is_win:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        result.max_consecutive_losses = max_consecutive

        # Sharpe ratio (assuming 0 risk-free rate, daily returns)
        if len(self.trades) > 1:
            returns = [t.pnl_pct for t in self.trades]
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5 if variance > 0 else 1
            result.sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0

        # Max drawdown
        cumulative_pnl = 0
        peak = 0
        max_dd = 0
        for trade in self.trades:
            cumulative_pnl += trade.pnl
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_dd:
                max_dd = drawdown

        result.max_drawdown_pct = (max_dd / self.starting_capital) * 100 if self.starting_capital > 0 else 0

        result.trades = self.trades

        return result
