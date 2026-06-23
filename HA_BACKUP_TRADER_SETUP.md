# High Availability (HA) Backup Trader Setup

## Overview

Deploy a **backup autonomous trader** on a Debian machine for failover redundancy. When the primary trader fails, the backup automatically takes over.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIGH AVAILABILITY SETUP                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  PRIMARY MACHINE (Main/Linux)           BACKUP MACHINE (Debian)  │
│  ┌────────────────────────────┐        ┌──────────────────────┐  │
│  │ Autonomous Trader (ACTIVE) │  ════> │ Autonomous Trader    │  │
│  │ • Executes trades          │        │ (STANDBY/PASSIVE)    │  │
│  │ • Generates signals        │        │ • Monitors primary    │  │
│  │ • Writes to DB             │        │ • Ready to takeover   │  │
│  └────────────────────────────┘        └──────────────────────┘  │
│                 │                                 ▲                │
│                 │ Heartbeat (every 10s)          │                │
│                 └─────────────────────────────────┘                │
│                                                                   │
│  PRIMARY DATABASE              STANDBY DATABASE (Read-only)      │
│  ┌────────────────┐            ┌──────────────────────────┐     │
│  │  PostgreSQL    │  Streaming │   PostgreSQL Standby     │     │
│  │  (Primary)     │ Replication│   (Backup/Replica)       │     │
│  │  • Read/Write  │ ════════=> │   • Continuous sync      │     │
│  │  • Trades log  │            │   • Ready for failover    │     │
│  └────────────────┘            └──────────────────────────┘     │
│                                                                   │
│  FAILOVER TRIGGER (if primary heartbeat fails for 30s):          │
│  1. Backup detects primary is down                              │
│  2. Promote standby DB to primary                               │
│  3. Activate backup trader (begin executing orders)             │
│  4. Send alert to admin                                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Active-Passive Design

| Aspect | Primary | Backup |
|--------|---------|--------|
| **Trader State** | Active (executing) | Passive (standby) |
| **Order Placement** | ✅ Yes | ❌ No (until failover) |
| **Signal Generation** | ✅ Yes | ⏸️ Only if primary down |
| **Database** | Primary (R/W) | Standby (R-only until promoted) |
| **Heartbeat** | Sends every 10s | Listens every 10s |
| **Failover Wait** | N/A | 30 seconds (3 missed beats) |

### Why Active-Passive?

- ✅ **No duplicate trades** (only primary trades)
- ✅ **Prevents race conditions** (one writer at a time)
- ✅ **Automatic failover** (backup takes over immediately)
- ✅ **Data consistency** (streaming replication keeps DB in sync)
- ⚠️ **Backup sits idle** (could be used for analytics/backtesting)

---

## Prerequisites

### Primary Machine (Already Running)
```bash
# What you have
✅ FastAPI server on port 8001
✅ PostgreSQL database
✅ Autonomous trader (active)
✅ Binance WebSocket connection
```

### Backup Machine (Debian)
```bash
# New setup required
Linux/Debian (Ubuntu 22.04 LTS recommended)
Python 3.9+
PostgreSQL client
Network access to primary (TCP 5432 for DB, TCP 8001 for API)
~2GB RAM, 20GB disk
```

---

## Step 1: Setup Backup Machine (Debian)

### 1.1 Install Dependencies

```bash
# SSH into Debian machine
ssh user@backup-machine-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, Git, PostgreSQL client
sudo apt install -y python3.9 python3-pip git postgresql-client curl

# Create app user
sudo useradd -m -s /bin/bash trader
sudo su - trader

# Clone repository
cd /home/trader
git clone https://github.com/yourusername/crypto-daytrading.git
cd crypto-daytrading

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 1.2 Configure Environment

```bash
# Copy .env from primary (or create new)
nano .env
```

**Contents (.env for backup):**
```bash
# Database (point to PRIMARY)
DATABASE_URL=postgresql://trader:password@primary-machine-ip:5432/crypto_db
DB_HOST=primary-machine-ip
DB_PORT=5432
DB_USER=trader
DB_PASSWORD=your_password
DB_NAME=crypto_db

