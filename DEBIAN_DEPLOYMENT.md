# Debian Backup Trader Deployment Guide

## Overview

Deploy the crypto daytrading bot to a Debian backup machine with **automatic failover** support. The backup trader will:
- Monitor the primary machine's health every 10 seconds
- Automatically activate if primary goes down
- Preserve all trading strategy and risk parameters
- Share the same Binance API credentials

```
PRIMARY MACHINE (Active)              DEBIAN BACKUP (Standby)
┌──────────────────────┐             ┌──────────────────────┐
│ Crypto Daytrading    │──heartbeat──→ Failover Monitor      │
│ Port 8001            │  (every 10s) │ Monitors health      │
│ • Executes trades    │             │                      │
│ • Generates signals  │             │ On failure (30s):    │
│ • Manages positions  │             │ • Promotes to active │
└──────────────────────┘             │ • Starts trading     │
         ▲                            │ • Continues strategy │
         │                            └──────────────────────┘
         │                                      ▲
         └──────── Active-Passive ─────────────┘
              (Only one trades at a time)
```

---

## Quick Start (3 steps)

### 1. Prepare your Debian machine

```bash
# Ensure Debian machine is accessible via SSH
ssh trader@192.168.3.204 echo "OK"
# Output: OK

# Note the IP address and username
```

### 2. Run the deployment script

```bash
cd /home/vali/projects/crypto-daytrading

# Option 1: Use defaults (update script first!)
./scripts/deploy_debian_backup.sh

# Option 2: Specify parameters
./scripts/deploy_debian_backup.sh \
  192.168.3.204 \
  trader \
  192.168.30.137 \
  8001
```

**Parameters:**
```
$1: Debian machine IP (default: 192.168.3.204)
$2: SSH username (default: trader)
$3: Primary machine IP (default: 192.168.30.137)
$4: Primary API port (default: 8001)
```

### 3. Verify deployment

```bash
# Check backup trader is running
curl http://192.168.3.204:8002/api/health

# Expected response:
{
  "status": "ok",
  "mode": "paper",
  "websocket": {"connected": true},
  "paper_trading": {
    "mode": "PAPER",
    "cash": 100000,
    "total_equity": 100000,
    "active_positions": 0
  }
}
```

---

## What Gets Deployed

### Services

1. **backup-trader.service** (Port 8002)
   - Runs the crypto daytrading bot
   - Starts in STANDBY mode (not trading)
   - Activates automatically on primary failure

2. **failover-monitor.service**
   - Monitors primary health every 10 seconds
   - Triggers failover after 3 failed checks (30 seconds)
   - Logs all failover events

3. **resource-monitor.service** (optional)
   - Monitors CPU, RAM, disk on Debian
   - Auto-stops backup if resources get low
   - Protects the system from resource exhaustion

### Files

```
/home/trader/crypto-daytrading/
├── .env                                # Backup configuration
├── scripts/
│   ├── failover_monitor.py            # Failover detection
│   └── resource_monitor.py            # Resource protection
├── backend/                            # Core trading logic
├── frontend/                           # Web interface
└── logs/
    └── failover_monitor.log           # Failover events
```

### Configuration

**/.env (on backup machine)**
```bash
BINANCE_TESTNET=false
API_PORT=8002              # Backup uses port 8002
BACKUP_MODE=true           # Flag as backup
TRADING_MODE=paper         # Start in paper trading
PRIMARY_API_URL=http://primary-ip:8001
HEARTBEAT_INTERVAL=10      # Check every 10 seconds
```

---

## Monitoring

### Real-time logs

```bash
# Backup trader activity
ssh trader@192.168.3.204 journalctl -u backup-trader -f

# Failover monitor events
ssh trader@192.168.3.204 journalctl -u failover-monitor -f

# Resource monitor alerts
ssh trader@192.168.3.204 journalctl -u resource-monitor -f
```

### Service status

