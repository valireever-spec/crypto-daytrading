# 15-Minute Health Check Guide

**Automated health monitoring for PRIMARY and BACKUP crypto trading HA system.**

---

## Overview

The `health_check_15min.py` script monitors **all critical systems** for both machines every 15 minutes:

- ✅ **API Health** — Response time, circuit breaker state, trading status
- ✅ **WebSocket Streams** — 3/3 streams connected, staleness detection
- ✅ **Database** — Recent writes, file size, integrity
- ✅ **HA Heartbeat** — PRIMARY→BACKUP sync, config version match
- ✅ **Resource Usage** — Memory, CPU, socket count
- ✅ **Trading Activity** — Positions, trades today, P&L
- ✅ **Log Health** — Errors, warnings, critical events
- ✅ **Signal Generation** — Rate tracking (target <1.0/min)
- ✅ **SSH Tunnel** — Remote BACKUP access availability
- ✅ **Position Reconciliation** — DB vs Binance mismatch detection
- ✅ **Binance Connectivity** — REST API availability

---

## What Gets Checked

### PRIMARY (192.168.30.137:8001)

```
📍 PRIMARY CHECK
├─ API Health
│  ├─ Status (healthy/degraded/unhealthy)
│  ├─ Response time (target <1000ms)
│  ├─ Circuit breaker state (CLOSED/OPEN)
│  ├─ Trading allowed (True/False)
│  └─ Account state (mode, cash, P&L, positions)
├─ WebSocket Health
│  ├─ All 3 streams connected (BTCUSDT, ETHUSDT, BNBUSDT)
│  ├─ Staleness check (no stream >30% stale)
│  └─ Reconnect count
├─ Binance Connectivity
│  └─ REST API reachable (via /api/health heartbeat)
├─ Order Execution
│  └─ Recent order count from logs
├─ Resources
│  ├─ Memory usage (target <300MB)
│  ├─ CPU usage (target <50%)
│  ├─ Socket count
│  └─ Thread count
├─ Log Health
│  ├─ Errors in last 200 lines (target 0)
│  ├─ Warnings (alert if >5)
│  └─ Criticals (alert if >0)
└─ Signal Frequency
   ├─ Signals/min (target <1.0)
   └─ Status (normal/excessive)
```

### BACKUP (192.168.3.25:8002)

```
📍 BACKUP CHECK
├─ API Health (same as PRIMARY)
├─ WebSocket Health (same as PRIMARY)
├─ Resource Usage (same as PRIMARY)
├─ Position Sync
│  ├─ Open positions count
│  └─ Last reconciliation time
└─ Log Health (via SSH or local logs)
```

### HA System

```
🔗 HA SYSTEM CHECK
├─ Heartbeat
│  ├─ Status (connected/disconnected)
│  └─ BACKUP sync enabled
├─ Config Sync
│  ├─ PRIMARY trades today vs BACKUP
│  ├─ Drift threshold (alert if >10 trades apart)
│  └─ Version match
├─ Database Health
│  ├─ File size (tracking growth)
│  ├─ Last write timestamp
│  └─ Staleness (alert if >1h no writes)
└─ SSH Tunnel
   ├─ Port 8443 reachable
   └─ Connection status
```

---

## Alerts & Thresholds

The script generates **⚠️ alerts** when:

| Metric | Threshold | Alert |
|--------|-----------|-------|
| API Response | >1000ms | "⚠️ PRIMARY: API response slow" |
| Memory | >400MB | "⚠️ PRIMARY: High memory usage" |
| Trading Allowed | False | "🔴 PRIMARY: Trading not allowed" |
| Circuit Breaker | OPEN | "🔴 PRIMARY: Circuit breaker OPEN" |
| WebSocket | Unhealthy | "⚠️ PRIMARY: WebSocket unhealthy" |
| Log Errors | >5 in 200 lines | "⚠️ PRIMARY: N ERROR log entries" |
| Log Criticals | >0 | "🔴 PRIMARY: N CRITICAL log entries" |
| Config Sync Drift | >10 trades | "⚠️ CONFIG SYNC: Drifted by N trades" |
| Database Writes | >1 hour old | "⚠️ DATABASE: No writes for Nm" |
| SSH Tunnel | Disconnected | "⚠️ SSH TUNNEL: Not responding" |
| Signal Frequency | >100 in recent logs | "⚠️ PRIMARY: Excessive signals" |

---

## Installation

### Step 1: Manual Installation (No sudo)

Run the health check manually anytime:

```bash
cd /home/vali/projects/crypto-daytrading
source venv/bin/activate
python3 scripts/health_check_15min.py
```

Output format: Structured JSON → pretty-printed table

### Step 2: Automated (Requires sudo)

Install the systemd timer (runs every 15 minutes automatically):

```bash
sudo bash scripts/install-health-check-timer.sh
```

This creates:
- `/etc/systemd/system/crypto-health-check.service` — One-shot service
- `/etc/systemd/system/crypto-health-check.timer` — Recurring timer (every 15min)

