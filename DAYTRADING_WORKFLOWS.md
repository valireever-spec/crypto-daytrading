# Real Daytrading Workflows — User Scenarios & Requirements

**Purpose:** Map actual daytrader needs to system requirements  
**Status:** Phase 0.5 — Design Review (CRITICAL GAPS IDENTIFIED)

---

## Scenario 1: Morning Setup (30 minutes)

### What A Real Daytrader Does

```
06:00 AM (Crypto markets always open)
├─ Wake up, check overnight trades
│  ├─ BTC trade filled at 3 AM while I slept? Check P&L
│  ├─ Got stopped out? Understand why
│  └─ Overnight volatility spikes? Adjust for today
│
├─ Review market conditions (30 sec)
│  ├─ BTC up 2% overnight? Market is hot → be aggressive
│  ├─ Major news overnight? (Fed, earnings, etc.)
│  └─ Which timeframe is trending? (15m, 1h, 4h?)
│
├─ Decide daily strategy mix (5 min)
│  ├─ "Today I'll run: 50% momentum, 30% mean reversion, 20% grid"
│  ├─ NOT fixed like "always run all strategies equally"
│  ├─ Adjust based on volatility & recent performance
│  ├─ Some strategies better in choppy markets (mean reversion)
│  ├─ Some better in trending markets (momentum)
│  └─ Some always work (grid = mechanical)
│
├─ Set daily risk parameters (5 min)
│  ├─ Daily loss limit: -5% if choppy, -3% if low vol
│  ├─ Position size: +20% if winning streak, -20% if losing streak
│  ├─ Correlation check: Not over-exposed to single direction
│  └─ Fee awareness: Each 0.1% move = 1-2 fee ticks cost
│
├─ Check system health (5 min)
│  ├─ Both machines running? (main + backup)
│  ├─ Binance API responding? 
│  ├─ Previous P&L dashboard: Are we up/down YTD?
│  └─ Any errors in overnight logs?
│
└─ Start trading (BEGIN at 07:00 AM, not automated)
   └─ Human decision: "OK, system is go"
```

### Requirement Gaps in Current Design

| What Daytrader Needs | Current Design | Gap |
|---------------------|-----------------|-----|
| View overnight trades | ✅ Dashboard shows | ✓ OK |
| Override fixed strategies | ❌ Strategies hardcoded | ❌ CRITICAL |
| Adjust daily loss limit | ❌ Hardcoded in config | ❌ CRITICAL |
| Switch strategy mix mid-day | ❌ Can't change without restart | ❌ CRITICAL |
| Manual start/stop signal | ❌ Automated from 00:00 | ❌ CRITICAL |
| See why last trade lost | ❌ Only logs what happened | ⚠️ PARTIAL |
| Pause trading if market weird | ❌ No pause mechanism | ❌ CRITICAL |

---

## Scenario 2: Morning Trading (07:00 - 12:00, 5 hours)

### What A Real Daytrader Does

