# High Availability Monitoring & Alerting

## Real-Time Health Monitoring

### Dashboard Integration

The unified dashboard includes HA health cards:
- **Primary Status** — Real-time health indicator
- **Backup Status** — Standby/Active role indicator
- **Replication Lag** — Graph of lag over time
- **Failover Readiness** — Pass/fail indicator
- **System Overall** — Health summary

Access: `http://127.0.0.1:8001/`

### API Endpoints for Monitoring

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `/api/redundancy/status` | Full redundancy status | Every 10s |
| `/api/redundancy/primary/health` | Primary health only | Every 10s |
| `/api/redundancy/backup/health` | Backup health only | Every 10s |
| `/api/redundancy/replication-lag` | Replication lag estimate | Every 10s |
| `/api/redundancy/failover/ready` | Failover readiness check | Every 30s |
| `/api/redundancy/config` | HA configuration | On demand |
| `/api/redundancy/history` | Historical status | Daily |

## Manual Monitoring

### Quick Health Check

```bash
# One-time status check
python3 scripts/check_ha_status.py

# Detailed output
python3 scripts/check_ha_status.py --detailed

# Watch status every 5 seconds
python3 scripts/check_ha_status.py --watch 5
```

Output colors:
- 🟢 **GREEN**: System healthy or component running
- 🟡 **YELLOW**: Degraded, warning, or standby mode
- 🔴 **RED**: System down or critical error

### Test Failover Scenarios

```bash
# Run comprehensive failover tests (non-destructive)
bash scripts/test_failover_scenarios.sh

# Shows:
# - Scenario 1: Healthy system status
# - Scenario 2: Replication lag measurement
# - Scenario 3: Failover readiness
# - Scenario 4: Failover simulation
# - Scenario 5: Sustained health monitoring
# - Scenario 6: Configuration verification
```

## Log Monitoring

### Primary Machine

**API Logs:**
```bash
journalctl -u crypto-daytrading -f
journalctl -u crypto-daytrading -S "1 hour ago"
```

**Recent errors:**
```bash
journalctl -u crypto-daytrading -p err -n 50
```

### Backup Machine

**Backup Trader Logs:**
```bash
ssh trader@192.168.3.204 journalctl -u backup-trader -f
ssh trader@192.168.3.204 journalctl -u backup-trader -S "1 hour ago"
```

**Failover Monitor Logs:**
```bash
ssh trader@192.168.3.204 journalctl -u failover-monitor -f
ssh trader@192.168.3.204 tail -f ~/crypto-daytrading/logs/failover_monitor.log
```

**Error events:**
```bash
ssh trader@192.168.3.204 journalctl -u backup-trader -p err -n 50
ssh trader@192.168.3.204 journalctl -u failover-monitor -p err -n 50
```

## Automated Monitoring Setup

### Systemd Timer for HA Health Checks

Create `check_ha_timer.service`:
```ini
[Unit]
Description=HA Health Check Timer
Documentation=man:check_ha_status.py(1)

[Timer]
# Run every 5 minutes
OnBootSec=1min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

Create `check_ha_timer.timer`:
```ini
[Unit]
Description=HA Health Check Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=trader
WorkingDirectory=/home/trader/crypto-daytrading
ExecStart=/home/trader/crypto-daytrading/scripts/check_ha_status.py --detailed
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ha-health-check

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now check_ha_timer.timer
```

View health check history:
```bash
journalctl -u check_ha_timer.service -n 100
```

### Cron Job Monitoring

Add to crontab (`crontab -e`):
```bash
# Health checks every 5 minutes
*/5 * * * * cd /home/trader/crypto-daytrading && python3 scripts/check_ha_status.py >> logs/ha_health.log 2>&1

# Detailed checks daily at 06:00
0 6 * * * cd /home/trader/crypto-daytrading && python3 scripts/check_ha_status.py --detailed >> logs/ha_health_daily.log 2>&1

