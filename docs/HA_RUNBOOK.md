# High Availability Runbook

Quick decision trees and response procedures for HA alerts.

## Alert Response Flowchart

```
HA Alert Received
  ├─ Check overall_status
  │  ├─ HEALTHY → Normal operation, no action
  │  ├─ DEGRADED → Backup unavailable (see: Backup Down)
  │  ├─ FAILOVER_ACTIVE → Primary failed, backup trading (see: Primary Down)
  │  └─ DOWN → System outage (see: Complete Outage)
```

## Runbook: Backup is DOWN

**Alert**: ⚠️ System is DEGRADED - Backup trader is unavailable

**Impact**: Active-passive redundancy lost; if primary fails, system goes down

**Response Time**: Within 1 hour

### Decision Tree

```
Is primary trading successfully?
  ├─ YES → Go to "Restore Backup"
  └─ NO  → Go to "Check Primary First"
```

### Check Primary First

```bash
# Verify primary is healthy
curl http://127.0.0.1:8001/api/redundancy/status | jq .primary

# If primary is down, this is a CRITICAL situation
if curl -s http://127.0.0.1:8001/api/health | grep -q "ok"; then
    echo "✓ Primary is trading"
else
    echo "✗ CRITICAL: Both primary and backup are down!"
    # Go to "Complete Outage" runbook
    exit 1
fi
```

### Restore Backup

**Option 1: Quick Restart** (5 minutes)

```bash
# On backup machine
ssh trader@192.168.3.204

# Check backup logs for errors
journalctl -u backup-trader -n 50 -p err

# Restart backup service
sudo systemctl restart backup-trader

# Wait for startup
sleep 5

# Verify it's responding
curl http://192.168.3.204:8002/api/health

# Check redundancy status from primary
curl http://127.0.0.1:8001/api/redundancy/status | jq .overall_status
# Should now be "HEALTHY" or "ACTIVE"
```

**Option 2: Deep Dive** (20 minutes)

```bash
ssh trader@192.168.3.204

# Check service status
sudo systemctl status backup-trader

# Check logs for errors
journalctl -u backup-trader -n 200 | grep -i error

# Check if port 8002 is in use
netstat -tuln | grep 8002

# Check Python environment
source ~/crypto-daytrading/venv/bin/activate
python3 --version
pip list | grep fastapi

# Manually start backup for debugging
cd ~/crypto-daytrading
PYTHONPATH=. python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8002 --log-level debug

# In another window, test it
curl http://192.168.3.204:8002/api/health
```

**Option 3: Full Redeploy** (30 minutes)

```bash
# From primary machine
bash scripts/deploy_debian_backup.sh 192.168.3.204 trader 192.168.30.137 8001

# Monitor deployment
watch -n 2 'curl -s http://192.168.3.204:8002/api/health | jq .'
```

### Verification

```bash
# After backup is restored, verify:
python3 scripts/check_ha_status.py --detailed

# Should show:
# - overall_status: HEALTHY
# - primary: ACTIVE
# - backup: STANDBY
# - failover_ready: YES
```

---

## Runbook: Primary is DOWN

**Alert**: 🔴 FAILOVER ACTIVE - Backup has taken over

**Impact**: Production is on backup machine; primary offline

**Response Time**: Immediate verification, recovery within 1 hour

### Decision Tree

```
Is backup trading?
  ├─ YES → Go to "Restore Primary"
  └─ NO  → Go to "Complete Outage"
```

### Verify Backup is Trading

```bash
# On primary machine (if SSH works)
curl http://127.0.0.1:8001/api/health
# Will fail if primary is truly down

# From backup machine
ssh trader@192.168.3.204

# Verify backup is now active
curl http://192.168.3.204:8002/api/redundancy/status | jq .overall_status
# Should show "FAILOVER_ACTIVE"

# Check it's executing trades
curl http://192.168.3.204:8002/api/paper/trades?limit=5

# Check portfolio is updating
curl http://192.168.3.204:8002/api/paper/account | jq .
```

### Restore Primary

**Option 1: Network Issue** (2 minutes)

```bash
# If you lost SSH connectivity to primary:

# Check from other machine
ping 192.168.30.137
ssh -v trader@192.168.30.137 echo "OK"

# If SSH works but API is down:
ssh trader@192.168.30.137

# Check if process is stuck
ps aux | grep uvicorn | grep -v grep

# Restart API
sudo systemctl restart crypto-daytrading

# Verify
curl http://192.168.30.137:8001/api/health
```

**Option 2: API Crashed** (5 minutes)

```bash
ssh trader@192.168.30.137

# Check status
sudo systemctl status crypto-daytrading

# View logs
journalctl -u crypto-daytrading -n 100 -p err

# Clean restart
sudo systemctl stop crypto-daytrading
sleep 2
sudo systemctl start crypto-daytrading

# Wait for startup
sleep 5

# Verify health
curl http://192.168.30.137:8001/api/health
```