Verify installation:

```bash
systemctl status crypto-health-check.timer
systemctl list-timers crypto-health-check.timer
```

---

## Usage

### View Live Checks

```bash
# Watch health checks as they run
journalctl -u crypto-health-check.service -n 100 -f
```

### Manually Trigger a Check

```bash
systemctl start crypto-health-check.service
```

### View Last N Checks

```bash
journalctl -u crypto-health-check.service --lines=50
```

### Stop/Disable Timer

```bash
systemctl stop crypto-health-check.timer
systemctl disable crypto-health-check.timer
```

### View Timer Schedule

```bash
systemctl list-timers crypto-health-check.timer
```

---

## Output Example

```
======================================================================
🏥 15-MINUTE HEALTH CHECK — 2026-07-05T19:30:00.000000
======================================================================

📍 PRIMARY (192.168.30.137:8001)
----------------------------------------------------------------------
  api:
    status: healthy
    response_time_ms: 46.92
    circuit_breaker: CLOSED
    trading_allowed: True
    websocket_healthy: True
    websocket_streams: 3/3
    trades_today: 249
    daily_pnl: -5.19
  websocket:
    overall_healthy: True
    healthy_streams: 3
    stale_streams: []
  resources:
    memory_percent: 2.5
    cpu_percent: 1.2
    sockets: 15
    threads: 8
  logs:
    errors_last_200: 0
    warnings_last_200: 2
    criticals_last_200: 0
  signals:
    recent_signals: 4
    status: normal

📍 BACKUP (192.168.3.25:8002)
----------------------------------------------------------------------
  api:
    status: healthy
    response_time_ms: 34.15
    circuit_breaker: CLOSED
    trading_allowed: True
    websocket_streams: 3/3
    trades_today: 249

🔗 HA SYSTEM
----------------------------------------------------------------------
  heartbeat:
    status: connected
  config_sync:
    status: synced
    drift: 0
  database:
    file_size_mb: 0.69
    last_write: 2026-07-05 15:08:14
    status: healthy
  ssh_tunnel:
    status: connected

📋 ALERTS SUMMARY
----------------------------------------------------------------------
✅ No alerts

======================================================================
```

---

## Interpreting Results

### ✅ Healthy System

```
✅ All PRIMARY/BACKUP checks green
✅ WebSocket 3/3 streams connected
✅ Circuit breaker CLOSED
✅ Trading allowed = True
✅ No log errors/warnings
✅ Config sync drift = 0
✅ Database recent writes
✅ SSH tunnel connected
```

### ⚠️ Warning (Investigate, Not Critical)

```
⚠️ API response slow (1500ms)
⚠️ WebSocket staleness >30%
⚠️ N ERROR log entries (but <5)
⚠️ Config sync drift (but <10 trades)
⚠️ Database no writes for 30m
⚠️ High memory usage (but <300MB)
```

### 🔴 Critical (Immediate Action Required)

```
🔴 API unreachable (HTTP error)
🔴 Trading not allowed
🔴 Circuit breaker OPEN
🔴 N CRITICAL log entries
🔴 WebSocket unhealthy
🔴 SSH tunnel disconnected
```

---

## Integration with Monitoring

The script output is **systemd journal compatible**, so you can integrate with:

- **Prometheus** — Parse journal logs via exporter
- **Grafana** — Ingest metrics from systemd journal
- **ELK Stack** — Forward to Elasticsearch via Filebeat
- **Slack/PagerDuty** — Parse journal → webhook alerting
- **Custom Dashboards** — JSON output available via API

---

## Troubleshooting

### Timer not running?

```bash
# Check if enabled
systemctl is-enabled crypto-health-check.timer

# Check for errors
journalctl -u crypto-health-check.service -n 50
```

### BACKUP log file not found?

The script tries multiple paths:
- `/tmp/backup.log`
- `/home/claude/crypto-daytrading/logs/system.log`

If BACKUP uses a different path, update `BACKUP_LOGS_PATHS` in the script.

### SSH tunnel not connecting?

SSH tunnel requires:
1. Port 8443 forwarding to BACKUP:8002
2. SSH tunnel active on PRIMARY machine

Check:
```bash
ssh -N -L 8443:192.168.3.25:8002 openhabian@192.168.3.25 &
```

---

## Performance

- **Execution time:** ~2-3 seconds per check
- **Resource overhead:** <50MB RAM, <1% CPU
- **Network calls:** 2 (PRIMARY + BACKUP API health)
- **Disk I/O:** Minimal (reads logs, no writes)

---

## Future Enhancements

Potential additions:
- [ ] Prometheus metrics export (`.prom` format)
- [ ] Slack/Discord alerting on critical events
- [ ] Historical trends (memory growth over time)
- [ ] Order fill rate tracking
- [ ] Slippage monitoring
- [ ] Position liquidation risk alerts
- [ ] Binance rate limit tracking (1200 req/min)
- [ ] Clock sync verification between machines