# Failover scenario tests weekly on Monday at 02:00
0 2 * * 1 bash /home/trader/crypto-daytrading/scripts/test_failover_scenarios.sh >> logs/ha_tests.log 2>&1
```

## Alert Conditions

### Critical Alerts (Page Immediately)

| Condition | Severity | Action |
|-----------|----------|--------|
| Primary down > 30s | 🔴 CRITICAL | Failover auto-triggers, manual verification |
| Backup down + Failover active | 🔴 CRITICAL | Primary-only mode, manual failback needed |
| Both primary & backup down | 🔴 CRITICAL | Complete outage, manual intervention |
| Replication lag > 5s | 🔴 CRITICAL | Data sync issue, check PostgreSQL replication |

### Warning Alerts (Investigate Within Hour)

| Condition | Severity | Action |
|-----------|----------|--------|
| Primary not responding (< 30s) | 🟡 WARNING | Monitor, check logs |
| Backup not responding | 🟡 WARNING | System degraded, failover unavailable |
| Replication lag 2-5s | 🟡 WARNING | Monitor network, check disk I/O |
| Failover readiness = false | 🟡 WARNING | Backup not ready, manual intervention needed |

### Informational Alerts (Log Only)

| Condition | Severity | Action |
|-----------|----------|--------|
| Primary → Backup failover | ℹ️ INFO | Log and notify team |
| Backup → Primary failback | ℹ️ INFO | Log and notify team |
| Config mismatch detected | ℹ️ INFO | Verify and re-sync |

## Integration with External Monitoring

### Prometheus Metrics

Create `/home/trader/crypto-daytrading/scripts/ha_prometheus_exporter.py`:

```python
#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge
import requests
import time

PRIMARY_API = "http://127.0.0.1:8001"
PROMETHEUS_PORT = 8002

# Metrics
primary_up = Gauge('ha_primary_up', 'Primary trader is up')
backup_up = Gauge('ha_backup_up', 'Backup trader is up')
replication_lag = Gauge('ha_replication_lag_seconds', 'Replication lag in seconds')
failover_active = Gauge('ha_failover_active', 'Failover is active')
failover_ready = Gauge('ha_failover_ready', 'Backup is ready for failover')

def update_metrics():
    try:
        r = requests.get(f"{PRIMARY_API}/api/redundancy/status", timeout=5)
        status = r.json()
        
        # Update gauges
        primary_up.set(1 if status['primary']['status']['healthy'] else 0)
        backup_up.set(1 if status['backup']['status']['healthy'] else 0)
        
        lag = status['replication']['lag_seconds']
        replication_lag.set(lag if lag is not None else -1)
        
        failover_active.set(1 if status['failover']['active'] else 0)
        failover_ready.set(1 if status['backup']['ready_for_failover']['ready'] else 0)
    except Exception as e:
        print(f"Error updating metrics: {e}")

if __name__ == '__main__':
    start_http_server(PROMETHEUS_PORT)
    while True:
        update_metrics()
        time.sleep(30)
```

Run:
```bash
nohup python3 scripts/ha_prometheus_exporter.py > logs/ha_prometheus.log 2>&1 &
```

Prometheus scrape config:
```yaml
scrape_configs:
  - job_name: 'crypto-ha'
    static_configs:
      - targets: ['localhost:8002']
    scrape_interval: 30s
```

### Slack Alerting

Create alert handler in `/home/trader/crypto-daytrading/scripts/ha_slack_alerter.py`:

```python
#!/usr/bin/env python3
import requests
import os
import json
from datetime import datetime

SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')
PRIMARY_API = "http://127.0.0.1:8001"
ALERT_THRESHOLD_LAG = 5  # seconds

def send_slack_alert(title, message, severity='warning'):
    """Send alert to Slack."""
    if not SLACK_WEBHOOK:
        return
    
    color = {
        'critical': '#ff0000',
        'warning': '#ffaa00',
        'info': '#0099ff'
    }.get(severity, '#999999')
    
    payload = {
        'attachments': [{
            'color': color,
            'title': title,
            'text': message,
            'footer': 'HA Monitoring',
            'ts': int(datetime.now().timestamp())
        }]
    }
    
    requests.post(SLACK_WEBHOOK, json=payload)

