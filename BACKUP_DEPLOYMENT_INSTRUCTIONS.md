# BACKUP DEPLOYMENT INSTRUCTIONS

**Status:** BACKUP API responding, SSH connection not available  
**Action Required:** Manual deployment to BACKUP machine  

---

## Current Status

| Component | Status |
|-----------|--------|
| **PRIMARY (192.168.30.137:8001)** | ✅ DEPLOYED & RUNNING with fixes |
| **BACKUP (192.168.3.25:8002)** | 🟡 Running, but needs file sync + restart |

---

## BACKUP Deployment Steps

You need to **copy 3 files to BACKUP** and **restart the service**.

### Option A: Direct Access to BACKUP Machine

If you have direct SSH/console access to BACKUP (192.168.3.25):

**Step 1: Copy files from PRIMARY to BACKUP**
```bash
# From BACKUP machine, pull files from PRIMARY
scp vali@192.168.30.137:/home/vali/projects/crypto-daytrading/backend/trading/autonomous_trader/exit.py \
    /home/claude/crypto-daytrading/backend/trading/autonomous_trader/

scp vali@192.168.30.137:/home/vali/projects/crypto-daytrading/backend/trading/autonomous_trader/entry.py \
    /home/claude/crypto-daytrading/backend/trading/autonomous_trader/

scp vali@192.168.30.137:/home/vali/projects/crypto-daytrading/backend/trading/autonomous_trader/core.py \
    /home/claude/crypto-daytrading/backend/trading/autonomous_trader/
```

**Step 2: Restart BACKUP service**
```bash
# Stop old BACKUP process
pkill -9 -f "uvicorn.*8002"
sleep 2

# Start BACKUP with new code
cd /home/claude/crypto-daytrading
source venv/bin/activate
nohup python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8002 --log-level info > logs/api_startup.log 2>&1 &

sleep 5

# Verify it's running
curl http://localhost:8002/api/health | jq .status
```

---

### Option B: Using Network File Share

If BACKUP has a mounted network share visible from PRIMARY:

```bash
# From PRIMARY machine
cp backend/trading/autonomous_trader/exit.py \
   /mnt/backup/crypto-daytrading/backend/trading/autonomous_trader/

cp backend/trading/autonomous_trader/entry.py \
   /mnt/backup/crypto-daytrading/backend/trading/autonomous_trader/

cp backend/trading/autonomous_trader/core.py \
   /mnt/backup/crypto-daytrading/backend/trading/autonomous_trader/
```

Then restart BACKUP (see Option A Step 2).

---

### Option C: Manual File Edit on BACKUP

If neither option works, you can manually edit the 3 files on BACKUP:

1. **exit.py** — Add at top:
```python
MIN_HOLD_TIME_SECONDS = 10  # Line 16
```

And add lines 40-51 (hold time check) before the exit logic.

2. **entry.py** — Add lines 160-190 for position limit check

3. **core.py** — Add lines 345-365 for hard data quality gate

[See FIX_IMPLEMENTATION_SUMMARY.md for exact code]

---

## Verification After Deployment

Once files are copied and BACKUP restarted:

**Check BACKUP is running:**
```bash
curl http://192.168.3.25:8002/api/health | jq .status
```

**Check fixes are active (from PRIMARY or BACKUP):**
```bash
# SSH to BACKUP then:
grep "MIN_HOLD_TIME_SECONDS" /home/claude/crypto-daytrading/backend/trading/autonomous_trader/exit.py
grep "max_position_pct = 10.0" /home/claude/crypto-daytrading/backend/trading/autonomous_trader/entry.py
grep "HARD GATE" /home/claude/crypto-daytrading/backend/trading/autonomous_trader/core.py
```

All three should return matches if deployment succeeded.

---

## Timeline

- **✅ PRIMARY:** Deployed & running with fixes (2026-07-04 14:XX UTC)
- **⏳ BACKUP:** Awaiting manual deployment (you need to do this)
- **⏳ 48-Hour Test:** Can start once both are running with fixes
- **⏳ Live Decision:** 2026-07-06 14:00 UTC

---

## Files to Deploy (with fixes)

Located on PRIMARY at:
```
/home/vali/projects/crypto-daytrading/backend/trading/autonomous_trader/
├── exit.py       (Add MIN_HOLD_TIME_SECONDS = 10)
├── entry.py      (Add position limit + real signals)
└── core.py       (Add hard data quality gate)
```

Copy these to BACKUP at:
```
/home/claude/crypto-daytrading/backend/trading/autonomous_trader/
```

---

**Once BACKUP is deployed, reply with:** "BACKUP deployed ✅"

Then we can begin the 48-hour testing phase.

