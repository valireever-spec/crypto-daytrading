# Deployment Checklist: Bug Fixes (2026-07-04)

**Fixes Being Deployed:**
1. ✅ Bug #1: Minimum hold time (exit.py)
2. ✅ Bug #3: Position limit (entry.py)
3. ✅ Bug #4: Data quality hard gate (core.py)
4. ✅ Real signal generation (entry.py) — BONUS

**Deployment Target:** BOTH PRIMARY (192.168.30.137:8001) and BACKUP (192.168.3.25:8002)

---

## Files Changed

```
backend/trading/autonomous_trader/
├── exit.py          (Added MIN_HOLD_TIME_SECONDS = 10, hold time check)
├── entry.py         (Added position limit + real signal generation)
└── core.py          (Added hard WebSocket stale gate)
```

---

## Deployment Steps

### PRIMARY Machine (192.168.30.137:8001)

**Step 1: Code Deployment**
```bash
# Deploy to PRIMARY
scp -P 22 \
  backend/trading/autonomous_trader/exit.py \
  backend/trading/autonomous_trader/entry.py \
  backend/trading/autonomous_trader/core.py \
  vali@192.168.30.137:/home/vali/projects/crypto-daytrading/backend/trading/autonomous_trader/
```

**Step 2: Service Restart**
```bash
ssh vali@192.168.30.137 "systemctl restart crypto-trading.service"
sleep 5
```

**Step 3: Verification**
```bash
ssh vali@192.168.30.137 "systemctl status crypto-trading.service"
ssh vali@192.168.30.137 "tail -50 /home/vali/projects/crypto-daytrading/logs/system.log | grep -E '(HARD GATE|MIN_HOLD|Position limit|Signal|Data Quality)'"
```

### BACKUP Machine (192.168.3.25:8002)

**Step 1: Code Deployment**
```bash
# Deploy to BACKUP via reverse SSH tunnel
ssh -R 2347:192.168.3.25:22 openhabian@192.168.30.137 << 'EOF'
scp -P 2347 \
  backend/trading/autonomous_trader/exit.py \
  backend/trading/autonomous_trader/entry.py \
  backend/trading/autonomous_trader/core.py \
  claude@localhost:/home/claude/crypto-daytrading/backend/trading/autonomous_trader/
EOF
```

**Step 2: Service Restart**
```bash
ssh -R 2347:192.168.3.25:22 openhabian@192.168.30.137 << 'EOF'
ssh -p 2347 claude@localhost "sudo systemctl restart crypto-trading.service"
sleep 5
EOF
```

**Step 3: Verification**
```bash
ssh -R 2347:192.168.3.25:22 openhabian@192.168.30.137 << 'EOF'
ssh -p 2347 claude@localhost "sudo systemctl status crypto-trading.service"
ssh -p 2347 claude@localhost "tail -50 /home/claude/crypto-daytrading/logs/system.log | grep -E '(HARD GATE|MIN_HOLD|Position limit|Signal|Data Quality)'"
EOF
```

---

## Verification Checklist (PRIMARY)

After restart on PRIMARY:

- [ ] Service is running (`systemctl status crypto-trading.service`)
- [ ] Logs show "Autonomous trader starting with Phase 1 hardening active..."
- [ ] Logs show "WebSocket resilience layer initialized"
- [ ] Logs show "Data Quality Score" messages every 10 seconds
- [ ] At least one HARD GATE message present (if WebSocket ever became stale during startup)
- [ ] No error messages about missing imports
- [ ] No "Exception" messages in logs

### Expected Log Messages (PRIMARY)

```
✅ Warmup complete: received prices for ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
Data Quality Score: 85% (example)
✅ Signal generated for BTCUSDT: [real signal reason]
✅ BUY BTCUSDT: 0.1234 @ $45,000.00
[wait 10 seconds...]
[position still held, no exit yet due to minimum hold time]
```

### If Minimum Hold Time Works

