# Code Review Checklist
**Crypto-Daytrading Platform**  
**Version:** 1.0  
**Last Updated:** 2026-07-07

---

## Pre-Merge Requirements

All items in this checklist must be completed before code can be merged to `main` branch.

### Functional Correctness

- [ ] **Feature Works as Specified**
  - Implemented feature matches acceptance criteria
  - All edge cases handled
  - Error cases return appropriate errors
  - Logs show expected messages

- [ ] **No Regressions**
  - Existing tests still pass
  - No performance degradation
  - No new console errors/warnings
  - Backward compatibility maintained

- [ ] **Code Logic is Sound**
  - Algorithm is correct
  - Business logic properly implemented
  - State management is correct
  - Race conditions considered

### Error Handling

- [ ] **Exception Handling Complete**
  - All methods have try-except blocks for risky operations
  - No unhandled exceptions in critical paths
  - Errors are logged with traceback (exc_info=True)
  - Users get meaningful error messages

- [ ] **Error Messages are Clear**
  - Error messages describe what went wrong
  - Error messages include actionable next steps
  - No exposing internal implementation details
  - No swallowing exceptions silently

- [ ] **Recovery Paths Exist**
  - Code can recover from transient failures
  - Retry logic is implemented where needed
  - Graceful degradation when services unavailable
  - No hanging processes or threads

### Security

- [ ] **No Hardcoded Secrets**
  - No API keys, passwords, tokens in code
  - All secrets use environment variables
  - No credential commits in history
  - Secrets never logged

- [ ] **Input Validation**
  - All user input validated
  - No SQL injection vulnerabilities
  - No command injection (no shell=True with user input)
  - No XSS vulnerabilities

- [ ] **Authentication & Authorization**
  - API endpoints require authentication (if applicable)
  - Users can only access their own data
  - Admin endpoints protected
  - Rate limiting in place

- [ ] **No Security Vulnerabilities**
  - No eval() or exec() with untrusted input
  - No insecure deserialization
  - No exposed debugging endpoints
  - No information disclosure

### Performance

- [ ] **Performance Acceptable**
  - Latency meets SLOs (NFR-001: <500ms signals, NFR-002: <2s orders)
  - No unnecessary database queries (N+1 problems)
  - No memory leaks
  - Queries use indexes

- [ ] **Scalability Considered**
  - Code works with 10,000+ trades
  - No hardcoded limits
  - Pagination used for large result sets
  - Caching implemented where needed

- [ ] **Resource Cleanup**
  - Connections closed properly
  - Database transactions committed/rolled back
  - Files closed after reading
  - Timers/intervals cleared

### Code Quality

- [ ] **Type Hints Present**
  - All function parameters have type hints
  - All return types specified
  - No `Any` types (use specific types)
  - Dict/List have value types specified

- [ ] **Code is Readable**
  - Variables have clear names
  - Functions are small (<50 lines preferred)
  - Comments explain "why", not "what"
  - No deep nesting (>3 levels)

- [ ] **No Code Smells**
  - No copy-paste code (use functions instead)
  - No dead code
  - No TODO/FIXME comments without issues
  - No god classes/functions

- [ ] **Follows Project Standards**
  - Follows naming conventions
  - Follows coding style (use formatter)
  - Uses project's error handling patterns
  - Uses project's logging style

### Testing

- [ ] **Tests Written**
  - Unit tests for logic changes
  - Integration tests for API changes
  - Edge cases tested
  - Error cases tested

- [ ] **Test Coverage Adequate**
  - New code has >80% coverage
  - Critical paths fully tested
  - Happy path and error paths covered
  - Edge cases not missed

- [ ] **Tests Pass**
  - All tests run locally
  - All tests pass consistently
  - No flaky tests
  - CI/CD tests pass

### Documentation

- [ ] **Code is Documented**
  - Public functions have docstrings
  - Complex logic has comments
  - Assumptions documented
  - Non-obvious behavior explained

- [ ] **README Updated (if needed)**
  - Setup instructions accurate
  - Architecture described
  - API endpoints documented
  - Configuration options explained

- [ ] **Changelog Updated**
  - User-facing changes documented
  - Breaking changes noted
  - New features listed
  - Bug fixes documented

### Database Changes (if applicable)

- [ ] **Schema Changes Safe**
  - Migrations are reversible
  - Indexes created for query performance
  - No dropping columns (use deprecation)
  - Transactions used for multi-step changes

- [ ] **Data Migration Correct**
  - Backfill logic tested
  - Handles partial migrations
  - Rollback strategy defined
  - No data loss risk

### Deployment Safety

- [ ] **Backwards Compatible**
  - Old code can read new data
  - New code can read old data
  - API changes use versioning
  - Database schema is compatible

- [ ] **Rollback Plan Exists**
  - Code can roll back cleanly
  - Rollback scenarios tested
  - No permanent data changes until safe
  - Zero-downtime deployment possible

- [ ] **Monitoring in Place**
  - Error logs monitored
  - Performance metrics logged
  - Health checks updated
  - Alerts configured

### Trading Logic Specific

- [ ] **P&L Calculation Correct**
  - Trades paired correctly (entry ↔ exit)
  - Fees included in calculation
  - P&L matches account equity
  - No data inconsistency

- [ ] **Order Execution Sound**
  - Orders execute at correct price
  - Position sizing correct
  - Stop loss triggered correctly
  - Profit target triggered correctly

- [ ] **Signal Generation Accurate**
  - Signals calculated correctly
  - Technical indicators verified
  - No divide-by-zero errors
  - Price data validated

- [ ] **Risk Management Enforced**
  - Position limits enforced
  - Daily loss limits enforced
  - Exposure limits enforced
  - Drawdown limits enforced

---

## Sign-Off

### Reviewer 1
- [ ] I have reviewed this code and approve it for merge
- [ ] All checklist items verified
- Name: ________________
- Date: ________________

### Reviewer 2 (Required for trading logic changes)
- [ ] I have reviewed this code and approve it for merge
- [ ] All checklist items verified
- [ ] Trading logic correctness confirmed
- Name: ________________
- Date: ________________

### Author
- [ ] I have incorporated all feedback
- [ ] Code ready for production
- [ ] All tests passing locally
- Name: ________________
- Date: ________________

---

## Notes

Add any additional context or concerns below:

```
[Space for reviewer notes]
```

---

## How to Use This Checklist

1. **Before creating a PR:** Author should self-review using this checklist
2. **During PR review:** Reviewers should check each item
3. **Before merging:** All items must be checked and signed off
4. **Post-merge:** Monitor deployment for any issues

## Minimum Requirements for Merge

- ✅ All HIGH priority items MUST be completed
- ✅ All MEDIUM items MUST be completed for core trading logic
- ✅ At least 1 reviewer sign-off required (2 for trading changes)
- ✅ All tests passing
- ✅ No critical security issues

## Fast-Track Criteria

Code can be merged with only 1 reviewer if:
- Changes are documentation only, OR
- Changes are test-only improvements, OR
- Changes are configuration/deployment only

Trading logic changes MUST always have 2 reviewers.

---

**Last Audit:** 2026-07-07  
**Audit Status:** ✅ Complete - Checklist verified by code review validator

