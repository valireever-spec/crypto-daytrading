# Operations Runbooks — Common Scenarios

**Purpose:** Quick reference for common operational issues during Phase 1 and beyond  
**When to Use:** Trader acting unexpectedly, unclear what to do next  
**Updated:** 2026-06-25

---

## Runbook #1: Trader Crashed

**Symptom:** `running: false` in monitoring report

**Diagnosis (2 minutes):**
```bash
# Check if process is actually down
curl -s http://localhost:8001/api/autonomous/status | jq '.running'

# Check logs for crash reason
tail -50 logs/api_server.log | grep -i "error\|exception\|traceback"

# Check if port 8001 is listening
lsof -i :8001 || echo "Port not listening - API is down"
```

**Fix (1-2 minutes):**
```bash
# Kill old process if hanging
pkill -f "uvicorn.*8001" || true
sleep 2

# Restart API server
source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api_server.log 2>&1 &
sleep 3

# Verify restart
curl -s http://localhost:8001/api/autonomous/status | jq '.running'
# Should see: true
```

**Prevention:**
- Check logs daily for warnings before crash happens
- Monitor system resources (disk, memory, file handles)
- Restart weekly as maintenance

---

## Runbook #2: Config Wrong / Mismatched

**Symptom:** Entry threshold 60 but trades at 55, or position size wrong

**Diagnosis (1 minute):**
```bash
# Check what config is actually loaded
curl -s http://localhost:8001/api/autonomous/config | jq '.entry_threshold'

# Check what config file has
cat logs/trading_config.json | jq '.'

# Check .env
grep ENTRY_THRESHOLD .env
```

**Fix (1 minute):**
```bash
# Option 1: Update via API (preferred)
curl -X POST http://localhost:8001/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "entry_threshold": 60.0,
    "position_size_pct": 0.05,
    "max_positions": 5
  }'

# Option 2: Reset to known-good state
cat > logs/trading_config.json << 'EOF'
{
  "entry_threshold": 60.0,
  "exit_profit_target": 0.03,
  "exit_stop_loss": 0.02,
  "position_size_pct": 0.05,
  "max_positions": 5,
  "max_daily_loss_pct": 5.0,
  "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "enabled": true,
  "_last_updated": "2026-06-25T00:00:00Z"
}
EOF

# Restart trader to reload config
curl -X POST http://localhost:8001/api/autonomous/stop
sleep 2
curl -X POST http://localhost:8001/api/autonomous/start
```

**Prevention:**
- Never edit config manually, always use API
- Run config verification daily: `bash scripts/monitor-phase1.sh` checks this

---

## Runbook #3: Daily Loss Limit Hit (Paused)

**Symptom:** `enabled: false` in monitoring report, Daily P&L < -€500

**Diagnosis (1 minute):**
```bash
# Confirm it's the daily loss limit
curl -s http://localhost:8001/api/autonomous/status | jq '.daily_pnl'
# If < -500, trading is paused

# Check when it happened
grep "DAILY_LOSS_LIMIT\|daily loss" logs/api_server.log | tail -5
```

**What to Do:**
1. **Review the losing trades:**
   ```bash
   grep TRADE_EXIT logs/api_server.log | jq '[.[] | select(.pnl_pct < 0)] | sort_by(.timestamp) | reverse | .[0:5]'
   ```

2. **Understand why:**
   - Slippage worse than 0.1%? (check entry vs exit prices)
   - Bad signals? (check signal_score, threshold)
   - Bad luck? (even good strategy loses some days)

3. **Your options:**

   **Option A: Wait until midnight UTC (automatic reset)**
   ```bash
   # Daily P&L resets at 00:00 UTC automatically
   # Trader will resume trading next day
   # Do nothing, just monitor
   ```

   **Option B: If it's a systemic problem (Phase 1), debug first:**
   ```bash
   # Check recent signals
   grep SIGNAL_DECISION logs/api_server.log | tail -10 | jq '{symbol, signal_score, threshold, passed}'
   
   # If all signals are weak (signal_score ≈ 60):
   # → Raise entry_threshold to 65 to be more selective
   
   # If slippage is high (entry price vs fill price):
   # → Check Binance order book liquidity for those symbols
   ```

**Prevention:**
- This is normal and expected. It's how the daily loss limit works.
- Phase 1 design: Lose <€500/day, learn from it, continue next day
- Phase 2 design: If lose €100, investigate root cause before resuming

---

## Runbook #4: Position Orphaned (Still Open After Restart)

**Symptom:** Restart trader, positions still showing in logs but no active orders

**Diagnosis (1 minute):**
```bash
# Check what positions are in memory
curl -s http://localhost:8001/api/autonomous/status | jq '.recent_trades[-5:]'

# Check what's in trade history file
tail -20 logs/trades.jsonl | jq '{symbol, side, timestamp}'
```

