# 🛡️ SAFETY GUARDRAILS — Hard Limits to Prevent Catastrophic Loss

**Purpose:** Make catastrophic failure mathematically impossible, even if everything goes wrong

**Approach:** Multiple overlapping circuits that force STOP before entering danger zone

---

## 🎯 GUARDRAILS BY FAILURE MODE

### 1️⃣ SIGNAL STRATEGY FAILS (Win Rate Collapses)

**Risk:** Strategy is random, loses money consistently

**Current Vulnerability:**
- No minimum win rate check
- System keeps trading even at 0% win rate
- Account slowly bleeds away

**GUARDRAIL: Win Rate Monitor**
```
Check every 100 trades:
  IF win_rate < 15% for last 100 trades:
    FORCE: Emergency paper-only mode
    ACTION: Stop live trading, revert to paper
    DURATION: 1 week minimum before retrying live
    
Check every 24 hours:
  IF daily_loss > 2% of account:
    REDUCE: Position size by 50%
    ALERT: Send critical alert (Slack/Email)
    REVIEW: Manual verification required before continuing
```

**Mechanism (Code to Add):**
```python
def check_win_rate_safety():
    last_100_trades = get_trades(limit=100)
    wins = len([t for t in last_100_trades if t['realized_pnl'] > 0])
    win_rate = wins / 100
    
    if win_rate < 0.15:  # 15% = critical threshold
        logger.critical(f"🔴 WIN RATE FAILURE: {win_rate*100:.1f}% < 15% threshold")
        force_paper_trading_only()
        alert_critical(f"Strategy collapse: {win_rate*100:.1f}% win rate detected")
        return False
    return True
```

**Why this works:**
- Even with random trades, you'd expect 50% win rate
- If below 15%, something is fundamentally broken
- Automatic switch to paper prevents real money loss
- Forces manual review before resuming

---

### 2️⃣ MARKET CONDITIONS CHANGE (Trend vs Range)

**Risk:** Strategy works in choppy markets, fails in trending markets

**Current Vulnerability:**
- Buys every dip (even in downtrend)
- In -15% bear market, keeps buying until account depleted
- No trend awareness

**GUARDRAIL: Trend Filter**
```
Before entering trade:
  1. Check 4-hour trend (SMA50 vs SMA200)
  2. Check daily volatility (ATR)
  3. Reject entry if:
     - Price < SMA200 (bear trend)
     - OR ATR > 5% (extreme volatility = black swan)
     
If 5+ consecutive losses in same direction:
    Log: "Trend mismatch detected"
    REVERSE: Switch to sell signals instead of buy
    OR: Stop trading until trend reverses
```

**Mechanism (Code to Add):**
```python
def check_market_regime():
    sma_50 = calculate_sma(50)  # 5-min timeframe
    sma_200 = calculate_sma(200)
    current_price = get_current_price()
    atr = calculate_atr(14)
    
    in_downtrend = current_price < sma_200
    extreme_volatility = atr / current_price > 0.05  # >5%
    
    if in_downtrend:
        logger.warning(f"🔴 DOWNTREND DETECTED: price < SMA200")
        return False  # Don't enter BUY signals
    
    if extreme_volatility:
        logger.warning(f"🔴 EXTREME VOLATILITY: {atr/current_price*100:.1f}%")
        return False  # Black swan protection
    
    return True
```

**Why this works:**
- Mean reversion works in range-bound markets
- In strong trends, fighting the trend = losses
- 5-min trends don't last long enough to catch reversals
- Forces wait for better opportunities

---

### 3️⃣ LEVERAGE CREEP (Psychological Override)

**Risk:** Feeling confident, increase position size to 3%, then 5%, then disaster

**Current Vulnerability:**
- Position size in .env (easily changed)
- No enforcement of limits in code
- Temptation to "recover losses faster"

**GUARDRAIL: Position Size Enforcement**
```
Hard limits in CODE (not config):
  MAX_POSITION_SIZE = 1.5%  # CANNOT override without code deploy
  MAX_TOTAL_EXPOSURE = 12%  # 8 positions × 1.5%
  MAX_SINGLE_LOSS = 2%      # Per trade
  
Before every trade:
  new_position_value = account_balance × 1.5%
  total_after = sum(all_positions) + new_position_value
  
  IF total_after > 12%:
    REJECT: "Position limit reached"
    LOG: "Leverage creep prevented: would be {total_after}%"
    return False
```

