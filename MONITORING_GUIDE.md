# Production Monitoring Guide

## Access

Open the monitoring dashboard in your browser:
```
http://localhost:8001/static/monitoring-dashboard.html
```

## System Overview

The monitoring system provides real-time visibility into system health, resource usage, and alerts.

## Dashboard Components

### 1. Overall Status Badge
Located in the header, shows:
- **Healthy (Green)**: All checks passing
- **Degraded (Yellow)**: Some checks failing
- **Critical (Red)**: Multiple failures or critical thresholds exceeded

Active alert count displayed next to status.

### 2. System Health Card
Shows status of all core services:
- **API**: FastAPI server responsiveness
- **Database**: PostgreSQL connectivity
- **Memory**: RAM usage
- **CPU**: Processor utilization
- **Disk**: Storage space
- **ML Model**: Ollama/Inference availability
- **Data Freshness**: Market data currency

Each service shows:
- Status indicator (✓ OK or ✗ FAILED)
- Last check time
- Detailed message

### 3. Resource Usage Card
Real-time system metrics:

**CPU Usage**
- Current percentage
- Color-coded thresholds:
  - Green: <80%
  - Yellow: 80-90%
  - Red: >90%
- Progress bar visualization

**Memory Usage**
- Used/available breakdown
- Percentage of total RAM
- Warning at 85%, critical at 95%

**Disk Usage**
- Used/free space in GB
- Percentage of total
- Warning at 85%, critical at 95%

### 4. Active Alerts Panel
Shows critical and warning-level alerts.

Each alert displays:
- Alert title and message
- Service affected
- Severity level
- Timestamp
- Resolution status

**No alerts** message (green) when all systems healthy.

### 5. Service Status Table
Detailed breakdown of all monitored services:

| Column | Meaning |
|--------|---------|
| Service | System being monitored |
| Status | Current health (Healthy/Failed) |
| Details | Metric value or error message |
| Last Check | Time of most recent check |

### 6. Alert History Table
Recent alerts (last 20) with:
- Service name
- Severity badge (colored)
- Alert title
- Timestamp
- Resolution status

Sorted by most recent first.

## Understanding Thresholds

### CPU
- **Warning**: 80-90% usage
- **Critical**: >90% usage
- **Action**: Check for runaway processes, reduce workload

### Memory
- **Warning**: 85-95% usage
- **Critical**: >95% usage
- **Action**: Restart services, add RAM, or reduce feature scope

### Disk
- **Warning**: 85-95% used
- **Critical**: >95% used
- **Action**: Delete logs/backups, expand storage, cleanup

### Data Freshness
- **Warning**: Last ingest >1 hour old
- **Critical**: Last ingest >3 hours old
- **Action**: Check ingest pipeline, manually run ingest script

### Database
- **Critical**: Connection timeout or unavailable
- **Action**: Check PostgreSQL status, verify network connectivity

## Alert Types

### Informational
- Data ingestion completed
- Configuration updated
- Routine maintenance tasks

### Warning
- CPU >80%
- Memory >85%
- Disk >85%
- Data stale (>1 hour)
- Slow API responses

### Critical
- CPU >90%
- Memory >95%
- Disk >95%
- Database unreachable
- API server down
- ML model unavailable

## Configuring Alerts

### Enable Slack Notifications

1. Create Slack webhook:
   - Go to https://api.slack.com/apps
   - Create new app
   - Enable Incoming Webhooks
   - Create new webhook URL
   - Copy webhook URL

2. Add to `.env` file:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

3. Restart API server:
   ```bash
   systemctl restart investing-platform
   ```

4. Test alert:
   ```bash
   curl -X POST http://localhost:8001/api/monitoring/alerts/create \
     -d "severity=warning&title=Test&message=Testing Slack&service=test"
   ```

### Enable Email Notifications

1. Get Gmail app password:
   - Enable 2FA on Google account
   - Generate app-specific password
   - Copy password

2. Add to `.env` file:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=your-app-password
   ALERT_EMAIL_TO=recipient@example.com
   ```

3. Restart API server and test

### Custom Alert Rules

Edit alert rules in `backend/core/alerting.py`:

```python
self.rules: List[Dict] = [
    {
        "name": "high_memory",
        "condition": "memory > 90",
        "severity": AlertSeverity.CRITICAL,
        "enabled": True
    }
]
```

Available conditions:
- `cpu > X` (percentage)
- `memory > X` (percentage)
- `disk > X` (percentage)
- `api.healthy == False`
- `database.healthy == False`
- `data_age > X` (seconds)

## API Endpoints Reference

### Health Checks

**Get overall health**
```bash
curl http://localhost:8001/api/monitoring/health
```

Response:
```json
{
  "timestamp": "2026-06-24T11:35:00.000000",
  "overall_healthy": true,
  "checks": {
    "api": {
      "name": "api",
      "healthy": true,
      "message": "API is responsive",
      "timestamp": "2026-06-24T11:35:00.000000"
    },
    ...
  },
  "summary": {
    "status": "HEALTHY",
    "total_checks": 7,
    "healthy": 7,
    "unhealthy": 0
  }
}
```

**Get service health**
```bash
curl http://localhost:8001/api/monitoring/health/service/cpu
```

**Get health history**
```bash
curl http://localhost:8001/api/monitoring/health/history/memory?limit=50
```

**Get metrics**
```bash
curl http://localhost:8001/api/monitoring/metrics
```

### Alerts

**Get all alerts**
```bash
curl http://localhost:8001/api/monitoring/alerts
```

**Get active alerts**
```bash
curl http://localhost:8001/api/monitoring/alerts/active
```

**Get alerts by service**
```bash
curl http://localhost:8001/api/monitoring/alerts/service/api
```

**Get alerts by severity**
```bash
curl http://localhost:8001/api/monitoring/alerts/severity/critical
```

**Create alert**
```bash
curl -X POST \
  'http://localhost:8001/api/monitoring/alerts/create?severity=warning&title=Low%20Disk&message=Disk%2085%25%20full&service=system'