You should see positions held for AT LEAST 10 seconds before first exit check fires. Compare with old behavior where positions exited after 5 seconds.

---

## Verification Checklist (BACKUP)

Same as PRIMARY, plus:

- [ ] BACKUP service is running independently
- [ ] BACKUP logs show same hardening messages
- [ ] BACKUP processes its own trades (not duplicating PRIMARY)
- [ ] BACKUP signal generation uses real data (not random)

---

## Testing After Deployment

### Test 1: Manual Trade Entry (Both Machines)

**On PRIMARY:**
```bash
curl -X POST http://192.168.30.137:8001/api/execute_trade \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001}'
```

Expected: Order filled, position created

**Check Hold Time:**
```bash
tail -f /home/vali/projects/crypto-daytrading/logs/trades.jsonl | jq '.[] | select(.symbol=="BTCUSDT") | {timestamp, side, entry_time, held_seconds}'
```

Expected: After entry, position should be held >10 seconds before any exit signal can fire.

### Test 2: Signal Generation Quality

Run for 1 hour, check signal logs:
```bash
grep "Signal generated" /home/vali/projects/crypto-daytrading/logs/system.log | wc -l
```

Expected: >6 signals/hour (at least 1 every 10 minutes)

Check signal reasoning:
```bash
grep "Signal generated" /home/vali/projects/crypto-daytrading/logs/system.log | tail -10
```

Expected: See messages like:
- "Mean reversion: price -0.5% below MA5, momentum +0.2%"
- "Weak momentum: +0.3%"
- "High volatility, skipping"

### Test 3: Hard Data Quality Gate

If WebSocket becomes stale:
```bash
grep "HARD GATE" /home/vali/projects/crypto-daytrading/logs/system.log
```

Expected: Message like: "🔴 HARD GATE: WebSocket stale 35.2s > 30s threshold. HALTING ALL TRADING until recovery."

### Test 4: Position Limit Enforcement

Try to open 2 large positions for same symbol:
```bash
curl -X POST http://192.168.30.137:8001/api/execute_trade \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "side": "BUY", "quantity": 1.0}'

# Wait, then try again
curl -X POST http://192.168.30.137:8001/api/execute_trade \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "side": "BUY", "quantity": 1.0}'
```

Expected: Second trade rejected with message: "Position size $XXX would exceed limit $XXX"

---

## Rollback Plan

If any fix causes issues:

1. **Revert to previous version:**
```bash
cd /home/vali/projects/crypto-daytrading
git checkout backend/trading/autonomous_trader/exit.py \
                  backend/trading/autonomous_trader/entry.py \
                  backend/trading/autonomous_trader/core.py
```

2. **Redeploy:**
```bash
scp -r backend/ vali@192.168.30.137:/home/vali/projects/crypto-daytrading/
ssh vali@192.168.30.137 "systemctl restart crypto-trading.service"
```

3. **Document issue:**
- What failed
- When it failed
- Which fix caused it

---

## Success Criteria

**All fixes working correctly if:**

1. ✅ Minimum hold time: Positions held 10+ seconds before first exit check
2. ✅ Position limit: Cannot open 2× 6% positions on same symbol
3. ✅ Data quality gate: Trading stops if WebSocket >30s old
4. ✅ Real signals: Signal reasons mention "Mean reversion", "momentum", not "random"
5. ✅ Both machines: PRIMARY and BACKUP running independently with fixes

---

## Timeline

- **Deployment:** 2026-07-04 (NOW)
- **First observation:** Within 5 minutes (logs will show fixes active)
- **Signal testing:** Within 1 hour (check signal quality)
- **Full trading test:** 48 hours (2026-07-05 to 2026-07-06)

---

## Next: 48-Hour Testing Phase

After successful deployment:
1. Monitor win rate hourly (target: >20% minimum)
2. Monitor average hold time (target: 300-600s)
3. Check no stale data trading incidents
4. Create TRADING_TEST_REPORT.md with results

Only proceed to live trading if all metrics pass.

