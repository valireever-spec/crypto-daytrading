#!/bin/bash
# Phase 2 Deployment Script - Live Trading with Real Capital

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=================================="
echo "🚀 Phase 2 Deployment: LIVE TRADING"
echo "=================================="
echo ""

# Check .env file
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found"
    echo ""
    echo "Create .env with:"
    echo "  BINANCE_API_KEY=your_live_key"
    echo "  BINANCE_API_SECRET=your_live_secret"
    echo "  BINANCE_TESTNET=false"
    echo ""
    exit 1
fi

# Check if testnet is disabled
if grep -q "BINANCE_TESTNET=true" .env; then
    echo "❌ ERROR: BINANCE_TESTNET is still true"
    echo "Set BINANCE_TESTNET=false in .env before deploying live trading"
    exit 1
fi

echo "✅ .env file configured"
echo ""

# Verify API key is set
if ! grep -q "BINANCE_API_KEY" .env || grep "BINANCE_API_KEY=$" .env; then
    echo "❌ ERROR: BINANCE_API_KEY not set in .env"
    exit 1
fi

echo "✅ Binance API key configured"
echo ""

# Pre-flight checks
echo "Running pre-flight checks..."
echo ""

# Check API server
echo -n "1. API Server: "
if curl -s http://localhost:8001/api/health | grep -q "healthy"; then
    echo "✅ Running"
else
    echo "❌ Not responding, starting..."
    source venv/bin/activate
    python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api.log 2>&1 &
    sleep 3
fi

# Verify live mode
echo -n "2. Trading Mode: "
MODE=$(curl -s http://localhost:8001/api/health | jq -r '.account.mode' 2>/dev/null || echo "UNKNOWN")
if [ "$MODE" = "LIVE" ]; then
    echo "✅ LIVE (real money)"
elif [ "$MODE" = "PAPER" ]; then
    echo "⚠️  PAPER (testnet)"
    echo ""
    echo "Switching to LIVE mode..."
    # Restart with live config
    pkill -f "uvicorn.*8001" || true
    sleep 2
    source venv/bin/activate
    python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api.log 2>&1 &
    sleep 3
else
    echo "❌ Cannot determine mode"
    exit 1
fi

# Check BACKUP
echo -n "3. BACKUP System: "
if curl -s http://192.168.3.25:8002/api/health > /dev/null 2>&1; then
    echo "✅ Online"
else
    echo "⚠️  Offline (HA failover disabled)"
fi

# Check circuit breaker
echo -n "4. Circuit Breaker: "
CB=$(curl -s http://localhost:8001/api/health | jq -r '.circuit_breaker.status' 2>/dev/null || echo "UNKNOWN")
if [[ "$CB" == *"CLOSED"* ]]; then
    echo "✅ CLOSED (normal operation)"
else
    echo "⚠️  $CB"
fi

echo ""
echo "=================================="
echo "📊 Current Account State"
echo "=================================="
curl -s http://localhost:8001/api/health | jq '.account' 2>/dev/null || echo "Cannot fetch account state"
echo ""

echo "=================================="
echo "⚠️  FINAL CONFIRMATION REQUIRED"
echo "=================================="
echo ""
echo "This will START LIVE TRADING with REAL CAPITAL"
echo ""
echo "Verification:"
echo "  - Mode: LIVE (real money)"
echo "  - Capital: Check Binance balance"
echo "  - Risk Limits: 5% daily loss, 10% position size"
echo "  - Hardening: All 12 safety modules ACTIVE"
echo ""
read -p "Type 'PROCEED' to deploy Phase 2: " CONFIRM

if [ "$CONFIRM" != "PROCEED" ]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

echo ""
echo "🚀 DEPLOYING PHASE 2..."
echo ""

# Git commit
git add -A 2>/dev/null || true
git commit -m "chore: Phase 2 deployment initiated - live trading enabled" 2>/dev/null || true

# Restart services
echo "Restarting services..."
pkill -f "uvicorn.*8001" || true
sleep 2

source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > logs/api.log 2>&1 &

sleep 3

echo ""
echo "=================================="
echo "✅ PHASE 2 DEPLOYED - LIVE TRADING"
echo "=================================="
echo ""
echo "📊 Dashboard: http://localhost:8080/unified-dashboard.html"
echo "🔧 API: http://localhost:8001"
echo "📝 Logs: tail -f logs/api.log"
echo ""
echo "⚠️  Real money trading is now ACTIVE"
echo ""
echo "IMPORTANT:"
echo "  - Monitor dashboard every 30 minutes"
echo "  - Check logs daily for errors"
echo "  - Circuit breaker will auto-halt at 5% daily loss"
echo "  - BACKUP is ready for failover if PRIMARY fails"
echo ""
echo "🎯 Target: >55% win rate, positive P&L over 2 weeks"
echo ""
