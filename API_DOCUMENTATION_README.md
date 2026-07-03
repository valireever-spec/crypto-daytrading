# API Documentation for Crypto-DayTrading Platform

## Overview

This directory contains comprehensive API documentation for the Crypto-DayTrading autonomous trading platform.

**Generated:** 2026-07-03
**Total Endpoints:** 197
**Documentation Format:** Markdown + OpenAPI 3.0

## Files

### 1. API_CONTRACT.md (48 KB, 3,182 lines)

**Purpose:** Complete REST API documentation with detailed endpoint specifications.

**Contents:**
- Executive summary and overview
- Connection details and response formats
- HTTP status codes reference
- 197 endpoints organized by 19 functional categories:
  - Trading Account Management (6 endpoints)
  - Autonomous Trading Control (8 endpoints)
  - Monitoring & Health Checks (19 endpoints)
  - High Availability & Failover (8 endpoints)
  - Portfolio Allocation & Optimization (7 endpoints)
  - Risk Management (6 endpoints)
  - Trading Control (6 endpoints)
  - Configuration Management
  - And 11+ more categories

- Detailed endpoint reference section with:
  - Parameter types and documentation
  - Request/response examples
  - cURL command cheat sheet
  - Error response examples
  - Integration guides (Python, JavaScript/Node.js)

- Production deployment recommendations
- Security checklist
- Troubleshooting guide

**How to Use:**
1. Start with "Executive Summary" for high-level overview
2. Use "Quick Reference" table to find endpoint categories
3. Jump to specific category section for detailed documentation
4. Reference "Detailed Endpoint Reference" for parameter details and examples
5. Use "cURL Cheat Sheet" for quick testing

### 2. openapi.json (13 KB)

**Purpose:** OpenAPI 3.0 specification for machine-readable API definition.

**Contents:**
- Standard OpenAPI structure with:
  - API metadata (title, version, description)
  - Server configuration
  - 14 core endpoint definitions
  - 6 reusable schema definitions:
    - Account (with cash, equity, P&L)
    - Position (symbol, quantity, entry_price, etc.)
    - Trade (side, quantity, price, timestamp)
    - Error (error, detail, status_code)
    - ConfigUpdateRequest (trading parameters)
    - HAStatus (PRIMARY/BACKUP role)

**How to Use:**
1. **Import into Postman/Insomnia:** File → Import → Select openapi.json
2. **Generate client libraries:**
   ```bash
   # Using OpenAPI Generator
   openapi-generator-cli generate -i openapi.json -g python -o python-client
   openapi-generator-cli generate -i openapi.json -g typescript-axios -o ts-client
   ```
3. **Validate with:** `openapi-spec-validator openapi.json`
4. **Publish API docs:** Use Swagger UI or ReDoc
5. **Create mock API:** Use Prism or similar tool

## Key Sections in API_CONTRACT.md

### Quick Start
1. Read "Executive Summary" (2 min)
2. Review "Connection Information" (1 min)
3. Check "Quick Reference" table (1 min)

### For Integration
1. Find your endpoint in category section (2 min)
2. Review request/response format (2 min)
3. Copy cURL example and adapt (3 min)
4. Test with actual API (5 min)

### For Production
1. Read "Production Recommendations" (5 min)
2. Review "Security Checklist" (5 min)
3. Implement authentication/HTTPS (30 min)
4. Set up monitoring/logging (30 min)

## API Categories

### Trading Account Management
- `GET /api/paper/account` - Get account balance and equity
- `GET /api/paper/positions` - Get open positions
- `GET /api/paper/trades` - Get trade history
- `POST /api/paper/reset` - Reset account (testing only)
- `GET /api/paper/status` - Get comprehensive trading status

### Autonomous Trading Control
- `GET /api/autonomous/status` - Get trader status
- `POST /api/autonomous/start` - Enable autonomous trading
- `POST /api/autonomous/stop` - Disable autonomous trading
- `GET /api/autonomous/config` - Get current configuration
- `POST /api/autonomous/config/update` - Update parameters
- Plus 3 more advanced endpoints