**Option 3: Database Connection Issue** (10 minutes)

```bash
ssh trader@192.168.30.137

# Check PostgreSQL
psql -c "SELECT 1"

# If PostgreSQL is down:
sudo systemctl restart postgresql

# Wait for replication to sync
sleep 30

# Restart API
sudo systemctl restart crypto-daytrading

# Verify replication
psql -c "SELECT * FROM pg_stat_replication;"
```

**Option 4: System Overload** (15 minutes)

```bash
ssh trader@192.168.30.137

# Check resources
free -h
df -h /
ps aux --sort=-%mem | head -10

# If low on disk:
sudo journalctl --vacuum=500M
sudo apt clean

# If memory pressure:
ps aux | grep python | grep -v grep
# Kill non-essential processes

# Restart services
sudo systemctl restart crypto-daytrading
```

### Failback to Primary

**Once primary is restored:**

```bash
# From backup machine
ssh trader@192.168.3.204

# Verify primary is back online
curl http://192.168.30.137:8001/api/health

# Stop backup trading
sudo systemctl stop backup-trader

# Wait for it to stop
sleep 5

# Verify backup is now in standby
curl http://192.168.3.204:8002/api/redundancy/status | jq '.overall_status, .backup.role'
```

### Verification

```bash
# From primary machine
python3 scripts/check_ha_status.py --detailed

# Should show:
# - overall_status: HEALTHY
# - primary: ACTIVE
# - backup: STANDBY
```

---

## Runbook: Complete Outage (Both Primary & Backup DOWN)

**Alert**: 🔴 CRITICAL - System is DOWN

**Impact**: All trading stopped; no active trader

**Response Time**: IMMEDIATE

### Immediate Actions

```bash
# Step 1: Assess the situation
echo "Checking both machines..."

# Check primary
if curl -s -m 2 http://127.0.0.1:8001/api/health | grep -q "ok"; then
    echo "✓ Primary is UP"
else
    echo "✗ Primary is DOWN"
fi

# Check backup
if curl -s -m 2 http://192.168.3.204:8002/api/health | grep -q "ok"; then
    echo "✓ Backup is UP"
else
    echo "✗ Backup is DOWN"
fi

# Step 2: Try to SSH to both
echo "Testing SSH connectivity..."
ssh -o ConnectTimeout=5 trader@192.168.30.137 echo "Primary SSH OK" || echo "Primary SSH FAILED"
ssh -o ConnectTimeout=5 trader@192.168.3.204 echo "Backup SSH OK" || echo "Backup SSH FAILED"

# Step 3: Check network
ping -c 2 192.168.30.137
ping -c 2 192.168.3.204
```

### Recovery Priority

**Priority 1: Restore Primary (fastest)**
- Primary is the source of truth
- Backup depends on primary's DB replication
- Start with primary

```bash
ssh trader@192.168.30.137

# Emergency restart
sudo systemctl restart crypto-daytrading

# Monitor startup
watch -n 1 'curl -s http://127.0.0.1:8001/api/health'
```

**Priority 2: Restore Backup (fallback)**
- If primary cannot be restarted
- Manually activate backup as primary

```bash
ssh trader@192.168.3.204

# Set backup to active trading
export TRADING_MODE=live  # if using live mode
export BACKUP_MODE=false  # disable backup mode

# Restart in active mode
sudo systemctl restart backup-trader

# Monitor
watch -n 1 'curl -s http://192.168.3.204:8002/api/health'
```

### Root Cause Analysis

```bash
# Once system is back up, investigate

# 1. Check disk space on both
df -h /

# 2. Check if OOM killer fired
dmesg | tail -20
ssh trader@192.168.3.204 dmesg | tail -20

# 3. Check network issues
journalctl -u systemd-networkd -n 50
ssh trader@192.168.3.204 journalctl -u systemd-networkd -n 50

# 4. Check database
psql -c "SELECT datname, pg_database_size(datname) FROM pg_database ORDER BY pg_database_size DESC;"

# 5. Generate incident report
# Location: docs/incidents/[YYYYMMDD]_outage_report.md
```

---

## Runbook: High Replication Lag

**Alert**: 🔴 Replication lag > 5 seconds

**Impact**: Backup is falling behind primary; failover may lose data

**Response Time**: Within 5 minutes

### Check Current Status

```bash
# Get replication lag
curl http://127.0.0.1:8001/api/redundancy/replication-lag | jq .

# Check PostgreSQL replication details
psql -c "SELECT usename, application_name, state, sync_state, replay_lsn FROM pg_stat_replication;"

# Check network latency
ping -c 10 192.168.3.204 | tail -1

# Check backup database write load
ssh trader@192.168.3.204 psql -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"
```

### Remediation

**Option 1: Check Network** (3 minutes)

```bash
# Test network bandwidth
# (if iperf3 is installed)
iperf3 -s &  # Start server
ssh trader@192.168.3.204 "iperf3 -c 192.168.30.137 -t 10"

# If bandwidth is limited:
# - Check network cables
# - Check switch configuration
# - Restart network interface

# Check for packet loss
mtr -r -c 100 192.168.3.204 | tail -20
```

