# Resource Monitoring: Auto-Stop Sentinel Bot When Resources Low

## Overview

Automatically **stop the Sentinel Bot (backup trader)** on Debian if system resources run low. This prevents the backup system from interfering with the primary machine and protects against resource exhaustion.

```
┌─────────────────────────────────────────────────────┐
│        RESOURCE MONITOR (Debian Backup)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Every 10 seconds:                                  │
│  1. Check CPU usage                                 │
│  2. Check RAM available                             │
│  3. Check disk space                                │
│  4. Compare to thresholds                           │
│                                                      │
│  If threshold exceeded:                             │
│  ├─ STOP backup-trader service                     │
│  ├─ STOP failover-monitor service                  │
│  ├─ Log reason + timestamp                         │
│  └─ Send alert (email/Slack)                       │
│                                                      │
│  When resources recover:                            │
│  ├─ START failover-monitor service                 │
│  ├─ START backup-trader service                    │
│  └─ Log recovery                                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Resource Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| **CPU Usage** | > 85% | Stop Sentinel Bot |
| **RAM Usage** | > 85% | Stop Sentinel Bot |
| **RAM Available** | < 200MB | Stop Sentinel Bot |
| **Disk Usage** | > 90% | Stop Sentinel Bot |

**Rationale:**
- Leave 15% headroom for OS and essential services
- If Debian is starved, backup won't help (primary is running fine)
- Better to stop gracefully than crash and lose data

---

## Installation on Debian

### Step 1: Copy Monitor Script

```bash
# SSH into Debian
ssh trader@backup-machine-ip

# Script is already in repo
cd /home/trader/crypto-daytrading
ls scripts/resource_monitor.py
```

### Step 2: Install Service File

```bash
# Copy systemd service
sudo cp scripts/resource-monitor.service /etc/systemd/system/

# Set permissions
sudo chmod 644 /etc/systemd/system/resource-monitor.service

# Reload systemd
sudo systemctl daemon-reload
```

### Step 3: Enable and Start Service

```bash
# Enable on boot
sudo systemctl enable resource-monitor

# Start immediately
sudo systemctl start resource-monitor

# Verify running
sudo systemctl status resource-monitor
```

### Step 4: Verify Installation

```bash
# Check service is running
sudo systemctl is-active resource-monitor
# Output: active

# View logs
sudo journalctl -u resource-monitor -f
# Should see: "Resource monitor started"
```

---

## How It Works

### Normal Operation (Resources OK)

```
Every 10 seconds:
  ✅ Check CPU: 45% (< 85%)  ← OK
  ✅ Check RAM: 60% (< 85%)  ← OK
  ✅ Check RAM free: 800MB (> 200MB)  ← OK
  ✅ Check Disk: 40% (< 90%)  ← OK
  
  Log: "Resources: CPU=45.0% | RAM=60% (800MB free) | Disk=40%"
  Action: Nothing - continue normal operation
```

### Low Resources Detected

```
10:15:23 - CPU usage spikes to 92% (> 85%)

Monitor detects threshold exceeded:
  🚨 STOPPING SENTINEL BOT: CPU usage critical: 92.0% (threshold: 85%)
  
  1. systemctl stop backup-trader
  2. systemctl stop failover-monitor
  3. Log: "✅ backup-trader stopped"
  4. Log: "✅ failover-monitor stopped"
  5. Send alert
  
Result:
  • Sentinel Bot is now OFF
  • No more background tasks consuming CPU
  • Monitor continues checking (every 10s)
  • Primary machine unaffected
```

### Resources Recover

```
10:20:45 - CPU usage drops to 60%

Monitor detects recovery:
  🚀 Resources recovered - restarting Sentinel Bot...
  
  1. systemctl start failover-monitor
  2. systemctl start backup-trader
  3. Log: "✅ failover-monitor started"
  4. Log: "✅ backup-trader started"
  
Result:
  • Sentinel Bot is back ONLINE
  • Ready for failover again
  • Continues monitoring
