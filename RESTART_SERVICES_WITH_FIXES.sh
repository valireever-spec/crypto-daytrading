#!/bin/bash

# RESTART SERVICES WITH BUG FIXES
# Run this script to restart PRIMARY and BACKUP with the new code
# Usage: bash RESTART_SERVICES_WITH_FIXES.sh

set -e

echo "================================================"
echo "🔄 RESTARTING SERVICES WITH BUG FIXES"
echo "================================================"

echo -e "\n📋 Changes being loaded:"
echo "  ✅ Bug #1: Minimum hold time (exit.py)"
echo "  ✅ Bug #3: Position limit (entry.py)"
echo "  ✅ Bug #4: Data quality hard gate (core.py)"
echo "  ✅ Real signal generation (entry.py)"

# === PRIMARY MACHINE (LOCAL) ===
echo -e "\n=========================================="
echo "PRIMARY MACHINE (192.168.30.137:8001)"
echo "=========================================="

echo "Step 1: Stopping PRIMARY service..."
pkill -TERM -f "uvicorn.*8001" || true
sleep 3

# Force kill if still running
if pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "Forcing termination..."
    pkill -9 -f "uvicorn.*8001" || true
    sleep 2
fi

echo "Step 2: Verifying PRIMARY is stopped..."
if ! pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "✅ PRIMARY stopped"
else
    echo "⚠️  WARNING: PRIMARY still running - permissions issue?"
    echo "   Try: sudo pkill -9 -f 'uvicorn.*8001'"
    exit 1
fi

echo "Step 3: Starting PRIMARY with new code..."
cd /home/vali/projects/crypto-daytrading
source venv/bin/activate
nohup python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --log-level info > logs/api_startup.log 2>&1 &

sleep 5

echo "Step 4: Verifying PRIMARY is running..."
if pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "✅ PRIMARY restarted (port 8001)"
    sleep 2
    curl -s http://localhost:8001/api/health | jq '.status' && echo "✅ PRIMARY API responding" || echo "⚠️  API not responding yet"
else
    echo "❌ PRIMARY failed to start"
    echo "Check logs: tail -50 logs/api_startup.log"
    exit 1
fi

# === BACKUP MACHINE (REMOTE via SSH) ===
echo -e "\n=========================================="
echo "BACKUP MACHINE (192.168.3.25:8002)"
echo "=========================================="

# Check if BACKUP is accessible
if ssh -o ConnectTimeout=5 -p 2347 claude@localhost "echo 'test'" > /dev/null 2>&1; then
    echo "✅ BACKUP accessible via SSH reverse tunnel"

    echo "Step 1: Stopping BACKUP service..."
    ssh -p 2347 claude@localhost "pkill -TERM -f 'uvicorn.*8002'" || true
    sleep 3

    echo "Step 2: Starting BACKUP with new code..."
    ssh -p 2347 claude@localhost << 'BACKUP_SCRIPT'
    cd /home/claude/crypto-daytrading
    source venv/bin/activate
    nohup python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8002 --log-level info > logs/api_startup.log 2>&1 &
    sleep 5
    echo "BACKUP startup initiated"
BACKUP_SCRIPT

    echo "Step 3: Verifying BACKUP is running..."
    sleep 3
    ssh -p 2347 claude@localhost "curl -s http://localhost:8002/api/health | jq '.status'" && echo "✅ BACKUP restarted (port 8002)" || echo "⚠️  BACKUP not responding yet"

else
    echo "⚠️  BACKUP not accessible via SSH (reverse tunnel not active)"
    echo "   BACKUP restart will need to be done manually:"
    echo "   ssh -p 2347 claude@BACKUP_IP"
    echo "   pkill -9 -f 'uvicorn.*8002'"
    echo "   cd /home/claude/crypto-daytrading && source venv/bin/activate"
    echo "   python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8002"
fi

# === VERIFICATION ===
echo -e "\n=========================================="
echo "✅ VERIFICATION CHECKLIST"
echo "=========================================="

echo "Checking PRIMARY..."
PRIMARY_HEALTH=$(curl -s http://localhost:8001/api/health | jq '.status' 2>/dev/null)
if [ "$PRIMARY_HEALTH" == '"healthy"' ]; then
    echo "✅ PRIMARY healthy"
else
    echo "⚠️  PRIMARY status: $PRIMARY_HEALTH"
fi

echo -e "\nChecking logs for bug fixes..."

echo -e "\n1️⃣  Minimum Hold Time (exit.py):"
grep -q "MIN_HOLD_TIME_SECONDS = 10" backend/trading/autonomous_trader/exit.py && echo "   ✅ Code change verified" || echo "   ❌ Not found"

echo -e "\n2️⃣  Position Limit (entry.py):"
grep -q "max_position_pct = 10.0" backend/trading/autonomous_trader/entry.py && echo "   ✅ Code change verified" || echo "   ❌ Not found"

echo -e "\n3️⃣  Real Signal Generation (entry.py):"
grep -q "Mean reversion" backend/trading/autonomous_trader/entry.py && echo "   ✅ Code change verified" || echo "   ❌ Not found"

echo -e "\n4️⃣  Data Quality Hard Gate (core.py):"
grep -q "HARD GATE" backend/trading/autonomous_trader/core.py && echo "   ✅ Code change verified" || echo "   ❌ Not found"

echo -e "\n=========================================="
echo "✅ RESTART COMPLETE"
echo "=========================================="
echo -e "\nNext steps:"
echo "1. Monitor logs: tail -f logs/system.log"
echo "2. Watch for 'HARD GATE' and 'MIN_HOLD' messages"
echo "3. Run trading test for 48 hours"
echo "4. Check win rate (target >20%)"
echo "5. If successful, approve live trading"

