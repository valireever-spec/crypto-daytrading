# Crypto Daytrading Platform — Runbooks

**Last Updated:** 2026-07-03  
**Phase:** 1 (Paper Trading)  
**On-Call Contacts:** See CONTACTS.md

---

## Quick Reference

| Alert | Severity | Response Time | Runbook |
|-------|----------|----------------|---------|
| **WebSocket Disconnected** | 🔴 Critical | 5 min | [RB-001](#rb-001-websocket-disconnected) |
| **Circuit Breaker Tripped** | 🔴 Critical | 5 min | [RB-002](#rb-002-circuit-breaker-tripped) |
| **Data Quality Low** | 🟡 High | 10 min | [RB-003](#rb-003-data-quality-low) |
| **Failover Triggered** | 🔴 Critical | 5 min | [RB-004](#rb-004-failover-triggered) |
| **Daily Loss Exceeded** | 🟡 High | 10 min | [RB-005](#rb-005-daily-loss-limit-exceeded) |
| **Position Reconciliation Failed** | 🟡 High | 15 min | [RB-006](#rb-006-position-reconciliation-failed) |
| **API Unresponsive** | 🔴 Critical | 5 min | [RB-007](#rb-007-api-unresponsive) |
| **Order Execution Timeout** | 🟡 High | 10 min | [RB-008](#rb-008-order-execution-timeout) |
| **Memory Usage Critical** | 🔴 Critical | 5 min | [RB-009](#rb-009-memory-usage-critical) |
| **Backup Sync Failed** | 🟡 High | 15 min | [RB-010](#rb-010-backup-sync-failed) |

---

## RB-001: WebSocket Disconnected

**Symptom:** Price feed stale >120 seconds, no price updates in logs

**Detection:**
```bash
# Check if WebSocket is connected
curl -s http://localhost:8001/api/health | jq '.websocket'

# Expected: {"websocket": {"connected": true, "last_message": "2026-07-03T14:50:00Z"}}
# Problem: connected=false OR last_message > 120 seconds old
```

**Root Causes:**
1. Binance API down or rate limited
2. Network connectivity issue (ISP, firewall)
3. WebSocket connection hung/zombie
4. Memory exhaustion (reconnect loop)

### Step 1: Assess Severity (2 min)

```bash
# Check how long WebSocket has been down
curl -s http://localhost:8001/api/health | jq '.websocket.last_message'

# Check if trading is actually affected
curl -s http://localhost:8001/api/paper/account | jq '{total_equity, positions: .positions | length}'

# Check circuit breaker status
curl -s http://localhost:8001/api/health | jq '.circuit_breaker.state'
```

**If Circuit Breaker = OPEN:** Go to [RB-002](#rb-002-circuit-breaker-tripped)

**If Circuit Breaker = CLOSED:** Continue to Step 2

### Step 2: Try Automatic Reconnect (3 min)

The system should auto-reconnect after 60s stale threshold. Check if it's recovering:

```bash
# Watch WebSocket health for 2 minutes
watch -n 5 'curl -s http://localhost:8001/api/health | jq ".websocket"'
```

**If reconnected:** ✅ Stop, alert has resolved

**If still disconnected:** Continue to Step 3

### Step 3: Check Binance API Status (2 min)

```bash
# Verify Binance is responding
curl -s https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT | jq '.price'

# Expected: A price like "62000.00"
# Error: Connection timeout, 5xx, or 429 (rate limited)
```

**If Binance is down:** 
- Create incident: "Binance API unavailable"
- Notify stakeholders (not actionable on our end)
- Monitor until Binance recovers
- Stop here

**If Binance is up:** Continue to Step 4

### Step 4: Reconnect WebSocket (2 min)

Restart the API service (triggers WebSocket reconnection):

```bash
# Check which machine (PRIMARY or BACKUP)
curl -s http://localhost:8001/api/health | jq '.machine_id'

# PRIMARY: 192.168.30.137:8001
# BACKUP: 192.168.3.25:8002

# SSH to machine
ssh -i ~/.ssh/trading_key openhabian@192.168.30.137

# Restart service (graceful)
sudo systemctl restart crypto-trading

# Verify it reconnects (wait 30 seconds)
sleep 30
curl http://localhost:8001/api/health | jq '.websocket.connected'
# Expected: true
```

### Step 5: Verify Recovery (2 min)

```bash
# Check prices are updating
curl -s http://localhost:8001/api/prices | jq '.prices'

# Expected: Recent prices like {"BTCUSDT": 62000.00, ...}

# Check trading resumed
curl -s http://localhost:8001/api/paper/status | jq '.status'
# Expected: "running" or "trading"
```

✅ **Resolution:** WebSocket reconnected, prices flowing, trading resumed

---

## RB-002: Circuit Breaker Tripped

**Symptom:** Trading stopped, CB state = "OPEN" in logs, no new trades

**Detection:**
```bash
curl -s http://localhost:8001/api/health | jq '.circuit_breaker'

# Expected: {"state": "CLOSED"}
# Problem: {"state": "OPEN", "trips": 5, "last_trip": "2026-07-03T14:50:00Z"}
```

**Root Causes:**
1. WebSocket disconnected (no price updates)
2. Data quality dropped below 30%
3. Order execution failed (insufficient balance, API error)
4. Position reconciliation failed
5. Daily loss limit exceeded

### Step 1: Identify Why CB Tripped (3 min)

```bash
# Check CB trip history
curl -s http://localhost:8001/api/monitoring/circuit-breaker/stats | jq '.recent_trips'

# Example output:
# [
#   {"timestamp": "...", "reason": "Price stale >120s", "data_quality": 0},
#   {"timestamp": "...", "reason": "Insufficient balance", "balance": 50}
# ]

# Check current state
curl -s http://localhost:8001/api/paper/account | jq '{cash, daily_pnl, total_equity}'
curl -s http://localhost:8001/api/prices | jq '.prices'
```

**Match trip reason to appropriate section below:**

### If Reason = "Price Stale" → RB-001: WebSocket Disconnected

### If Reason = "Data Quality Low"

```bash
# Check data quality score
curl -s http://localhost:8001/api/health | jq '.data_quality'
# Expected: >30% for trading, <30% = CB trip

# If <30%: Check WebSocket (RB-001), check Binance API status
```

### If Reason = "Insufficient Balance"

```bash
# Check account cash
curl -s http://localhost:8001/api/paper/account | jq '.cash'

# If cash ≈ 0: Losses consumed capital
# Next step: Pause trading, investigate loss patterns
```

**Go to RB-005: Daily Loss Exceeded**

### If Reason = "Order Failed"

```bash
# Check latest trade logs
tail -20 logs/trades.jsonl | jq '.{timestamp, symbol, side, status, error}'

# Check if Binance is rejecting orders
curl -s https://api.binance.com/api/v3/account | jq '.balances[] | select(.asset=="USDT")'
```

**If Binance API error:** 
- Check Binance status (https://status.binance.com)
- Wait for Binance recovery
- CB auto-reset after 5 min

### Step 2: Reset Circuit Breaker (1 min)

**After fixing root cause**, manually reset:

```bash
# Reset CB (requires ≥30% data quality)
curl -X POST http://localhost:8001/api/admin/circuit-breaker/reset

# Verify state
curl -s http://localhost:8001/api/health | jq '.circuit_breaker.state'
# Expected: "CLOSED"
```

**If reset fails:** Data quality still <30%, fix WebSocket first (RB-001)

### Step 3: Verify Trading Resumed (2 min)

```bash
# Check status
curl -s http://localhost:8001/api/paper/status | jq '.status'
# Expected: "running"

# Watch for new trades
watch -n 5 'curl -s http://localhost:8001/api/paper/account | jq ".trades | length"'
# Should increment every 15 minutes if signals are generated
```

✅ **Resolution:** CB reset, root cause fixed, trading resumed

---

## RB-003: Data Quality Low

**Symptom:** Data quality <30%, alerts in logs, CB may trip

**Detection:**
```bash
curl -s http://localhost:8001/api/health | jq '.data_quality'

# Expected: 50-100% (green)
# Warning: 30-50% (yellow)
# Critical: <30% (red) → CB trips
```

**Root Causes:**
1. Missing prices for some symbols
2. Prices stale (haven't updated recently)
3. Volatility calculation missing
4. WebSocket partially connected

### Step 1: Check Which Symbols Are Missing (2 min)

```bash
curl -s http://localhost:8001/api/prices | jq '.prices'

# Expected: {"BTCUSDT": 62000, "ETHUSDT": 1750, "BNBUSDT": 565}
# Problem: Missing symbols or very old prices
```

### Step 2: Check Price Freshness (2 min)

```bash
curl -s http://localhost:8001/api/health | jq '.websocket.prices'

# Expected output:
# {
#   "BTCUSDT": {"price": 62000, "age_seconds": 2.5},
#   "ETHUSDT": {"price": 1750, "age_seconds": 3.1},
#   "BNBUSDT": {"price": 565, "age_seconds": 2.8}
# }

# Problem: age_seconds > 20 = stale
```

### Step 3: Fix Root Cause

**If prices missing:** 
- Check WebSocket subscriptions
- Restart API (see RB-001 Step 4)

**If prices stale:**
- Check WebSocket (RB-001)

**If all prices fresh but still <30%:**
- This is a measurement bug
- Note in logs: "False positive data quality alert"
- Reset CB manually (RB-002 Step 2)

### Step 4: Verify Quality Recovers (3 min)

```bash
# Monitor data quality
watch -n 5 'curl -s http://localhost:8001/api/health | jq ".data_quality"'

# Should improve to >50% within 1-2 minutes
```

✅ **Resolution:** Prices flowing, data quality >30%, trading continues

---

## RB-004: Failover Triggered

**Symptom:** PRIMARY becomes unresponsive, BACKUP takes over

**Detection:**
```bash
# On BACKUP machine (192.168.3.25:8002)
curl -s http://localhost:8002/api/health | jq '.status'
# If "healthy": BACKUP is now trading (failover happened)

# Check heartbeat status
curl -s http://localhost:8002/api/monitoring/ha/explicit-heartbeat/stats | jq '.primary_status'
# If "dead": PRIMARY has failed
```

### Step 1: Assess Severity (2 min)

```bash
# Check BACKUP trading status
curl -s http://192.168.3.25:8002/api/paper/account | jq '{cash, positions, total_pnl}'

# Check how long PRIMARY has been down
curl -s http://192.168.3.25:8002/api/monitoring/ha/explicit-heartbeat/stats | jq '.last_primary_check'
```

**If BACKUP is trading:** ✅ Failover working, continue to Step 2

**If BACKUP is NOT trading:** 🔴 Critical, go to Step 3

### Step 2: Investigate PRIMARY Failure (5 min)

**Try to reach PRIMARY:**

```bash
# From your local machine
ping 192.168.30.137
curl -s http://192.168.30.137:8001/api/health

# If no response: PRIMARY is down (network or service crash)
# If response: PRIMARY is up (check why BACKUP thinks it's dead)
```

**If PRIMARY is unreachable:**
- PRIMARY machine appears offline
- Continue with BACKUP trading
- Investigate PRIMARY machine:
  ```bash
  # SSH to PRIMARY (if reachable)
  ssh -i ~/.ssh/trading_key openhabian@192.168.30.137
  
  # Check service status
  sudo systemctl status crypto-trading
  
  # View logs
  sudo journalctl -u crypto-trading -n 50 --no-pager
  
  # Restart if crashed
  sudo systemctl restart crypto-trading
  ```

**If PRIMARY is reachable:**
- Network issue between machines
- Check SSH tunnel status (see RB-010)
- Trigger manual failback once PRIMARY is verified stable

### Step 3: Verify BACKUP Stability (5 min)

```bash
# Check BACKUP health
ssh openhabian@192.168.3.25 'curl -s http://localhost:8002/api/health | jq ".status"'

# Verify prices are updating
ssh openhabian@192.168.3.25 'curl -s http://localhost:8002/api/prices | jq ".prices"'

# Check circuit breaker
ssh openhabian@192.168.3.25 'curl -s http://localhost:8002/api/health | jq ".circuit_breaker.state"'
```

**If BACKUP is healthy:** Continue to Step 4

**If BACKUP is degraded:** 
- Apply appropriate runbook (RB-001, RB-002, etc.)

### Step 4: Resume PRIMARY (When Recovered)

Once PRIMARY is back online and stable:

```bash
# Verify PRIMARY is healthy
curl -s http://192.168.30.137:8001/api/health | jq '.status'

# Trigger failback (BACKUP → PRIMARY)
curl -X POST http://192.168.30.137:8001/api/failover/failback

# Verify PRIMARY is now trading
curl -s http://192.168.30.137:8001/api/paper/account | jq '.status'
```

### Step 5: Analyze Root Cause (10 min)

```bash
# Review PRIMARY logs for what caused failure
ssh openhabian@192.168.30.137 'sudo journalctl -u crypto-trading --since "30 min ago" | grep -i error'

# Common causes:
# - Out of memory (check: free -h)
# - WebSocket reconnection loop
# - Order execution timeout
# - Database corruption

# Document in incident report:
# - When failover triggered
# - How long PRIMARY was down
# - Root cause
# - Fix applied
```

✅ **Resolution:** PRIMARY recovered and trading, or BACKUP stable if PRIMARY recovery ongoing

---

## RB-005: Daily Loss Limit Exceeded

**Symptom:** Trading stopped, daily P&L < -5% of capital, CB may trip

**Detection:**
```bash
curl -s http://localhost:8001/api/paper/account | jq '{daily_pnl, total_equity, loss_pct: (.daily_pnl / .total_equity * 100)}'

# Expected: daily_pnl ≥ -50 (5% of 1000)
# Problem: daily_pnl < -50
```

**Root Causes:**
1. Systematic losses (signal not working)
2. High slippage (too much market movement)
3. Stop loss hit multiple times in succession
4. Bug in order execution

### Step 1: Review Today's Trades (5 min)

```bash
# Get all trades from today
curl -s http://localhost:8001/api/paper/trades | jq '.trades[] | select(.timestamp | startswith("2026-07-03")) | {timestamp, symbol, side, entry_price, exit_price, pnl, pnl_pct}'

# Example:
# [
#   {"symbol": "BTCUSDT", "side": "BUY", "pnl": -25.50, "pnl_pct": -2.3},
#   {"symbol": "ETHUSDT", "side": "BUY", "pnl": -18.20, "pnl_pct": -1.8},
#   ...total: -60.12 loss
# ]

# Count winning vs losing trades
curl -s http://localhost:8001/api/paper/trades | jq '[.trades[] | select(.timestamp | startswith("2026-07-03")) | .pnl] | {total_pnl: add, winning: map(select(. > 0)) | length, losing: map(select(. < 0)) | length, win_rate: (map(select(. > 0)) | length) / length * 100}'
```

### Step 2: Classify Loss Pattern (3 min)

**Pattern 1: Consistent small losses (win_rate < 40%)**
- Signal generation not working
- Entry/exit thresholds miscalibrated
- Action: Pause trading, review signal logs

**Pattern 2: Few large losses**
- Slippage or sudden price moves
- Action: Check market volatility, review stop losses

**Pattern 3: Stop loss cascades (multiple -1.5% losses)**
- Trading too aggressively in volatile market
- Action: Review entry_threshold, increase stop_loss

### Step 3: Decide Next Action (2 min)

**Option A: Pause Trading (Conservative)**
```bash
# Disable trading
curl -X POST http://localhost:8001/api/trading/disable

# Investigate during market hours when you can analyze live
curl -s http://localhost:8001/api/paper/status | jq '.trading_enabled'
```

**Option B: Continue with Reduced Exposure (Moderate)**
```bash
# Reduce position size to 0.5%
curl -X POST http://localhost:8001/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"position_size_pct": 0.5}'

# Verify change
curl -s http://localhost:8001/api/paper/account | jq '.config.position_size_pct'
```

**Option C: Increase Stop Loss (Defensive)**
```bash
# Increase stop loss from 1.5% to 2.5%
curl -X POST http://localhost:8001/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"exit_stop_loss": 0.025}'

# Verify
curl -s http://localhost:8001/api/config | jq '.exit_stop_loss'
```

### Step 4: Document and Analyze (5 min)

Create an entry in RETROSPECTIVES.md:

```markdown
## 2026-07-03 Daily Loss Incident

**Loss:** €5.17 (-0.5% of €1,000)

**Pattern:** [Consistent losses / Stop loss cascade / Single large loss]

**Trades:** X wins, Y losses, Z% win rate

**Root Cause:** [Signal miscalibration / High volatility / ... ]

**Action Taken:** [Paused / Reduced exposure / Increased stop loss]

**Next Steps:** [Adjust thresholds / Review signal logic / Increase capital]
```

### Step 5: Recover Capital Next Day

```bash
# Next trading day, resume with updated config
curl -X POST http://localhost:8001/api/trading/enable

# Monitor first hour closely
watch -n 10 'curl -s http://localhost:8001/api/paper/account | jq "{daily_pnl, positions: .positions | length}"'
```

✅ **Resolution:** Loss documented, containment action taken, trading paused or adjusted

---

## RB-006: Position Reconciliation Failed

**Symptom:** Position counts mismatch between ENGINE and DB, or invalid positions

**Detection:**
```bash
# Check for reconciliation errors in logs
tail -50 logs/system.log | grep -i "reconciliation\|mismatch\|invalid"

# Check position count
curl -s http://localhost:8001/api/paper/positions | jq '.positions | length'

# Check account positions
curl -s http://localhost:8001/api/paper/account | jq '.positions | length'

# If mismatch: reconciliation failed
```

**Root Causes:**
1. Database corruption
2. Concurrent position updates (race condition)
3. Failed order not properly rolled back
4. Backup sync incomplete

### Step 1: Get Current State (3 min)

```bash
# Dump all positions from API
curl -s http://localhost:8001/api/paper/positions | jq '.positions'

# Dump raw database (if accessible)
sqlite3 data/trading.db "SELECT * FROM positions;"

# Check if counts match
API_COUNT=$(curl -s http://localhost:8001/api/paper/positions | jq '.positions | length')
DB_COUNT=$(sqlite3 data/trading.db "SELECT COUNT(*) FROM positions;")
echo "API: $API_COUNT, DB: $DB_COUNT"
```

### Step 2: Identify Invalid Positions (3 min)

```bash
# Check for:
# - Negative quantity
# - Zero entry price
# - Unknown symbol
# - Duplicate positions (same symbol)

curl -s http://localhost:8001/api/paper/positions | jq '.positions[] | select(.quantity <= 0 or .entry_price <= 0 or .entry_price == null)'

# If any results: Those positions are corrupt
```

### Step 3: Fix Corrupt Positions (5 min)

**Option A: Remove corrupt positions (risky, may lose history)**
```bash
# Identify corrupt position ID
CORRUPT_ID=$(curl -s http://localhost:8001/api/paper/positions | jq '.positions[] | select(.quantity <= 0) | .id' | head -1)

# Delete (only if clearly invalid)
curl -X DELETE http://localhost:8001/api/paper/positions/$CORRUPT_ID

# Verify
curl -s http://localhost:8001/api/paper/positions | jq '.positions | length'
```

**Option B: Rebuild positions from trade log (safer)**
```bash
# Rebuild positions from trades
curl -X POST http://localhost:8001/api/admin/rebuild-positions

# Verify
curl -s http://localhost:8001/api/paper/positions | jq '.positions'
```

### Step 4: Verify DB Integrity (3 min)

```bash
# Run consistency check
curl -X POST http://localhost:8001/api/admin/check-consistency | jq '.results'

# Expected: all "OK" or "consistent"
# If errors: DB may need repair
```

### Step 5: Sync BACKUP if Needed (5 min)

```bash
# Force sync positions to BACKUP
curl -X POST http://192.168.3.25:8002/api/autonomous/config/sync

# Verify BACKUP has same positions
ssh openhabian@192.168.3.25 'curl -s http://localhost:8002/api/paper/positions | jq ".positions | length"'
```

✅ **Resolution:** Positions consistent across API/DB/BACKUP, reconciliation passes

---

## RB-007: API Unresponsive

**Symptom:** API timeouts, HTTP errors, no responses to requests

**Detection:**
```bash
# Try simple health check
curl -s -m 5 http://localhost:8001/api/health

# If timeout or connection refused: API is down
```

**Root Causes:**
1. Service crash (out of memory, unhandled exception)
2. API hung on long-running operation
3. Resource exhaustion (sockets, file descriptors)
4. Network connectivity issue

### Step 1: Check if Service is Running (1 min)

```bash
# Check service status
sudo systemctl status crypto-trading

# Expected: active (running)
# Problem: inactive, failed, or restarting

# Check if process exists
ps aux | grep "python.*main.py"
```

**If service is running:** Go to Step 2

**If service is down:** Go to Step 4

### Step 2: Check Resource Usage (2 min)

```bash
# Check memory
free -h
# If Mem available < 100 MB: Out of memory likely

# Check open sockets
netstat -an | grep -c ESTABLISHED
# If > 500: Possible socket leak

# Check CPU
top -b -n 1 | grep python

# Check disk
df -h /
# If / is >90% full: Disk may be issue
```

### Step 3: Restart Service (2 min)

```bash
# Graceful restart
sudo systemctl restart crypto-trading

# Wait for it to come up
sleep 10

# Verify it's responding
curl -s http://localhost:8001/api/health | jq '.status'
# Expected: "healthy"
```

**If it recovers:** ✅ Go to Step 5

**If it crashes again:** Go to Step 4

### Step 4: Check Logs for Root Cause (5 min)

```bash
# Get recent logs
sudo journalctl -u crypto-trading -n 100 --no-pager

# Look for:
# - MemoryError
# - Traceback (unhandled exception)
# - Out of file descriptors
# - Database locked

# Get application logs
tail -100 logs/system.log | tail -30
```

**Common fixes:**

**If Memory Error:**
```bash
# Restart service (should recover)
sudo systemctl restart crypto-trading

# If repeats: May need to increase VM memory or find memory leak
```

**If Database Locked:**
```bash
# Database connection still open from crashed process
# Kill lingering connections
lsof | grep trading.db
# Then restart

sudo systemctl restart crypto-trading
```

**If Unhandled Exception:**
```bash
# Report bug with traceback
# Fix: Deploy code patch
# For now: Restart service to recover
sudo systemctl restart crypto-trading
```

### Step 5: Verify Recovery (3 min)

```bash
# Check API is responding
curl -s http://localhost:8001/api/health | jq '{status, circuit_breaker: .circuit_breaker.state}'

# Check trading is running
curl -s http://localhost:8001/api/paper/status | jq '.status'

# Check prices are fresh
curl -s http://localhost:8001/api/prices | jq '.prices'
```

✅ **Resolution:** API responding, trading resumed

---

## RB-008: Order Execution Timeout

**Symptom:** Order stuck "pending", not filled after 30 seconds

**Detection:**
```bash
# Check recent orders
curl -s http://localhost:8001/api/paper/trades | jq '.pending_orders[] | select(.status == "pending" and .age_seconds > 30)'

# If any results: Order is stuck
```

**Root Causes:**
1. Binance API slow (rare)
2. Order execution service crashed
3. Network latency spike
4. Order rejected (insufficient balance, invalid symbol)

### Step 1: Check Order Details (2 min)

```bash
# Get stuck order info
STUCK_ORDER=$(curl -s http://localhost:8001/api/paper/trades | jq '.pending_orders[0]')
echo $STUCK_ORDER | jq '{symbol, side, quantity, price, status, age_seconds}'

# Typical output:
# {
#   "symbol": "BTCUSDT",
#   "side": "BUY",
#   "quantity": 0.5,
#   "price": 62000,
#   "status": "pending",
#   "age_seconds": 45
# }
```

### Step 2: Check Binance for Order (3 min)

```bash
# Did order reach Binance?
curl -s https://api.binance.com/api/v3/openOrders | jq '.[] | select(.symbol == "BTCUSDT")'

# If order appears: It's at Binance, waiting to fill
# Action: Wait, it should fill soon

# If order not there: Order never reached Binance
# Action: Check execution service
```

### Step 3: Retry Order (1 min)

```bash
# Cancel stuck order (if it's your internal state, not at Binance)
curl -X POST http://localhost:8001/api/paper/cancel-order \
  -H "Content-Type: application/json" \
  -d '{"order_id": "'$ORDER_ID'"}'

# Retry execution
curl -X POST http://localhost:8001/api/paper/place-order \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.5}'
```

### Step 4: If Retry Fails (2 min)

```bash
# Check Binance status
curl -s https://status.binance.com | grep -i "operational"

# Check account balance
curl -s https://api.binance.com/api/v3/account | jq '.balances[] | select(.asset == "USDT")'

# If insufficient balance: Use smaller order size
# If Binance down: Wait for recovery
```

✅ **Resolution:** Order cancelled, retry placed, or waiting for Binance fill

---

## RB-009: Memory Usage Critical

**Symptom:** Memory >85%, swap usage increasing, API slowing down

**Detection:**
```bash
free -h | grep -E "Mem:|Swap:"

# Expected: Mem < 3 GB free (on 4GB machine)
# Critical: Mem < 200 MB free (will cause swap thrashing)
```

**Root Causes:**
1. Memory leak in WebSocket handler
2. Large log files not rotating
3. Database memory cache growing unbounded
4. Too many concurrent connections

### Step 1: Identify Memory Hog (3 min)

```bash
# Show process memory usage
ps aux --sort=-%mem | head -5

# Check if crypto-trading is the culprit
ps aux | grep crypto-trading | grep -v grep

# Example:
# User  PID  %CPU %MEM  VSIZE  RSS
# root  1234  5.2  78.9  2.4GB 3.1GB  <- THIS IS BAD

# If RSS > 1.5 GB: Process has memory leak
```

### Step 2: Clean Up Logs (2 min)

```bash
# Check log sizes
du -sh logs/*

# If > 500 MB: Old logs taking space
# Compress old logs
gzip logs/*.log.*

# Check if rotating
ls -lh logs/trades.jsonl*
# Should see: trades.jsonl.1, trades.jsonl.2, etc.

# If not rotating: Adjust logrotate config
sudo cat /etc/logrotate.d/crypto-trading
```

### Step 3: Restart Service (2 min)

```bash
# Graceful restart (stops trading loop, saves state)
sudo systemctl restart crypto-trading

# Wait for startup
sleep 10

# Check memory after restart
free -h
# Should drop significantly
```

### Step 4: Monitor for Recurrence (5 min)

```bash
# Watch memory over next 5 minutes
for i in {1..5}; do
  echo "=== Minute $i ==="
  free -h | grep Mem
  sleep 60
done

# If memory growing steadily: Memory leak detected
# Action: Save logs, report bug with heap dump
```

### Step 5: If Leak Detected

```bash
# Collect heap dump for debugging
curl -X POST http://localhost:8001/api/admin/dump-heap

# Monitor growth
watch -n 30 'ps aux | grep python | grep main.py | awk "{print \$6}"'

# If doubles in 30 minutes: Critical leak
# Action: Disable trading, investigate code
```

✅ **Resolution:** Memory freed, service restarted, or leak identified for investigation

---

## RB-010: Backup Sync Failed

**Symptom:** BACKUP positions differ from PRIMARY, or sync endpoint errors

**Detection:**
```bash
# Compare positions
PRIMARY_POS=$(curl -s http://192.168.30.137:8001/api/paper/positions | jq '.positions | length')
BACKUP_POS=$(curl -s http://192.168.3.25:8002/api/paper/positions | jq '.positions | length')

if [ "$PRIMARY_POS" != "$BACKUP_POS" ]; then
  echo "Mismatch! PRIMARY: $PRIMARY_POS, BACKUP: $BACKUP_POS"
fi

# Check sync endpoint
curl -s http://192.168.3.25:8002/api/autonomous/config/sync
# Expected: 200 OK with synced state
# Error: 404, 500, timeout
```

**Root Causes:**
1. SSH tunnel down (PRIMARY unreachable from BACKUP)
2. BACKUP code outdated (old version missing endpoint)
3. Sync timeout (network latency)
4. Database corruption on BACKUP

### Step 1: Check Network Connectivity (3 min)

```bash
# From BACKUP machine
ssh openhabian@192.168.3.25

# Try to reach PRIMARY
ping 192.168.30.137
# Expected: Replies
# Problem: No route, timeout

# Try SSH tunnel
ssh -vvv openhabian@192.168.30.137 "echo OK"
# Expected: OK
# Problem: Permission denied, timeout, no route
```

### Step 2: Verify BACKUP Code Version (2 min)

```bash
# SSH to BACKUP
ssh openhabian@192.168.3.25

# Check if sync endpoint exists
curl -s http://localhost:8002/api/autonomous/config/sync
# Expected: 200 or 405 (method not allowed - GET on POST endpoint)
# Error: 404 (endpoint missing = old code)

# Check git version
cd /home/openhabian/crypto-daytrading
git log -1 --oneline
# Should match PRIMARY version
```

### Step 3: Manually Sync Config (3 min)

```bash
# If sync endpoint missing, use alternative
ssh openhabian@192.168.3.25

# Manual sync: Download config from PRIMARY
PRIMARY_CONFIG=$(curl -s http://192.168.30.137:8001/api/config)

# Update BACKUP config
curl -X POST http://localhost:8002/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d "$PRIMARY_CONFIG"

# Verify
curl -s http://localhost:8002/api/config | jq '.entry_threshold'
# Should match PRIMARY
```

### Step 4: Full State Sync (5 min)

```bash
# If config synced but positions still differ:
# Sync positions and trades

# Dump PRIMARY state
PRIMARY_STATE=$(curl -s http://192.168.30.137:8001/api/paper/account)

# Update BACKUP to match
curl -X POST http://192.168.3.25:8002/api/paper/account/sync \
  -H "Content-Type: application/json" \
  -d "$PRIMARY_STATE"

# Verify match
curl -s http://192.168.30.137:8001/api/paper/account | jq '.cash'
curl -s http://192.168.3.25:8002/api/paper/account | jq '.cash'
# Should be same
```

### Step 5: Verify Sync Health (3 min)

```bash
# Check sync status on BACKUP
curl -s http://192.168.3.25:8002/api/health | jq '.sync_status'

# Expected:
# {
#   "last_sync": "2026-07-03T14:50:00Z",
#   "is_synced": true,
#   "config_matches": true,
#   "positions_match": true
# }
```

✅ **Resolution:** BACKUP synced with PRIMARY, positions match, ready for failover

---

## Emergency Procedures

### When Multiple Systems Fail

1. **PRIMARY + BACKUP both down:**
   - You've lost the system
   - No automated recovery possible
   - Manual restart: SSH to each machine, restart services
   - Restore state from daily backups
   - Report outage window in INCIDENTS.md

2. **Network between machines down:**
   - PRIMARY continues trading (doesn't need BACKUP)
   - BACKUP becomes standby only (can't trade without PRIMARY)
   - Fix network, sync BACKUP (RB-010)
   - Don't trigger failover unless PRIMARY actually down

3. **Database corrupted:**
   - Check database integrity: `sqlite3 data/trading.db "PRAGMA integrity_check;"`
   - Restore from backup: `cp data/trading.db.backup data/trading.db`
   - Restart service: `sudo systemctl restart crypto-trading`
   - Re-sync BACKUP

### Escalation Path

```
Issue discovered
  ↓
Follow appropriate runbook (RB-001 through RB-010)
  ↓
Issue resolved? → YES → Done, document in INCIDENTS.md
  ↓ NO
Escalate to on-call lead
  ↓
Review code, check logs for root cause
  ↓
Deploy fix or hotpatch
  ↓
Issue resolved? → YES → Document fix, commit code
  ↓ NO
Pause trading, investigate offline
```

---

## Quick Commands Reference

```bash
# Health checks
curl -s http://localhost:8001/api/health | jq '.'
curl -s http://localhost:8001/api/paper/status | jq '.'

# Reset circuit breaker
curl -X POST http://localhost:8001/api/admin/circuit-breaker/reset

# Pause trading
curl -X POST http://localhost:8001/api/trading/disable

# Resume trading
curl -X POST http://localhost:8001/api/trading/enable

# View logs
tail -f logs/system.log
tail -50 logs/trades.jsonl | jq '.'

# Restart service
sudo systemctl restart crypto-trading

# Check service status
sudo systemctl status crypto-trading

# View service logs
sudo journalctl -u crypto-trading -n 50
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-03  
**Next Review:** 2026-07-15 (Post-Phase 1)