def check_ha_status():
    """Check HA status and send alerts."""
    try:
        r = requests.get(f"{PRIMARY_API}/api/redundancy/status", timeout=5)
        status = r.json()
        
        overall = status['overall_status']
        lag = status['replication']['lag_seconds']
        
        # Check conditions
        if overall == 'DOWN':
            send_slack_alert(
                '🔴 CRITICAL: HA System DOWN',
                'Both primary and backup are down!',
                'critical'
            )
        elif overall == 'FAILOVER_ACTIVE':
            send_slack_alert(
                '🔴 FAILOVER ACTIVE',
                'Primary is down, Backup has taken over',
                'critical'
            )
        elif overall == 'DEGRADED':
            send_slack_alert(
                '⚠️ DEGRADED: Backup unavailable',
                'Primary is up but backup is down',
                'warning'
            )
        
        if lag and lag > ALERT_THRESHOLD_LAG:
            send_slack_alert(
                '🔴 High Replication Lag',
                f'Replication lag: {lag}s (threshold: {ALERT_THRESHOLD_LAG}s)',
                'critical'
            )
    except Exception as e:
        send_slack_alert(
            '⚠️ HA Monitor Error',
            f'Could not check HA status: {str(e)}',
            'warning'
        )

if __name__ == '__main__':
    check_ha_status()
```

Run via cron:
```bash
# Check every 5 minutes
*/5 * * * * python3 /home/trader/crypto-daytrading/scripts/ha_slack_alerter.py
```

## Monitoring Dashboard

### Key Metrics to Track

1. **Uptime**: Primary + (Failover + Backup)
2. **Failover Events**: Count and duration per week
3. **Replication Lag**: P95, P99, max
4. **Health Check Failures**: Rate and duration
5. **Data Consistency**: Equity diff between primary/backup
6. **API Response Time**: Primary vs Backup

### Sample Dashboard Query

```sql
-- Weekly uptime report
SELECT
    DATE_TRUNC('week', timestamp) as week,
    COUNT(*) as total_checks,
    SUM(CASE WHEN overall_status = 'HEALTHY' THEN 1 ELSE 0 END) as healthy_checks,
    ROUND(100.0 * SUM(CASE WHEN overall_status = 'HEALTHY' THEN 1 ELSE 0 END) / COUNT(*), 2) as uptime_pct,
    AVG(replication_lag_seconds) as avg_replication_lag,
    MAX(replication_lag_seconds) as max_replication_lag,
    COUNT(DISTINCT CASE WHEN failover_active THEN timestamp END) as failover_count
FROM ha_status_history
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1 DESC;
```

## Troubleshooting Alerts

### "Primary down" alert

1. **Check API is running:**
   ```bash
   curl http://127.0.0.1:8001/api/health
   sudo systemctl status crypto-daytrading
   ```

2. **Check logs:**
   ```bash
   journalctl -u crypto-daytrading -n 100 -p err
   ```

3. **Check disk/memory:**
   ```bash
   df -h /
   free -h
   ```

### "Backup unreachable" alert

1. **Verify network connectivity:**
   ```bash
   ping 192.168.3.204
   ssh trader@192.168.3.204 echo "OK"
   ```

2. **Check backup service:**
   ```bash
   ssh trader@192.168.3.204 sudo systemctl status backup-trader
   ```

3. **Check backup logs:**
   ```bash
   ssh trader@192.168.3.204 journalctl -u backup-trader -n 100 -p err
   ```

### "High replication lag" alert

1. **Check PostgreSQL replication:**
   ```bash
   psql -c "SELECT * FROM pg_stat_replication;"
   ```

2. **Check network:**
   ```bash
   iperf3 -c 192.168.3.204  # Test bandwidth
   mtr -r 192.168.3.204     # Test route stability
   ```

3. **Check disk I/O on backup:**
   ```bash
   ssh trader@192.168.3.204 iostat -x 1 5
   ```

## SLA & Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Availability | 99.9% | TBD |
| Failover Time | ≤ 30s | ≤ 30s |
| Replication Lag | < 2s | TBD |
| RTO (Recovery Time Objective) | 30s | 30s |
| RPO (Recovery Point Objective) | 0 | 0 (no trades lost) |
| Mean Time To Failure (MTTF) | > 720 hours | TBD |
| Mean Time To Repair (MTTR) | < 5 min | TBD |

## Monthly Review

First Monday of each month:
1. ✅ Review failover metrics from previous month
2. ✅ Run failover drill (simulated failure)
3. ✅ Update runbooks based on learnings
4. ✅ Review alert thresholds and adjust if needed
5. ✅ Verify backup capacity meets growth
6. ✅ Check PostgreSQL replication health

---

For full deployment guide, see [HA_DEPLOYMENT.md](HA_DEPLOYMENT.md)
