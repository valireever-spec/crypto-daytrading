# HA Acceptance Test - Quick Start

## What This Script Does

Tests the Active-Passive failover system by:
1. **Loop 1-3:** Each loop runs 3 phases
   - **Phase 1:** Kill PRIMARY → BACKUP takes over → Trade 60 min
   - **Phase 2:** Restart PRIMARY → PRIMARY takes over → Trade 60 min  
   - **Phase 3:** Kill PRIMARY again → BACKUP takes over → Trade 60 min

2. **Validates:**
   - Only 1 bot trades at a time (no dual-active corruption)
   - Database syncs correctly between machines
   - Failover happens automatically
   - No trade loss or duplication
   - System stable after 3 full cycles

## Quick Start

```bash
# 1. Ensure both bots are trading-disabled
curl -X POST http://127.0.0.1:8001/api/autonomous/stop
curl -X POST http://192.168.3.25:8002/api/autonomous/stop

# 2. Run the test (4.5 hour runtime)
cd /home/vali/projects/crypto-daytrading
./ha_acceptance_test.sh

# 3. Monitor progress in separate terminal
tail -f /tmp/ha_acceptance_test/test.log

# 4. Check results when complete
cat /tmp/ha_acceptance_test/test.log | tail -100
```

## Expected Output

**SUCCESS:**
```
========================================================================
TEST SUMMARY
========================================================================
Loops Passed: 3/3
Loops Failed: 0/3
Total Errors: 0
Total Warnings: 0
✓ HA ACCEPTANCE TEST PASSED
System is production-ready for Phase 2 live trading
```

**FAILURE:**
```
✗ LOOP 3 PHASE 2 FAILED - stopping loop
✗ HA ACCEPTANCE TEST FAILED
See logs for detailed failure analysis
```

## Files Generated

- **`/tmp/ha_acceptance_test/test.log`** - Detailed timeline (colorized)
- **`/tmp/ha_acceptance_test/ha_test_report.json`** - Structured results
- **`/tmp/crypto-trading-primary.log`** - PRIMARY startup logs
- **`/tmp/ha_failover_test_results.log`** - Previous test results (for comparison)

## What Gets Checked

### ✅ Passes When

- PRIMARY process kills cleanly
- BACKUP detects PRIMARY down
- BACKUP trading enables successfully
- Database syncs complete (trade counts match)
- Both bots trade for 60 minutes without crashes
- PRIMARY restarts successfully
- PRIMARY takes back over from BACKUP
- BACKUP failover repeats without issues
- **All 9 phases complete with 0 critical errors**

### ❌ Fails When

- PRIMARY can't be killed or restarted
- BACKUP can't enable trading
- Database counts don't match after sync
- Both bots are trading simultaneously
- Any phase times out
- SSH to BACKUP fails
- Health checks fail

## Common Issues & Fixes

### Issue: "PRIMARY is not reachable"
```bash
# PRIMARY might have crashed or port conflict
curl http://127.0.0.1:8001/api/health
netstat -tulpn | grep 8001
pkill -f "uvicorn backend.api.main"
cd /home/vali/projects/crypto-daytrading
source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 &
```

### Issue: "Cannot SSH to BACKUP"
```bash
# Check SSH key and connectivity
ssh -v openhabian@192.168.3.25 "echo OK"
# If fails, check:
# - Network connectivity: ping 192.168.3.25
# - SSH key: ls -la ~/.ssh/
# - BACKUP availability: ask admin
```

### Issue: "Database sync timeout"
```bash
# Check if databases exist and have tables
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*) FROM trades"
ssh openhabian@192.168.3.25 "sqlite3 /home/claude/crypto-daytrading/data/trading.db 'SELECT COUNT(*) FROM trades'"

# If counts don't match, sync endpoint may be broken
curl http://192.168.3.25:8002/api/ha/sync-from-primary
```

