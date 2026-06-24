# High Availability Deployment Guide

## Architecture Overview

**Active-Passive Redundancy** — Two trading instances with automatic failover:
- **Primary (Main Machine)**: Actively executes trades, generates signals, writes to database
- **Backup (Debian Machine)**: Monitors primary, maintains read-only copy, auto-failovers within 30 seconds

```
PRIMARY (192.168.30.137:8001)  ←─ Heartbeat (10s interval) ─→  BACKUP (192.168.3.204:8002)
  ├─ Active trading                                               ├─ Standby mode
  ├─ DB writes                                                    ├─ Read-only analytics
  └─ Signals                                                      └─ Failover monitor
```

## Deployment Steps

### Phase 1: Prerequisites

Ensure both machines have:
- Python 3.9+
- PostgreSQL client (for replication)
- Git access to repository
- SSH key-based auth between machines
- Network connectivity on port 8001-8002

### Phase 2: Deploy Backup Machine

```bash
# On primary machine:
bash scripts/deploy_debian_backup.sh 192.168.3.204 trader 192.168.30.137 8001
```

This script automates:
1. SSH connectivity verification
2. Dependency installation (Python, PostgreSQL, etc.)
3. Repository cloning
4. Python venv setup
5. Environment configuration
6. Systemd service creation for backup trader
7. Failover monitor setup
8. Health checks

### Phase 3: Verify Deployment

**Check backup trader is running:**
```bash
curl http://192.168.3.204:8002/api/health
```

**Monitor failover status:**
```bash
curl http://127.0.0.1:8001/api/redundancy/status | jq .
```

**Check replication lag:**
```bash
curl http://127.0.0.1:8001/api/redundancy/replication-lag | jq .
```

## Architecture Details

### Health Check System

**Interval**: Every 10 seconds
**Threshold**: 3 consecutive failures = 30-second failover timeout
**Endpoints**:
- `/api/health` — Basic liveness check
- `/api/redundancy/status` — Full redundancy status
- `/api/redundancy/primary/health` — Primary-specific health
- `/api/redundancy/backup/health` — Backup-specific health

### Failover Mechanism

**Automatic failover triggers when:**
1. Primary `/api/health` returns non-200 for 30 seconds
2. Backup confirms availability
3. Backup has matching trading config

**Backup activation:**
1. Stops standby instance
2. Initializes autonomous trader in active mode
3. Resumes trading with same signals & risk parameters
4. Updates portfolio from database

**Manual failback (when primary recovers):**
```bash
# Stop backup trader
ssh trader@192.168.3.204 sudo systemctl stop backup-trader

# Restart primary
sudo systemctl restart crypto-daytrading
```

### Data Consistency

**PostgreSQL Streaming Replication**:
- Primary → Backup continuous WAL streaming
- Backup applies all changes asynchronously
- Replication lag monitored at `/api/redundancy/replication-lag`

**Order Deduplication**:
- Each order assigned UUID at primary
- Backup inherits order IDs from DB
- Prevents duplicate trades during failover

**Risk Parameters**:
- Synchronized via API before failover
- Backup reads from same DB (replication)
- Config version checked before activation

## Monitoring & Alerts

### API Endpoints

**Redundancy Status (comprehensive)**:
```bash
curl http://127.0.0.1:8001/api/redundancy/status
```

Returns:
- Overall status: HEALTHY, DEGRADED, FAILOVER_ACTIVE, DOWN
- Primary & backup role and health
- Replication lag & status
- Failover readiness

**Replication Lag**:
```bash
curl http://127.0.0.1:8001/api/redundancy/replication-lag
```

Status levels:
- ✅ HEALTHY: < 2 seconds
- ⚠️ WARNING: 2–5 seconds
- 🔴 CRITICAL: > 5 seconds

**Failover Readiness**:
```bash
curl http://127.0.0.1:8001/api/redundancy/failover/ready
```

**Configuration**:
```bash
curl http://127.0.0.1:8001/api/redundancy/config
```

### Real-Time Dashboard

The unified dashboard at `http://127.0.0.1:8001/` includes:
- **HA Status Card**: Primary/backup status, failover readiness
- **Replication Lag Graph**: Real-time replication lag monitoring
- **Failover Timeline**: History of failover events
- **Health Check History**: Last 50 health checks per service

## Testing HA

### Automated Test Suite

```bash
# Run comprehensive HA tests
python3 -m pytest tests/integration/test_ha_failover.py -v

# Specific tests:
python3 -m pytest tests/integration/test_ha_failover.py::TestHAStrategyConsistency::test_primary_and_backup_generate_same_signals -v
```

### Manual Failover Test

**Simulate primary failure:**
```bash
# Terminal 1: Watch backup
ssh trader@192.168.3.204 journalctl -u failover-monitor -f

# Terminal 2: Watch primary
journalctl -u crypto-daytrading -f

# Terminal 3: Stop primary
sudo systemctl stop crypto-daytrading

# Observe: Backup takes over within 30 seconds
# Terminal 3: Monitor failover
watch -n 1 'curl -s http://127.0.0.1:8001/api/redundancy/status | jq .overall_status'

# Restart primary
sudo systemctl start crypto-daytrading
```

### Load Test HA

