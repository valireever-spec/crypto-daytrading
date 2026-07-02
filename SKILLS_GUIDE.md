# Gap Detection Skills Guide

**Quick reference for using 5 specialized skills to detect and fix gaps in crypto-daytrading.**

**Location:** Generated from skill-creator project  
**Purpose:** Systematically find security issues, test gaps, and quality problems  
**Typical runtime:** 5-15 minutes per skill

---

## 1️⃣ SECRETS-SCANNER-V2 (Security First)

**What it does:** Finds hardcoded API keys, private keys, passwords, tokens.

**Why critical for crypto:** Leaked keys = instant total loss of funds.

**Run it:**
```bash
secrets-scanner-v2 /home/vali/projects/crypto-daytrading
```

**What to look for in output:**
```
CRITICAL: Binance API key found in backend/core/config.py:15
CRITICAL: Private key in .env (committed to git history)
WARNING: Potential secret in logs/trades.jsonl
```

**How to fix:**
1. Move all secrets to `.env` file (git-ignored)
2. Update config.py to load from `os.environ`
3. Force-remove from git history: `git filter-branch --tree-filter 'rm -f .env'`
4. Rotate all exposed API keys on Binance immediately
5. Re-run skill to verify

**Checklist after fix:**
- [ ] No .env file in git
- [ ] All API keys loaded from `os.environ`
- [ ] `.gitignore` includes `.env`, `*.key`, `secrets/`
- [ ] Pre-commit hook detects secrets (run `pip install detect-secrets`)
- [ ] Re-run skill: 0 findings

**Links:**
- CSF Pillar 6: Security & Privacy
- CSF Pillar 7: Audit Trail

---

## 2️⃣ TEST-SECURITY-ANALYZER-V2 (Security Testing)

**What it does:** Finds security-critical code that lacks test coverage.

**Why it matters:** Trading systems fail silently on untested paths. Missing one error case = lost trades.

**Run it:**
```bash
test-security-analyzer-v2 /home/vali/projects/crypto-daytrading
```

**What to look for in output:**
```
CRITICAL: exchange/binance.py:45 (place_order) - no error tests
  Found 3 error scenarios: timeout, 5xx, rate_limit (0 tests)
  
CRITICAL: execution/order_manager.py:120 (check_balance) - untested
  Scenario: insufficient_balance (no test)
  
HIGH: strategies/momentum.py:80 (signal) - missing edge cases
  NaN handling untested, inf values untested
```

**How to fix:**
1. Add test file: `tests/unit/test_exchange_errors.py`
2. Test each error scenario:
   ```python
   def test_place_order_timeout():
       # Mock timeout, verify retry + backoff
   
   def test_place_order_429_rate_limit():
       # Mock rate limit, verify queue + delay
   
   def test_insufficient_balance():
       # Mock balance=0, verify rejection + alert
   ```
3. Re-run skill to verify coverage

**Checklist after fix:**
- [ ] All exchange API calls have error tests
- [ ] Rate limit scenario tested (429 response)
- [ ] Insufficient balance tested
- [ ] Circuit breaker tested (exchange down)
- [ ] Invalid order rejection tested
- [ ] Test coverage ≥85% on `backend/execution/`

**Links:**
- CSF Pillar 3: Error handling
- CSF Pillar 5: Verification & Validation

---

## 3️⃣ DEPENDENCY-VULNERABILITY-CHECKER-V2 (CVE Scanning)

**What it does:** Scans for known CVEs in Python dependencies.

**Why critical:** Vulnerable crypto libraries = system compromise.

**Run it:**
```bash
dependency-vulnerability-checker-v2 /home/vali/projects/crypto-daytrading
```