```

---

## Log Examples

### Startup

```
2026-06-23 14:22:15 - INFO - 🔍 Resource monitor started
2026-06-23 14:22:15 - INFO - CPU threshold: 85%
2026-06-23 14:22:15 - INFO - RAM threshold: 85% or <200MB
2026-06-23 14:22:15 - INFO - Disk threshold: 90%
2026-06-23 14:22:15 - INFO - Check interval: 10s
2026-06-23 14:22:25 - INFO - Resources: CPU=45.0% | RAM=62% (600MB free) | Disk=42%
2026-06-23 14:22:35 - INFO - Resources: CPU=48.0% | RAM=63% (590MB free) | Disk=42%
```

### When Threshold Exceeded

```
2026-06-23 14:35:12 - WARNING - CPU usage critical: 86.5% (threshold: 85%)
2026-06-23 14:35:12 - CRITICAL - 🚨 STOPPING SENTINEL BOT: CPU usage critical: 86.5%
2026-06-23 14:35:12 - INFO - Stopping backup trader service...
2026-06-23 14:35:13 - WARNING - ✅ backup-trader stopped
2026-06-23 14:35:13 - INFO - Stopping failover monitor service...
2026-06-23 14:35:14 - WARNING - ✅ failover-monitor stopped
2026-06-23 14:35:14 - CRITICAL - ALERT: Sentinel Bot stopped at 2026-06-23T14:35:14
```

### When Resources Recover

```
2026-06-23 14:42:30 - INFO - Resources recovered - restarting Sentinel Bot...
2026-06-23 14:42:30 - INFO - Starting failover monitor service...
2026-06-23 14:42:31 - INFO - ✅ failover-monitor started
2026-06-23 14:42:31 - INFO - Starting backup trader service...
2026-06-23 14:42:32 - INFO - ✅ backup-trader started
```

---

## Monitoring the Monitor

### View Real-Time Logs

```bash
# Watch resource monitor logs
sudo journalctl -u resource-monitor -f

# Or check log file directly
tail -f /home/trader/crypto-daytrading/logs/resource_monitor.log
```

### Check Service Status

```bash
# Is monitor running?
sudo systemctl is-active resource-monitor

# Full status
sudo systemctl status resource-monitor

# Recent errors
sudo journalctl -u resource-monitor -n 50 --no-pager
```

### Check If Services Are Running

```bash
# Is backup trader running?
sudo systemctl is-active backup-trader

# Is failover monitor running?
sudo systemctl is-active failover-monitor
```

### Get Current Resource Usage

```bash
# Real-time stats
top -b -n 1 | head -10

# Or more detailed
free -h          # Memory
df -h            # Disk
top -bn1 | grep "Cpu" # CPU
```

---

## Testing Resource Monitor

### Test 1: Verify Monitor is Detecting Resources Correctly

```bash
# Check logs show resource readings
sudo journalctl -u resource-monitor -n 20 --no-pager | grep "Resources:"

# Should see lines like:
# Resources: CPU=45.0% | RAM=62% (600MB free) | Disk=42%
```

### Test 2: Simulate Low CPU (Trigger Stop)

```bash
# Start a CPU-intensive process to spike CPU
stress-ng --cpu 8 --timeout 60s

# In another terminal, watch the monitor
sudo journalctl -u resource-monitor -f

# Should see:
# 🚨 STOPPING SENTINEL BOT: CPU usage critical
```

### Test 3: Verify Services Stop When CPU High

```bash
# Start CPU stress
stress-ng --cpu 8 --timeout 60s &

# Wait for monitor to trigger
sleep 5

# Check if backup-trader is stopped
sudo systemctl is-active backup-trader
# Output: inactive

# Kill stress
killall stress-ng

# Wait for recovery (up to 20 seconds)
sleep 20

# Check if backup-trader restarted
sudo systemctl is-active backup-trader
# Output: active
```

### Test 4: Simulate Low RAM (Trigger Stop)

```bash
# Create memory pressure (requires appropriate tool)
# Option 1: Use stress-ng
stress-ng --vm 1 --vm-bytes 90% --timeout 60s

# Monitor should detect high memory and stop services
sudo journalctl -u resource-monitor -f | grep "STOPPING"
```

### Test 5: Simulate Low Disk (Trigger Stop)

```bash
# Create large temporary files to fill disk
dd if=/dev/zero of=/tmp/bigfile bs=1M count=10000

