# Crypto Daytrading Bot - Deployment Guide

## Current Status
- ✅ Code: Production-ready (298/298 tests passing)
- ✅ Capital: Paper trading mode (no real loss risk)
- ❌ HA: Single instance (no redundancy yet)
- ⏱️ Phase: Acceptance testing

---

## 1. Quick Start (Manual)

### Start the bot on port 8001:
```bash
cd ~/projects/crypto-daytrading
source venv/bin/activate
uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
```

### Verify it's running:
```bash
curl http://127.0.0.1:8001/api/health
```

### Expected output:
```json
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

## 2. Systemd Setup (Permanent Deployment)

### Create service file (run with sudo):
```bash
sudo tee /etc/systemd/system/crypto-daytrading.service > /dev/null << 'EOF'
[Unit]
Description=Crypto Daytrading Bot (Paper Trading)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=vali
WorkingDirectory=/home/vali/projects/crypto-daytrading
ExecStart=/home/vali/projects/crypto-daytrading/venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

# Resource limits
MemoryMax=4G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-daytrading
sudo systemctl start crypto-daytrading
```

### Verify service:
```bash
sudo systemctl status crypto-daytrading
journalctl -u crypto-daytrading -f  # Watch logs
```

---

## 3. Monitoring

### Health check endpoint:
```bash
curl http://127.0.0.1:8001/api/health
```

### Account status:
```bash
curl http://127.0.0.1:8001/api/paper/account
```

### Active positions:
```bash
curl http://127.0.0.1:8001/api/paper/positions
```

### Regime detection:
```bash
curl -X POST http://127.0.0.1:8001/api/regime/detect?symbol=BTCUSDT
```

### Smart gateway test:
```bash
curl -X POST "http://127.0.0.1:8001/api/trading/smart-gateway?symbol=BTCUSDT&quantity=0.01&current_price=50000"
```

---

## 4. Testing Checklist (Acceptance Phase)

### Week 1: System Stability
- [ ] Bot runs 24/7 without crashes
- [ ] Health checks pass every 5 minutes
- [ ] No memory leaks (RAM stable <500MB)
- [ ] CPU usage <10% idle
- [ ] All API endpoints respond <1s

### Week 2: Trading Logic
- [ ] Signal generation working (momentum/reversion/grid)
- [ ] Regime detection classification correct
- [ ] Entry validation enforced (position limits)
- [ ] Exit rules triggering on profit target/stop loss
- [ ] PnL calculation accurate

### Week 3-4: Risk Management
- [ ] Portfolio risk score updating
- [ ] Rebalancing recommendations generated
- [ ] Position correlations tracked
- [ ] Health monitoring alerts working
- [ ] Recovery from network interruptions

### Final: Production Readiness
- [ ] Zero critical bugs in logs
- [ ] All regression tests passing
- [ ] Performance meets requirements (<100ms latency)
- [ ] Ready for live capital allocation

---

## 5. Parallel Operation (Dual Bot Setup)

### Port assignments:
- **Port 8000**: investing-platform (Sentinel Bot) — Equities
- **Port 8001**: crypto-daytrading (New Bot) — Crypto

### Running both simultaneously:
```bash
# Terminal 1: Investing Platform (no changes)
cd ~/projects/investing-platform
source venv/bin/activate
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Crypto Daytrading (new)
cd ~/projects/crypto-daytrading
source venv/bin/activate
uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
```

### Verify both running:
```bash
curl http://127.0.0.1:8000/api/health  # Equities bot
curl http://127.0.0.1:8001/api/health  # Crypto bot
```

---

## 6. Monitoring Dashboard

### Real-time logs (crypto bot):
```bash
journalctl -u crypto-daytrading -f
```

### System resources:
```bash
watch -n 1 'ps aux | grep uvicorn | grep -v grep'
```

### API load test:
```bash
for i in {1..100}; do curl -s http://127.0.0.1:8001/api/health > /dev/null; done
echo "100 requests completed"
```

---

## 7. Migration Path (After Acceptance Testing)

### After 2-4 weeks of stable operation:

**Remains unchanged:**
- investing-platform: Continues running on port 8000
- Sentinel Bot: No changes to redundancy setup
- Equity positions: Unaffected

**New addition:**
- crypto-daytrading: Continues on port 8001
- Crypto positions: Isolated from equity portfolio
- Monitoring: Separate dashboards for each

**Decision point:**
- If crypto bot proves stable: Keep both (different asset classes)
- If issues found: Keep equities bot, iterate on crypto bot
- No cannibalization of capital or risk

---

## 8. Troubleshooting

### Bot won't start:
```bash
# Check port 8001 is available
lsof -i :8001

# Check logs
journalctl -u crypto-daytrading -n 50
```

### Memory usage high:
```bash
# Check process
ps aux | grep crypto-daytrading

# Restart service
sudo systemctl restart crypto-daytrading
```

### API endpoint slow:
```bash
# Check system load
top -b -n 1 | head -5

# Check database (if applicable)
# Monitor Binance WebSocket connection
```

---

## 9. Rollback Procedure

If issues found during testing:

```bash
# Stop the bot
sudo systemctl stop crypto-daytrading

# Verify it's stopped
curl http://127.0.0.1:8001/api/health  # Should fail

# Check investing-platform still running
curl http://127.0.0.1:8000/api/health  # Should succeed

# All equity positions preserved
# No capital loss (paper trading mode)
```

---

## Current Deployment Status

- ✅ Code ready
- ✅ Tests passing (298/298)
- ✅ APIs functional
- ✅ Risk controls in place
- ⏳ Waiting: systemd service setup + go-live decision

**Next step:** Run `sudo systemctl start crypto-daytrading` to go live

---

**Questions?**
- Health checks: `curl http://127.0.0.1:8001/api/health`
- Logs: `journalctl -u crypto-daytrading -f`
- Status: `sudo systemctl status crypto-daytrading`
