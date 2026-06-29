# HA Network Architecture & Requirements

## Network Topology

### Scenario 1: Local Network (Same LAN)
```
PRIMARY (192.168.30.137 on local LAN)
    ├─ Direct reachability: 192.168.30.137:8001
    └─ Trades actively
    
BACKUP (192.168.3.25 on same LAN)
    ├─ Can reach PRIMARY directly via LAN
    └─ Standby, ready to take over
```

### Scenario 2: Remote Network (Different LAN, Internet)
```
PRIMARY (behind ISP router, unknown external IP)
    ├─ Internal LAN: 192.168.30.137 (or different IP each time)
    ├─ External IP: Dynamic (assigned by ISP, changes)
    ├─ Initiates: Reverse SSH tunnel → r33v3r.ddns.net:22
    │   └─ Tunnel command: ssh -R 8001:127.0.0.1:8001 r33v3r.ddns.net
    └─ Sends heartbeat signal through tunnel to BACKUP
    
BACKUP (192.168.3.25)
    ├─ Cannot reach PRIMARY on local IPs (different network)
    ├─ Connects to PRIMARY via tunnel: localhost:8001 (forwarded to r33v3r.ddns.net)
    ├─ Listens for heartbeat from PRIMARY
    └─ On heartbeat loss: Activates autonomous trader
```

---

## Core Requirements

### R1: PRIMARY IP Variability
- **Requirement:** PRIMARY machine IP is NOT fixed
- **Reason:** PRIMARY can be:
  - On local LAN: 192.168.30.137 (or different subnet)
  - On remote LAN behind router: Unknown dynamic IP assigned by ISP
  - On internet directly: Another dynamic IP
- **Implication:** Cannot use static IP-based health checks
- **Solution:** Use reverse SSH tunnel (PRIMARY initiates outbound connection)

### R2: Reverse SSH Tunnel Setup
- **Requirement:** PRIMARY must establish reverse SSH tunnel to r33v3r.ddns.net
- **Reason:** 
  - PRIMARY is behind router, unreachable from internet
  - PRIMARY initiates outbound connection (firewalls allow this)
  - BACKUP can connect back through tunnel
- **Command:** `ssh -R 8001:127.0.0.1:8001 user@r33v3r.ddns.net -N`
- **Result:** localhost:8001 on r33v3r.ddns.net forwards to PRIMARY:8001
- **BACKUP accesses via:** `http://localhost:8001` (with tunnel configured)

### R3: Heartbeat Signal (Critical)
- **Requirement:** PRIMARY must send regular heartbeat to BACKUP through SSH tunnel
- **Reason:**
  - When PRIMARY goes offline, reverse SSH tunnel dies
  - HTTP health checks through dead tunnel may timeout instead of failing fast
  - Explicit heartbeat proves PRIMARY is alive and tunnel is healthy
- **Heartbeat endpoint:** `POST /api/ha/heartbeat` on BACKUP
- **Frequency:** Every 5 seconds (matches sync frequency)
- **Payload:** `{machine_id: "main", timestamp: ISO8601, state: {cash, positions}}`
- **Detection:** BACKUP monitors heartbeat; if no heartbeat for >15 seconds → PRIMARY down

### R4: Failover Detection (Two-Path)
- **Path A (Primary):** Listen for heartbeat from PRIMARY
  - If heartbeat stops: PRIMARY is down, activate trading
  - Fast detection: ~5-15 seconds
  - Reliable: Independent of tunnel connectivity
  
- **Path B (Fallback):** HTTP health check via tunnel
  - If tunnel fails AND no recent heartbeat: Assume PRIMARY down
  - Slower: ~10-30 seconds (timeout-based)
  - Confirms tunnel connectivity

### R5: BACKUP Configuration
- **PRIMARY_API_URL:** `http://localhost:8001` (tunnel endpoint on BACKUP)
- **SSH tunnel setup:** Must be configured in ~/.ssh/config or systemd
- **Heartbeat listener:** Always active, logs every heartbeat
- **Failover trigger:** No heartbeat for >15 seconds (3 consecutive missed beats @ 5s interval)

### R6: PRIMARY Configuration
- **BACKUP_API_URL:** IP of BACKUP machine (192.168.3.25:8002)
- **Heartbeat task:** Send heartbeat every 5 seconds
- **Heartbeat route:** POST → BACKUP_API_URL/api/ha/heartbeat
- **Sync task:** Continue every 5 seconds (state sync)
- **Both independent:** Heartbeat and sync operate separately

---

## Failover Flow

### Phase 1: Normal Operation
```
PRIMARY (alive)
├─ Every 5s: Send heartbeat to BACKUP
├─ Every 5s: Sync state (cash, positions) to BACKUP
└─ Trading: Enabled

BACKUP (standby)
├─ Every 5s: Receive heartbeat (reset timer)
├─ Every 5s: Receive state sync
└─ Trading: Disabled
```

