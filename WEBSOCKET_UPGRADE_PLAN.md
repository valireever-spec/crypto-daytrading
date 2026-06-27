# WebSocket Real-Time Dashboard Upgrade Plan

**Current Status:** Dashboard polls every 10 seconds (10-second lag)  
**Goal:** Real-time push updates via WebSocket  
**Complexity:** Medium (4-6 hours)  
**Phase:** Phase 3 (after Phase 1 acceptance testing)  

---

## Current Implementation

```
Dashboard (polling)
  ├─ Every 10 seconds:
  │  └─ GET /api/paper/account
  │  └─ GET /api/paper/trades
  │  └─ GET /api/paper/positions
  └─ Lag: 10 seconds average
```

---

## Proposed WebSocket Implementation

```
Trading System
  ├─ Event: ORDER_FILLED
  │  └─ WebSocket broadcast to dashboard
  ├─ Event: POSITION_CLOSED
  │  └─ WebSocket broadcast to dashboard
  ├─ Event: P&L_UPDATED
  │  └─ WebSocket broadcast to dashboard
  └─ Lag: <100ms

Dashboard (WebSocket listener)
  ├─ Connect: GET /ws/trades
  ├─ Receive events real-time
  └─ Lag: <100ms average
```

---

## Implementation Steps

### Step 1: Create WebSocket Manager (3 hours)

**File:** `backend/api/websocket_manager.py`

```python
from fastapi import WebSocket
from typing import Set
import json
import logging

class WebSocketManager:
    """Manage WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
    
    async def broadcast_event(self, event_type: str, data: dict):
        """Broadcast event to all connected clients."""
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                await self.disconnect(connection)

# Global instance
_ws_manager: WebSocketManager = None

def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
```

### Step 2: Add WebSocket Endpoint (1 hour)

**File:** `backend/api/routes.py`

```python
@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    """Real-time trade updates via WebSocket."""
    manager = get_ws_manager()
    await manager.connect(websocket)
    
    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
```

### Step 3: Broadcast Events from Trading Loop (2 hours)

**File:** `backend/trading/autonomous_trader/core.py` & `exit.py`

When orders fill, broadcast events:

```python
# After order execution
manager = get_ws_manager()
await manager.broadcast_event("ORDER_FILLED", {
    "symbol": symbol,
    "side": side,
    "quantity": quantity,
    "price": price,
    "timestamp": datetime.utcnow().isoformat()
})
```

### Step 4: Update Frontend Dashboard (1 hour)

**File:** `frontend/dashboard.html`

```javascript
// Old: polling
// setInterval(() => fetch('/api/paper/account'), 10000)

// New: WebSocket
const ws = new WebSocket(`ws://${window.location.host}/ws/trades`);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'ORDER_FILLED':
            updateTrade(message.data);
            break;
        case 'POSITION_CLOSED':
            updatePositions(message.data);
            break;
        case 'P&L_UPDATED':
            updateMetrics(message.data);
            break;
    }
};
```

---

## Benefits

| Aspect | Polling (Current) | WebSocket (Proposed) |
|--------|-------------------|----------------------|
| Latency | ~10 seconds | <100 milliseconds |
| Server Load | HIGH (10 req/sec) | LOW (event-driven) |
| Frontend Complexity | Simple | Moderate |
| Network Usage | 4KB/10s = 0.4 KB/s | 1KB/event ≈ 0.1 KB/s |

---

## Timeline

**Phase 3 (after Phase 1 complete):**
- Week 1: Implement WebSocket manager + endpoint (3 hours)
- Week 2: Integrate with trading loop (2 hours)
- Week 3: Update frontend (1 hour)
- Week 4: Test real-time under load (1 hour)

**Total effort:** 7 hours  
**Breaking point:** Can ship Phase 1 without this

---

## Fallback: Shorter Polling Interval

If WebSocket not feasible, reduce polling to 1 second (vs 10s now):
- **Effort:** 5 minutes (change `setInterval(10000)` → `setInterval(1000)`)
- **Latency:** ~1 second average
- **Trade-off:** Higher server load, but still acceptable for paper trading

---

## Why Phase 3?

✅ Phase 1 & 2 work perfectly with 10-second polling  
✅ Paper trading doesn't need real-time precision  
✅ Frees up effort for critical Phase 1 work (HA, testing)  
✅ WebSocket adds complexity that can wait  

**Decision:** Ship Phase 1 with polling, upgrade Phase 3.