```bash
# Test failover under trading load
python3 scripts/test_failover_load.py \
  --primary http://192.168.30.137:8001 \
  --backup http://192.168.3.204:8002 \
  --trades-per-second 10 \
  --duration 300
```

## Production Hardening

### Environment Variables

Set on both primary and backup:

```bash
# .env
PRIMARY_API_URL=http://192.168.30.137:8001
BACKUP_API_URL=http://192.168.3.204:8002
BACKUP_MODE=true  # Only on backup
FAILOVER_THRESHOLD=3
HEALTH_CHECK_INTERVAL=10
REPLICATION_LAG_WARNING=2
REPLICATION_LAG_CRITICAL=5
```

### Systemd Services

**Primary** (`/etc/systemd/system/crypto-daytrading.service`):
```ini
[Unit]
Description=Crypto Trading Bot - Primary
After=network-online.target postgresql.service

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/crypto-daytrading
ExecStart=/home/trader/crypto-daytrading/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=10
MemoryMax=8G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

**Backup** (deployed via `deploy_debian_backup.sh`):
```ini
[Unit]
Description=Crypto Trading Bot - Backup
After=network-online.target

[Service]
Type=simple
User=trader
Environment="BACKUP_MODE=true"
ExecStart=/home/trader/crypto-daytrading/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8002
Restart=on-failure
RestartSec=10
MemoryMax=4G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

**Failover Monitor** (backup machine):
```ini
[Unit]
Description=Failover Monitor
After=backup-trader.service

[Service]
Type=simple
User=trader
ExecStart=/home/trader/crypto-daytrading/venv/bin/python /home/trader/crypto-daytrading/scripts/failover_monitor.py 192.168.30.137 8001
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Database Replication Setup

**On primary** (PostgreSQL):
```sql
-- Create replication user
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'secure_password';

-- Grant permissions
GRANT CONNECT ON DATABASE crypto_db TO replicator;
```

**postgresql.conf** (primary):
```ini
wal_level = replica
max_wal_senders = 10
wal_keep_size = 1GB
hot_standby = on
```

**pg_hba.conf** (primary):
```
host    replication     replicator      192.168.3.204/32        md5
```

**On backup** (PostgreSQL):
```bash
# Stop backup PostgreSQL
sudo systemctl stop postgresql

# Init replication
pg_basebackup -h 192.168.30.137 -D /var/lib/postgresql/13/main -U replicator -v -P -W

# Create recovery.conf
sudo tee /var/lib/postgresql/13/main/recovery.conf << EOF
standby_mode = 'on'
primary_conninfo = 'host=192.168.30.137 port=5432 user=replicator password=secure_password'
EOF

# Start backup
sudo systemctl start postgresql
```

## Troubleshooting

### Backup shows as DOWN

```bash
# Check backup service status
ssh trader@192.168.3.204 sudo systemctl status backup-trader

# View backup logs
ssh trader@192.168.3.204 journalctl -u backup-trader -n 50

# Test direct connection
curl -v http://192.168.3.204:8002/api/health
```

### Replication lag is HIGH

```bash
# Check PostgreSQL replication status
psql -c "SELECT * FROM pg_stat_replication;"

# Monitor WAL sender/receiver
ssh trader@192.168.3.204 psql -c "SELECT * FROM pg_stat_wal_receiver;"

# Check network latency
ping -c 5 192.168.3.204
iperf3 -c 192.168.3.204  # If iperf3 installed
```

### Failover won't activate

1. Verify backup is healthy: `curl http://192.168.3.204:8002/api/health`
2. Check failover monitor is running: `ssh trader@192.168.3.204 systemctl status failover-monitor`
3. Verify network path: `ssh trader@192.168.3.204 ping 192.168.30.137`
4. Check primary is actually down: `curl http://192.168.30.137:8001/api/health`

### Manual failover activation (emergency)

```bash
# On backup machine
ssh trader@192.168.3.204
cd crypto-daytrading
source venv/bin/activate

# Set to active trading mode
export BACKUP_MODE=false
export TRADING_MODE=live

# Restart backup trader
sudo systemctl restart backup-trader

# Monitor takeover
journalctl -u backup-trader -f
```

## Monitoring Checklist

Daily:
- ✅ Check `/api/redundancy/status` returns HEALTHY or DEGRADED
- ✅ Verify replication lag < 2 seconds
- ✅ Confirm backup failover readiness = true

Weekly:
- ✅ Run failover simulation: `curl -X POST http://127.0.0.1:8001/api/redundancy/failover/simulate`
- ✅ Review failover logs on backup
- ✅ Test manual failover in sandbox environment

Monthly:
- ✅ Execute full failover drill (stop primary, observe backup takeover, restart primary)
- ✅ Verify data consistency between primary and backup
- ✅ Update runbooks based on lessons learned

## Next Steps

1. **Deploy backup machine** → Run deployment script
2. **Verify connectivity** → Test health endpoints
3. **Run test suite** → Execute HA tests
4. **Monitor production** → Check status daily
5. **Practice failover** → Monthly drills

Questions? Check the logs:
- Primary: `journalctl -u crypto-daytrading -f`
- Backup: `ssh trader@192.168.3.204 journalctl -u backup-trader -f`
- Failover: `ssh trader@192.168.3.204 tail -f ~/crypto-daytrading/logs/failover_monitor.log`
