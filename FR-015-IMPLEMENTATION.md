# FR-015: Automatic Database Authority Resolution — Implementation Workflow

**Status:** IN PROGRESS  
**Priority:** CRITICAL (blocking HA failover reliability)  
**Target:** Complete by EOD today  
**Owner:** Claude Code

---

## Overview

Implement automatic database synchronization based on chronological timestamps to resolve database divergence between PRIMARY and BACKUP machines.

**Why Critical:** Current system lost €221.56 in P&L because backup database wasn't updated after PRIMARY crashed. This prevents future data loss.

---

## Implementation Tasks

### Task 1: Database Authority Detection Module
**File:** `backend/core/database_authority.py`  
**Lines:** <150  
**Time:** 30 min

```python
class DatabaseAuthority:
    def detect_authority(self, primary_db_path, backup_db_path):
        """
        Determine which database is authoritative based on timestamps.
        
        Returns: {
            'authoritative': 'primary' | 'backup' | 'diverged' | 'unknown',
            'primary_timestamp': datetime,
            'backup_timestamp': datetime,
            'divergence_seconds': int,
            'reason': str
        }
        """
        pass
```

**Implementation:**
1. Open both databases (read-only)
2. Query `MAX(account_state.updated_at)` from both
3. If divergence >60s: return which is authoritative
4. If same timestamp: return 'unknown' (shouldn't happen)
5. If can't connect: return 'unknown'

**Tests:** (Unit, no I/O)
- UT-FR015-001: Primary newer → Primary authoritative
- UT-FR015-002: Backup newer → Backup authoritative
- UT-FR015-003: Same timestamp → Unknown
- UT-FR015-004: <60s divergence → Unknown (not sync error)

---

### Task 2: Database Sync Executor
**File:** `backend/core/database_sync.py`  
**Lines:** <200  
**Time:** 45 min

```python
class DatabaseSyncer:
    def sync_from_authoritative(self, 
                                from_path: str, 
                                to_path: str,
                                verify: bool = True):
        """
        Copy authoritative database to stale machine.
        
        Returns: {
            'success': bool,
            'bytes_copied': int,
            'checksum_before': str,
            'checksum_after': str,
            'time_seconds': float,
            'error': str | None
        }
        """
        pass
```

**Implementation:**
1. Verify `from_path` exists and is readable
2. Stop API process on `to_path` machine (if remote)
3. Copy file: `shutil.copy2(from_path, to_path)`
4. Verify checksums match: `sha256sum(from_path) == sha256sum(to_path)`
5. Log all steps to audit trail
6. Return sync report

**Tests:** (Integration, file I/O)
- IT-FR015-001: Sync local file → checksums match
- IT-FR015-002: Sync to remote via SSH → checksums match
- IT-FR015-003: Sync fails (permission) → error logged
- IT-FR015-004: Partial sync (disk full) → rollback

---

### Task 3: Startup Recovery Hook
**File:** `backend/api/lifecycle.py` (modify)  
**Lines:** +20-30  
**Time:** 30 min

**Hook:** Add to `lifespan()` context manager, before trading starts:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    
    # NEW: Database Authority Recovery (FR-015)
    from backend.core.database_authority import DatabaseAuthority
    from backend.core.database_sync import DatabaseSyncer
    
    authority = DatabaseAuthority()
    result = authority.detect_authority(
        primary_db=DB_PATH_PRIMARY,
        backup_db=DB_PATH_BACKUP
    )
    
    if result['authoritative'] == 'diverged':
        logger.warning(f"Database divergence detected: {result}")
        # Auto-sync via SSH
        syncer = DatabaseSyncer()
        await syncer.sync_from_authoritative(...)
        logger.info("Database recovery complete")
    
    # ... continue with trading startup ...
```

**Tests:** (Integration, full API startup)
- IT-FR015-005: Startup with diverged DBs → auto-sync triggers
- IT-FR015-006: Startup after sync → trading resumes normally

---

### Task 4: Test Suite (Critical)
**File:** `tests/test_database_authority.py`  
**Total Tests:** 10  
**Time:** 60 min

#### Unit Tests (5)
```python
def test_primary_newer_is_authoritative():
    """PRIMARY timestamp is later → PRIMARY authoritative"""
    # Arrange: PRIMARY.db updated_at=16:35, BACKUP.db updated_at=16:30
    # Act: detect_authority()
    # Assert: authoritative == 'primary'
    pass

def test_backup_newer_is_authoritative():
    """BACKUP timestamp is later → BACKUP authoritative"""
    # Setup BACKUP.db with later timestamp
    # Assert: authoritative == 'backup'
    pass

def test_same_timestamp_returns_unknown():
    """If timestamps match → divergence is not a timestamp issue"""
    pass

def test_divergence_less_than_60s_is_ignored():
    """Minor time drift <60s doesn't trigger sync"""
    pass

def test_cannot_read_db_returns_error():
    """If DB file unreadable → graceful error"""
    pass
```

#### Integration Tests (5)
```python
def test_sync_copies_file_correctly():
    """Files match after sync (checksum verify)"""
    pass

def test_sync_via_ssh_tunnel():
    """Sync works when databases are on different machines"""
    pass

def test_sync_on_api_startup():
    """API startup detects divergence & syncs before trading"""
    pass

def test_api_resumes_trading_after_sync():
    """Trading resumes with correct state (€ from authoritative DB)"""
    pass

def test_sync_fails_gracefully():
    """Sync error doesn't crash API (logs & waits for manual intervention)"""
    pass
```

---

## Execution Steps (Do This Now)

### Step 1: Create Database Authority Module (30 min)
```bash
cat > backend/core/database_authority.py << 'EOF'
# Code here
EOF
```

### Step 2: Create Database Sync Module (45 min)
```bash
cat > backend/core/database_sync.py << 'EOF'
# Code here
EOF
```

### Step 3: Add Recovery Hook to Lifecycle (30 min)
Edit `backend/api/lifecycle.py`:
- Import new modules
- Add authority detection before trading starts
- Log all sync events

### Step 4: Write Test Suite (60 min)
```bash
cat > tests/test_database_authority.py << 'EOF'
# Unit tests
EOF

cat > tests/test_database_sync.py << 'EOF'
# Integration tests
EOF
```

### Step 5: Test on Real Machines (30 min)
1. Sync PRIMARY database to local test
2. Verify checksums match
3. Start API with diverged DBs
4. Verify auto-sync triggers
5. Verify trading resumes

### Step 6: Document & Verify (15 min)
- [ ] All tests passing (10/10)
- [ ] Audit trail shows sync events
- [ ] Handbook updated with recovery process
- [ ] Commit with message: "feat: FR-015 Database Authority Resolution"

---

## Success Criteria

- ✅ All 10 tests passing
- ✅ Sync works on both PRIMARY (127.0.0.1) and BACKUP (192.168.3.25)
- ✅ API startup with diverged DBs auto-syncs (no manual intervention)
- ✅ Trade state correctly restored from authoritative database
- ✅ Audit log shows every sync event with timestamp
- ✅ No data loss during sync (checksums verify)

---

## Rollback Plan

If sync breaks trading:
1. `git revert <commit-hash>` back to current stable
2. Manually restore BACKUP database from PRIMARY using SSH:
   ```bash
   ssh claude@192.168.3.25 "cp /home/claude/crypto-daytrading/data/trading.db{,.backup}"
   scp /home/vali/projects/crypto-daytrading/data/trading.db \
       claude@192.168.3.25:/home/claude/crypto-daytrading/data/
   ```
3. Restart both APIs

---

## Estimated Total Time: 3.5 hours

| Task | Time | Status |
|------|------|--------|
| Database Authority Module | 30 min | ⏳ TODO |
| Database Sync Module | 45 min | ⏳ TODO |
| Lifecycle Hook | 30 min | ⏳ TODO |
| Test Suite | 60 min | ⏳ TODO |
| Real Machine Testing | 30 min | ⏳ TODO |
| Documentation | 15 min | ⏳ TODO |
| **TOTAL** | **3.5h** | **⏳ NOT STARTED** |

---

## Git Workflow

```bash
# Create feature branch
git checkout -b feat/FR-015-database-authority

# Work on each task
# ... implement ...

# Run tests
pytest tests/test_database_authority.py -v
pytest tests/test_database_sync.py -v

# Commit
git add -A
git commit -m "feat: FR-015 Database Authority Resolution

- Detect which database is authoritative by timestamp
- Auto-sync stale database on startup
- Verify checksums to ensure integrity
- Full test suite (10 tests)

Fixes: Database divergence causing P&L loss during failover"

# Push
git push origin feat/FR-015-database-authority

# Create PR (optional for solo work)
gh pr create --title "FR-015: Database Authority Resolution" \
  --body "Implements automatic database sync based on timestamps"
```

