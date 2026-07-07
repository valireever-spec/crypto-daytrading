# REST API Conventions
**Crypto-Daytrading Platform**  
**Version:** 1.0  
**Last Updated:** 2026-07-07

---

## Overview

This document defines the REST API standards for consistent, predictable endpoints.

---

## HTTP Methods

### GET - Retrieve Resources
- **Purpose:** Fetch data without side effects
- **Body:** None (query parameters only)
- **Response:** 200 OK with resource(s)
- **Example:**
  ```
  GET /api/trades?limit=100&offset=0
  GET /api/trades/uuid-123
  GET /api/signals?symbol=BTCUSDT
  ```

### POST - Create Resources
- **Purpose:** Create new resource
- **Body:** JSON object with resource data
- **Response:** 201 Created with created resource
- **Example:**
  ```
  POST /api/trades
  {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.1
  }
  ```

### PUT - Replace Resources
- **Purpose:** Replace entire resource
- **Body:** Complete resource object
- **Response:** 200 OK with updated resource
- **Idempotent:** Yes
- **Example:**
  ```
  PUT /api/trades/uuid-123
  {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.2
  }
  ```

### PATCH - Partial Update
- **Purpose:** Update specific fields only
- **Body:** Only changed fields
- **Response:** 200 OK with updated resource
- **Idempotent:** Yes
- **Example:**
  ```
  PATCH /api/trades/uuid-123
  {
    "quantity": 0.15
  }
  ```

### DELETE - Remove Resources
- **Purpose:** Delete resource
- **Body:** None
- **Response:** 204 No Content (or 200 OK with deleted resource)
- **Idempotent:** Yes
- **Example:**
  ```
  DELETE /api/trades/uuid-123
  ```

---

## URL Structure

### Base Patterns

#### Collection Endpoints
```
GET    /api/resource              - List all resources
POST   /api/resource              - Create new resource
```

#### Item Endpoints
```
GET    /api/resource/{id}         - Get specific resource
PUT    /api/resource/{id}         - Replace resource
PATCH  /api/resource/{id}         - Update resource
DELETE /api/resource/{id}         - Delete resource
```

#### Nested Collections
```
GET    /api/parent/{id}/children          - List related items
POST   /api/parent/{id}/children          - Create related item
GET    /api/parent/{id}/children/{id}     - Get specific related item
```

### Naming Rules
- ✅ Use nouns (not verbs): `/api/trades` not `/api/getTrades`
- ✅ Use lowercase: `/api/trades` not `/api/Trades`
- ✅ Use plural for collections: `/api/trades` not `/api/trade`
- ✅ Use hyphens for compound words: `/api/signal-analysis` not `/api/signalanalysis`
- ✅ Use UUIDs for resource IDs: `/api/trades/550e8400-e29b-41d4-a716-446655440000`

### Examples (Current & Corrected)

| Current | ✅ Corrected | Issue |
|---------|-------------|-------|
| `/api/get-trades` | `GET /api/trades` | Verb in endpoint |
| `/getTrade/{id}` | `GET /api/trades/{id}` | Inconsistent prefix |
| `/trade/{id}/Delete` | `DELETE /api/trades/{id}` | Method in URL |
| `/api/SignalAnalysis` | `GET /api/signals/analysis` | Mixed case |
| `/trading/place_order` | `POST /api/trades` | Inconsistent prefix |

---

## Response Format

### Success Response (200, 201)
```json
{
  "data": {
    "id": "uuid-123",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.1,
    "created_at": "2026-07-07T12:00:00Z"
  },
  "meta": {
    "timestamp": "2026-07-07T12:00:00Z"
  }
}
```

### List Response (200)
```json
{
  "data": [
    {"id": "uuid-1", "symbol": "BTCUSDT"},
    {"id": "uuid-2", "symbol": "ETHUSDT"}
  ],
  "meta": {
    "total": 100,
    "limit": 10,
    "offset": 0,
    "timestamp": "2026-07-07T12:00:00Z"
  }
}
```

### Error Response (400, 401, 403, 404, 429, 500)
```json
{
  "error": {
    "code": "invalid_symbol",
    "message": "Trading pair 'INVALID' not supported",
    "details": {
      "supported_pairs": ["BTCUSDT", "ETHUSDT"]
    }
  },
  "meta": {
    "timestamp": "2026-07-07T12:00:00Z"
  }
}
```

### Rate Limit Response (429)
```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests. Limit: 100 per minute"
  },
  "meta": {
    "timestamp": "2026-07-07T12:00:00Z",
    "rate_limit": {
      "limit": 100,
      "remaining": 0,
      "reset_at": "2026-07-07T12:01:00Z"
    }
  }
}
```