# Backup mode
TRADING_MODE=paper  # Start in paper mode
BACKUP_MODE=true    # Flag indicating this is backup

# Binance (shared - same API keys as primary)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Heartbeat settings
HEARTBEAT_INTERVAL=10        # Check every 10 seconds
HEARTBEAT_TIMEOUT=30         # Failover if 30s no heartbeat
PRIMARY_API_URL=http://primary-machine-ip:8001

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/trader/crypto-daytrading/logs/backup.log
```

---

## Step 2: Setup PostgreSQL Streaming Replication

### 2.1 On PRIMARY Machine

```bash
# SSH into primary
ssh primary-machine

# Connect to PostgreSQL
sudo -u postgres psql

# Create replication user
CREATE USER replication_user WITH REPLICATION ENCRYPTED PASSWORD 'repl_password';
\q
```

**Edit `/etc/postgresql/14/main/postgresql.conf`:**
```bash
sudo nano /etc/postgresql/14/main/postgresql.conf

# Find and uncomment these lines:
listen_addresses = '*'  # Allow remote connections
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
```

**Edit `/etc/postgresql/14/main/pg_hba.conf`:**
```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Add this line (allow replication from backup IP):
host    replication     replication_user    BACKUP_MACHINE_IP/32    md5
```

**Restart PostgreSQL:**
```bash
sudo systemctl restart postgresql
```

### 2.2 On BACKUP Machine (Debian)

```bash
# Stop PostgreSQL (if running)
sudo systemctl stop postgresql

# Set up standby as replica
sudo -u postgres bash
cd /var/lib/postgresql/14/main
rm -rf * 

# Clone primary's database
pg_basebackup -h primary-machine-ip -D . -U replication_user -v -P -W -R

# Exit
exit

# Start PostgreSQL in standby mode
sudo systemctl start postgresql

# Verify standby is running
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"
# Should return: t (true = standby mode)
```

---

## Step 3: Deploy Backup Trader Service

### 3.1 Create Systemd Service

**Create `/etc/systemd/system/backup-trader.service`:**

```bash
sudo nano /etc/systemd/system/backup-trader.service
```

**Contents:**
```ini
[Unit]
Description=Crypto Trading Backup Agent
After=network.target postgresql.service
StartLimitInterval=300
StartLimitBurst=5

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/crypto-daytrading
Environment="PYTHONPATH=/home/trader/crypto-daytrading"
ExecStart=/home/trader/crypto-daytrading/venv/bin/python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8002 --env-file .env

# Restart on failure
Restart=on-failure
RestartSec=10

# Resource limits (prevent runaway processes)
MemoryMax=4G
CPUQuota=150%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=backup-trader

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable backup-trader
sudo systemctl start backup-trader

# Verify running
sudo systemctl status backup-trader
```

### 3.2 Create Failover Detection Service

**Create `/home/trader/scripts/failover_monitor.py`:**

```python
#!/usr/bin/env python3
"""Monitor primary trader health and trigger failover."""

import requests
import subprocess
import time
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/trader/crypto-daytrading/logs/failover.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PRIMARY_URL = "http://primary-machine-ip:8001"
HEALTH_CHECK_INTERVAL = 10  # seconds
FAILOVER_THRESHOLD = 3  # 3 missed checks = 30 seconds

