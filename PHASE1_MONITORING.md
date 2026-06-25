# Phase 1 Daily Monitoring

**Phase 1 Duration:** 2026-06-25 → 2026-07-05 (10 days)  
**Target:** >55% win rate, positive cumulative P&L, system stability

## Daily Check (Takes 2 minutes)

Run this command each morning:
```bash
bash scripts/monitor-phase1.sh
```

This generates a report with:
- ✅ Trader running status
- ✅ Total trades executed
- ✅ Daily P&L and win rate
- ✅ Error count (order failures, exit failures)
- ✅ Progress toward 10-day goal

Reports are saved to: `logs/phase1_monitoring.log`

## What to Look For

### ✅ **Healthy Signs**
- `Running: true` and `Enabled: true`
- `Total Trades > 0` (activity happening)
- `Daily P&L > €0` (profitable)
- `Failed Orders: 0` and `Failed Exits: 0` (no errors)
- Signal decisions matching trade executions

### ⚠️ **Warning Signs (Investigate)**
- `Running: false` (trader crashed - restart API server)
- `Enabled: false` (config issue - check trading_config.json)
- `Daily P&L < -€500` (approaching 5% daily loss limit)
- Repeated `ORDER_FAILED` or `EXIT_FAILED` messages
- No trades for >1 hour (check Binance connectivity)

### 🔴 **Critical Issues (Stop & Debug)**
- Trader crashes more than once per day
- Win rate drops below 30% (strategy issue)
- P&L loss > 5% (€500) in single day
- Cannot connect to Binance API (network issue)

## Manual Checks

### Check trader status
```bash
curl http://localhost:8001/api/autonomous/status | jq .
```

### View recent trades
```bash
curl http://localhost:8001/api/autonomous/status | jq '.recent_trades[-5:]'
```

### Check for signal decisions
```bash
grep "SIGNAL_DECISION" logs/api_server.log | jq '.symbol, .signal_score, .passed' | tail -10
```

### Check for trade executions
```bash
grep "TRADE_EXECUTED" logs/api_server.log | jq '.symbol, .side, .price, .signal_strength' | tail -10
```

### Check for errors
```bash
grep "ORDER_FAILED\|EXIT_FAILED" logs/api_server.log | jq '.symbol, .error_message' | tail -5
```

## Restart Procedures

### If trader stops running:
```bash
# Kill old process
pkill -f "uvicorn.*8001" || true

# Restart API server
source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 &
```

### If config is wrong:
```bash
# Check current config
cat logs/trading_config.json

# Reset to enabled trading
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
  "_last_updated": "2026-06-25T08:00:00Z",
  "_source": "manual_reset"
}
EOF

# Restart trader
curl -X POST http://localhost:8001/api/autonomous/stop
sleep 2
curl -X POST http://localhost:8001/api/autonomous/start
```

## Phase 1 Success Criteria

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Win Rate | >55% | TBD | Measuring |
| Cumulative P&L | >€0 | €0.00 | Neutral |
| Total Trades | 20-30 | 3 | In progress |
| System Uptime | 100% | TBD | Monitoring |
| Failed Orders | 0 | 0 | ✅ Clean |

## Timeline

| Date | Milestone | Action |
|------|-----------|--------|
| 2026-06-25 | Day 1 Start | ✅ Trader running, 3 trades |
| 2026-06-26 | Day 2 | Monitor & verify strategy |
| 2026-06-27 | Day 3 | Check for pattern issues |
| 2026-06-28 | Day 4 | Analyze signal quality |
| 2026-06-29 | Day 5 | Mid-phase review |
| 2026-06-30 | Day 6 | Adjust if needed |
| 2026-07-01 | Day 7 | Final week begins |
| 2026-07-02 | Day 8 | Performance validation |
| 2026-07-03 | Day 9 | Pre-completion check |
| 2026-07-04 | Day 10 | Final day analysis |
| 2026-07-05 | Phase 1 End | Go/no-go decision for Phase 2 |

## Phase 2 Decision Criteria

**Proceed to live trading (€1,000) if:**
- ✅ Win rate ≥ 55%
- ✅ Cumulative P&L > €0
- ✅ No system crashes
- ✅ All trades properly logged
- ✅ No repeated errors

**Pause and debug if:**
- ❌ Win rate < 45%
- ❌ Cumulative P&L < -€100
- ❌ Repeated crashes
- ❌ Consistent order failures