### Issue: "Could not enable trading"
```bash
# Check if circuit breaker is blocking
curl http://192.168.3.25:8002/api/health | jq '.circuit_breaker'

# Check if trading is already enabled
curl http://192.168.3.25:8002/api/autonomous/config | jq '.enabled'

# If circuit breaker is OPEN, wait for auto-recovery or manually reset
# (requires API endpoint or direct code fix)
```

## Monitoring While Running

**In another terminal:**
```bash
# Follow logs in real-time
tail -f /tmp/ha_acceptance_test/test.log | grep -E "(✓|✗|⚠)"

# Or watch for specific events
watch -n 5 'curl -s http://127.0.0.1:8001/api/ha/status | jq ".role"'
watch -n 5 'curl -s http://192.168.3.25:8002/api/ha/status | jq ".role"'

# Check database sync progress
watch -n 10 'echo "PRIMARY:"; sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*) FROM trades" 2>/dev/null; echo "BACKUP:"; ssh openhabian@192.168.3.25 "sqlite3 /home/claude/crypto-daytrading/data/trading.db \"SELECT COUNT(*) FROM trades\" 2>/dev/null"'
```

## Safety Checks

✅ Script **will:**
- Only kill/restart PRIMARY
- Never modify BACKUP code or config
- Log all actions with timestamps
- Stop immediately on critical errors
- Preserve all test data for analysis

❌ Script **will NOT:**
- Delete any data
- Force-push code to BACKUP
- Skip important validations
- Continue if both bots are active

## Success Indicators

**Loop 1 Success:**
```
✓ PHASE 1 COMPLETE: Backup traded for 15 minutes
✓ PHASE 2 COMPLETE: Primary traded for 15 minutes
✓ PHASE 3 COMPLETE: Backup traded again for 15 minutes
✓✓✓ LOOP 1/3 SUCCESSFUL
```

**All Loops Complete:**
```
✓ LOOP 1/3 SUCCESSFUL
✓ LOOP 2/3 SUCCESSFUL
✓ LOOP 3/3 SUCCESSFUL
✓ HA ACCEPTANCE TEST PASSED
```

## Next Steps After Success

✅ **Ready for Phase 2:** Live trading with €1,000 on Binance spot  
✅ **Deploy to Production:** Both machines validated as redundant  
✅ **Set up Monitoring:** Alert on failover events in Slack  
✅ **Document Runbooks:** How to manually failover if needed  

## Next Steps After Failure

❌ **Investigate Logs:** Review `/tmp/ha_acceptance_test/test.log` for exact error  
❌ **Fix Issue:** Implement suggested remediation from logs  
❌ **Re-run Test:** Start fresh after each fix  
❌ **Track Failures:** Document in issue tracker for Phase 3+  

---

## Estimated Runtime

- **Per Loop:** ~55 minutes (3 phases × 15 min trading + 5 min waits)
- **All 3 Loops:** ~2.75 hours total
- **Total with buffer:** Plan for 3 hours

**Breakdown:**
- Loop 1: 14:00-14:55 (~55 min)
- Loop 2: 15:00-15:55 (~55 min)
- Loop 3: 16:00-16:55 (~55 min)
- Total: ~2 hours 45 minutes

---

## Configuration

To modify test parameters, edit `ha_acceptance_test.sh`:

```bash
# Trading duration per phase (currently: 15 minutes)
readonly TRADING_DURATION_MINUTES=15

# Wait between phases (currently: 5 minutes)
readonly WAIT_DURATION_SECONDS=300

# Timeouts
readonly ROLE_CHANGE_TIMEOUT=30
readonly SYNC_TIMEOUT=60

# Retry logic
readonly RETRY_ATTEMPTS=3
readonly RETRY_DELAY_SECONDS=2
```

---

## Support

For detailed information on gaps filled and assumptions made, see:
**`HA_TEST_ASSUMPTIONS.md`**

For the full test approach with 3-loop protocol, see:
**`CLAUDE.md` (Critical Systems Framework section)**
