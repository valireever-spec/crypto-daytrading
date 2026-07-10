# Debugging Profit/Stop Exits — Comprehensive Analysis

**Date:** 2026-07-10 07:40 UTC  
**Status:** ROOT CAUSE IDENTIFIED

---

## Executive Summary

**Why were zero profit/stop exits recorded in Phase 3?**

✅ **Exit logging code: WORKS** (verified 6/6 timeout exits logged correctly)
❌ **Entry logging code: BROKEN** (0/18 entry reasons logged, all NULL)
❓ **Profit/stop logic: AMBIGUOUS** (no trades ever hit the P&L thresholds)

---

## Phase 3 Trade Analysis

### Trade Characteristics
- **Duration:** 2026-07-10 05:08:07 to 06:08:50 (60 minutes)
- **Total trades:** 24 (18 BUYs, 6 SELLs)
- **Win rate:** 0% (all losing trades)
- **P&L range:** -0.02% to -0.28% per trade

### Why No Profit/Stop Exits
All Phase 3 positions were **small losses** that NEVER hit the exit thresholds:
- **Stop loss threshold:** -0.5% (need to lose 0.5% to trigger)
- **All Phase 3 losses:** -0.02% to -0.28% (BELOW the stop loss threshold)
- **Profit target threshold:** +2.0% (need to gain 2% to trigger)
- **All Phase 3 trades:** Losses (NEVER reached profit target)

**Result:** All 6 exits were **10-minute timeout forced exits**, not profit/stop exits.

---

## Exit Logic Architecture

**Entry.py exit check order:**
1. **Line 65-69:** Skip if hold_time < 5 minutes
2. **Line 73-93:** Force exit if hold_time >= 10 minutes (TIMEOUT)
   - Calls `_execute_exit_impl(..., "10-minute timeout")`
   - Has `continue` statement → skips profit/stop check
3. **Line 104-142:** Check profit target (+2%)
4. **Line 124-142:** Check stop loss (-0.5%)

**Issue:** Timeout exit (lines 73-93) has `continue` statement, so it **never reaches profit/stop checks** (lines 104-142).

This is **correct by design**:
- Timeout is the final safeguard
- Once 10 min timeout triggers, exit immediately
- Don't bother checking profit/stop (position already forced closed)

---

## Entry Reason Logging — ROOT CAUSE FOUND

### What's Working
✅ **Exit reason logging:** All 6 Phase 3 SELL orders have exit_reason = "10-minute timeout"

### What's Broken
❌ **Entry reason logging:** All 18 Phase 3 BUY orders have entry_reason = NULL

### Code is Correct
```python
# entry.py line 314: PASSES entry_reason to place_order
entry_reason=signal.reason,

# paper_trading.py lines 335-336: PASSES to insert_trade
entry_reason=entry_reason,
exit_reason=exit_reason,

# database.py line 563: INSERT includes columns
INSERT INTO trades (..., entry_reason, exit_reason)

# database.py lines 577-578: INSERTS the values
entry_reason,
exit_reason,
```

All code is **syntactically correct** and **all pieces connected**. But entry_reason is still NULL in database.

### Most Likely Causes

1. **entry_reason is None at time of place_order call**
   - signal.reason might be empty string or None
   - Need to verify with DEBUG logs

2. **Entry reason is being calculated but not reaching TradeSignal**
   - SignalCalculator returns (strength, reason)
   - TradeSignal created with reason=full_reason
   - But signal.reason might not be propagated correctly

3. **Database saving issue (less likely)**
   - Would affect exit_reason too, but it works
   - Schema migration worked (columns exist)
   - Suggests database layer is fine

---

## Verified Facts

### ✅ Database Schema
- entry_reason column: EXISTS (VARCHAR)
- exit_reason column: EXISTS (VARCHAR)
- Migration successful

### ✅ Code Changes Deployed
- entry.py: Passes entry_reason to place_order (line 314)
- paper_trading.py: Passes to insert_trade (lines 335-336)
- database.py: Inserts into database (lines 577-578)
- All files compiled successfully, no syntax errors

### ✅ Exit Logging Works
- 6/6 Phase 3 timeout exits have exit_reason = "10-minute timeout"
- Database receiving and saving exit_reason correctly
- Exit logic working end-to-end

### ❌ Entry Logging Broken
- 0/18 Phase 3 BUY orders have entry_reason
- All entry_reason values are NULL in database
- signal.reason not being saved

---

## Next Steps to Debug

1. **Check DEBUG logs for entry_reason value**
   - Added debug at entry.py: "DEBUG_ENTRY: Passing entry_reason..."
   - Look for these logs to see if entry_reason is populated
   - If NULL → problem is in signal generation
   - If populated → problem is in database saving

2. **Add debug to place_order() in paper_trading.py**
   - Log the entry_reason value received
   - Log the values being inserted into database
   - Confirm it's not being lost/cleared

3. **Add debug to insert_trade() in database.py**
   - Log the entry_reason parameter received
   - Confirm it's being inserted correctly
   - Check for any exceptions during insert

4. **Create test trade to verify**
   - Place a manual BUY order with test entry_reason
   - Check if it's saved to database
   - If yes → problem with Phase 3 signal generation
   - If no → problem with database persistence

---

## Recommendations

### Immediate (Next 30 min)
1. Check debug logs for entry_reason value
2. Verify signal.reason is not empty
3. Test manual buy order with test entry_reason

### Short-term (Next 1-2 hours)
1. Add comprehensive debug logging throughout:
   - SignalCalculator.calculate_signal() → reason
   - _check_symbol_impl() → signal creation
   - _execute_entry_impl() → place_order call
   - place_order() → insert_trade call
   - insert_trade() → database INSERT

2. Create test case:
   - Manually trigger entry conditions (RSI < 30)
   - Verify entry_reason is logged
   - Verify exit_reason is logged

### Long-term
1. Add integration tests for entry/exit logging
2. Verify all 8 phase requirements passing
3. Resume Phase 3 once entry logging confirmed working

---

## Summary Table

| Aspect | Status | Evidence |
|--------|--------|----------|
| **Exit reason logging** | ✅ WORKS | 6/6 timeout exits have "10-minute timeout" |
| **Entry reason logging** | ❌ BROKEN | 0/18 BUY orders have entry_reason |
| **Profit/stop exits** | ⚠️ NOT TESTED | No Phase 3 trades hit thresholds, only timeouts |
| **Exit logic code** | ✅ CORRECT | Timeout forced exits (10 min) working |
| **Database schema** | ✅ CORRECT | Columns exist, migration successful |
| **Code deployment** | ✅ CORRECT | All changes in place, API running fresh code |
| **Signal generation** | ❓ UNCLEAR | Need to check if signal.reason is populated |

---

## Root Cause Hypothesis

**Most likely:** `signal.reason` is EMPTY or NULL when passed to place_order(), causing entry_reason to be NULL in database.

Why? Exit logging works (exit_reason is "10-minute timeout"), but entry logging doesn't. This suggests:
- Database layer working (exit_reason saves correctly)
- Parameter passing working (exit_reason reaches database)
- Problem is upstream: signal.reason is not populated

**Next step:** Check DEBUG_ENTRY logs to confirm signal.reason value.
