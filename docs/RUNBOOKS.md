# Operational Runbooks

**Purpose**: Step-by-step diagnosis and resolution guides for common alerts and failures.

**Updated**: Phase 337 (2026-06-24)

---

## Runbook Index

| Alert | Severity | Diagnosis | Resolution |
|-------|----------|-----------|-----------|
| High Error Rate (>10%) | 🔴 CRITICAL | Check `/metrics` endpoint | See [RB-001](#rb-001-high-error-rate) |
| High Latency (p99 >1s) | 🟠 WARNING | Profile with logs | See [RB-002](#rb-002-high-latency) |
| Authentication Failures | 🟠 WARNING | Check auth tokens | See [RB-003](#rb-003-auth-failures) |
| API Unresponsive | 🔴 CRITICAL | Check process health | See [RB-004](#rb-004-api-unresponsive) |
| Metrics Collection Failed | 🟡 INFO | Check metrics endpoint | See [RB-005](#rb-005-metrics-collection-failed) |

---

## RB-001: High Error Rate (>10%)

**Alert Condition**: `error_rate_percent > 10` (check `/metrics`)

**Symptoms**:
- Many requests returning 4xx or 5xx status codes
- Users report "Something went wrong"
- Spikes in error rate correlating with time of day

### Diagnosis

1. **Check current error rate**:
   ```bash
   curl http://localhost:8000/metrics | jq '.error_rate_percent'
   ```

2. **View recent error logs**:
   ```bash
   journalctl -u investing-platform -f | grep ERROR
   ```

3. **Identify error patterns**:
   ```bash
   journalctl -u investing-platform -S "5 minutes ago" | grep ERROR | jq -r '.message' | sort | uniq -c | sort -rn
   ```

4. **Check error by endpoint**:
   ```bash
   journalctl -u investing-platform -S "5 minutes ago" | jq 'select(.level=="ERROR")' | jq -r '.logger'
   ```

### Resolution

**If auth errors** (401/403):
- Check token validity: `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/multi-asset/assets`
- Confirm user role: Check logs for `Authorization failed: user X lacks Y role`
- **Fix**: Issue new token or elevate user permissions

**If validation errors** (400):
- Check request format: `curl -X GET http://localhost:8000/api/multi-asset/assets/INVALID`
- Review error details in logs
- **Fix**: Correct client request format or API input

**If server errors** (500):
- Get full error stack: `journalctl -u investing-platform -S "1 minute ago" -p err --no-pager`
- Check for resource issues (RAM, disk, CPU)
- **Fix**: Restart service or increase resources

**Recovery Steps**:
1. Identify root cause from above
2. Restart service if needed: `sudo systemctl restart investing-platform`
3. Verify error rate dropped: `curl http://localhost:8000/metrics | jq '.error_rate_percent'`
4. If error rate remains >10%, escalate to engineering team

---

## RB-002: High Latency (p99 >1000ms)

**Alert Condition**: `p99_latency_ms > 1000` (check `/metrics`)

**Symptoms**:
- UI feels sluggish or times out
- API responses take >1 second
- 99th percentile of requests very slow (but median OK)

### Diagnosis

1. **Check latency breakdown**:
   ```bash
   curl http://localhost:8000/metrics | jq '.[] | {p50:.p50_latency_ms, p95:.p95_latency_ms, p99:.p99_latency_ms}'
   ```

2. **Identify slow endpoints** (from logs):
   ```bash
   journalctl -u investing-platform -S "5 minutes ago" | jq 'select(.latency_ms > 1000)' | jq -r '.message'
   ```

3. **Check system resources**:
   ```bash
   free -h           # RAM usage
   df -h /           # Disk usage
   top -bn1 | head   # CPU usage
   ```

4. **Profile a specific endpoint**:
   ```bash
   time curl http://localhost:8000/api/multi-asset/assets
   ```

### Resolution

**If CPU high (>80%)**:
- Identify hot function: `python -m cProfile -s cumtime backend/api/main.py` (development only)
- Optimize heavy computation (optimizer, backtesting)
- **Fix**: Reduce calculation scope or add caching

**If RAM high (>90%)**:
- Check memory leaks: `ps aux | grep "python\|gunicorn" | awk '{print $6}' | tail -20`
- Restart service to clear memory: `sudo systemctl restart investing-platform`
- **Fix**: Profile memory usage and fix leaks

**If Disk I/O high**:
- Check if logs filling disk: `du -sh /var/log /home/vali/projects/crypto-daytrading/logs`
- Archive old logs: `tar czf logs-archive.tar.gz logs/` && `rm logs/*.log`
- **Fix**: Rotate logs or increase disk space

**If query slow** (e.g., optimizer convergence):
- Reduce problem size (fewer assets in portfolio)
- Add timeout to optimizer: `set_timeout(optimizer, 5000)  # 5 seconds max`
- **Fix**: Use approximation instead of exact optimization

**Recovery Steps**:
1. Identify bottleneck from above
2. Apply fix (restart, optimize, cache, etc.)
3. Monitor latency: `watch 'curl -s http://localhost:8000/metrics | jq .p99_latency_ms'`
4. Confirm p99 <1000ms before closing

---

## RB-003: Authentication Failures

**Alert Condition**: Multiple 401/403 responses in logs

**Symptoms**:
- Users cannot call `/api/multi-asset/*` endpoints
- Error: "Invalid authentication credentials" or "Missing Authorization header"
- Legitimate users locked out

### Diagnosis

1. **Check auth logs**:
   ```bash
   journalctl -u investing-platform -S "5 minutes ago" | grep "Authentication failed\|Authorization failed"
   ```

2. **Verify token format**:
   ```bash
   # Token should be sent as: Authorization: Bearer <token>
   curl -H "Authorization: Bearer admin-token-123" http://localhost:8000/api/multi-asset/assets
   ```

3. **Check user roles** (from auth manager in logs):
   ```bash
   # Search for specific user authentication
   journalctl -u investing-platform -S "5 minutes ago" | grep "Authenticated user\|user_id"
   ```

4. **Verify auth server/config** (if using external auth):
   - Check if auth service is running (OAuth2, JWT service, etc.)
   - Verify config points to correct auth endpoint

### Resolution

**If token invalid**:
- Regenerate token for user
- Distribute new token to client
- **Fix**: Issue new token, revoke old one

**If token expired**:
- Implement token refresh: add `/api/auth/refresh` endpoint (Phase 338+)
- For now: Issue new token
- **Fix**: Add token expiration and refresh logic

**If user role insufficient**:
- Check required role for endpoint: `router.endpoint_requires_role = UserRole.ANALYST`
- Elevate user: `auth_manager.users['token'].roles.add(UserRole.TRADER)`
- **Fix**: Adjust user permissions or endpoint requirements

**If CORS blocking requests**:
- Error: "CORS policy: No 'Access-Control-Allow-Origin' header"
- Check allowed origins in `main.py` line ~298
- **Fix**: Add client origin to `allow_origins` list

**Recovery Steps**:
1. Identify root cause from above
2. Apply fix (new token, role elevation, CORS config, etc.)
3. Test with same client: `curl -H "Authorization: Bearer <new-token>" http://localhost:8000/api/multi-asset/assets`
4. Confirm 200 response before closing

---

## RB-004: API Unresponsive (No Response)

**Alert Condition**: API doesn't respond to any request (timeout, connection refused)

**Symptoms**:
- `curl http://localhost:8000/api/health` times out or connection refused
- All endpoints down (not just one)
- Possible crash or hang

### Diagnosis

1. **Check if process running**:
   ```bash
   ps aux | grep "python\|uvicorn" | grep -v grep
   # Should show: uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
   ```

2. **Check logs for crashes**:
   ```bash
   sudo journalctl -u investing-platform -n 50 --no-pager
   # Look for: Exception, Traceback, ERROR, CRITICAL
   ```

3. **Check port availability**:
   ```bash
   netstat -tlnp | grep 8000
   # Should show: LISTEN on 127.0.0.1:8000
   ```

4. **Check system resources**:
   ```bash
   free -h            # RAM might be exhausted
   df -h /            # Disk might be full
   dmesg | tail -20   # OOM killer events
   ```

### Resolution

**If process not running**:
- Start API: `source venv/bin/activate && uvicorn backend.api.main:app --host 127.0.0.1 --port 8000`
- Or via systemd: `sudo systemctl start investing-platform`
- **Fix**: Restart service

**If process crashed**:
- Check crash reason in logs: `journalctl -u investing-platform -e`
- Common causes:
  - `NameError`: Missing import or undefined variable
  - `ImportError`: Missing dependency
  - `MemoryError`: RAM exhausted → restart or increase RAM
  - `PermissionError`: File permissions issue
- **Fix**: Fix root cause and restart

**If port already in use**:
- Find process using port 8000: `lsof -i :8000`
- Kill it: `kill -9 <PID>` or `sudo fuser -k 8000/tcp`
- **Fix**: Clear port and restart

**If disk full**:
- Check disk: `df -h /`
- Clear logs: `rm /home/vali/projects/crypto-daytrading/logs/*.log*`
- Or archive: `tar czf logs-old.tar.gz logs/` && `rm logs/*.log*`
- **Fix**: Free up disk space and restart

**If memory exhausted**:
- Restart process: `sudo systemctl restart investing-platform`
- Monitor: `watch 'free -h'` and `watch 'ps aux | grep python'`
- If repeats, profile memory: implement memory limit in systemd
- **Fix**: Add MemoryMax to service file (see CLAUDE.md)

**Recovery Steps**:
1. Identify root cause from above
2. Fix issue (restart, delete logs, kill process, etc.)
3. Verify API responds: `curl http://localhost:8000/api/health`
4. Confirm health check returns 200 before closing

---

## RB-005: Metrics Collection Failed

**Alert Condition**: `/metrics` endpoint returns error or empty data

**Symptoms**:
- `curl http://localhost:8000/metrics` returns 500 or no data
- Monitoring dashboard can't scrape metrics
- Latency percentiles missing

### Diagnosis

1. **Check metrics endpoint**:
   ```bash
   curl -v http://localhost:8000/metrics
   # Should return: 200 OK with JSON
   ```

2. **Check metrics collector initialization**:
   ```bash
   journalctl -u investing-platform -S "1 hour ago" | grep "metrics\|Metrics"
   ```

3. **Check for exceptions in metrics collection**:
   ```bash
   journalctl -u investing-platform -S "1 hour ago" | grep "ERROR\|Exception" | grep -i metric
   ```

### Resolution

**If endpoint returns 500**:
- Full error: `curl http://localhost:8000/metrics 2>&1 | tail -20`
- Check logs: `journalctl -u investing-platform -e`
- Likely cause: metrics collector not initialized
- **Fix**: Ensure `get_metrics()` called in middleware setup

**If metrics are empty**:
- Metrics data might not be collected yet (need some requests first)
- Wait a few seconds and retry: `sleep 5 && curl http://localhost:8000/metrics | jq`
- **Fix**: No action needed, metrics will populate

**If latency percentiles are 0**:
- Not enough samples yet for percentiles (need >100 requests)
- **Fix**: No action needed, will be calculated after more requests

**Recovery Steps**:
1. Verify endpoint works: `curl http://localhost:8000/metrics | jq '.requests_total'`
2. Make test requests: `for i in {1..10}; do curl http://localhost:8000/api/health; done`
3. Check metrics updated: `curl http://localhost:8000/metrics | jq '.requests_total'`
4. Confirm metrics populated before closing

---

## Quick Reference: Common Commands

```bash
# Health check
curl http://localhost:8000/api/health

# View metrics
curl http://localhost:8000/metrics | jq

# View error rate
curl http://localhost:8000/metrics | jq '.error_rate_percent'

# View latency percentiles
curl http://localhost:8000/metrics | jq '{p50:.p50_latency_ms, p95:.p95_latency_ms, p99:.p99_latency_ms}'

# Tail logs
journalctl -u investing-platform -f

# Recent errors only
journalctl -u investing-platform -S "5 minutes ago" -p err

# JSON logs (if structured logging enabled)
journalctl -u investing-platform -o json | jq .

# Restart service
sudo systemctl restart investing-platform

# Check service status
sudo systemctl status investing-platform

# Check if port 8000 in use
lsof -i :8000
```

---

## Escalation Path

**Tier 1** (Operations/Oncall):
- Run diagnostics from above
- Restart service if needed
- Check resources (RAM, disk, CPU)

**Tier 2** (Engineering/Backend):
- Profile code performance
- Fix bugs identified in logs
- Optimize slow queries/algorithms

**Tier 3** (Architecture/Lead):
- Design scalability improvements
- Review infrastructure capacity
- Plan roadmap (caching, async, etc.)

---

## Phase 338 Roadmap (Future Runbooks)

- [ ] RB-006: Circuit Breaker Activation (when Binance API fails)
- [ ] RB-007: Database Connection Pool Exhausted
- [ ] RB-008: Optimizer Convergence Timeout
- [ ] RB-009: Cache Staleness Detected
- [ ] RB-010: Duplicate Trade Detection

