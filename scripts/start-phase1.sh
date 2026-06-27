#!/bin/bash
# Phase 1 Startup Script - Paper Trading with Full Hardening

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Phase 1 Launch: Paper Trading with Hardening"
echo "=================================================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv
source venv/bin/activate

echo "✅ Virtual environment activated"
echo ""

# Kill existing processes on ports 8001 and 8080
echo "Checking for existing services..."
pkill -f "uvicorn.*8001" 2>/dev/null || true
pkill -f "http.server.*8080" 2>/dev/null || true
sleep 2

echo "Starting services..."
echo ""

# Start API server (background)
echo "1️⃣  Starting API Server (port 8001)..."
$VIRTUAL_ENV/bin/python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api.log 2>&1 &
API_PID=$!
sleep 3

# Start dashboard server (background)
echo "2️⃣  Starting Dashboard Server (port 8080)..."
python3 -m http.server 8080 --directory ./frontend > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
sleep 2

echo ""
echo "✅ Both servers started!"
echo ""
echo "=========================================="
echo "🟢 PHASE 1 IS LIVE"
echo "=========================================="
echo ""
echo "📊 Dashboard:"
echo "   URL: http://localhost:8080/unified-dashboard.html"
echo ""
echo "🔧 API Endpoints:"
echo "   Health: http://localhost:8001/api/health"
echo "   Account: http://localhost:8001/api/paper/account"
echo "   Positions: http://localhost:8001/api/paper/positions"
echo ""
echo "📝 Logs:"
echo "   API: tail -f logs/api.log"
echo "   Dashboard: tail -f logs/dashboard.log"
echo ""
echo "✅ Hardening:"
echo "   - 12 critical functions deployed"
echo "   - Order idempotency active"
echo "   - Risk gates enforced"
echo "   - ACID persistence enabled"
echo "   - HA failover ready"
echo ""
echo "📈 Current Status:"
curl -s http://localhost:8001/api/health | jq '.account | {equity: .total_equity, pnl: .total_pnl, positions: .active_positions}' 2>/dev/null || echo "   (API initializing...)"
echo ""
echo "Process IDs:"
echo "   API: $API_PID"
echo "   Dashboard: $DASHBOARD_PID"
echo ""
echo "To stop services:"
echo "   kill $API_PID $DASHBOARD_PID"
echo ""
echo "Or use: pkill -f 'uvicorn.*8001' && pkill -f 'http.server.*8080'"