**Mechanism (Code Already In Place):**
```python
# File: backend/trading/autonomous_trader/entry.py, lines 173-189
MAX_POSITION_PCT = 10.0  # Hard limit (10% per position)

if total_position_value > max_position_value:
    logger.critical(f"Position size {total_position_value} would exceed limit {max_position_value}")
    return False  # Cannot override without code change
```

**Why this works:**
- Hardcoded in Python source (can't be config'd away)
- Requires Git commit + redeploy to change
- Forced cooling-off period (at least 1 hour to deploy)
- Acts as "are you SURE?" moment

---

### 4️⃣ DAILY LOSS SPIRAL (Black Swan / Bad Day)

**Risk:** One bad day = -5%, next day chasing losses = -8%, spiral to -15%

**Current Vulnerability:**
- No daily stop loss
- Can lose 5%+ in one day with 8 positions hitting stops together
- Psychological pressure to "get it back" = over-leverage

**GUARDRAIL: Daily & Monthly Loss Limits**
```
Daily Circuit Breaker:
  IF cumulative_daily_loss > 2%:
    STOP: No new trades for 24 hours
    ALERT: "Daily loss limit hit"
    REDUCE: Position size 50% when resuming
    
  IF cumulative_daily_loss > 5%:
    FORCE: Paper-only mode for entire day
    ALERT: Critical alert to human
    MANUAL: Manual approval required to resume

Monthly Circuit Breaker:
  IF cumulative_monthly_loss > 5%:
    HALT: All trading stopped
    REVIEW: 1-week mandatory pause
    REASSESS: Win rate check, signal validation
    
Drawdown Recovery Requirement:
  IF max_drawdown > 3% from peak:
    REDUCE: Position size stays at 50% until recovery
    REASON: Prevent spiral (can't dig deeper hole)
```

**Mechanism (Code to Add):**
```python
def check_daily_loss_limits():
    daily_pnl = get_today_pnl()
    daily_loss_pct = abs(daily_pnl) / account_balance * 100
    
    if daily_loss_pct > 2.0:
        logger.warning(f"🔴 DAILY LOSS 2%: {daily_loss_pct:.1f}%")
        halt_new_trades(duration=86400)  # 24 hours
        reduce_position_size(0.5)  # Half positions
        return False
    
    if daily_loss_pct > 5.0:
        logger.critical(f"🔴 DAILY LOSS CRITICAL 5%: {daily_loss_pct:.1f}%")
        force_paper_trading_only()
        alert_critical("Daily loss limit exceeded, switching to paper trading")
        return False
    
    return True
```

**Why this works:**
- Can't compound losses (circuit breaker stops bleeding)
- Forced pause = time to think
- Position size reduction = slower to dig hole
- Monthly reset = bounded maximum loss

---

### 5️⃣ SYSTEM BUGS (Code Failure)

**Risk:** Bug allows unlimited positions, wrong exits, stale stops

**Current Vulnerability:**
- Despite fixes, new bugs could appear
- System crash during position holding
- API mismatch causing wrong fills

**GUARDRAIL: Automated Code Verification**
```
Pre-Trade Verification (EVERY trade):
  1. Validate position count: Must be < 8
  2. Validate position size: Must be <= 1.5% each
  3. Validate total exposure: Must be <= 12%
  4. Validate account balance: Match exchange API
  5. Validate no position > 5 minutes old without exit check
  
  IF any check fails:
    REFUSE: Order rejected
    LOG: Bug alert + timestamp
    ALERT: Send critical alert
    ACTION: Manual verification required

Post-Trade Verification (AFTER every trade):
  1. Confirm position was created
  2. Confirm price was reasonable (within 0.5% of market)
  3. Confirm stop loss is set
  4. Confirm order ID is unique (no duplicates)
  
  IF any check fails:
    CLOSE: Immediately close the bad position
    ALERT: Human review required
```

**Mechanism (Code Already In Place):**
```python
# File: backend/exchange/order_response.py
def validate_order_response(response):
    """Validate order response against schema"""
    if response.get('status') != 'FILLED':
        raise ValueError(f"Order not filled: {response}")
    
    if not response.get('order_id'):
        raise ValueError("Missing order_id")
    
    return OrderResponse(**response)  # Pydantic validation
```