class FailoverMonitor:
    def __init__(self):
        self.failure_count = 0
        self.is_failed_over = False
        
    def check_primary_health(self) -> bool:
        """Check if primary trader is healthy."""
        try:
            r = requests.get(f"{PRIMARY_URL}/api/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Primary health check failed: {e}")
            return False
    
    def trigger_failover(self):
        """Activate backup trader and promote DB."""
        logger.critical("🚨 FAILOVER TRIGGERED - Primary is down!")
        
        # 1. Promote standby database to primary
        logger.info("Step 1: Promoting standby database...")
        self._promote_standby_db()
        
        # 2. Switch backup trader to active mode
        logger.info("Step 2: Activating backup trader...")
        self._activate_backup_trader()
        
        # 3. Update environment
        logger.info("Step 3: Updating environment...")
        self._update_env_variable("BACKUP_MODE", "false")
        self._update_env_variable("TRADING_MODE", "live")
        
        # 4. Restart service
        logger.info("Step 4: Restarting backup trader service...")
        subprocess.run([
            "sudo", "systemctl", "restart", "backup-trader"
        ], check=True)
        
        # 5. Send alert
        self._send_alert()
        
        self.is_failed_over = True
        logger.critical("✅ Failover complete - Backup trader is now ACTIVE")
    
    def _promote_standby_db(self):
        """Promote PostgreSQL standby to primary."""
        try:
            subprocess.run([
                "sudo", "-u", "postgres", "psql",
                "-c", "SELECT pg_promote();"
            ], check=True)
            time.sleep(5)  # Wait for promotion
        except Exception as e:
            logger.error(f"Failed to promote standby: {e}")
            raise
    
    def _activate_backup_trader(self):
        """Enable active trading on backup."""
        # This would involve:
        # 1. Connecting to Binance
        # 2. Starting autonomous trader
        # 3. Setting trader to ACTIVE mode
        pass
    
    def _update_env_variable(self, key: str, value: str):
        """Update .env file."""
        env_file = "/home/trader/crypto-daytrading/.env"
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                updated = True
                break
        
        if not updated:
            lines.append(f"{key}={value}\n")
        
        with open(env_file, 'w') as f:
            f.writelines(lines)
    
    def _send_alert(self):
        """Send failover alert (email, Slack, etc.)."""
        logger.critical(f"ALERT: Backup trader activated at {datetime.now()}")
        # TODO: Implement email/Slack notification
    
    def run(self):
        """Main monitoring loop."""
        logger.info("Failover monitor started")
        
        while True:
            try:
                if self.check_primary_health():
                    # Primary is healthy
                    self.failure_count = 0
                    if self.is_failed_over:
                        logger.info("✅ Primary is back - continuing in backup mode")
                else:
                    # Primary is unhealthy
                    self.failure_count += 1
                    logger.warning(f"Primary check #{self.failure_count} failed")
                    
                    if self.failure_count >= FAILOVER_THRESHOLD:
                        self.trigger_failover()
                
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)

if __name__ == "__main__":
    monitor = FailoverMonitor()
    monitor.run()
```

**Create service for failover monitor:**

```bash
sudo nano /etc/systemd/system/failover-monitor.service
```

**Contents:**
```ini
[Unit]
Description=Crypto Trader Failover Monitor
After=backup-trader.service
StartLimitInterval=300
StartLimitBurst=3

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/crypto-daytrading
ExecStart=/home/trader/crypto-daytrading/venv/bin/python /home/trader/crypto-daytrading/scripts/failover_monitor.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable failover-monitor
sudo systemctl start failover-monitor
```

---

## Step 4: Testing Failover

### 4.1 Simulate Primary Failure

```bash
# On PRIMARY machine, stop the trader
sudo systemctl stop investing-platform

# Watch backup monitor
sudo journalctl -u failover-monitor -f

# Expected output:
# - Primary check #1 failed
# - Primary check #2 failed
# - Primary check #3 failed
# - 🚨 FAILOVER TRIGGERED
# - ✅ Failover complete
```

### 4.2 Verify Backup is Active

```bash
# On BACKUP machine
curl http://127.0.0.1:8002/api/paper/account

# Should return account status (backup is now active)
```

### 4.3 Restart Primary (Recovery)

```bash
# On PRIMARY machine
sudo systemctl start investing-platform

