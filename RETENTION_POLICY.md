# Transaction Retention Policy
**Effective:** 2026-07-02  
**Policy:** Keep 3 years of immutable transaction history

---

## Overview

The crypto-daytrading system maintains transaction records across three layers with different retention strategies:

| Layer | Retention | Purpose |
|-------|-----------|---------|
| **JSONL Immutable Log** | 3 years | Compliance, audit trail, historical analysis |
| **SQLite Database** | 90 days | Active trading, quick queries, operational |
| **API Memory Cache** | Since last restart | Real-time access |

---

## Retention Details

### 1. JSONL Immutable Log (3 Years) ✅

**Location:** `logs/immutable/trades_active.jsonl`

**Retention Span:** 2023-07-02 to 2026-07-02 (and rolling forward)

**Capacity Planning:**
- Current: 6 trades = 2.5 KB
- Estimated at 50 trades/day: ~8.7 MB/year
- For 3 years: ~26 MB storage
- Available: 820 GB
- **Impact:** Negligible (<0.001% of disk)

**Archival Strategy:**
- Every July 2nd, compress trades older than 3 years
- Archive to: `logs/archive/trades_<year>.jsonl.gz`
- Keep active log ≤ 50 MB
- Verify checksums before deletion

**Example Timeline:**
```
2026-07-02: Current (keep)
2025-07-02: 1 year old (keep)
2024-07-02: 2 years old (keep)
2023-07-02: 3 years old (keep until 2026-07-03)
2023-07-01: 3+ years old (archive to backup)
```

---

### 2. SQLite Database (90 Days)

**Purpose:** Live trading queries, fast access

**Cleanup Schedule:**
- Daily: Archive trades older than 90 days
- Command: `python scripts/archive_old_trades.py --days 90`
- Result: Trade exported to JSONL archive, then deleted from live DB

**Size Target:** Keep <1 GB (prevents query slowdown)

---

### 3. Backup Strategy

**Primary Backups (3-year archive):**
- `logs/archive/trades_2023.jsonl.gz`
- `logs/archive/trades_2024.jsonl.gz`
- `logs/archive/trades_2025.jsonl.gz`

**Verification:**
- SHA256 hash stored in `logs/archive/.checksums`
- Verify on retrieval: `sha256sum -c .checksums`

**Disaster Recovery:**
- If SQLite corrupts: restore from JSONL archive
- If JSONL corrupts: restore from backup copy (NAS/cloud)

---

## Implementation Checklist

- [x] Define 3-year retention policy
- [ ] Create `scripts/archive_old_trades.py` (Python script)
- [ ] Create `scripts/verify_archive.py` (integrity check)
- [ ] Setup cron: `0 2 * * * /home/vali/projects/crypto-daytrading/scripts/rotate_logs.sh`
- [ ] Document in operations runbook
- [ ] Test restore procedure quarterly

---

## Compliance & Legal

**Why 3 years?**
- Tax compliance: Most jurisdictions require 3-year record retention
- Trading regulation: FCA/MiFID2 requires 5-year record, but 3-year for operational logs
- Incident investigation: 3 years covers typical investigation timeframe

**Immutable Log Requirement:**
- Append-only JSONL prevents accidental modification
- Checksums prevent silent corruption
- Timestamped entries prove transaction history

---

## Operational Tasks

### Weekly (Monday 02:00 UTC)
```bash
# Verify active JSONL integrity
python scripts/verify_archive.py --active

# Check disk usage
du -h logs/immutable/trades_active.jsonl
```

### Quarterly (First day of quarter)
```bash
# Test restore from archive
python scripts/restore_from_archive.py --test --date 2025-01-01

# Verify all archives are readable
for f in logs/archive/trades_*.jsonl.gz; do gunzip -t "$f"; done
```

### Annually (July 2nd - Anniversary)
```bash
# Archive trades older than 3 years
python scripts/archive_old_trades.py --days 1095

# Create backup copy to NAS
rsync -a logs/archive/ /mnt/nas-backup/trades/

# Generate compliance report
python scripts/generate_retention_report.py
```

---

## Space Forecast

| Year | Trades | Size | Cumulative |
|------|--------|------|------------|
| 2023 | 18,250 | 8.7 MB | 8.7 MB |
| 2024 | 18,250 | 8.7 MB | 17.4 MB |
| 2025 | 18,250 | 8.7 MB | 26.1 MB |
| 2026 | 18,250 | 8.7 MB | ~26 MB (rolling) |

**Status:** ✅ Negligible impact (0.003% of 820 GB available)

---

## Rollout Schedule

| Date | Action |
|------|--------|
| 2026-07-02 | Policy effective (this date) |
| 2026-07-03 | Create archive structure |
| 2026-07-04 | Deploy rotation scripts |
| 2026-07-10 | First test rotation |
| 2026-07-17 | Setup cron automation |
| 2026-08-02 | First automated rotation |

---

## Contacts & Escalation

- **Owner:** Trading System Operations
- **Emergency restore:** Check `logs/archive/.checksums` first
- **Compliance questions:** Review this document and FUNCTIONAL_REQUIREMENTS.md

---

**Last Updated:** 2026-07-02  
**Next Review:** 2026-10-02 (quarterly)
