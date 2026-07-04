# Production Deployment Guide - Crypto Daytrading Platform

**Version:** 1.0.0  
**Last Updated:** 2026-07-04  
**Status:** PRODUCTION READY  

## Overview

This guide covers deploying the crypto daytrading platform to production with full Phase 2 monitoring, HA failover, and automated incident response.

## Pre-Deployment Checklist

- [ ] All tests passing: `pytest tests/ -v`
- [ ] Code review completed
- [ ] Security review completed
- [ ] Database migration tested on staging
- [ ] Monitoring configured (Prometheus, Grafana, Slack, PagerDuty)
- [ ] Backup strategy validated
- [ ] Runbooks written for on-call team
- [ ] HA primary/backup servers configured
- [ ] Network/firewall rules in place

## Architecture Overview

### Primary (Main) Machine

```
┌────────────────────────────────────────────────┐
│              Primary Trading Machine           │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │  FastAPI Application (uvicorn)        │   │
│  │  - Autonomous Trader                   │   │
│  │  - Paper Trading Engine                │   │
│  │  - HA State Sync (→ Backup)            │   │
│  │  - Phase 2 Monitoring                  │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │  Database (SQLite/PostgreSQL)          │   │
│  │  - Positions, trades, config           │   │
│  │  - Atomic transactions (ACID)          │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  Port: 8001                                   │
└────────────────────────────────────────────────┘
                     │ Heartbeat + State Sync (every 5s)
                     │ Emergency Stop on Cascade
                     ▼
┌────────────────────────────────────────────────┐
│              Backup Trading Machine            │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │  FastAPI Application (standby)         │   │
│  │  - Autonomous Trader (disabled)        │   │
│  │  - Paper Trading Engine (synced)       │   │
│  │  - Failover Monitor                    │   │
│  │  - Phase 2 Monitoring                  │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │  Database (synced from Primary)        │   │
│  │  - Positions, trades, config           │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  Port: 8002                                   │
│  (Auto-enables trading if Primary fails)     │
└────────────────────────────────────────────────┘
```

### Monitoring Stack

```
Prometheus (scrapes every 5s)
    ↓
    ├─ /metrics endpoint (app)
    ├─ /metrics/health
    ├─ /metrics/cascade-risk
    ├─ /metrics/summary
    └─ /metrics/history
    
Grafana (queries Prometheus)
    ↓
    ├─ Real-time dashboard (6 panels)
    ├─ Alert thresholds
    ├─ Cascade risk visualization
    └─ Alert notification channels
    
Alert Routing
    ├─ Slack (channel: #crypto-alerts)
    ├─ PagerDuty (on-call escalation)
    ├─ Email (backup alerts)
    └─ Emergency Stop (trading pause)
```

## Step 1: Prepare Servers

### Primary Server (Production)

1. **Install dependencies:**

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
sudo apt-get install -y git curl wget postgresql postgresql-contrib
sudo apt-get install -y prometheus grafana-server
```

2. **Create application user:**

```bash
sudo useradd -m -s /bin/bash trading
sudo usermod -aG sudo trading
```

3. **Clone repository:**

```bash
cd /opt
sudo git clone https://github.com/yourorg/crypto-daytrading.git
cd crypto-daytrading
sudo chown -R trading:trading .
```

4. **Create virtual environment:**

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Backup Server (Standby)

Repeat steps 1-4 on backup server, but use different ports in .env

## Step 2: Configure Environment

### Primary (.env)

```bash
MACHINE_ID=main
PRIMARY_API_URL=http://<primary-private-ip>:8001
BACKUP_API_URL=http://<backup-private-ip>:8002
STATE_SYNC_INTERVAL=5
HEARTBEAT_CHECK_INTERVAL=2
INITIAL_CAPITAL=10000
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
PAGERDUTY_INTEGRATION_KEY=your_pagerduty_key_here
```

### Backup (.env)

```bash
MACHINE_ID=backup
PRIMARY_API_URL=http://<primary-private-ip>:8001
BACKUP_API_URL=http://<backup-private-ip>:8002
```

## Step 3: Configure Systemd Services

Create `/etc/systemd/system/crypto-daytrading-primary.service`:

```ini
[Unit]
Description=Crypto Daytrading Platform - Primary
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=trading
WorkingDirectory=/opt/crypto-daytrading
Environment="PYTHONUNBUFFERED=1"
Environment="MACHINE_ID=main"
ExecStart=/opt/crypto-daytrading/venv/bin/python -m uvicorn \
    backend.api.main:app --host 0.0.0.0 --port 8001 --workers 4 --loop uvloop
Restart=on-failure
RestartSec=10
WatchdogSec=30
MemoryLimit=512M
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Create similar service for backup (port 8002, MACHINE_ID=backup).

Enable services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-daytrading-primary
sudo systemctl enable crypto-daytrading-backup
```

## Step 4: Configure Prometheus

Create `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: 'crypto-daytrading-primary'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'crypto-daytrading-backup'
    static_configs:
      - targets: ['localhost:8002']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

Enable:

```bash
sudo systemctl restart prometheus
sudo systemctl enable prometheus
```

## Step 5: Configure Grafana

1. Start Grafana: `sudo systemctl start grafana-server`
2. Open http://localhost:3000
3. Add Prometheus data source (http://localhost:9090)
4. Import dashboard from `monitoring/grafana_dashboard.json`

## Step 6: Deploy Application

```bash
cd /opt/crypto-daytrading
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
sudo systemctl start crypto-daytrading-primary
sudo systemctl start crypto-daytrading-backup
```

## Step 7: Verify Deployment

### Health Checks

```bash
curl http://localhost:8001/api/health
curl http://localhost:8002/api/health
```

### Metrics

```bash
curl http://localhost:8001/metrics/summary
curl http://localhost:8001/metrics/health
curl http://localhost:8001/metrics/cascade-risk
```

### Logs

```bash
sudo journalctl -u crypto-daytrading-primary -f
sudo journalctl -u crypto-daytrading-backup -f
```

Look for:
- ✅ "Phase 2 Monitoring Loop started"
- ✅ "Alert routing configured"
- ✅ No ERROR or CRITICAL messages

## Troubleshooting

### Application Won't Start

```bash
sudo journalctl -u crypto-daytrading-primary -n 50
source /opt/crypto-daytrading/venv/bin/activate
python -c "from backend.api.main import app; print('OK')"
```

### Metrics Not Collecting

```bash
curl http://localhost:8001/metrics/summary
sudo journalctl -u crypto-daytrading-primary | grep "Phase 2"
```

### Alerts Not Firing

```bash
curl http://localhost:8001/metrics/cascade-risk
sudo journalctl -u crypto-daytrading-primary | grep "Alert routing"
```

### Failover Not Working

```bash
sudo systemctl stop crypto-daytrading-primary
sudo journalctl -u crypto-daytrading-backup -f
# Should see failover activation within 10 seconds
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Memory Usage | <300MB |
| CPU Usage | <50% |
| P99 Latency | <100ms |
| Uptime | 99.9% |
| Failover Time | <10s |

---

**Status:** ✅ PRODUCTION READY FOR DEPLOYMENT
