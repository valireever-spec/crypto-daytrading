# Crypto-DayTrading API - Quick Reference Card

## Connection
```
Base URL: http://localhost:8000
Method: REST + JSON
Rate Limit: 100 req/min
Auth: None (local)
```

## Essential Endpoints

### Account
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/paper/account` | GET | Account balance & equity |
| `/api/paper/positions` | GET | Open positions |
| `/api/paper/trades` | GET | Trade history (limit=100) |
| `/api/paper/status` | GET | Full trading status |
| `/api/paper/reset` | POST | Reset account (testing) |

### Autonomous Trading
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/autonomous/status` | GET | Trader status |
| `/api/autonomous/start` | POST | Enable trading |
| `/api/autonomous/stop` | POST | Disable trading |
| `/api/autonomous/config` | GET | Get config |
| `/api/autonomous/config/update` | POST | Update config |

### Health & Monitoring
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | System health |
| `/api/monitoring/health` | GET | Detailed health |
| `/api/monitoring/alerts` | GET | Get alerts |
| `/metrics` | GET | Prometheus metrics |

### Trading Control
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/trading/pause` | POST | Pause trading |
| `/api/trading/resume` | POST | Resume trading |
| `/api/trading/exit` | POST | Partial exit |

### High Availability
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ha/status` | GET | HA status |
| `/api/ha/heartbeat` | POST | Heartbeat (BACKUP) |
| `/api/ha/sync-from-primary` | POST | Sync from PRIMARY |

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Server Error |
| 503 | Unavailable |

## Common cURL Commands

### Get Account
```bash
curl http://localhost:8000/api/paper/account | jq .
```

### Check Health
```bash
curl http://localhost:8000/api/health | jq .
```

### Start Trading
```bash
curl -X POST http://localhost:8000/api/autonomous/start
```

### Get Positions
```bash
curl http://localhost:8000/api/paper/positions | jq .
```

### Get Metrics
```bash
curl http://localhost:8000/metrics | head -20
```

### Update Config
```bash
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{"position_size_pct": 2.0, "max_positions": 5}'
```

### Get Alerts
```bash
curl "http://localhost:8000/api/monitoring/alerts?status=active"
```

## Request Format

All requests use JSON:
```json
{
  "field1": "value",
  "field2": 123,
  "field3": true
}
```

Response:
```json
{
  "status": "success",
  "data": {...},
  "timestamp": "2026-07-03T17:30:00Z"
}
```

Error:
```json
{
  "error": "ERROR_CODE",
  "detail": "Error message",
  "status_code": 400
}
```

## Config Parameters

Key trading configuration parameters:

| Parameter | Type | Range | Default | Purpose |
|-----------|------|-------|---------|---------|
| `enabled` | bool | - | true | Enable trading |
| `entry_threshold` | float | 0-1 | 0.65 | Signal strength for entries |
| `exit_profit_target` | float | % | 2.5% | Take profit target |
| `exit_stop_loss` | float | % | 1.5% | Stop loss limit |
| `position_size_pct` | float | % | 2.0% | Risk per position |
| `max_positions` | int | 1-20 | 5 | Max open positions |
| `max_daily_loss_pct` | float | % | 5.0% | Daily loss limit |
| `symbols` | array | - | - | Trading symbols |
| `loop_sleep_seconds` | float | secs | 5.0 | Trading frequency |
| `quality_gate_entry` | float | % | 85% | Data quality for entries |
| `quality_gate_exit` | float | % | 80% | Data quality for exits |

## Update Config Example
```bash
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "entry_threshold": 0.68,
    "exit_profit_target": 0.03,
    "position_size_pct": 2.5,
    "max_positions": 4
  }'
```

## Monitoring Checklist

Daily monitoring:
- [ ] Check `/api/health` (should be 200)
- [ ] Review `/api/paper/account` (P&L, equity)
- [ ] Check `/api/monitoring/alerts?status=active`
- [ ] Verify trading is running: `/api/autonomous/status`
- [ ] Check metrics: `/metrics` (CPU, memory)

## Troubleshooting Quick Fix

| Issue | Check | Fix |
|-------|-------|-----|
| 503 Error | `/api/health` | Restart API |
| Slow response | `/metrics` | Check CPU/memory |
| Rate limit | X-RateLimit-Remaining | Wait 60 seconds |
| 400 Bad Request | Request JSON format | Validate JSON |

## Common Workflows

### Start Trading
```bash
# 1. Get current config
curl http://localhost:8000/api/autonomous/config

# 2. Update if needed
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{"position_size_pct": 2.0}'

# 3. Start
curl -X POST http://localhost:8000/api/autonomous/start

# 4. Verify
curl http://localhost:8000/api/autonomous/status
```

### Monitor Trading
```bash
# Health
curl http://localhost:8000/api/health

# Account
curl http://localhost:8000/api/paper/account

# Positions
curl http://localhost:8000/api/paper/positions

# Alerts
curl "http://localhost:8000/api/monitoring/alerts?status=active"
```

### Stop & Review
```bash
# Stop
curl -X POST http://localhost:8000/api/trading/pause

# Get trades
curl http://localhost:8000/api/paper/trades?limit=20

# Get final account
curl http://localhost:8000/api/paper/account
```

## Response Fields Reference

### Account Response
```json
{
  "cash": 1220.41,              // Available cash
  "equity": 1441.97,            // Total equity
  "pnl": 221.56,                // P&L
  "pnl_percent": 15.4,          // P&L %
  "currency": "EUR",            // Currency
  "starting_capital": 1000.0,   // Initial amount
  "timestamp": "2026-07-03T17:30:00Z"
}
```

### Position Response
```json
{
  "symbol": "BTC/USDT",     // Ticker
  "quantity": 0.01,         // Size
  "entry_price": 42500.00,  // Entry
  "current_price": 42700.00,// Current
  "pnl": 2.00,              // Position P&L
  "pnl_percent": 0.47,      // % P&L
  "entry_time": "2026-07-03T17:20:00Z"
}
```

### Trade Response
```json
{
  "id": "trade_123",        // Trade ID
  "symbol": "BTC/USDT",     // Ticker
  "side": "BUY",            // BUY/SELL
  "quantity": 0.01,         // Size
  "price": 42500.00,        // Execution price
  "status": "FILLED",       // Status
  "timestamp": "2026-07-03T17:20:00Z"
}
```

## Documentation Files

| File | Size | Purpose |
|------|------|---------|
| API_CONTRACT.md | 48 KB | Complete documentation (197 endpoints) |
| openapi.json | 13 KB | OpenAPI 3.0 spec (machine-readable) |
| API_DOCUMENTATION_README.md | 12 KB | Guide to documentation |
| API_QUICK_REFERENCE.md | This file | Quick lookup reference |

---

**Version:** 1.0.0
**Updated:** 2026-07-03
**Total Endpoints:** 197
