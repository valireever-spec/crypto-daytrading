# Failover Test Plan — Pre-Live Trading Validation

**Purpose:** Verify HA system works before deploying real money  
**Duration:** 4-6 hours (can run tests in parallel)  
**Risk Level:** SAFE (paper trading only)  
**Expected Outcome:** Confidence in failover behavior or bugs to fix

---

## TEST SUITE: Phase 1 - Basic Failover (2-3 hours)

### TEST #1: PRIMARY Crash Detection (5 iterations)

**Goal:** Verify BACKUP detects PRIMARY crash and promotes

**Setup:**
```bash
# Terminal 1: Monitor BACKUP
ssh openhabian@192.168.3.25
tail -f /home/claude/crypto-daytrading/logs/api.log | grep -i "PRIMARY\|failover\|promote"

# Terminal 2: Monitor PRIMARY
tail -f /home/vali/projects/crypto-daytrading/logs/api.log | grep -i "heartbeat\|sync"

# Terminal 3: Execute test
```

**Procedure:**
1. Let system stabilize (1 min)
2. Record timestamp, current cash, trade count
3. Kill PRIMARY: `ps aux | grep "8001.*uvicorn" | grep -v grep | awk '{print $2}' | xargs kill -9`
4. Watch BACKUP logs for:
   - ⏳ Heartbeat misses (should be 3 in a row)
   - ⏳ Failover promotion message
5. Measure failover time (when trading resumes)
6. Verify:
   - ❓ Did BACKUP promote? YES/NO
   - ❓ How long to promote? (should be <30s)
   - ❓ Did trading resume? YES/NO
   - ❓ Any error messages? YES/NO
7. Restart PRIMARY
8. Repeat 4 more times

**Pass Criteria:**
- ✅ BACKUP promotes within 30 seconds
- ✅ No error messages
- ✅ Trading resumes on BACKUP
- ✅ Cash balance intact

**Failure Mode:** If BACKUP doesn't promote, check:
- Is heartbeat actually being sent? Check PRIMARY logs
- Is BACKUP receiving heartbeats? Check BACKUP logs
- Is failover monitor running? Check BACKUP process

---

### TEST #2: BACKUP Crash Resilience (5 iterations)

**Goal:** Verify PRIMARY continues trading if BACKUP crashes

**Procedure:**
1. Let system stabilize (1 min)
2. Record PRIMARY status
3. Kill BACKUP: `ssh openhabian@192.168.3.25 "pkill -9 -f 8002"`
4. Watch PRIMARY logs
5. Verify PRIMARY continues:
   - ❓ Trading continues? YES/NO
   - ❓ Circuit breaker halts? YES/NO
   - ❓ Sync errors logged? YES/NO
6. Let PRIMARY trade for 1 minute (execute 5+ trades)
7. Restart BACKUP
8. Verify BACKUP re-syncs with PRIMARY
9. Repeat 4 more times

**Pass Criteria:**
- ✅ PRIMARY trading continues
- ✅ Circuit breaker doesn't trip (or recovers quickly)
- ✅ Trades execute normally
- ✅ BACKUP syncs correctly after recovery

**Failure Mode:** If circuit breaker halts:
- Check sync timeout threshold (should be 300s)
- Check if BACKUP health checks are failing
- Verify sync error handling

---

### TEST #3: Network Partition Simulation (3 iterations)

**Goal:** Verify system behaves correctly if network breaks

**Procedure:**
1. Let system stabilize (1 min)
2. Break network: `sudo iptables -A INPUT -s 192.168.3.25 -j DROP && sudo iptables -A OUTPUT -d 192.168.3.25 -j DROP`
3. Watch both machines for 30 seconds
4. Verify behavior:
   - ❓ PRIMARY notices BACKUP unreachable? YES/NO
   - ❓ BACKUP notices PRIMARY unreachable? YES/NO
   - ❓ Do both try to be PRIMARY (split-brain)? YES/NO
   - ❓ Is split-brain prevented? YES/NO
5. Restore network: `sudo iptables -D INPUT -s 192.168.3.25 -j DROP && sudo iptables -D OUTPUT -d 192.168.3.25 -j DROP`
6. Verify convergence:
   - ❓ Do machines re-sync? YES/NO
   - ❓ Is data consistent? YES/NO
   - ❓ How long to recover? (should be <1 min)
7. Repeat 2 more times

**Pass Criteria:**
- ✅ Split-brain prevented (only one PRIMARY)
- ✅ System recovers when network restored
- ✅ No data corruption detected

**Failure Mode:** If split-brain occurs:
- Both machines think they're PRIMARY
- Trades duplicated or conflicting
- This is CRITICAL - don't go live until fixed

---

## TEST SUITE: Phase 2 - Data Integrity (2-3 hours)

### TEST #4: Sync Consistency During Trading (10 iterations)

**Goal:** Verify BACKUP state matches PRIMARY state after sync

**Procedure:**
```bash
# Script to verify consistency
curl -s http://127.0.0.1:8001/api/health | jq '.account | {cash, positions, trades}' > /tmp/primary.json
curl -s http://192.168.3.25:8002/api/health | jq '.account | {cash, positions, trades}' > /tmp/backup.json
diff /tmp/primary.json /tmp/backup.json
```

1. Let system trade normally (3-5 minutes)
2. Check consistency (compare PRIMARY vs BACKUP)
3. Verify:
   - ❓ Cash amount matches? YES/NO
   - ❓ Position count matches? YES/NO
   - ❓ How old is BACKUP data? (should be <5s)
4. Record any divergence
5. Repeat 9 more times

**Pass Criteria:**
- ✅ Cash matches within €0.01
- ✅ Position count matches exactly
- ✅ No divergence detected
- ✅ Sync age <5 seconds