```bash
# Check if backup trader is running
ssh trader@192.168.3.204 sudo systemctl status backup-trader

# Check if failover monitor is running
ssh trader@192.168.3.204 sudo systemctl status failover-monitor

# Check if both are ready
curl http://192.168.3.204:8002/api/health
```

### Failover detection

```bash
# View failover monitor logs
ssh trader@192.168.3.204 tail -f ~/crypto-daytrading/logs/failover_monitor.log

# Expected output (when healthy):
# [timestamp] INFO - Primary healthy - backup in standby
# [timestamp] INFO - Primary healthy - backup in standby
# ...

# When primary fails:
# [timestamp] WARNING - Primary check #1 failed
# [timestamp] WARNING - Primary check #2 failed
# [timestamp] WARNING - Primary check #3 failed
# [timestamp] CRITICAL - 🚨 FAILOVER TRIGGERED - Primary is down!
# [timestamp] CRITICAL - ✅ Backup trader is now ACTIVE
```

---

## Testing Failover

### Manual failover test

```bash
# Step 1: Start the test
ssh trader@192.168.3.204 \
  tail -f ~/crypto-daytrading/logs/failover_monitor.log &

# Step 2: Stop primary trader
sudo systemctl stop crypto-daytrading

# Step 3: Watch for failover in logs
# Should see "FAILOVER TRIGGERED" within 30 seconds

# Step 4: Verify backup is now active
curl http://192.168.3.204:8002/api/paper/account

# Step 5: Check trading (should show active positions if any)
curl http://192.168.3.204:8002/api/paper/positions

# Step 6: Restart primary
sudo systemctl start crypto-daytrading

# Step 7: Verify recovery
curl http://192.168.30.137:8001/api/health
```

### Expected sequence

```
Time    Primary         Failover Monitor        Backup Trader
────────────────────────────────────────────────────────────
00:00   Running         Check #1 PASS           Standby
00:10   Running         Check #2 PASS           Standby
00:20   Running         Check #3 PASS           Standby
...
10:00   STOP (failure)  Check #1 FAIL           Standby
10:10   Down            Check #2 FAIL           Standby
10:20   Down            Check #3 FAIL           Standby
10:25   Down            🚨 FAILOVER!            ACTIVE ✅
10:26   Down            Monitoring              Trading
...
12:00   START (recovery)Check #1 PASS           Trading
12:10   Running         Check #2 PASS           Trading
12:20   Running         Check #3 PASS           Trading
```

---

## Architecture Details

### Active-Passive Design

**Why not active-active?**
- Prevents duplicate trades
- Eliminates race conditions
- Simpler to debug and maintain
- Only primary executes orders
- Backup inherits all positions on promotion

**Failover flow:**
1. Primary sends heartbeat → `/api/health`
2. Backup listens (every 10 seconds)
3. If 3 checks fail → assume primary is dead
4. Backup: `systemctl stop backup-trader`
5. Backup: `systemctl start backup-trader` (active mode)
6. Backup starts executing trades
7. All subsequent signals processed by backup
8. When primary returns, backup continues (or manual intervention)

### Database Considerations

Currently using **paper trading** (no real database). If you add PostgreSQL:

```bash
# Primary: Configure streaming replication
# Backup: Set up as standby (read-only)
# Failover: pg_promote() on backup DB
# Result: Zero data loss, point-in-time recovery
```

See `HA_BACKUP_TRADER_SETUP.md` for PostgreSQL streaming replication setup.

---

## Troubleshooting

### Backup won't start

```bash
# Check logs
ssh trader@192.168.3.204 journalctl -u backup-trader -n 50

# Verify port 8002 is available
ssh trader@192.168.3.204 sudo lsof -i :8002

# Test manually
ssh trader@192.168.3.204 \
  "cd ~/crypto-daytrading && source venv/bin/activate && python -m backend.api.main"
```

### Failover not triggering

