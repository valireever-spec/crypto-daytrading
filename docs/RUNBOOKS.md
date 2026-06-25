# Operational Runbooks — Crypto Daytrading Phase 1

**Purpose**: Step-by-step response guides for circuit breaker triggers  
**Updated**: 2026-06-25  
**Severity Levels**: 🔴 CRITICAL (immediate) | 🟠 HIGH (< 5 min) | 🟡 MEDIUM (< 30 min)

---

## Quick Alert Reference

| Alert | Severity | RB | Response |
|-------|----------|-----|----------|
| Data Quality <30% | 🔴 | [#1](#rb-1-data-quality-low) | Check WebSocket stream |
| WebSocket Disconnected >2 min | 🔴 | [#2](#rb-2-websocket-disconnect) | Wait for auto-reconnect or restart |
| Position Reconciliation Failed | 🔴 | [#3](#rb-3-position-reconciliation) | Check DB integrity |
| Daily Loss >5% | 🟠 | [#4](#rb-4-daily-loss) | Review & adjust settings |
| API Latency >5s | 🟡 | [#5](#rb-5-api-latency) | Check CPU/memory |

---

## RB-1: Data Quality Drops Below 30%

**Trigger**: Circuit breaker trips, trading halted  
**Severity**: 🔴 CRITICAL  
**Response Time**: Immediate

### Check Status
```bash
curl http://localhost:8001/api/health/detailed | jq .data_quality
# Should show: {score: 100, sanity: 100, coverage: 100, ...}
```

### Root Causes
1. **WebSocket disconnected** → Price stream dead
2. **Missing symbol prices** → One of BTCUSDT/ETHUSDT/BNBUSDT not updating
3. **Binance API down** → Exchange unavailable
4. **Network issues** → High latency, packet loss

### Fix Steps

**If WebSocket disconnected:**
```bash
tail -50 logs/system.log | grep -i "websocket\|disconnect"
# System auto-reconnects in <30 seconds
# If still down after 2 min → Restart API
```

**If Binance is down:**
- Check status: https://www.binance.com/en/support/announcement
- Wait for recovery (do NOT trade manually, system pause is correct)

**If network issue:**
```bash
ping stream.binance.com  # Should have <100ms latency
nslookup stream.binance.com  # Should resolve to IP
```

### Recovery
- Circuit breaker auto-recovers when quality ≥60%
- Trading resumes automatically
- Log will show: "Circuit Breaker Auto-recovery..."

---

## RB-2: WebSocket Disconnected >2 Minutes

**Trigger**: No price updates for >120 seconds  
**Severity**: 🔴 CRITICAL  
**Response Time**: <2 minutes

### Check Status
```bash
curl http://localhost:8001/api/paper/positions | head -1
# If no prices updating → WebSocket dead
```

### Fix - Option A: Wait (Recommended)
- System auto-reconnects with exponential backoff
- Usually recovers in <30 seconds
- Max wait: 120 seconds

### Fix - Option B: Manual Restart
```bash
lsof -i :8001 | grep python | awk '{print $2}' | xargs kill -9
sleep 2
source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 &
# Wait 30-60 seconds for prices to appear in logs
```

### Fix - Option C: Failover to Backup
```bash
ssh -i ~/.ssh/openhab_key openhabian@192.168.3.25
curl http://localhost:8002/api/health
# If backup is OK, trading continues there
```

---

## RB-3: Position Reconciliation Failed

**Trigger**: Paper engine positions ≠ autonomous trader positions  
**Severity**: 🔴 CRITICAL  
**Response Time**: Immediate

### Check Positions
```bash
echo "=== Paper Engine ===" && \
curl http://localhost:8001/api/paper/positions | jq '.positions | length'

echo "=== Autonomous Trader ===" && \
curl http://localhost:8001/api/autonomous/status | jq .active_positions
# These should match
```

### Fix - Duplicate Positions
```bash
sqlite3 data/trading.db "SELECT symbol, COUNT(*) FROM positions WHERE status='open' GROUP BY symbol HAVING COUNT(*) > 1;"
# If any symbol appears twice:
curl -X POST http://localhost:8001/api/paper/close-position \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","quantity":0.5}'
```

### Fix - Orphaned Positions
```bash
sqlite3 data/trading.db "UPDATE positions SET status='closed' WHERE symbol='ETHUSDT';"
# Then restart API
pkill -f uvicorn; sleep 2; python -m uvicorn backend.api.main:app &
```

### Recovery
- Wait 120 seconds for auto-recovery
- Log will show: "Positions reconciled successfully"

---

## RB-4: Daily Loss Exceeds 5%

**Trigger**: Daily P&L < -5% of equity  
**Severity**: 🟠 HIGH  
**Response Time**: <5 minutes

### Check Current Loss
```bash
curl http://localhost:8001/api/paper/account | jq '{daily_pnl, total_equity, daily_pnl_pct}'
# Should show: daily_pnl_pct < -5.0
```

### Analyze Losing Position
```bash
curl http://localhost:8001/api/paper/positions | jq '.positions[] | {symbol, unrealized_pnl}'
# Identify which symbol is losing money
```

### Option A: Stop Trading (Conservative)
```bash
curl -X POST http://localhost:8001/api/autonomous/stop
# Closes autonomous trader
# Manual: Close all positions
curl -X POST http://localhost:8001/api/paper/close-all
# Document in RETROSPECTIVES.md what went wrong
# Resume next day with fixes
```

### Option B: Continue with Adjustments
```bash
# Tighten risk settings
curl -X POST http://localhost:8001/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "entry_threshold": 75,
    "exit_stop_loss": 0.01,
    "max_positions": 5
  }'

# Reset circuit breaker
curl -X POST http://localhost:8001/api/circuit-breaker/reset \
  -H "Content-Type: application/json" \
  -d '{"reason":"Adjusted settings after loss review"}'
```

### Document & Learn
- Update RETROSPECTIVES.md with: what signal misfired, why, prevention
- If repeated → rethink entire strategy

---

## RB-5: API Latency Exceeds 5 Seconds

**Trigger**: Response time >5000ms  
**Severity**: 🟡 MEDIUM  
**Response Time**: <10 minutes

### Check Latency
```bash
time curl http://localhost:8001/api/health
# Should be <100ms
```

### If CPU High (>80%)
```bash
top -bn1 | head -20  # See top processes
# Kill background processes or restart API
pkill -f uvicorn; python -m uvicorn backend.api.main:app &
```

### If Memory High (>90%)
```bash
free -h  # Check RAM usage
# Restart API (usually fixes it)
pkill -f uvicorn; python -m uvicorn backend.api.main:app &
```

### If Disk I/O High
```bash
du -sh logs/  # Check log size
# If >500MB, archive old logs
tar czf logs-archive.tar.gz logs/trades.jsonl
# Keep only recent trades
head -1000 logs/trades.jsonl > logs/trades.tmp && mv logs/trades.tmp logs/trades.jsonl
```

---

## Emergency: Complete System Failure

### Step 1: Pause Trading
```bash
curl -X POST http://localhost:8001/api/autonomous/stop
# Stop autonomous trader immediately
```

### Step 2: Failover to Backup
```bash
ssh -i ~/.ssh/openhab_key openhabian@192.168.3.25
cd /home/claude/crypto-daytrading
curl http://localhost:8002/api/health
# Verify backup is healthy
```

### Step 3: Close All Positions (if needed)
```bash
curl -X POST http://localhost:8001/api/paper/close-all
# Or manually in Binance Testnet UI
```

### Step 4: Data Recovery
- All positions backed up in: `data/trading.db`
- All trades logged in: `logs/trades.jsonl` (append-only)
- Config saved in: `logs/trading_config.json`

---

## Daily Health Check (Run Every Morning)

```bash
#!/bin/bash

# Check WebSocket connection freshness
HEALTH=$(curl -s http://localhost:8001/api/health/detailed)
WS_CONNECTED=$(echo "$HEALTH" | jq -r '.websocket.connected')
WS_LAST_UPDATE=$(echo "$HEALTH" | jq -r '.websocket.last_price_update')

echo "=== System Health ===" && \
curl http://localhost:8001/api/health && \
echo "" && \
echo "=== WebSocket Status ===" && \
echo "$HEALTH" | jq '.websocket' && \
echo "" && \
echo "=== Data Quality ===" && \
echo "$HEALTH" | jq .data_quality && \
echo "" && \
echo "=== Positions ===" && \
curl http://localhost:8001/api/paper/positions | jq '.positions | length' && \
echo "" && \
echo "=== P&L ===" && \
curl http://localhost:8001/api/paper/account | jq '{daily_pnl, total_equity}' && \
echo "" && \
echo "=== WebSocket Connection Check ===" && \
if [ "$WS_CONNECTED" != "true" ]; then
  echo "🔴 WARNING: WebSocket NOT CONNECTED"
  echo "Last update: $WS_LAST_UPDATE"
  echo "ACTION: Restart API immediately"
  echo "Command: pkill -f uvicorn; sleep 2; python -m uvicorn backend.api.main:app &"
else
  echo "✅ WebSocket connected"
  echo "Last update: $WS_LAST_UPDATE"
fi
```

---

## Common Commands

```bash
# Health check
curl http://localhost:8001/api/health

# Full system status
curl http://localhost:8001/api/health/detailed

# Check positions
curl http://localhost:8001/api/paper/positions

# Check account P&L
curl http://localhost:8001/api/paper/account

# View autonomous trader status
curl http://localhost:8001/api/autonomous/status

# View recent trades
curl http://localhost:8001/api/autonomous/trades

# Tail logs
tail -f logs/system.log

# Search logs for errors
grep -i ERROR logs/system.log

# Check circuit breaker
curl http://localhost:8001/api/health | jq .circuit_breaker
```

---

## When to Escalate

**Don't handle yourself:**
- Database corruption (PRAGMA integrity_check returns errors)
- Multiple simultaneous failures
- System running out of disk space
- Need to manually edit database records
- Network infrastructure issues (ISP down)

**In those cases:**
1. Document exactly what happened in RETROSPECTIVES.md
2. Stop trading to prevent further loss
3. Contact backup for takeover
4. Review post-incident

---

**Last Updated**: 2026-06-25  
**Next Review**: 2026-07-01  
**Version**: 1.0