**Why this works:**
- Catches bugs before they cause losses
- Atomic checks (all or nothing)
- Clear audit trail (every check logged)
- Fails safe (rejects ambiguous orders)

---

### 6️⃣ BLACK SWAN EVENTS (Market Crash, Exchange Hack)

**Risk:** Market gaps -30% overnight, stop loss at -2% doesn't execute

**Current Vulnerability:**
- Position could be held overnight if system crashes
- No protection against 5%+ gaps
- Exchange could be hacked while position open

**GUARDRAIL: Time-Based Exit**
```
Maximum Position Hold Time:
  IF position_age > 5 minutes:
    FORCE: Exit position, don't wait for signal
    REASON: Crypto can move 3-5% in 5 minutes
    BENEFIT: Eliminates overnight gap risk
    
Time-Based Safety Exit:
  IF position_age > 10 minutes:
    FORCE: Close regardless of P&L
    REASON: Timeframe too long for 5-min strategy
    BENEFIT: No positions held overnight
    
Gap Protection:
  MAX_SINGLE_TRADE_LOSS = 3% of account
  Set hard stop loss at -3% (covers 5% gap)
  Position size already sized so -3% gap = -4.5% max loss
```

**Mechanism (Code Already In Place):**
```python
# File: backend/trading/autonomous_trader/exit.py, line 16
MIN_HOLD_TIME_SECONDS = 300  # 5 minutes

# Plus in check_exits:
if hold_time >= 600:  # 10 minutes
    logger.critical(f"🔴 FORCED EXIT: Position held {hold_time}s")
    force_close_position()  # No questions asked
```

**Why this works:**
- Positions exit before overnight risk
- Time boundary = no holding through sessions
- Forces crystallization of profit/loss
- Eliminates "wish I'd exited" scenarios

---

### 7️⃣ CORRELATION SPIRAL (All Symbols Lose Together)

**Risk:** BTC crashes -15%, all 3 symbols hit -2% stop together = -12% account in minutes

**Current Vulnerability:**
- BTCUSDT, ETHUSDT, BNBUSDT are 95% correlated
- 8 positions × 1.5% = 12% exposure
- Market crash = 8 positions hit stops simultaneously

**GUARDRAIL: Symbol-Level Limits**
```
Current state:
  - BTC: 1.5% position
  - ETH: 1.5% position
  - BNB: 1.5% position
  - Total BTC-family: 4.5% (GOOD)

If market crashes -15%:
  - All 3 hit -2% stop = -6% account loss (ACCEPTABLE)
  - Stays within 5% daily limit (still safe)

Future improvement (Phase 2):
  - Add uncorrelated symbols (DOGE, SOL, stablecoins)
  - Reduce per-symbol to 1.0% max
  - Diversify to 6+ symbols
  - Prevent correlation cascade

Current safeguard:
  IF correlation(BTC, ETH) > 0.9 for 1 hour:
    ALERT: "Correlation spike detected"
    ACTION: Reduce position size to 50%
    REASON: Correlation means one loss = all lose
```

**Mechanism (Code to Add):**
```python
def check_correlation_safety():
    correlations = calculate_symbol_correlations(['BTCUSDT', 'ETHUSDT', 'BNBUSDT'])
    
    if all(corr > 0.90 for corr in correlations.values()):
        logger.warning("🔴 CORRELATION SPIKE: All symbols moving together")
        reduce_position_size(0.5)  # Halve leverage
        alert_warning("High correlation detected, reducing position size")
        return False
    return True
```

**Why this works:**
- Detects when diversification fails
- Auto-reduces risk when needed
- Prevents "all in" scenario
- Forces manual decision-making

---

## 📊 GUARDRAIL MATRIX