### Monitoring & Health
- `GET /api/health` - Overall system health
- `GET /api/monitoring/health` - Comprehensive health status
- `GET /api/monitoring/health/service/{name}` - Service-specific health
- `GET /api/monitoring/alerts` - Get alerts
- `POST /api/monitoring/alerts/create` - Create manual alert
- Plus 14 more monitoring endpoints

### High Availability
- `GET /api/ha/status` - Get PRIMARY/BACKUP status
- `POST /api/ha/heartbeat` - Send heartbeat (BACKUP endpoint)
- `POST /api/ha/sync-from-primary` - Sync state (BACKUP)
- `POST /api/ha/sync-from-backup` - Sync state (PRIMARY recovery)
- Plus 4 more HA endpoints

### Portfolio & Risk
- `/allocation` - Portfolio allocation endpoints (7 endpoints)
- `/risk` - Risk management endpoints (6 endpoints)
- `/rebalancing` - Rebalancing endpoints (5 endpoints)
- `/portfolio` - Portfolio analysis endpoints (4 endpoints)

### Trading Control
- `POST /api/trading/pause` - Pause trading
- `POST /api/trading/resume` - Resume trading
- `POST /api/trading/exit` - Partial position exit
- Plus 3 more control endpoints

### Remaining Categories
- Configuration Management (1 endpoint)
- Dashboard Integration (5 endpoints)
- System Metrics (4 endpoints)
- Stock Trading (7 endpoints)
- Tax Management (8 endpoints)
- User Management (4 endpoints)
- And 5+ more specialized categories

## Common Use Cases

### 1. Monitor Account Health
```bash
# Check account balance
curl http://localhost:8000/api/paper/account

# Check trading status
curl http://localhost:8000/api/paper/status

# Check system health
curl http://localhost:8000/api/health
```

### 2. Start Autonomous Trading
```bash
# Get current config
curl http://localhost:8000/api/autonomous/config

# Update config
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{"position_size_pct": 2.0, "max_positions": 5}'

# Start trading
curl -X POST http://localhost:8000/api/autonomous/start
```

### 3. Monitor Alerts
```bash
# Get active alerts
curl "http://localhost:8000/api/monitoring/alerts?status=active"

# Get alerts for specific service
curl "http://localhost:8000/api/monitoring/alerts/service/paper_trading"
```

### 4. Get Metrics
```bash
# System metrics (Prometheus format)
curl http://localhost:8000/metrics

# Get current metrics (JSON)
curl http://localhost:8000/api/monitoring/metrics
```

## Testing the API

### Using cURL
```bash
# Simple health check
curl http://localhost:8000/api/health

# With pretty JSON output
curl http://localhost:8000/api/paper/account | jq .

# POST with data
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Using Postman
1. File → Import
2. Select `openapi.json`
3. Use "Collections" tab to browse endpoints
4. Fill in parameters and send

### Using Python
```python
import requests

# Get account status
resp = requests.get('http://localhost:8000/api/paper/account')
print(resp.json())

# Start trading
resp = requests.post('http://localhost:8000/api/autonomous/start')
print(resp.json())
```

### Using JavaScript
```javascript
// Get account status
fetch('http://localhost:8000/api/paper/account')
  .then(r => r.json())
  .then(data => console.log(data));

// Start trading
fetch('http://localhost:8000/api/autonomous/start', {
  method: 'POST'
})
  .then(r => r.json())
  .then(data => console.log(data));