```
07:00 AM — START (Manual button click)
├─ System begins scanning 5 trading pairs for signals
├─ Every 15 seconds, check for entries
└─ FAST FEEDBACK to trader

OPPORTUNITY #1 (07:15 AM)
├─ Signal: BTCUSDT momentum ≥75
├─ Trader sees ALERT on dashboard: "BTC entry opportunity"
├─ BUT: Trader checks 1-min chart first
│  ├─ Yes, I see the breakout → PROCEED
│  └─ OR No, candle looks weak → SKIP
├─ If YES: Click "ENTER" on dashboard
│  ├─ Order placed in <500ms
│  ├─ See fill price immediately
│  └─ Position now open: 0.05 BTC @ $45,000
│
├─ Position size: NOT fixed 2%
│  ├─ Small: 0.5% if uncertain (low conviction)
│  ├─ Medium: 1.5% if clear signal (normal)
│  ├─ Large: 3% if extremely confident + account heat allows
│  └─ Depends on: Volatility, risk/reward ratio, recent wins/losses
│
└─ Monitor position (ACTIVE WATCHING)
   ├─ Every 5 seconds: Check price
   ├─ If price +0.5%: May take partial profit early
   ├─ If price +2%: Take full profit manually
   ├─ If drawdown -1% but signal still strong: HOLD
   ├─ If drawdown -2% AND signal weakening: HIT STOP MANUALLY
   └─ NOT automated: Want human judgment in real-time

OPPORTUNITY #2 (08:30 AM)
├─ Signal: ETHUSDT mean reversion (Bollinger lower band bounce)
├─ Trader sees chart: Yes, definitely support
├─ But account already has 40% deployed (BTC + other trades)
├─ Trader reduces position size: 1% instead of 1.5%
│  └─ Reason: "I'm already at heat, can't afford big loss"
├─ Enter trade with reduced size
└─ Monitor alongside BTC position

OPPORTUNITY #3 (09:00 AM)
├─ Earlier BTC trade: +1.5% now
├─ Trader checks 5-min chart
├─ Momentum signal weakening (RSI rolling over)
├─ Decision: Take profit NOW (not wait for exit signal)
├─ Click "EXIT" button → Market sell
├─ Locked in +€67.50 profit
├─ Free up capital for next entry
└─ Emotional win: "I caught the move perfectly"

OPPORTUNITY #4 (09:45 AM)
├─ Market suddenly drops -3% (Fed news!)
├─ Trader's ETH position is -$42 (underwater)
├─ Trader sees news on Twitter
├─ Decision: Panic? No, I have strong stop loss
├─ BUT: Maybe trend is changing → close partially?
├─ OR: Buy more on dip (contrarian)?
├─ Trader decision: HOLD, signal still good
│  └─ This is HUMAN JUDGMENT, not algorithm
└─ Position survives, next hour rebounds

OPPORTUNITY #5 (10:15 AM)
├─ Strategy mixing in action
├─ Momentum trades: 2 this morning, both winners
├─ Mean reversion trades: 1, currently underwater
├─ Grid trades: None triggered yet (too much momentum)
├─ Total P&L: +€89 (3 trades, 2 wins)
├─ Heat check: Account now +0.89% (within risk limit)
└─ Decision: Continue trading, momentum looking strong

MID-MORNING REVIEW (11:00 AM)
├─ Check dashboard: "Win rate this morning: 67% (2/3)"
├─ Strategy breakdown:
│  ├─ Momentum: 2 trades, 2 wins (100%)
│  ├─ Mean reversion: 1 trade, 0 wins (0%)
│  └─ Observation: "Momentum is working today, momentum is winner"
│
├─ Trader decision: Boost momentum allocation
│  ├─ Reduce mean reversion signals (too choppy)
│  ├─ Increase momentum position sizes
│  ├─ Grid stays mechanical (always 20% of capital)
│  └─ "Adapt strategy mix based on live performance"
│
└─ Continue with new mix

LATE MORNING (11:30 AM - 12:00 PM)
├─ 4 more trades executed
├─ Closing to lunch time
├─ Review: Total 7 trades, 5 winners, 2 losers
├─ Win rate: 71%
├─ Daily P&L: +€156
├─ Time for lunch break? Trader decides:
│  ├─ Option A: Close all positions, take break
│  ├─ Option B: Keep 1-2 winners running (overnight risk)
│  ├─ Option C: Pause system, keep positions, ready to react after lunch
│  └─ FLEXIBILITY: Not "system closed at market close"
└─ Decision: Keep grid trades running (mechanical), pause momentum/reversion
```

### Requirement Gaps Exposed