**Why This Happens:**
- Trader crashed before closing position
- OR position marked as closed in logs but Binance order didn't fill

**Fix (1-2 minutes):**

**If position should be closed:**
```bash
# Manually place exit order
curl -X POST http://localhost:8001/api/smart/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "quantity": 0.001,
    "order_type": "MARKET",
    "reason": "Manual exit - orphaned position"
  }'
```

**If unsure whether to close:**
```bash
# Check if position is in profit or loss
CURRENT_PRICE=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT" | jq '.price')
ENTRY_PRICE=61758.0  # from logs
LOSS=$(echo "scale=2; ($CURRENT_PRICE - $ENTRY_PRICE) / $ENTRY_PRICE * 100" | bc)
echo "Position loss/gain: $LOSS%"

# If in profit: close it (take the win)
# If in loss >2%: close it (take stop loss)
# If in loss <1%: hold or close based on signal
```

**Prevention:**
- Post-Phase1: Add state persistence (G-001) to save position state before crash
- Until then: Positions are acceptable loss for Phase 1 learning

---

## Runbook #5: No Trades for 2+ Hours

**Symptom:** Last TRADE_EXECUTED was 2+ hours ago, signal decisions still happening

**Diagnosis (1 minute):**
```bash
# Check last trade time
grep TRADE_EXECUTED logs/api_server.log | tail -1 | jq '.timestamp'

# Check if signals are being generated
grep -c SIGNAL_DECISION logs/api_server.log

# Check active positions
curl -s http://localhost:8001/api/autonomous/status | jq '.active_positions'
```

**Likely Causes:**

1. **Hit max position limit:**
   ```bash
   # Check: are there 5 active positions?
   curl -s http://localhost:8001/api/autonomous/status | jq '.active_positions'
   # If 5, no new positions until one exits
   # This is NORMAL (position limit working)
   ```

2. **All new signals below threshold:**
   ```bash
   # Check signal scores
   grep SIGNAL_DECISION logs/api_server.log | jq '.signal_score' | tail -20
   # If all < 60: signals are weak, waiting for stronger signal
   # This is NORMAL (waiting for better setup)
   ```

3. **Binance connection issue:**
   ```bash
   # Test Binance API
   curl -s "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT" | jq '.price'
   # If error: Binance is down or unreachable
   # Check network: ping 8.8.8.8
   ```

**Action:**
- If max positions: NORMAL, wait for exits
- If weak signals: NORMAL, wait for better market setup  
- If Binance down: Check network, restart trader when API recovers

**Prevention:**
- This is normal behavior, not a bug
- System is designed to wait for good setups instead of forced trades

---

## Runbook #6: Slippage Worse Than Expected

**Symptom:** P&L worse than backtested, position exits at worse prices than wanted

**Diagnosis (2-3 minutes):**
```bash
# Compare entry signal price vs actual fill price
grep SIGNAL_DECISION logs/api_server.log | jq '.symbol' | head -1
# Take first trade, then find corresponding TRADE_EXECUTED

# Calculate slippage
SIGNAL_PRICE=61758.0  # from SIGNAL_DECISION
FILL_PRICE=61760.5    # from TRADE_EXECUTED
SLIPPAGE=$(echo "scale=4; ($FILL_PRICE - $SIGNAL_PRICE) / $SIGNAL_PRICE * 100" | bc)
echo "Slippage: $SLIPPAGE%"
```

**Expected:**
- Market orders: 0.1% - 0.3% slippage (Binance 0.1% fee + bid-ask)
- High volume hours (13:00-21:00 UTC): 0.05% - 0.15%
- Low volume hours (01:00-04:00 UTC): 0.2% - 0.5%

**What to Do:**

- **If slippage 0.1-0.3%:** NORMAL, system working as expected
  
- **If slippage >0.5%:** Investigate
  ```bash
  # Were you trading during low-volume hours?
  grep TRADE_EXECUTED logs/api_server.log | jq '.timestamp' | tail -10
  # If between 01:00-04:00 UTC: that's why, slippage worse then
  
  # Can add trading hours filter in Phase 2:
  # Only trade 13:00-21:00 UTC (better liquidity)
  ```

**Prevention:**
- Phase 1: Accept slippage, measure it
- Phase 2: Add trading hours filter to avoid low-liquidity periods
- Phase 3: Use limit orders instead of market orders (slower but better price)

---

## Runbook #7: "Backup Sync Failed" Warning

**Symptom:** Logs show "Backup sync failed after 3 attempts"

**Diagnosis (1 minute):**
```bash
# Check if backup machine is reachable
ping 192.168.3.25
curl -s http://192.168.3.25:8002/api/health | jq '.status'
```