**What to look for in output:**
```
CRITICAL: ccxt==2.1.0 has CVE-2024-1234 (key exposure)
  Affected: order placement with sensitive data
  Fix: Upgrade to ccxt≥2.5.0

CRITICAL: pydantic==1.8.0 has CVE-2024-2456 (validation bypass)
  Affected: Input validation
  Fix: Upgrade to pydantic≥2.0.0

HIGH: aiohttp==3.8.0 has CVE-2023-9999 (SSL verification bypass)
  Fix: Upgrade to aiohttp≥3.9.0
```

**How to fix:**
1. Update `requirements.txt`:
   ```
   ccxt==2.5.0          # Was 2.1.0
   pydantic==2.0.0      # Was 1.8.0
   aiohttp==3.9.0       # Was 3.8.0
   ```
2. Run upgrade: `pip install -r requirements.txt --upgrade`
3. Test: `pytest tests/ -v`
4. Commit: `git commit -m "fix: upgrade deps to patch CVEs"`

**Checklist after fix:**
- [ ] All dependencies pinned to exact versions
- [ ] 0 high-severity CVEs
- [ ] Crypto libraries current (ccxt, pydantic, aiohttp)
- [ ] Pre-commit hook runs `pip check` (detect outdated packages)
- [ ] CI/CD checks dependencies on every PR
- [ ] Re-run skill: 0 critical findings

**Automation:**
```bash
# Add to .pre-commit-config.yaml
- repo: local
  hooks:
  - id: pip-check-deps
    name: Check pip dependencies for CVEs
    entry: pip check
    language: system
    types: [python]
```

**Links:**
- CSF Pillar 2: Build Quality In
- CSF Pillar 8: Least Privilege / Safe Defaults

---

## 4️⃣ TESTING-INTELLIGENCE-ENGINE-V2 (Coverage Analysis)

**What it does:** Analyzes test coverage and recommends missing test scenarios.

**Why it matters:** Trading logic = high-stakes code. ≥90% coverage is mandatory.

**Run it:**
```bash
testing-intelligence-engine-v2 /home/vali/projects/crypto-daytrading
```

**What to look for in output:**
```
Coverage by module:
├─ backend/exchange/binance.py         62% (NEEDS TESTS)
│  Missing: error handling, retries, API key rotation
├─ backend/strategies/momentum.py      55% (NEEDS TESTS)
│  Missing: NaN handling, inf values, division by zero
├─ backend/execution/order_manager.py  48% (CRITICAL)
│  Missing: concurrent trades, settlement, position sizing
└─ backend/portfolio/portfolio.py      78% (OK)

Recommended: Add 45 new tests to reach 90% coverage
Est. effort: 4-6 hours
```

**How to fix:**
1. Run coverage report: `coverage run -m pytest && coverage html`
2. Open `htmlcov/index.html`, find red (uncovered) lines
3. Write tests for each uncovered path
4. Prioritize: order_manager (highest impact) → strategies → exchange

**Example test additions:**
```python
# tests/unit/test_momentum_strategy.py
def test_signal_with_nan_values():
    # Handle NaN in price data
    
def test_signal_division_by_zero():
    # Handle 0 std dev in returns

# tests/unit/test_order_manager.py
def test_concurrent_orders():
    # Place 5 orders simultaneously
    
def test_position_sizing_edge_case():
    # Min/max position sizes
```

**Checklist after fix:**
- [ ] Total coverage ≥90%
- [ ] `backend/execution/order_manager.py` ≥90%
- [ ] `backend/strategies/` ≥85%
- [ ] All error paths tested
- [ ] Edge cases covered (0 balance, max leverage, NaN, inf)
- [ ] Concurrent scenarios tested
- [ ] Run: `pytest --cov=backend --cov-report=term-missing`

**Links:**
- CSF Pillar 5: Verification & Validation

---

## 5️⃣ CHAOS-TESTING-FRAMEWORK-V2 (Resilience Testing)

**What it does:** Tests how system behaves when things fail (exchange down, no liquidity, market crashes).

**Why critical:** Real markets fail. Your system must degrade gracefully.