### Phase 2: PRIMARY Goes Down
```
PRIMARY: Offline (machine/network down)
├─ Reverse SSH tunnel dies
├─ Heartbeat stops
└─ State sync stops

BACKUP: Detects failure
├─ Heartbeat timer: No signal for 5s (1 miss) → Log warning
├─ Heartbeat timer: No signal for 10s (2 misses) → Log critical
├─ Heartbeat timer: No signal for 15s (3 misses) → Failover triggered
└─ Action: Enable autonomous trader, start trading
```

### Phase 3: PRIMARY Recovers
```
PRIMARY: Back online
├─ Establishes reverse SSH tunnel to r33v3r.ddns.net
├─ Resumes heartbeat to BACKUP every 5s
└─ Resumes state sync every 5s

BACKUP: Detects recovery
├─ Heartbeat received → Reset timer
├─ Confirm PRIMARY healthy (e.g., 3 consecutive heartbeats)
└─ Action: Stop autonomous trader, return to standby
```

---

## Implementation Details

### Heartbeat Endpoint (BACKUP)
```
POST /api/ha/heartbeat
Content-Type: application/json

{
  "machine_id": "main",
  "timestamp": "2026-06-29T10:30:45Z",
  "state": {
    "cash": 1000.0,
    "total_pnl": 25.50,
    "positions": [
      {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 45000}
    ],
    "active_positions": 1,
    "trades_today": 3
  }
}

Response:
{
  "status": "received",
  "timestamp": "2026-06-29T10:30:45Z",
  "backup_state": {...}
}
```

### Heartbeat Monitor (BACKUP)
```python
class HeartbeatMonitor:
    - missed_count: int = 0
    - last_heartbeat_time: datetime
    - threshold: int = 3 (15 seconds @ 5s interval)
    
    - on_heartbeat_received():
        - missed_count = 0
        - last_heartbeat_time = now()
        
    - check_timeout():
        - elapsed = now() - last_heartbeat_time
        - if elapsed > 5s: missed_count += 1
        - if missed_count >= threshold: TRIGGER_FAILOVER()
```

### Heartbeat Sender (PRIMARY)
```python
async def send_heartbeat():
    """Send heartbeat every 5 seconds to BACKUP."""
    backup_url = os.getenv("BACKUP_API_URL")
    while True:
        try:
            state = {
                "machine_id": "main",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "state": {
                    "cash": engine.cash,
                    "total_pnl": engine.total_pnl,
                    "positions": engine.get_positions(),
                    "active_positions": count_active(),
                    "trades_today": count_today()
                }
            }
            
            response = await httpx.post(
                f"{backup_url}/api/ha/heartbeat",
                json=state,
                timeout=2
            )
            
            if response.status_code == 200:
                logger.debug(f"✅ Heartbeat sent to BACKUP")
            else:
                logger.warning(f"❌ Heartbeat failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Heartbeat error (will retry): {e}")
        
        await asyncio.sleep(5)
```

---

## Network Configuration

### ~/.ssh/config (on BACKUP or via systemd)
```
Host primary-reverse
    HostName r33v3r.ddns.net
    User your_user
    IdentityFile ~/.ssh/id_rsa
    LocalForward 8001 127.0.0.1:8001
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ConnectionAttempts 3
    ConnectTimeout 10
```

### Systemd Service (to maintain tunnel)
```ini
[Unit]
Description=SSH Reverse Tunnel to r33v3r.ddns.net
After=network.target

[Service]
Type=simple
User=claude
ExecStart=/usr/bin/ssh -N -R 8001:127.0.0.1:8001 r33v3r.ddns.net
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Success Criteria

- ✅ PRIMARY sends heartbeat every 5 seconds
- ✅ BACKUP receives heartbeat reliably
- ✅ Heartbeat contains state (cash, positions, trades)
- ✅ BACKUP detects PRIMARY failure within 15 seconds (3 missed heartbeats)
- ✅ BACKUP enables autonomous trader on failure
- ✅ BACKUP disables trader when PRIMARY recovers
- ✅ No dual-active (both trading at same time)
- ✅ Trades continue uninterrupted during failover
- ✅ State syncs after failover

---

## Open Questions

1. **Heartbeat on recovery:** How many consecutive heartbeats before BACKUP disables trading? (Recommend: 3)
2. **Timeout handling:** What if heartbeat times out but PRIMARY is actually alive? (Recommend: Log warning, continue waiting)
3. **Network flakiness:** How to distinguish between network glitch vs. actual PRIMARY down? (Recommend: 15s threshold)
4. **Reverse tunnel monitoring:** Should we also monitor the reverse SSH tunnel health independently? (Recommend: Yes, as Path B)