| What's Critical | Current Design | Gap |
|-----------------|-----------------|-----|
| **Real-time alerts** | ❌ Fixed 15-min intervals | ❌ CRITICAL (opportunities missed) |
| **Manual order buttons** | ❌ Fully automated | ❌ CRITICAL (can't override) |
| **Flexible position sizing** | ❌ Fixed 2% per trade | ❌ CRITICAL (can't risk-adjust) |
| **Partial profit taking** | ❌ All-or-nothing exits | ❌ CRITICAL (leave money on table) |
| **Dynamic strategy mix** | ❌ Fixed 33/33/33 split | ❌ CRITICAL (can't adapt to market) |
| **Live P&L breakdown** | ❌ Only aggregate P&L | ⚠️ PARTIAL (need per-strategy) |
| **Pause/resume trading** | ❌ Can't pause without stopping | ❌ CRITICAL (can't handle news) |
| **Heat tracking** | ❌ Only daily cap | ⚠️ PARTIAL (need real-time % deployed) |
| **Trade quality analysis** | ❌ Win/loss only | ⚠️ PARTIAL (need: entry quality, exit quality, holding time) |
| **Manual stop/profit override** | ❌ Automated only | ❌ CRITICAL (human judgment important) |

---

## Scenario 3: Afternoon Slump (12:00 - 15:00, low volume)

### What A Real Daytrader Does

```
12:00 - 15:00 (AFTERNOON SLUMP)
├─ Market often choppy, low volume
├─ Perfect for: Mean reversion (bounces off support)
├─ TERRIBLE for: Momentum (false breakouts)
│
├─ Trader updates strategy mix:
│  ├─ Reduce momentum signals (too many false breaks)
│  ├─ Increase mean reversion (bounces predictable)
│  └─ Grid stays high (works in chop)
│
├─ Execution style changes:
│  ├─ Use limit orders (save 0.1% fee, market is slow)
│  ├─ Tighter stops (-1% instead of -2%, quick fakes)
│  ├─ Faster exits (+0.8% instead of +1.5%, lock in quick wins)
│  └─ Smaller position sizes (less capital at risk in low volume)
│
└─ P&L: Maybe +€45 today (half of morning, but still good)
```

### Requirement: Dynamic Parameter Adjustment

Current design has HARDCODED parameters:
```python
PROFIT_TARGET_PCT = 1.5      # Fixed
STOP_LOSS_PCT = 2.0          # Fixed
POSITION_SIZE_PCT = 2.0      # Fixed
```

Real daytraders need:
```
Can I change these MID-DAY without restarting?
├─ Time 07:00-11:00: AGGRESSIVE (target +2%, stop -2%, size +3%)
├─ Time 11:00-15:00: CONSERVATIVE (target +0.8%, stop -1%, size +1%)
├─ Time 15:00-17:00: CLOSE-OUT (target +0.5%, stop -0.5%, size -50%)
└─ Time 17:00+: REST (disabled, let grid trade only)
```

---

## Scenario 4: Evening Wind-Down (17:00 - 22:00)

### What A Real Daytrader Does

```
17:00 PM (US market close, crypto continues 24/7)
├─ Some traders: Close everything, "daytrading is done"
├─ Other traders: Switch to swing mode, hold overnight
│  ├─ Risk: Overnight gaps (big news)
│  ├─ Reward: Overnight moves (sometimes)
│  └─ "I'll hold my best winners, close my shakier trades"
│
├─ Decision points:
│  ├─ Current P&L: +€156 (good day)
│  ├─ How many positions to hold overnight?
│  │  ├─ Max 2 (reduce overnight risk)
│  │  ├─ Only strongest signals (≥80)
│  │  ├─ With wide stops (-5%)
│  │  └─ Mental accounting: "I can afford to lose this"
│  │
│  ├─ Positions to close:
│  │  ├─ Weak signals (50-60)
│  │  ├─ Losing positions (-1% or more)
│  │  └─ "Lock in winners" mindset
│  │
│  └─ Overnight risk setup:
│     ├─ Set "only close" mode (no new entries)
│     ├─ Grid trading continues (mechanical)
│     ├─ Mean reversion disabled (too risky overnight)
│     └─ Stop losses active & wide
│
└─ Evening tasks:
   ├─ Export today's trades for tax/record
   ├─ Analyze which strategy worked best
   │  ├─ Momentum: 5 trades, 80% win (best!)
   │  ├─ Mean reversion: 2 trades, 50% win
   │  └─ Grid: 3 trades, 100% win (smallest trades)
   │
   ├─ Plan tomorrow:
   │  ├─ "Momentum is clearly winning, use it more"
   │  ├─ "Mean reversion had bad timing, skip 12-3pm"
   │  ├─ "Grid is boring but consistent, keep it"
   │  └─ "Maybe add a volatility strategy for slow markets"
   │
   └─ Sleep, system running on backup machine
```

### Requirement: Mode Switching

Current design: Always in "trading mode"

Real daytraders need:
```
MODES:
├─ DAYTRADE: Full entry/exit, all strategies
├─ SWING HOLD: Close weak, hold winners, wide stops
├─ CLOSE_OUT: No new entries, reduce positions
├─ PAUSE: Stop all, system monitors only
├─ BACKTEST: Simulate on historical data
└─ PAPER: No real money, test new strategies
```

---

## Scenario 5: Overnight Crisis (22:00 - 06:00 next day)

### What A Real Daytrader Does

```
01:00 AM (Trader sleeping, but system running)

CRISIS #1: Exchange goes down for 10 minutes
├─ System can't place orders
├─ But position is stuck (can't exit)
├─ Backup: "Should I liquidate on backup exchange if available?"
│  ├─ NO: Too risky (different prices, slippage)
│  ├─ YES: Accept small loss, at least reduce risk
│  └─ Requirement: Have fallback exit strategy
│
└─ Current design: SYSTEM HANGS, trader doesn't know!
   └─ Need: System alerts trader IMMEDIATELY (push notification, SMS)

CRISIS #2: Position gets stopped out, but trader disagrees
├─ Overnight BTC spike to -2.2%
├─ System exits: "Stop loss at -2%"
├─ But market rebounded 4 hours later, trade was good
├─ Trader wakes up: "Ugh, I got stopped out right before recovery"
├─ Lesson: Should have used wider stops overnight (-3% or -5%)
│
└─ Requirement: Different stop losses for day vs overnight
   ├─ Daytime: Tight stops (-2%)
   ├─ Overnight: Loose stops (-5%)
   └─ Should be parameter, not hardcoded

CRISIS #3: Major news hit (Fed announcement, exchange hack, etc.)
├─ Market gaps down 5%
├─ Trader's positions: All stopped out automatically
├─ Good news: Protected by stops
├─ Bad news: Market recovers 2 hours later
│
└─ Lesson: Sometimes you DON'T want to trade the news
   └─ Requirement: "Disable trading during known news events"
      ├─ Fed meetings
      ├─ CPI releases
      ├─ US stock market opens
      └─ Param: "News calendar" to pause trading
```

---

## Scenario 6: Weekly Review & Learning

### What A Real Daytrader Does

```
SUNDAY EVENING — Review the week

OVERALL METRICS:
├─ Total trades: 89
├─ Winning trades: 54 (61% win rate) ✓
├─ Losing trades: 35 (39%)
├─ Gross profit: €340
├─ Fee cost: €45 (0.1% per trade × 89)
├─ NET profit: €295 (3% on €10k)
│
├─ By strategy:
│  ├─ Momentum: 34 trades, 68% win ← BEST
│  ├─ Mean reversion: 28 trades, 54% win
│  ├─ Grid: 27 trades, 61% win
│  └─ Insight: Momentum >> Mean Reversion
│
├─ By time of day:
│  ├─ 07:00-11:00: 45 trades, 68% win ← BEST TIME
│  ├─ 11:00-15:00: 28 trades, 50% win ← WORST (lunch slump)
│  ├─ 15:00-18:00: 16 trades, 75% win (evening reversal)
│  └─ Insight: Focus on morning & evening, skip lunch chop
│
├─ By pair:
│  ├─ BTC: 38 trades, 63% win ✓
│  ├─ ETH: 32 trades, 59% win
│  ├─ SOL: 19 trades, 68% win ✓
│  └─ Insight: BTC & SOL are best, SOL is risky (volatility)
│
└─ DECISIONS for NEXT WEEK:
   ├─ Increase momentum allocation: 60% (was 33%)
   ├─ Reduce mean reversion: 10% (was 33%)
   ├─ Keep grid: 30% (stays same)
   ├─ Focus on 07:00-11:00 and 15:00-18:00 only
   ├─ Skip 11:00-15:00 (close out at lunch)
   ├─ Remove low-performing pairs (ETH? DOGE?)
   ├─ Add SOL focus: Better risk/reward than BTC
   └─ "This is how I improve win rate each week"
```

### Requirement: Analytics & Learning

Current design: "Just log trades"

Real daytraders need:
```
ANALYTICS DASHBOARD:
├─ Win rate by strategy (which is best?)
├─ Win rate by time of day (when do I trade best?)
├─ Win rate by pair (which cryptos do I trade well?)
├─ Average trade duration (am I scalping or swinging?)
├─ Risk/reward ratio (am I risking enough to win big?)
├─ Consecutive wins/losses (am I in a streak?)
├─ Fee impact analysis (am I trading too much?)
├─ Optimal strategy mix (momentum 60%, reversion 10%, grid 30%)
└─ Time-of-day adjustment (be aggressive 7-11am, conservative 11-3pm)
```

---

## User Scenarios Summary → Requirements Mapping

### Scenario 1: Morning Setup
```
User Need                          → Requirement ID
View overnight trades              → FR-008 (dashboard)
Override strategy mix              → NEW: FR-003B (dynamic strategy allocation)
Adjust daily loss limit            → NEW: FR-005B (dynamic risk parameters)
Switch trading mode                → NEW: FR-004B (pause/resume/mode switching)
Check system health                → FR-009 (alerts)
```

### Scenario 2: Morning Trading (Active)
```
User Need                          → Requirement ID
Real-time entry alerts             → NEW: FR-008B (sub-second alerts, not 15-min intervals)
Manual order buttons                → NEW: FR-004C (click-to-enter/exit)
Flexible position sizing           → NEW: FR-005C (risk-adjusted sizing based on account heat)
Partial profit taking              → NEW: FR-004D (scale out, pyramiding)
View live P&L per strategy         → NEW: FR-008C (strategy-specific metrics)
Manual stop override               → NEW: FR-004E (manual stop/profit override)
Pause trading if market weird      → FR-004B (pause mechanism)
Account heat tracking              → NEW: FR-005D (real-time % capital deployed)
```

### Scenario 3: Afternoon Adjustment
```
User Need                          → Requirement ID
Dynamic parameter adjustment       → NEW: FR-003C (time-of-day parameters)
Change profit targets mid-day      → NEW: FR-003C
Change stop loss sizes mid-day     → NEW: FR-003C
Switch to limit orders in slow mkt → NEW: FR-004F (order type selection)
```

### Scenario 4: Evening Wind-Down
```
User Need                          → Requirement ID
Mode: Close-only (no new entries)  → FR-004B (mode switching)
Hold overnight selectively         → NEW: FR-003D (overnight mode)
Export trades for tax              → NEW: FR-008D (export functionality)
Analyze daily performance          → FR-008C (basic analytics)
Plan tomorrow based on today       → NEW: FR-008E (strategy recommendations)
```

### Scenario 5: Overnight Crisis
```
User Need                          → Requirement ID
System alerts trader immediately   → NEW: FR-009B (critical alerts: SMS, push, email)
Different stops day vs overnight   → NEW: FR-003E (time-based parameter switching)
Pause trading during news events   → NEW: FR-004G (news calendar integration)
Fallback exit on exchange down     → NEW: FR-001B (fallback exchange support)
```

### Scenario 6: Weekly Review
```
User Need                          → Requirement ID
Win rate by strategy               → NEW: FR-008F (detailed analytics)
Win rate by time of day            → NEW: FR-008F
Win rate by pair                   → NEW: FR-008F
Risk/reward metrics                → NEW: FR-008F
Consecutive wins/losses tracking   → NEW: FR-008F
Fee impact analysis                → NEW: FR-008F
Optimal strategy mix recommendations → NEW: FR-008G (ML-based optimization)
```

---

## Critical Gaps Identified

### BLOCKING ISSUES (Stop Implementation Until Fixed)

| # | Issue | Impact | Fix Required |
|---|-------|--------|--------------|
| 1 | **15-minute interval too slow** | Opportunities in crypto are SECONDS, not minutes | Change to real-time alerts (sub-second signal latency) |
| 2 | **No manual order entry** | Trader can't override signals or react to news | Add manual BUY/SELL buttons on dashboard |
| 3 | **Fixed position sizing** | Can't adjust for risk, account heat, conviction | Add dynamic position sizing (0.5-3% based on parameters) |
| 4 | **No pause mechanism** | Can't stop trading without restarting system | Add PAUSE/RESUME state machine |
| 5 | **All-or-nothing exits** | Can't scale out of winners or average down | Add partial exit capability (25%, 50%, 75%, 100%) |
| 6 | **No mode switching** | Afternoon/evening require different parameters | Add modes: DAYTRADE, SWING, CLOSE_OUT, PAUSE |
| 7 | **Fixed parameters hardcoded** | Can't adjust stops/targets mid-day | Make all parameters dynamic (via UI, not config) |

### MAJOR GAPS (Implement Before Live Trading)

| # | Gap | Impact |
|---|-----|--------|
| 8 | No strategy mix adjustment | Can't adapt to market conditions |
| 9 | No per-strategy metrics | Can't identify which strategy works best |
| 10 | No heat tracking (% capital deployed) | Risk management is blind |
| 11 | No partial profit taking | Leave money on table or get stopped |
| 12 | No critical alerts (SMS/push) | Overnight crises not noticed |
| 13 | No fallback exchange | If Binance down, can't exit |
| 14 | No manual stop override | Can't defend against bad stops |
| 15 | No trade quality analysis | Can't learn why you win/lose |

### MINOR GAPS (Nice-to-Have, Post-Launch)

| # | Gap | Impact |
|---|-----|--------|
| 16 | No news calendar | Can't pause for important events |
| 17 | No export functionality | Hard to track taxes |
| 18 | No strategy recommendations | Manual optimization only |
| 19 | No fee impact tracking | Hard to see cost impact |

---

## Revised Requirements: From Workflows

### FR-003 Revised: Daytrading Strategies (EXPANDED)

**Old:** "Implement 3-4 crypto-specific strategies"

**New (From Scenarios):**
- Momentum scalper: Fast entry/exit, works 7-11am & 3-5pm
- Mean reversion: Bounce trading, works afternoon slump
- Grid trading: Mechanical, works always but small size
- User MUST be able to:
  - Enable/disable each strategy (on/off toggle)
  - Adjust allocation mix: (momentum 60%, reversion 10%, grid 30%) NOT fixed thirds
  - Change parameters PER STRATEGY PER TIME:
    - 7-11am: Aggressive (stops -2%, targets +2%)
    - 11am-3pm: Conservative (stops -1%, targets +0.8%)
    - 3pm-close: Close-out mode (stops -0.5%, no new entries)
  - Time-based strategy switching (morning = momentum, afternoon = reversion)

### FR-004 Revised: Execution Engine (EXPANDED)

**Old:** "Execute every 15 minutes"

**New (From Scenarios):**
- Real-time signal alerts (sub-second latency to trader awareness)
- Manual order buttons: BUY/SELL on dashboard (click to enter)
- Partial exit capability:
  - Take 25%, 50%, 75%, 100% of position
  - Scale out as price moves
  - Average in to positions
- Order types: Market (speed) + Limit (fee savings)
- Manual stop override: "I know system says stop, but I disagree"
- Pause/Resume: Stop new entries, keep monitoring
- Modes:
  - DAYTRADE: Full automation
  - SWING: Hold winners, close losers
  - CLOSE_ONLY: No new entries
  - PAUSE: System watches only
  - PAPER: Simulated

### FR-005 Revised: Portfolio Management (EXPANDED)

**Old:** "Track positions, P&L, max 5 concurrent"

**New (From Scenarios):**
- Dynamic position sizing (not fixed 2%):
  - Base: 1.5% per trade
  - Volatility adjustment: +50% if low vol, -50% if high vol
  - Account heat adjustment: Reduce if >60% deployed
  - Win streak: +10% per consecutive win (up to +50%)
  - Loss streak: -10% per consecutive loss (down to -50%)
- Real-time heat map: "30% of account deployed right now"
- Overnight risk management:
  - Different stops for day (-2%) vs overnight (-5%)
  - Optional: Close out all at market close, let grid continue
- Max concurrent positions: 5 (normal) to 3 (overnight)
- Correlation tracking: Don't have 80% account in same direction

### FR-008 Revised: Dashboard & Monitoring (EXPANDED)

**Old:** "Real-time P&L display, positions, health"

**New (From Scenarios):**
- LIVE metrics (update every 1 second):
  - Account equity, cash, deployed %, daily P&L %
  - Active positions (entry, current price, P&L, unrealized)
  - Current signals for all pairs (score, grade, trend)
  - System status (binance OK? Main OK? Backup OK?)
  
- STRATEGY breakdown:
  - Win rate by strategy (momentum 68%, reversion 54%, grid 61%)
  - Total trades, avg win, avg loss, profit factor per strategy
  - Allocation % (momentum 50%, reversion 30%, grid 20%)
  - Toggle enable/disable per strategy
  
- TIME OF DAY analysis:
  - Win rate by hour (7am best, 2pm worst)
  - Suggest which hours to trade aggressively vs conservatively
  
- PAIR analysis:
  - Win rate by pair (BTC 63%, ETH 59%, SOL 68%)
  - Suggest focus pairs
  
- QUICK ACTIONS (buttons):
  - BUY / SELL (manual entry)
  - SCALE OUT (25%, 50%, 75%)
  - PAUSE / RESUME
  - CLOSE ALL POSITIONS
  
- ANALYTICS (post-market):
  - Win/loss breakdown
  - Best & worst trades
  - Trade duration distribution
  - Fee impact ($45 fees on €295 profit = 15%)
  - Sharpe ratio, Sortino, max drawdown

### FR-009 Revised: Alerts & Runbooks (EXPANDED)

**Old:** "Alerts for daily loss >5%, connectivity, failover"

**New (From Scenarios):**
- CRITICAL (SMS + push + email):
  - Exchange down (Binance API timeout >30s)
  - Backup machine failover triggered
  - Daily loss >5% (auto-stop further trading)
  - Position margin called (if using margin)
  
- WARNING (push + email):
  - Account heat >60% (too much deployed)
  - Consecutive losses >3 (might be losing streak)
  - Signal quality dropped (strategy accuracy <50%)
  
- INFO (dashboard notification):
  - Trade filled
  - Position hit profit target
  - Strategy mix changed (allocation adjusted)
  - Mode changed (DAYTRADE → CLOSE_ONLY)

### NEW FR-003B: Dynamic Strategy Management

**User must be able to:**
- Enable/disable strategies on the fly (toggle)
- Adjust strategy allocation: 0-100% per strategy
- Set time-of-day parameters:
  - 7am-11am: momentum 60%, reversion 10%, grid 30%
  - 11am-3pm: momentum 20%, reversion 60%, grid 20%
  - 3pm-close: momentum 30%, reversion 0%, grid 70%
- Per-strategy parameters:
  - Profit target (0.5% to 3%)
  - Stop loss (0.5% to 5%)
  - Entry signal threshold (50-90)

### NEW FR-005D: Heat Tracking & Risk

**Real-time risk dashboard:**
- % of account deployed: "Currently 45% of capital in trades"
- Risk per trade: Varies by account size and conviction
- Drawdown tracking: Daily, weekly, all-time
- Volatility-adjusted position sizing
- Consecutive win/loss tracking

### NEW FR-008E: Trade Quality Analysis

**Post-trade analysis:**
- Entry quality: "Was this a good entry? Signal was 78/100" ✓
- Exit quality: "Did I exit at peak? Exited at +1.2% of +1.5% possible" ~
- Holding time: "Held 3 minutes, average is 8 minutes" 
- Fee cost: "Paid €1.80 in fees, profit was €6.50" (73% fee ratio)
- Time of day impact: "Morning trades won 67%, afternoon 50%"

---

## New Project Scope (REVISED)

### What MUST be built for daytrading (not theoretical trading)

**CRITICAL PATH (Blocking):**
1. Real-time alerts (<500ms latency)
2. Manual order buttons (click to enter)
3. Dynamic position sizing (account heat, win streak)
4. Pause/resume mechanism
5. Partial exits (scale out)
6. Mode switching (DAYTRADE/SWING/CLOSE_ONLY/PAUSE)
7. Dynamic parameters (no hardcoding)
8. Per-strategy analytics
9. Trade quality analysis
10. Critical alerts (SMS/push)

**NEEDED BEFORE LIVE (Not blocking paper test):**
1. Overnight vs day parameter differences
2. Fallback exchange support
3. News calendar pause
4. Correlation/heat tracking
5. Export trades
6. Strategy recommendations

**NICE-TO-HAVE (Post-launch):**
1. ML-based strategy mix optimization
2. Advanced fee analytics
3. Tax reporting integration
4. Multi-asset portfolio optimization

---

## Revised Timeline (More Realistic)

| Phase | Timeline | What's New |
|-------|----------|-----------|
| **Phase 1A: MVP Core** | Week 1 | Binance API, paper trading, basic momentum strategy |
| **Phase 1B: Daytrader UX** | Week 2 | Manual buttons, pause/resume, dynamic sizing, real-time alerts |
| **Phase 1C: Strategy Control** | Week 2.5 | Multi-strategy with allocation control, time-based parameters |
| **Phase 1D: Analytics** | Week 3 | Per-strategy win rate, time-of-day analysis, trade quality |
| **Phase 1E: Paper Acceptance** | Week 3.5 | 10-day paper run, >55% win rate required |
| **Phase 2: HA + Live** | Week 4-5 | Dual machine, failover, SMS alerts, overnight mode |
| **Phase 2 Acceptance** | Week 5.5 | 2-week live with €1,000 |

**More realistic:** 5-6 weeks, not 4 weeks

---

## Why This Matters

**Old design:** "System trades automatically, trader watches dashboard"
- Ignores that trader is PRIMARY intelligence
- Removes human judgment (often wrong!)
- Can't adapt to market conditions
- No learning loop

**New design:** "Trader directs system, system executes & learns"
- Trader approves/rejects signals
- Trader adjusts risk based on feelings
- Trader adapts strategies to market
- Trader learns what works via analytics
- System is TOOL, not replacement

---

## Conclusion

**The design was missing the HUMAN.**

Daytrading is NOT a "set it and forget it" system. It requires:
1. Human judgment on entries (system suggests, trader decides)
2. Human risk management (real-time heat tracking)
3. Human adaptation (switch strategies based on market)
4. Human learning (win rate analysis → next week's plan)

Real requirement: Build a **daytrading decision support system**, not an **autopilot**.

Revised approach:
- System generates signals
- Trader approves entries
- System manages risk (stops, position sizing)
- Trader can override stops
- Dashboard shows strategy performance
- Trader optimizes based on data

This is massively different from current design.

