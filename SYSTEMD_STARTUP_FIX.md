# Systemd Startup Fix — Port Binding Failures (2026-07-05)

## Root Cause: Missing `fuser` Command on BACKUP

**Problem:** BACKUP service repeatedly failed to start with "address already in use" error, requiring manual restart every time it crashed.

**Root Cause Analysis:**

1. **Symptom:** ExecStartPre was supposed to kill lingering processes on port 8002
2. **Diagnosis:** `fuser` command doesn't exist on BACKUP machine
3. **Failure Mode:**
   - ExecStartPre runs: `sudo fuser -k 8002/tcp`
   - Command returns "not found" error
   - Error redirected to `/dev/null` (silenced)
   - Port cleanup never happens
   - Service tries to bind port 8002, fails (still in TIME_WAIT from previous crash)
   - Service crashes with exit code 1
   - Systemd waits RestartSec=10 seconds
   - Retry happens, but TIME_WAIT still active (usually expires in ~60 seconds)
   - Takes multiple retries until TIME_WAIT naturally expires
   - Eventually binds successfully

**Cascading Effects:**
- Service unavailable for 60+ seconds after each crash
- HA failover monitor gets confused (sees BACKUP down)
- Could trigger unnecessary failover in production
- Admin must manually restart or wait for TIME_WAIT timeout

## Solution: Use `lsof` Instead of `fuser`

`lsof` is more universally available and doesn't require separate installation.

**Fix Applied:**

On BACKUP machine (`/etc/systemd/system/crypto-backup.service`):

```bash
# BEFORE (fails silently - fuser not found)
ExecStartPre=/bin/bash -c "sudo fuser -k 8002/tcp 2>/dev/null || true"

# AFTER (uses lsof - universally available)
ExecStartPre=/bin/bash -c "sudo lsof -ti:8002 | xargs -r kill -9 2>/dev/null || true"
```

**How it works:**
1. `lsof -ti:8002` = list processes using port 8002 (i=IP, t=pid only)
2. `xargs -r kill -9` = pass PIDs to kill -9 (r=no error if empty list)
3. Errors silenced if no process found (expected case)

**Verification:**

```bash
# Before fix: Port binding failure
❌ ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8002): address already in use

# After fix: Clean startup
✅ Application startup complete
✅ Port 8002 bound successfully
```

## Deployment Status

| Machine | Fix Status | Port Binding | Service Health |
|---------|-----------|--------------|-----------------|
| PRIMARY | N/A (uses fuser, works fine) | ✅ 8001 | ✅ Healthy |
| BACKUP | ✅ Applied | ✅ 8002 | ✅ Healthy |

## Testing

```bash
# Verify both services are running
curl http://192.168.30.137:8001/api/health | jq .status
curl http://192.168.3.25:8002/api/health | jq .status

# Expected output: "healthy" on both
```

## Why This Matters

- **Tier 1 Fragility Detection:** This was a core cascading failure point
- **HA Reliability:** Clean restarts are essential for active-passive failover
- **Operational Stability:** Eliminates 60+ second startup delays after crashes
- **Production Ready:** Required for live trading with €1,000 capital

## Files Modified

- `/etc/systemd/system/crypto-backup.service` (on BACKUP machine 192.168.3.25)
  - ExecStartPre: fuser → lsof
  - Applied via: `sudo sed -i` + `systemctl daemon-reload`

## Prevention

Future deployments should:
1. Test ExecStartPre commands on target machine before deploying
2. Prefer universally-available tools (lsof, pkill) over specialized ones (fuser)
3. Add monitoring for port binding failures in health checks
4. Document all systemd hooks (ExecStartPre, ExecStart, ExecStopPost)

---

**Status:** ✅ FIXED — Both machines healthy, ready for validation