```

## Response Formats

### Success Response (200 OK)
```json
{
  "cash": 1220.41,
  "equity": 1441.97,
  "pnl": 221.56,
  "timestamp": "2026-07-03T17:30:00Z"
}
```

### Error Response (4xx/5xx)
```json
{
  "error": "ERROR_CODE",
  "detail": "Human-readable message",
  "status_code": 400
}
```

## HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful request |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Auth required |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource missing |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Internal error |
| 503 | Service Unavailable | Service down |

## Rate Limiting

- **Limit:** 100 requests/minute per client
- **Window:** Rolling 60-second window
- **Header:** `X-RateLimit-Remaining` (remaining requests)
- **Status:** 429 when limit exceeded

## Security

### Current State
- **Authentication:** None (local deployment)
- **HTTPS:** Not enforced (HTTP only)
- **CORS:** Enabled for all origins

### Before Production
- Add JWT or OAuth2 authentication
- Use HTTPS/TLS certificates
- Restrict CORS to specific origins
- Implement stricter rate limiting
- Add request signing

### Security Headers
The API includes these headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`

## Architecture

### High Availability
```
PRIMARY Instance (machine_id=main)
  └─ Sends heartbeats every 5s
  └─ Syncs state to BACKUP
  └─ Active trading

BACKUP Instance (machine_id=backup)
  └─ Monitors heartbeats
  └─ Automatically promotes on failure
  └─ Syncs state back to PRIMARY on recovery
```

### Failover Flow
1. PRIMARY sends heartbeat to BACKUP every 5 seconds
2. BACKUP monitors heartbeat status
3. On heartbeat loss, BACKUP automatically promotes itself
4. When PRIMARY recovers, it syncs state from BACKUP

## Troubleshooting

### 503 Service Unavailable
- Paper trading engine not initialized
- Check `/api/health` endpoint
- Restart API server if needed

### 400 Bad Request
- Missing required parameters
- Invalid parameter types
- Check request format and Content-Type

### 429 Too Many Requests
- Rate limit exceeded (100 req/min)
- Implement exponential backoff
- Distribute requests over time

### Slow Response Times
- Check system metrics: `/metrics`
- Monitor CPU, memory, database performance
- Scale horizontally if needed

## Integration Guide

### Build a Client Library
```bash
# Using OpenAPI Generator
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o crypto-trading-client
```

### Set Up Monitoring
```bash
# Prometheus scrape config
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'crypto-trading'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Create Dashboards
- Import `openapi.json` into Swagger UI
- Use Grafana with Prometheus data
- Build custom dashboards from metrics

## Documentation Structure

```
API_CONTRACT.md (48 KB)
├── Executive Summary
├── API Overview
│   └── Connection Information, Response Formats
├── Quick Reference
│   └── Summary table by category
├── Endpoint Categories (19 sections)
│   ├── Trading Account Management
│   ├── Autonomous Trading Control
│   ├── Monitoring & Health Checks
│   └── ... (16 more categories)
├── Detailed Endpoint Reference
│   ├── Core Parameters & Types
│   ├── Request/Response Examples
│   ├── Error Handling
│   ├── Integration Guides
│   └── cURL Cheat Sheet
├── Deployment Considerations
├── Security & Troubleshooting
└── Next Steps

openapi.json (13 KB)
├── Metadata (title, version)
├── Servers
├── Paths (14+ endpoints)
├── Components
│   └── Schemas (6 reusable)
└── Security Schemes
```

## Next Steps

1. **Validate API:** `openapi-spec-validator openapi.json`
2. **Generate Client:** Use OpenAPI Generator
3. **Set Up Testing:** Create integration tests
4. **Build Monitoring:** Wire up Prometheus/Grafana
5. **Secure:** Add authentication before production
6. **Document Webhooks:** When event streaming is added

## Support

For API issues:
1. Check `/api/health` for overall status
2. Review error response details
3. Check application logs
4. Refer to "Troubleshooting" section
5. Validate request format against documentation

---

**Generated:** 2026-07-03
**Platform:** Crypto-DayTrading v1.0
**API Version:** 1.0.0
**Documentation Format:** Markdown + OpenAPI 3.0