# Monitor should detect high disk usage and stop services
sudo journalctl -u resource-monitor -f | grep "disk_percent"

# Clean up
rm /tmp/bigfile
```

---

## Customizing Thresholds

If you want different thresholds (e.g., more aggressive stopping):

**Edit resource_monitor.py:**

```bash
nano /home/trader/crypto-daytrading/scripts/resource_monitor.py
```

**Find and modify:**

```python
THRESHOLDS = {
    "cpu_percent": 85,           # Change this (e.g., 75 for earlier stop)
    "memory_percent": 85,        # Change this (e.g., 80)
    "disk_percent": 90,          # Change this (e.g., 85)
    "memory_mb": 200,            # Change this (e.g., 300 for more buffer)
}
```

**Restart service after changes:**

```bash
sudo systemctl restart resource-monitor
```

---

## Production Checklist

- [ ] resource_monitor.py copied to `/home/trader/crypto-daytrading/scripts/`
- [ ] resource-monitor.service copied to `/etc/systemd/system/`
- [ ] Service is enabled: `sudo systemctl is-enabled resource-monitor` → enabled
- [ ] Service is running: `sudo systemctl is-active resource-monitor` → active
- [ ] Logs are being written: `tail /home/trader/crypto-daytrading/logs/resource_monitor.log`
- [ ] Test 1 passed: Monitor detects resource usage correctly
- [ ] Test 2 passed: Monitor stops services when CPU high
- [ ] Test 3 passed: Monitor restarts services when CPU recovers
- [ ] Alerts configured (email/Slack on stop)
- [ ] Backup trader service stops gracefully when called
- [ ] Failover monitor service stops gracefully when called

---

## Alerts (Optional)

The resource monitor logs everything to:
- `/home/trader/crypto-daytrading/logs/resource_monitor.log`
- systemd journal (visible via `journalctl`)

To add email or Slack alerts, modify the `_send_alert()` method in `resource_monitor.py`.

### Email Alert Example

```python
def _send_alert(self, reason: str):
    """Send alert notification via email."""
    import smtplib
    from email.mime.text import MIMEText
    
    timestamp = datetime.now().isoformat()
    message = f"Sentinel Bot stopped: {reason}\nTime: {timestamp}"
    
    msg = MIMEText(message)
    msg['Subject'] = "CRITICAL: Sentinel Bot Stopped (Resource Alert)"
    msg['From'] = "trader@debian-backup"
    msg['To'] = "your-email@example.com"
    
    # Send via Gmail or your email server
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login("your-email@gmail.com", "your-app-password")
        server.send_message(msg)
```

---

## Troubleshooting

### Monitor Not Stopping Services

```bash
# Check if monitor is running
sudo systemctl is-active resource-monitor

# Check its logs
sudo journalctl -u resource-monitor -n 50

# Verify it has sudo permissions
sudo -l -U trader | grep systemctl
```

### Services Won't Restart

```bash
# Check why restart failed
sudo systemctl status backup-trader
sudo systemctl status failover-monitor

# Try manual restart
sudo systemctl start backup-trader
sudo systemctl start failover-monitor

# Check for dependency issues
sudo systemctl list-dependencies backup-trader
```

### Threshold Too Aggressive (Stops Too Often)

```bash
# Increase thresholds in resource_monitor.py
# Then restart
sudo systemctl restart resource-monitor
```

### Threshold Too Permissive (Never Stops)

```bash
# Decrease thresholds in resource_monitor.py
# Then restart
sudo systemctl restart resource-monitor
```

---

## Cost Impact

| Component | Cost | Notes |
|-----------|------|-------|
| Python script | Free | Minimal overhead |
| psutil library | Free | Already installed |
| Monitor service | Free | <50MB RAM, <1% CPU |
| **Total** | **Free** | Adds ~10-15% overhead |

**Monitor itself is lightweight** — won't significantly impact system resources.

---

## Summary

✅ **Auto-stops Sentinel Bot when resources low**  
✅ **Checks every 10 seconds**  
✅ **Configurable thresholds**  
✅ **Auto-restarts when resources recover**  
✅ **Comprehensive logging**  
✅ **Minimal overhead (<50MB)**  
✅ **Production-ready**

**Ready to deploy! 🚀**