**Failure Mode:** If divergence detected:
- PRIMARY thinks: cash=$900, positions=2
- BACKUP thinks: cash=$850, positions=3
- This indicates sync failure - CRITICAL

---

### TEST #5: Reverse Sync (BACKUP promotion)

**Goal:** Verify trades executed by BACKUP are preserved

**Procedure:**
1. Let PRIMARY trade normally (5 min, record trade count)
2. Kill PRIMARY (force crash)
3. BACKUP promotes, trades for 2 minutes (record new trade count)
4. Restart PRIMARY
5. Verify:
   - ❓ New trades from BACKUP preserved? YES/NO
   - ❓ PRIMARY state updated? YES/NO
   - ❓ No trades overwritten? YES/NO
6. Check cash and position changes

**Pass Criteria:**
- ✅ BACKUP trades preserved (not overwritten)
- ✅ PRIMARY receives reverse sync
- ✅ Final state = PRIMARY initial + BACKUP new trades

**Failure Mode:** If trades lost:
- PRIMARY recovers with OLD state
- BACKUP new trades overwritten
- This is DATA LOSS - CRITICAL

---

## TEST SUITE: Phase 3 - Edge Cases (1-2 hours)

### TEST #6: In-Flight Order Handling

**Goal:** Verify orders at Binance are tracked if PRIMARY crashes

**Setup:**
1. Monitor Binance account for actual orders
2. Trigger trade execution
3. Kill PRIMARY immediately after order sent

**Procedure:**
1. Execute trade (creates order at Binance)
2. Kill PRIMARY mid-trade
3. BACKUP detects crash, recovers
4. Verify:
   - ❓ Is order present at Binance? YES/NO
   - ❓ Does BACKUP know about order? YES/NO
   - ❓ Is position tracked correctly? YES/NO
5. Let order execute naturally
6. Verify final state matches Binance

**Pass Criteria:**
- ✅ No orphaned orders at Binance
- ✅ No missing positions after recovery
- ✅ Cash balance matches Binance

**Failure Mode:** If orders orphaned:
- Order executes at Binance
- BACKUP has no record
- Position mismatch with Binance

---

### TEST #7: Circuit Breaker Auto-Recovery

**Goal:** Verify trading resumes after BACKUP recovers

**Procedure:**
1. Kill BACKUP (trading should halt after 300s)
2. Verify: Trading halted (CB triggers)
3. Restart BACKUP
4. Verify:
   - ❓ Trading resumes automatically? YES/NO
   - ❓ How long to resume? (should be <30s)
   - ❓ Manual reset needed? YES/NO

**Pass Criteria:**
- ✅ Trading resumes automatically
- ✅ No manual intervention needed
- ✅ CB recovers within 30 seconds

**Failure Mode:** If trading stays halted:
- BACKUP recovered but CB still frozen
- Manual restart needed
- Document procedure as workaround

---

## TESTING CHECKLIST

### Before Starting
- [ ] Both machines running and synced
- [ ] Paper trading active (both can trade)
- [ ] Cash balance: €900+ (room for test losses)
- [ ] No pending orders
- [ ] No active positions

### During Tests
- [ ] Monitor both machine logs simultaneously
- [ ] Record timestamps for each test
- [ ] Note any errors or warnings
- [ ] Verify cash/position after each test
- [ ] Check for data divergence

### After Each Test
- [ ] Verify final state (cash, positions)
- [ ] Restart both machines
- [ ] Wait 2 minutes for stability
- [ ] Proceed to next test

---

## EXPECTED OUTCOMES

### ✅ Healthy HA System (All Tests Pass)
- Failover time: 8-15 seconds
- No data loss: €0 discrepancy
- No trade duplication: 0 duplicates
- Auto-recovery: All automatic
- Confidence: ✅ Ready for €100 live

### ⚠️ Minor Issues (Some Tests Fail)
- Failover time: 20-30 seconds (acceptable)
- Manual recovery needed (document procedure)
- Confidence: ⚠️ Fix issues, re-test before €100 live

### ❌ Critical Issues (Multiple Failures)
- Failover doesn't work
- Data loss detected
- Split-brain occurs
- Confidence: ❌ DO NOT go live, fix bugs first

---

## AFTER TESTING

**If All Tests Pass:**
1. Document results in `FAILOVER_TEST_RESULTS.md`
2. Update CI/CD to run tests weekly
3. Create runbooks for manual recovery (if needed)
4. Set up alerting for failover events
5. Approve for €100 live trading

**If Tests Fail:**
1. Document failure mode
2. Implement fix
3. Re-run failed test
4. Verify fix doesn't break others
5. Repeat until all pass

---

## Expected Test Duration

| Phase | Tests | Duration | Notes |
|-------|-------|----------|-------|
| Phase 1 | 3 tests × 5 iterations | 1.5-2h | Basic failover |
| Phase 2 | 3 tests × 10 iterations | 1.5-2h | Data integrity |
| Phase 3 | 2 tests × 3 iterations | 0.5-1h | Edge cases |
| **Total** | **13 test iterations** | **4-6 hours** | Ready for live |

---

## Success Criteria for Live Trading Approval

After all tests pass:
- [ ] No data loss detected (€0.00 variance)
- [ ] No trade duplication (0 duplicates)
- [ ] Failover time <30 seconds
- [ ] No split-brain scenarios
- [ ] Circuit breaker auto-recovery
- [ ] Runbooks documented
- [ ] Team trained on procedures
- [ ] Alerting verified

**Then: Approved for €100 live trading (low-risk validation)**

After 2 weeks of €100 live without issues:
- [ ] Scale to €1,000
- [ ] Continue monitoring
- [ ] Adjust strategy as needed
- [ ] Scale further if performance >50% win rate