---

## Status Codes

### Success (2xx)
| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | GET, PUT, PATCH successful |
| 201 | Created | POST successful, resource created |
| 204 | No Content | DELETE successful, no response body |

### Client Error (4xx)
| Code | Meaning | When Used |
|------|---------|-----------|
| 400 | Bad Request | Invalid parameters, missing required fields |
| 401 | Unauthorized | Missing/invalid authentication |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded (see rate-limiting.py) |

### Server Error (5xx)
| Code | Meaning | When Used |
|------|---------|-----------|
| 500 | Internal Server Error | Unhandled exception |
| 503 | Service Unavailable | Database down, external service unavailable |

---

## Request Format

### Required Headers
```
Content-Type: application/json
X-API-Key: {api-key}  # If authentication required
```

### Optional Headers
```
X-Request-ID: {uuid}        # For tracking requests
Accept: application/json    # Always JSON for this API
```

### Query Parameters
```
GET /api/trades?limit=10&offset=0&status=filled
  - limit: Max results (default: 100, max: 1000)
  - offset: Skip N results (default: 0)
  - status: Filter by status (optional)
  - sort_by: Sort field (optional, default: created_at)
  - sort_order: asc or desc (optional, default: desc)
```

---

## Pagination

### Request
```
GET /api/trades?limit=10&offset=20
```

### Response
```json
{
  "data": [...],
  "meta": {
    "total": 500,
    "limit": 10,
    "offset": 20,
    "has_more": true
  }
}
```

### Rules
- Default limit: 100
- Maximum limit: 1000
- Use offset for pagination (not cursor)
- Include `has_more` to indicate more results

---

## Filtering & Sorting

### Filtering
```
GET /api/trades?status=filled
GET /api/trades?symbol=BTCUSDT&side=BUY
GET /api/trades?created_at_gte=2026-07-01&created_at_lte=2026-07-07
```

Supported operators:
- `=` (exact match)
- `_gte` (greater than or equal)
- `_lte` (less than or equal)
- `_gt` (greater than)
- `_lt` (less than)
- `_ne` (not equal)
- `_in` (comma-separated list)

### Sorting
```
GET /api/trades?sort_by=created_at&sort_order=desc
GET /api/trades?sort_by=pnl&sort_order=asc
```

Supported fields: `created_at`, `symbol`, `pnl`, `status`

---

## Timestamps

### Format
- All timestamps are ISO 8601 format: `2026-07-07T12:00:00Z`
- All times in UTC (Z suffix)
- Include milliseconds if precision needed: `2026-07-07T12:00:00.123Z`

### Fields
```json
{
  "created_at": "2026-07-07T12:00:00Z",      # When resource was created
  "updated_at": "2026-07-07T13:00:00Z",      # When resource was last updated
  "executed_at": "2026-07-07T12:00:01Z"      # When action completed
}
```

---

## Data Types

### Numbers
- Prices: Decimal numbers (6 decimal places): `61987.123456`
- Quantities: Decimal numbers (8 decimal places): `0.12345678`
- Percentages: Decimal 0-100: `5.5` (not `0.055`)
- Integers: No decimals: `100`

### Identifiers
- UUIDs: `550e8400-e29b-41d4-a716-446655440000`
- Never use sequential integers

### Booleans
- `true` / `false` (lowercase JSON)

### Enums
- All uppercase: `"status": "FILLED"`
- Valid values documented in schema

---

## Versioning

### Current Version
- Version: 1.0
- Base URL: `/api/` (no version suffix for v1)

### Future Versioning
When breaking changes needed:
- `/api/v2/trades` (new version)
- `/api/v1/trades` (old version continues working)
- Minimum 6-month support for old versions

---

## Documentation

All endpoints must have:
1. ✅ OpenAPI/Swagger definition (see `openapi.yaml`)
2. ✅ Description of what the endpoint does
3. ✅ Request parameters documented
4. ✅ Response format documented
5. ✅ Error codes documented
6. ✅ Example request/response

---

## Checklist for New Endpoints

- [ ] URL follows REST conventions (nouns, lowercase, hyphens)
- [ ] HTTP method is correct (GET, POST, PUT, PATCH, DELETE)
- [ ] Request format documented
- [ ] Response format documented
- [ ] Status codes documented
- [ ] Error cases documented
- [ ] Pagination implemented (if returning lists)
- [ ] Rate limiting applied
- [ ] Authentication required (if sensitive)
- [ ] OpenAPI spec updated
- [ ] Tests written
- [ ] Code reviewed

---

**Audit Status:** ✅ Complete - REST conventions validated  
**Last Updated:** 2026-07-07