**Run it:**
```bash
chaos-testing-framework-v2 /home/vali/projects/crypto-daytrading
```

**What to look for in output:**
```
Failure Scenario: Exchange API Down (500 error)
├─ Current behavior: Raises exception, crashes
├─ Expected behavior: Backoff + retry + circuit breaker
├─ Fix: Implement exponential backoff in binance.py
└─ Test: test_exchange_down_recovery()

Failure Scenario: Insufficient Balance
├─ Current behavior: Order placed, rejected, no handling
├─ Expected behavior: Check balance before placement, alert
├─ Fix: Add pre-flight balance check in order_manager.py
└─ Test: test_insufficient_balance_alert()

Failure Scenario: High Slippage
├─ Current behavior: No slippage limit, order always fills
├─ Expected behavior: Reject if slippage > threshold
├─ Fix: Add slippage validation in execution engine
└─ Test: test_slippage_rejection()
```

**Scenarios to test:**
1. **Exchange API Error (5xx)**
   - Behavior: Backoff + retry (exponential, 3 attempts)
   - Test: Mock 500, verify retry after 2s, then 4s, then 8s

2. **Rate Limit (429)**
   - Behavior: Queue order, delay, then retry
   - Test: Mock 429, verify retry after 60s

3. **Insufficient Balance**
   - Behavior: Reject order, alert operator
   - Test: Check balance before placing, log error

4. **High Slippage (Market Moved)**
   - Behavior: Reject if actual price > threshold
   - Test: Place order, market moves, verify rejection

5. **Network Timeout**
   - Behavior: Retry with backoff, never double-order
   - Test: Timeout during placement, verify no duplicate

6. **Order Never Fills**
   - Behavior: Cancel if unfilled for >60s
   - Test: Place order, don't fill, verify auto-cancel

**How to fix:**
```python
# backend/execution/order_manager.py

import time
from functools import wraps

def with_retry(max_attempts=3, backoff_base=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_base ** attempt
                    logger.warning(f"Attempt {attempt+1} failed, retrying in {wait_time}s")
                    time.sleep(wait_time)
        return wrapper
    return decorator

@with_retry(max_attempts=3, backoff_base=2)
def place_order(self, symbol, side, amount, price):
    # Will auto-retry on error
    pass

def place_order_with_balance_check(self, symbol, side, amount, price):
    available = self.portfolio.get_available_balance()
    if available < amount * price * 1.01:  # 1% buffer for fees
        logger.error(f"Insufficient balance: {available} < {amount * price}")
        raise InsufficientBalanceError()
    
    actual_price = self.exchange.place_order(symbol, side, amount, price)
    slippage_pct = abs(actual_price - price) / price * 100
    
    if slippage_pct > self.max_slippage_pct:
        logger.error(f"Slippage {slippage_pct}% > {self.max_slippage_pct}%")
        self.exchange.cancel_order(order_id)
        raise HighSlippageError()
    
    return actual_price
```

**Checklist after fix:**
- [ ] Exponential backoff on API errors (2s, 4s, 8s)
- [ ] Rate limit respected (1200 req/min for Binance)
- [ ] Circuit breaker: stop trading if exchange down >5 min
- [ ] Balance check before order placement
- [ ] Slippage validation (reject if > threshold)
- [ ] Timeout handling (retry, never double-order)
- [ ] Order auto-cancel if unfilled >60s
- [ ] All scenarios tested in `tests/acceptance/test_chaos.py`

**Links:**
- CSF Pillar 3: Error Handling
- CSF Pillar 6: Resilience
- CSF Pillar 9: Observability (alert on failures)

---

## Running All Skills (Full Audit)