**Option 2: Check Backup I/O** (5 minutes)

```bash
ssh trader@192.168.3.204

# Check disk I/O
iostat -x 1 5

# Check if backup is running large queries
psql -c "SELECT pid, query FROM pg_stat_activity WHERE state = 'active';"

# Check system load
uptime

# If backup is overloaded:
# - Restart backup to clear buffers
sudo systemctl restart backup-trader
```

**Option 3: Check Primary Throughput** (5 minutes)

```bash
# If primary is writing too fast:

psql -c "SELECT COUNT(*) FROM pg_stat_statements WHERE calls > 1000;"

# Check WAL generation rate
watch -n 1 'pg_controldata /var/lib/postgresql/13/main | grep "WAL"'

# If WAL is growing too fast:
# - Check for any bulk operations
# - Review trade execution volume
# - Check if any background jobs are running
```

### Temporary Workaround

```bash
# If lag persists, temporarily reduce failover readiness
# by adjusting replication threshold

# Edit redundancy.py thresholds
nano backend/api/routers/redundancy.py

# Increase warning/critical thresholds
REPLICATION_LAG_WARNING_THRESHOLD = 3  # was 2
REPLICATION_LAG_CRITICAL_THRESHOLD = 10  # was 5

# Restart API
sudo systemctl restart crypto-daytrading
```

### Monitoring

```bash
# Watch lag trend
watch -n 2 'curl -s http://127.0.0.1:8001/api/redundancy/replication-lag | jq .lag_seconds'

# Should trend downward within 5 minutes
```

---

## Runbook: Failover Not Activating

**Alert**: ⚠️ Primary is DOWN but backup is NOT taking over

**Impact**: System is unresponsive to user actions

**Response Time**: IMMEDIATE

### Quick Diagnosis

```bash
# 1. Confirm primary is actually down
curl http://127.0.0.1:8001/api/health
# Expected: connection refused or timeout

# 2. Confirm backup is up
ssh trader@192.168.3.204 curl http://192.168.3.204:8002/api/health

# 3. Check failover monitor on backup
ssh trader@192.168.3.204 sudo systemctl status failover-monitor

# 4. Check failover monitor logs
ssh trader@192.168.3.204 tail -f ~/crypto-daytrading/logs/failover_monitor.log
```

### Manual Failover Activation

```bash
ssh trader@192.168.3.204

# Option 1: Restart backup in active mode
sudo systemctl set-environment BACKUP_MODE=false
sudo systemctl restart backup-trader

# Option 2: Manually start trading on backup
cd ~/crypto-daytrading
source venv/bin/activate
python3 << 'EOF'
from backend.trading.autonomous_trader import init_autonomous_trader, TradingConfig
from backend.api.main import app

# Force active trading
config = TradingConfig(enabled=True)  # Enable trading
trader = init_autonomous_trader(config)
print("Backup is now trading!")
EOF
```

### Re-enable Failover Monitor

```bash
ssh trader@192.168.3.204

# Check if monitor process is running
ps aux | grep failover_monitor

# If not running, restart it
sudo systemctl restart failover-monitor

# Monitor its activity
journalctl -u failover-monitor -f
```

---

## Incident Response Checklist

After any outage or failover:

- [ ] Document when outage started
- [ ] Document when service was restored
- [ ] Note which component failed (primary/backup/network/DB)
- [ ] Record root cause
- [ ] Identify preventive measure for next time
- [ ] Update relevant runbooks
- [ ] Create incident report: `docs/incidents/[YYYYMMDD]_[name].md`
- [ ] Schedule incident review with team
- [ ] Implement fix or monitoring improvement
- [ ] Close incident

---

## Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| Primary unreachable | Network/API down | `ssh` then `systemctl restart crypto-daytrading` |
| Backup unreachable | Network/Service down | `ssh` then `systemctl restart backup-trader` |
| High replication lag | Network slow or DB overload | Check `iperf3`, check `iostat` |
| System unresponsive | Both down | Manual failover activation |
| Failover not working | Monitor service down | Restart `failover-monitor` |
| Data mismatch | Replication issue | Check PostgreSQL replication status |

---

## Escalation Path

| Level | Condition | Action | ETA |
|-------|-----------|--------|-----|
| L1 | Backup is down | Restart service | 5 min |
| L2 | Primary is down | Restore from backup | 5 min |
| L3 | Both are down | Manual intervention | 15 min |
| L4 | Data corruption | Database recovery | 1 hour |
| Executive | Extended outage | Prepare stakeholder comms | Ongoing |

---

For detailed deployment and monitoring, see:
- [HA_DEPLOYMENT.md](HA_DEPLOYMENT.md) — Setup and configuration
- [HA_MONITORING.md](HA_MONITORING.md) — Monitoring and alerting
