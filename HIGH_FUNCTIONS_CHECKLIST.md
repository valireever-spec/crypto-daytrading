# HIGH FUNCTIONS VALIDATION CHECKLIST (Must be 100%)

## 1. HA Sync Status
- [ ] BACKUP reachable on local network (192.168.3.25:8002)
- [ ] BACKUP reachable on remote (r33v3r.ddns.net:8443)
- [ ] Sync bi-directional (PRIMARY → BACKUP → PRIMARY)
- [ ] State replicated (cash, positions, trades)
- [ ] Heartbeat working (every 2-5 seconds)

**Current Status:** BACKUP OFFLINE (Scenario C active - no-HA mode)
**Action:** N/A for now, running standalone

---

## 2. Entry/Exit Logic (Live Validation)
- [ ] Entry signals generated correctly (regime detection working)
- [ ] Orders placed at correct prices (no slippage > 0.5%)
- [ ] Fills confirmed in DB immediately
- [ ] Exit logic: Profit targets hit at +2.0%
- [ ] Exit logic: Stop losses hit at -0.5%
- [ ] Exit logic: 10-minute timeout implemented

**Current Status:** 
- ✅ Entry: BNB trade just executed @ $586.28
- ✅ Order placed correctly with UUID tracking
- ⏳ Exit logic: PENDING (monitoring live trade)
- ⏳ Stop loss: Will trigger at $583.25
- ⏳ Profit target: Will trigger at $597.95

**Validation Timeline:** 24 hours of live trading

---

## 3. Portfolio Management
- [ ] Max 4 positions enforced (currently 1)
- [ ] Position sizing: 0.5% per trade (currently ~0.5% for BNB)
- [ ] No over-leverage
- [ ] New entries blocked when at max positions
- [ ] Concurrent position tracking accurate

**Current Status:**
- ✅ 1 open position (BNB) @ 0.0079 qty
- ✅ Position size: $4.63 value = 0.5% of $930 account ✅
- ✅ Max positions: 4 limit respected

**Validation:** Monitor next entry attempts

---

## 4. Alerts & Logging
- [ ] All trades logged to DB with order ID
- [ ] Slippage tracked per trade
- [ ] Fee tracked per trade
- [ ] Realized P&L calculated per exit
- [ ] Critical events: Entry, Exit, Stop Loss, Profit Target logged
- [ ] Telegram alerts sent (if enabled)

**Current Status:**
- ✅ BNB trade in DB with:
  - Order ID: f34e065d-7a43-4216-a542-687b2ba68313
  - Slippage: 0.0999%
  - Fee: 0.0046 (recorded)
  - Time: 2026-07-06T19:52:42.516416
- ⏳ Exit logging: PENDING (waiting for exit condition)

**Validation:** Check all exit events are logged

---

## 5. API Health & Responsiveness
- [ ] /api/health: Responds <100ms ✅
- [ ] /api/health: Returns accurate data ✅
- [ ] /api/config: Accessible and up-to-date ✅
- [ ] /api/trading/status: Returns strategy state (if exists)
- [ ] All endpoints: No timeouts, no 5xx errors

**Current Status:**
- ✅ /api/health: Responds immediately with accurate account state
- ✅ /api/health: Shows 1 open position, $926.61 cash, -$5.19 PnL
- ✅ Config: entry_threshold=25, position_size=0.5%, max_pos=4

**Validation:** Monitor for any API errors during 24h test

---

## VALIDATION PROTOCOL

### Every 30 seconds (Automated):
1. Check `/api/health`
2. Query DB for new trades
3. Verify circuit breaker state
4. Verify WebSocket health

### Every hour (Manual):
1. Check no fatal errors in logs
2. Verify account state consistency
3. Review all trades executed in last hour
4. Check stop loss levels on open positions

### On exit event (Immediate):
1. Verify order filled at expected price
2. Verify P&L calculated correctly
3. Verify position closed in DB
4. Log exit reason (profit target, stop loss, timeout)

---

## SUCCESS CRITERIA (For 100% Status)

| Function | Target | Current | Status |
|----------|--------|---------|--------|
| Entry signals | Consistent generation | 1 trade in 30min | ⏳ MONITORING |
| Order fills | 100% at market | BNB filled correctly | ✅ YES |
| Position tracking | ±$0.01 accuracy | $4.63 exact | ✅ YES |
| Risk gates | 100% enforced | All gates active | ✅ YES |
| Alerts | All events logged | 1 trade logged | ⏳ MONITORING |
| API health | <100ms response | Instant | ✅ YES |
| System uptime | 24/7 stable | 0 restarts | ✅ YES |

---

## 24-HOUR VALIDATION SCHEDULE

**Start:** 2026-07-06 22:00 UTC
**End:** 2026-07-07 22:00 UTC

**Checkpoints:**
- [ ] 2h mark: At least 2 new signals triggered
- [ ] 6h mark: At least 1 exit (profit target or stop loss)
- [ ] 12h mark: Min 5 completed trades, win rate >30%
- [ ] 24h mark: Final report - strategy is 100% operational

**Stop conditions:**
- Circuit breaker trips 3+ times → FAILURE
- WebSocket disconnects for >5min → FAILURE
- Position tracking error >$1 → FAILURE
- Unlogged exit → FAILURE
- Account state inconsistent → FAILURE