```bash
#!/bin/bash
# Full gap detection audit

PROJECT=/home/vali/projects/crypto-daytrading

echo "🔴 Security: Scanning for secrets..."
secrets-scanner-v2 $PROJECT > GAPS_SECRETS.txt

echo "🟠 Security Testing: Finding untested security paths..."
test-security-analyzer-v2 $PROJECT > GAPS_SECURITY_TESTS.txt

echo "🟡 Dependencies: Checking for CVEs..."
dependency-vulnerability-checker-v2 $PROJECT > GAPS_DEPS.txt

echo "🟢 Test Coverage: Finding coverage gaps..."
testing-intelligence-engine-v2 $PROJECT > GAPS_COVERAGE.txt

echo "🔵 Resilience: Testing failure scenarios..."
chaos-testing-framework-v2 $PROJECT > GAPS_CHAOS.txt

echo ""
echo "📊 Summary:"
echo "Secrets: $(grep -c CRITICAL GAPS_SECRETS.txt || echo 0) critical issues"
echo "Security Tests: $(grep -c CRITICAL GAPS_SECURITY_TESTS.txt || echo 0) critical issues"
echo "Dependencies: $(grep -c CRITICAL GAPS_DEPS.txt || echo 0) critical issues"
echo "Coverage: $(grep -c CRITICAL GAPS_COVERAGE.txt || echo 0) critical issues"
echo "Chaos: $(grep -c CRITICAL GAPS_CHAOS.txt || echo 0) critical issues"

echo ""
echo "All findings logged to GAPS_*.txt"
echo "Next: Review each file and create GAPS.md with findings"
```

**Expected time:** 10-15 minutes per full audit

---

## Tracking & Next Steps

After running all skills:

1. **Create `GAPS.md`** with table of all findings
2. **Prioritize by severity:** Critical → High → Medium → Low
3. **Link each gap to CSF pillar** (know which section to fix)
4. **Assign owners** (who fixes which gap)
5. **Set deadlines** (security gaps: this week, others: by phase end)
6. **Create PRs** for each gap fix
7. **Re-run skills** after each PR to verify

**CSF Scoring Target After All Fixes:**
- Pillar 1: 4/5 (Architecture documented)
- Pillar 2: 4/5 (Build quality enforced)
- Pillar 3: 4/5 (Verified & validated)
- Pillar 4: 4/5 (Safe delivery pipeline)
- Pillar 5: 3/5 (Learning from issues)
- **Pillar 6: 5/5 (Security, non-negotiable)**
- **Pillar 7: 5/5 (Observability, critical for 24/7)**
- Pillar 8: 4/5 (Maintainable code)

**Overall target: 4+/5 across all pillars**

---

## Questions & Troubleshooting

**Q: What if a skill finds nothing?**  
A: Great! That gap is covered. Document as ✅ in GAPS.md.

**Q: What if skill output is unclear?**  
A: Add `--verbose` flag for more detail (if skill supports it).

**Q: Can I automate these skills?**  
A: Yes! Add to pre-commit hooks or CI/CD pipeline:
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
  - id: security-scan
    name: Security scanning
    entry: secrets-scanner-v2 .
    language: system
    types: [python]
    stages: [commit]
```

**Q: How often should I run these?**  
A: 
- Secrets-scanner: Every commit (pre-commit hook)
- Security tests: Every PR (CI/CD)
- Dependency check: Weekly (cron job)
- Coverage: Every PR (pytest --cov)
- Chaos tests: Every release (acceptance phase)

**Q: What if I disagree with a finding?**  
A: Document it in `GAPS.md` as "False Positive" with reasoning. Skills use heuristics; human judgment applies.

---

## References

- **Skill-Creator:** `/home/vali/projects/skill-creator/`
- **CSF Framework:** `CRITICAL_SYSTEMS_FRAMEWORK.md` (this project)
- **Portfolio Framework:** `../project-designer/FRAMEWORK.md`
- **Runbooks:** `docs/runbooks.md` (for incident response)

---

**Created:** 2026-07-02  
**Last Updated:** 2026-07-02  
**Status:** Draft (update after first skill run)