```

**Resolve alert**
```bash
curl -X POST http://localhost:8001/api/monitoring/alerts/{alert_id}/resolve
```

## Dashboard Interpretation

### Green Status = Everything Healthy
- All services responding
- Resource usage normal
- No active alerts
- Data is current

**Action**: None required, system operating normally

### Yellow Status = Degraded Performance
- 1-2 services experiencing issues
- Some resource usage elevated
- Non-critical alerts active
- Data may be slightly stale

**Action**: Monitor closely, prepare to intervene if worsens

### Red Status = Critical Issues
- Multiple service failures
- Resource usage critical
- Critical alerts active
- Data is stale

**Action**: Investigate immediately, may need to restart services

## Common Issues & Solutions

### High CPU Usage
```bash
# Check top processes
top -n 1 | head -20

# Check for Ollama inference loops
ps aux | grep ollama

# Kill runaway process
kill -9 <PID>

# Restart API
systemctl restart investing-platform
```

### High Memory Usage
```bash
# Check memory by process
ps aux --sort=-%mem | head

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Restart services to free memory
systemctl restart investing-platform
```

### Disk Full
```bash
# Find large files
find / -type f -size +100M -exec ls -lh {} \;

# Check log sizes
du -sh /var/log/*

# Clean old logs
journalctl --vacuum=30d  # Keep 30 days

# Delete old backups
ls -lth logs/backups/ | tail
rm logs/backups/db_backup_*.gz  # Old ones
```

### Database Unreachable
```bash
# Check if PostgreSQL is running
systemctl status postgresql

# Check connectivity
psql -U trading -h localhost -d crypto_trading -c "SELECT 1"

# Restart PostgreSQL
systemctl restart postgresql

# Restart API
systemctl restart investing-platform
```

### Data Stale
```bash
# Manually run ingest
PYTHONPATH=. python scripts/ingest_daily.py

# Check last ingest timestamp
sqlite3 logs/ingest.db "SELECT MAX(timestamp) FROM ingests"

# Check systemd timer
systemctl status investing-platform-ingest.timer
sudo systemctl start investing-platform-ingest.timer
```

## Performance Optimization

### Reduce Check Frequency
Edit `monitoring-dashboard.html` to change refresh interval:
```javascript
autoRefreshInterval = setInterval(updateStatus, 10000);  // 10 seconds instead of 5
```

### Limit Alert History
Edit `alerting.py`:
```python
self.max_history = 500  # Keep 500 alerts instead of 1000
```

### Reduce Health Check Depth
Edit `health_checker.py` to skip expensive checks in high-load scenarios.

## Monitoring Best Practices

### Daily Checks
1. Review dashboard every morning
2. Check for new alerts
3. Verify data freshness
4. Note resource trends

### Weekly Review
1. Analyze alert patterns
2. Identify systemic issues
3. Review performance trends
4. Update thresholds if needed

### Monthly Maintenance
1. Clean old logs and backups
2. Archive alert history
3. Update documentation
4. Capacity planning

### Incident Response
1. **Identify**: What service failed? What metric triggered it?
2. **Isolate**: Can we continue operating in degraded mode?
3. **Remediate**: Fix root cause
4. **Document**: Note what happened and why
5. **Prevent**: Update rules/thresholds to catch earlier next time

## Health Check Details

### API Check
- Verifies FastAPI server is running
- Response time checked
- Status: OK if server responds within timeout

### Database Check
- Tests PostgreSQL connectivity
- Verifies tables exist
- Status: OK if query succeeds

### Memory Check
- Gets system RAM usage
- Compares to thresholds
- Status: OK if <85%, WARNING if 85-90%, CRITICAL if >90%

### CPU Check
- Samples CPU usage over 1 second
- Compares to thresholds
- Status: OK if <80%, WARNING if 80-90%, CRITICAL if >90%

### Disk Check
- Checks root filesystem usage
- Compares to thresholds
- Status: OK if <85%, WARNING if 85-90%, CRITICAL if >90%

### ML Model Check
- Verifies Ollama is responding
- Status: OK if inference available

### Data Freshness Check
- Compares last ingest time to current time
- Status: OK if <1 hour old, WARNING if 1-3 hours, CRITICAL if >3 hours

## Metrics Collection

Health checks run every time the dashboard refreshes (5s default).

Historical data stored in memory (100 checks per service).

To persist historical data, implement database logging:
```python
# In health_checker.py
await db.execute("INSERT INTO health_history ...")
```

---

**Last Updated**: 2026-06-24  
**Version**: Phase 334 (Production Ready)  
**Status**: ✅ Fully Operational