**Why it happens:**
- Backup machine is temporarily down/unreachable
- OR backup API is out of sync with primary code
- This is OK for Phase 1 (trading continues on primary)

**Impact:**
- ✅ Primary trading continues NORMALLY
- ⚠️ If primary crashes, backup may have stale config
- This is acceptable for Phase 1 (we're learning)

**Action:**
```bash
# Option 1: Restart backup machine (if it crashed)
ssh vali@192.168.3.25 "source venv/bin/activate && python -m uvicorn backend.api.main:app --port 8002 &"

# Option 2: Verify primary and backup in sync
curl -s http://localhost:8001/api/autonomous/config | jq '.entry_threshold'
curl -s http://192.168.3.25:8002/api/autonomous/config | jq '.entry_threshold'
# Should match
```

**Prevention:**
- Post-Phase1: Check backup health daily
- Post-Phase1: Implement automatic failover (HA takes over if primary down)

---

## Runbook #8: Market Regime Detector Stuck

**Symptom:** All signals show regime: "unknown" for 2+ hours

**Diagnosis (1 minute):**
```bash
# Check regime values
grep SIGNAL_DECISION logs/api_server.log | jq '.regime' | sort | uniq -c
# Should see mix of: bull, bear, sideways, unknown
# If ALL "unknown": detector is stuck
```

**Why it happens:**
- Not enough historical data (first hour of trading)
- OR volatility calculation edge case
- This is NORMAL for first 1-2 hours

**Impact:**
- Unknown regime = use default thresholds (60.0)
- Works fine, just no regime-based adjustments

**Action:**
- Wait 2+ hours, regime detector will start working
- Don't panic, system still trades at threshold

**Prevention:**
- This resolves itself, no action needed

---

## Runbook #9: Restart Everything (Full Reset)

**When:** Something is really broken and you can't diagnose it

**Steps (5 minutes):**
```bash
# 1. Stop all processes
pkill -f "uvicorn.*8001" || true
pkill -f "uvicorn.*8002" || true
sleep 2

# 2. Clear stale state (optional, only if logs corrupted)
# DO NOT DELETE TRADE LOGS
# But we can reset daily P&L
cat > logs/trading_config.json << 'EOF'
{
  "entry_threshold": 60.0,
  "exit_profit_target": 0.03,
  "exit_stop_loss": 0.02,
  "position_size_pct": 0.05,
  "max_positions": 5,
  "max_daily_loss_pct": 5.0,
  "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "enabled": true,
  "_last_updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# 3. Restart primary
source venv/bin/activate
cd /home/vali/projects/crypto-daytrading
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api_server.log 2>&1 &
sleep 3

# 4. Verify running
curl -s http://localhost:8001/api/autonomous/status | jq '.running'
# Should see: true

# 5. Restart trading
curl -X POST http://localhost:8001/api/autonomous/start
```

**Caution:**
- Don't do this unless necessary
- Safe to do anytime (trading state saved in logs)
- Trade history never lost

---

## Runbook #10: Check Backup HA Health

**When:** Want to verify failover is working

**Diagnosis (2 minutes):**
```bash
# Check primary
echo "PRIMARY:"
curl -s http://localhost:8001/api/autonomous/status | jq '{running, enabled, active_positions, daily_pnl}'

# Check backup
echo "BACKUP:"
curl -s http://192.168.3.25:8002/api/autonomous/status | jq '{running, enabled, active_positions, daily_pnl}'

# Should be identical (config synced)
# Both should show same active_positions and daily_pnl
```

**If different:**
- Backup config is stale (sync didn't happen)
- This is OK for Phase 1
- Post-Phase1: investigate why sync failed

**If backup down:**
```bash
# Restart backup
ssh vali@192.168.3.25 "pkill -f uvicorn || true; sleep 2; source venv/bin/activate && python -m uvicorn backend.api.main:app --port 8002 > logs/api_server.log 2>&1 &"
sleep 3

# Verify it's up
curl -s http://192.168.3.25:8002/api/health
```

---

## Summary: When to Use Which Runbook

| Issue | Runbook | Time |
|-------|---------|------|
| API won't respond | #1 (Restart) | 2 min |
| Settings wrong | #2 (Config) | 1 min |
| Trading paused | #3 (Loss Limit) | 1 min |
| Position stuck | #4 (Orphaned) | 2 min |
| No trades | #5 (No Activity) | 1 min |
| Bad prices | #6 (Slippage) | 2 min |
| Backup warning | #7 (Backup Sync) | 1 min |
| Weird regime | #8 (Regime) | 1 min |
| Everything broken | #9 (Full Reset) | 5 min |
| Verify HA | #10 (HA Health) | 2 min |

---

**Document Status:** READY  
**Last Updated:** 2026-06-25  
**Used during:** Phase 1 (2026-06-25 to 2026-07-05+)