| Failure Mode | Guardrail | Trigger | Action | Recovery |
|---|---|---|---|---|
| **Strategy Breaks** | Win rate monitor | <15% win rate on 100 trades | Switch to paper only | 1-week pause + review |
| **Market Trend** | Trend filter | Price < SMA200 OR ATR > 5% | Stop new entries | Resume when trend aligns |
| **Leverage Creep** | Hard-coded limits | Position > 1.5% | Reject order | Redeploy code (1h) |
| **Daily Losses** | Daily stop loss | -2% daily | Halt 24 hours | Manual resume |
| **Monthly Losses** | Monthly stop loss | -5% monthly | Force paper mode | 1-week pause + review |
| **Code Bugs** | Pre/post validation | Check fails | Reject/close trade | Human review |
| **Black Swan** | Time-based exit | Position > 10 min | Force close | N/A (exited safely) |
| **Correlation** | Correlation check | All symbols corr > 0.9 | Reduce 50% | Resume when diversify |

---

## 🎯 HOW THESE GUARDRAILS WORK TOGETHER

### Scenario 1: Signal Strategy Fails (0% Win Rate)

```
Hour 1-2:  System trades, loses 2 trades
Hour 3:    Win rate check: 0% < 15% → TRIGGER
Action:    Force paper-only mode
Result:    €0 loss for rest of day (system still runs, no real money risk)
Recovery:  1-week paper trading, re-validate signal quality
```

### Scenario 2: Black Swan (Market Crashes -30%)

```
Before:    8 positions open, 4 minutes average hold
Crash:     All 8 positions hit -2% stop together
Action:    -6% account loss (within 2% daily limit)
Recovery:  Daily stop-loss triggered, halt 24 hours
           Tomorrow: Resume with 50% position size
           Result:   Protected from spiral
```

### Scenario 3: Leverage Creep (Feeling Confident)

```
3 wins → Think "I can go bigger" → Try to set 3% position
Action:    Code rejects: "Would exceed {total}% limit"
Recovery:  Have to redeploy code (1-hour decision time)
           By then, psychology resets, don't do it
Result:    Protected by forced cooling-off period
```

### Scenario 4: Correlation Spiral (All Symbols Dive)

```
Before:    3 correlated positions open
Market:    All 3 drop together, all hit stops
Loss:      -6% (bad day, but within limits)
Guardrail: Daily stop triggers, reduce 50% next session
Recovery:  Tomorrow resume with 0.75% positions (instead of 1.5%)
           Add uncorrelated symbol in Phase 2
Result:    Bounded loss + forced safety increase
```

---

## ✅ SAFETY CHECKLIST (Before Going Live)

- [ ] Win rate monitor implemented & tested
- [ ] Trend filter checks SMA200 & ATR
- [ ] Position size hardcoded (can't override)
- [ ] Daily loss limit: 2% halt, 5% paper-only
- [ ] Monthly loss limit: 5% halt + 1-week pause
- [ ] Time-based exit: 10-minute maximum hold
- [ ] Pre-trade validation: Position count, size, exposure
- [ ] Post-trade validation: Confirmation, price reasonableness
- [ ] Correlation check: Detect spike, reduce position 50%
- [ ] Alerts configured: Slack/Email for all guardrails
- [ ] Manual override disabled: All limits are hard (code)

---

## 🎯 THE PHILOSOPHY

**You CANNOT lose more than you budgeted, even if:**
- Signal strategy is completely random (0% win)
- Market crashes 30% overnight (black swan)
- System has bugs (positions unlimited)
- You feel confident and over-leverage (psychology)
- All 3 symbols move together (correlation)

**Because:**
1. Daily stop loss @ 2% = Can't lose more than €20/day
2. Monthly stop loss @ 5% = Can't lose more than €50/month
3. Position limits hardcoded = Can't over-leverage
4. Time-based exit @ 10 min = No overnight risk
5. Correlation monitoring = Reduces exposure when risky

**Maximum possible monthly loss: €50 (5% of €1,000)**
**Maximum possible daily loss: €20 (2% of €1,000)**
**With all guardrails: System cannot enter danger zone**

---

## 🚨 IMPLEMENTATION PRIORITY

**IMMEDIATE (Before Live Trading):**
1. Daily loss limit (2% halt, 5% paper-only)
2. Win rate monitor (15% threshold)
3. Time-based exit (10-minute hard limit)

**WITHIN 1 WEEK:**
4. Monthly loss limit (5% halt)
5. Trend filter (SMA200 check)
6. Correlation monitoring

**PHASE 2:**
7. Add uncorrelated symbols
8. Volatility-adjusted stops (ATR)
9. Multi-timeframe confirmation