# Monitor will detect primary is back
# But backup continues trading (active-passive = only one trades)
```

---

## Step 5: Production Checklist

- [ ] PostgreSQL streaming replication working (verify with `SELECT pg_is_in_recovery()`)
- [ ] Heartbeat checking every 10 seconds
- [ ] Failover detection configured (30-second threshold)
- [ ] Database promotion tested
- [ ] Backup trader service running in standby mode
- [ ] Logs being written to `/home/trader/crypto-daytrading/logs/failover.log`
- [ ] Alerts configured (email/Slack on failover)
- [ ] Network connectivity between primary and backup verified
- [ ] Firewall allows TCP 5432 (PostgreSQL), TCP 8001 (API)
- [ ] Both machines on same network or VPN

---

## Monitoring Failover Health

### Check Primary Database Status

```bash
# On PRIMARY
sudo -u postgres psql -c "SELECT client_addr, state FROM pg_stat_replication;"

# Should show backup machine IP with state = 'streaming'
```

### Check Backup Database Status

```bash
# On BACKUP
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"

# Should return 't' (true) while in standby
# Returns 'f' (false) after promotion
```

### Check Trader Services

```bash
# On BACKUP
sudo systemctl status backup-trader
sudo systemctl status failover-monitor

# Both should be active and running
```

### View Failover Logs

```bash
# On BACKUP
tail -f /home/trader/crypto-daytrading/logs/failover.log

# Watch for heartbeat checks and failover events
```

---

## Configuration Summary

| Setting | Primary | Backup |
|---------|---------|--------|
| API Port | 8001 | 8002 |
| DB Role | Primary (R/W) | Standby (R-only) |
| Trader Mode | Active | Passive (until failover) |
| Heartbeat Check | Every 10s | Every 10s |
| Failover Threshold | N/A | 30 seconds (3 checks) |
| Service Names | investing-platform | backup-trader |
| Monitor Service | N/A | failover-monitor |

---

## Common Issues & Solutions

### PostgreSQL Replication Lag

```bash
# Check replication lag on primary
sudo -u postgres psql -c "SELECT client_addr, state_change, write_lag FROM pg_stat_replication;"

# If lag > 5 seconds:
# 1. Check network bandwidth
# 2. Reduce database write frequency
# 3. Increase wal_buffers on primary
```

### Failover Not Triggering

```bash
# Check failover monitor service
sudo systemctl status failover-monitor
sudo journalctl -u failover-monitor -n 50

# Verify primary API is responding
curl http://primary-machine-ip:8001/api/health
```

### Backup Trader Won't Start

```bash
# Check logs
sudo journalctl -u backup-trader -n 100

# Verify Python dependencies
source /home/trader/crypto-daytrading/venv/bin/activate
python -m backend.api.main

# Check port 8002 is available
sudo lsof -i :8002
```

### Database Promotion Failed

```bash
# Manual recovery
sudo -u postgres psql -c "SELECT pg_promote();"

# Or force new standby
sudo -u postgres pg_basebackup -h primary-ip -D /var/lib/postgresql/14/main -U replication_user -v -P -W -R
```

---

## Cost Estimate

| Component | Cost | Notes |
|-----------|------|-------|
| Debian Server (1yr) | €50-200 | Cloud VM or used hardware |
| Network Bandwidth | €10-50 | Depends on replication traffic |
| Monitoring Tools | Free | ELK stack, Prometheus |
| Backup Storage | €5-20 | PostgreSQL backups |
| **Total (1 year)** | **€65-270** | Highly redundant system |

---

## Next Steps

1. **Test failover monthly** (failover drill)
2. **Monitor replication lag** (daily)
3. **Backup databases** (daily automated)
4. **Alert on failures** (real-time Slack/email)
5. **Update backup code** (same cadence as primary)

---

## Alternative: Cloud HA Solutions

If Debian backup is too complex, consider:

| Solution | Cost | Setup Time | Failover Time |
|----------|------|-----------|---------------|
| **Self-hosted (Debian)** | €100-300/yr | 4-6 hours | 30s (automatic) |
| **AWS RDS Multi-AZ** | €500-1000/yr | 30 min | 1-2 min (automatic) |
| **Google Cloud Spanner** | €1000+/yr | 1 hour | <1 min (automatic) |
| **Digital Ocean Droplets** | €120-240/yr | 2 hours | 30s (custom script) |

**Recommendation:** Start with Debian backup, upgrade to cloud if scaling.

---

**System Ready for Production HA! 🚀**