```bash
# Check failover monitor service
ssh trader@192.168.3.204 sudo systemctl status failover-monitor

# Verify monitor can reach primary
ssh trader@192.168.3.204 curl http://192.168.30.137:8001/api/health

# Check firewall
ssh trader@192.168.3.204 sudo ufw status
# Should show: Allow 192.168.30.137 8001

# Manually trigger for testing
ssh trader@192.168.3.204 \
  "sudo systemctl stop backup-trader && sleep 2 && sudo systemctl start backup-trader"
```

### High latency or lag

```bash
# Check network connectivity
ping 192.168.3.204
ping 192.168.30.137

# Test API response times
time curl http://192.168.3.204:8002/api/health

# Monitor resource usage on backup
ssh trader@192.168.3.204 top -b -n 1 | head -20
```

### Memory or CPU issues

```bash
# Check resource monitor
ssh trader@192.168.3.204 journalctl -u resource-monitor -n 30

# View current usage
ssh trader@192.168.3.204 free -h
ssh trader@192.168.3.204 top -b -n 1

# If resources low, check what's consuming
ssh trader@192.168.3.204 ps aux | sort -k 3 -nr | head
```

---

## Post-Deployment Checklist

- [ ] Both machines on same network or VPN
- [ ] Firewall allows TCP 8001 and 8002 between machines
- [ ] SSH keys configured for password-less access
- [ ] Backup trader responds at `http://backup-ip:8002/api/health`
- [ ] Failover monitor logs show "Primary healthy - backup in standby"
- [ ] Resource monitor is running (if enabled)
- [ ] Both machines have correct time sync (NTP)
- [ ] Monitoring dashboard set up
- [ ] Alerts configured for failover events
- [ ] Tested manual failover at least once

---

## Security Notes

### Network access

- Limit firewall rules to just what's needed:
  ```bash
  # Backup machine: Allow primary to send heartbeat
  sudo ufw allow from 192.168.30.137 to any port 8002
  
  # Primary machine: Allow backup to check health
  sudo ufw allow from 192.168.3.204 to any port 8001
  ```

### Credentials

- ✅ Same Binance API keys on both machines (intentional)
- ✅ `.env` files contain same config (intentional)
- ✅ Active-passive prevents duplicate orders (safe)
- ❌ Never expose API ports to internet
- ❌ Keep `.env` files restricted (chmod 600)

### Data protection

- Use VPN or SSH tunnel if machines over internet
- Enable HTTPS for API if exposed
- Implement IP whitelisting
- Regular backups of trading database

---

## Maintenance

### Weekly

```bash
# Check failover monitor health
ssh trader@192.168.3.204 \
  tail -100 ~/crypto-daytrading/logs/failover_monitor.log | grep -i error

# Verify replication lag (if using PostgreSQL)
ssh trader@192.168.3.204 \
  "sudo -u postgres psql -c 'SELECT * FROM pg_stat_replication;'"
```

### Monthly

```bash
# Run failover drill
sudo systemctl stop crypto-daytrading
sleep 35
curl http://192.168.3.204:8002/api/health  # Should be active
sudo systemctl start crypto-daytrading
sleep 5
curl http://192.168.30.137:8001/api/health  # Should be back
```

### Quarterly

```bash
# Update both machines
git pull origin master
pip install -r requirements.txt
sudo systemctl restart backup-trader
sudo systemctl restart failover-monitor
```

---

## Cost Estimate

| Item | Cost | Notes |
|------|------|-------|
| Debian VM (1yr) | €50-200 | Cloud or used hardware |
| Network bandwidth | €10-50 | Depends on traffic |
| Monitoring | Free | ELK stack, Prometheus |
| Storage backups | €5-20 | PostgreSQL snapshots |
| **Total** | **€65-270** | Highly redundant |

---

## Support

**Questions or issues?**

1. Check logs: `journalctl -u failover-monitor -n 100`
2. Test connectivity: `curl http://backup-ip:8002/api/health`
3. Review failover monitor: `tail -f ~/crypto-daytrading/logs/failover_monitor.log`

---

**Deployment ready! 🚀**
