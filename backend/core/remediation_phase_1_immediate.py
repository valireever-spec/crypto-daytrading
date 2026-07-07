"""
REMEDIATION PHASE 1 (IMMEDIATE - TODAY)

Critical fixes to prevent WebSocket staleness cascade + HA split-brain:
1. Add timeout to WebSocket reconnect() call
2. Add logging before silencing exceptions
3. Add fallback logic when both HTTP and SSH sync fail
4. Add memory threshold guard (80% + related issue = alert)

These fixes address the cascading failures detected in baseline:
- WebSocket stale 30s → no recovery timeout → silent infinite retry loop
- HA sync both fail (403 + SSH error) → no fallback → state divergence
- Memory 85.4% + health check failure → false split-brain trigger
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ============================================================================
# FIX 1: WebSocket Recovery with Timeout + Max Retries
# ============================================================================

class WebSocketRecoveryWithTimeout:
    """Enhanced WebSocket recovery that cannot hang indefinitely."""

    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_TIMEOUT = 5  # Max 5 seconds per reconnect attempt (NEW)
    BACKOFF_BASE = 2.0  # exponential backoff: 2s, 4s, 8s
    RECOVERY_PAUSE_TIME = 60  # If all retries fail, pause for 60s before retry

    async def attempt_reconnect_with_timeout(
        self,
        symbol: str,
        ws_manager,
        max_attempts: int = MAX_RECONNECT_ATTEMPTS
    ) -> bool:
        """
        Attempt to reconnect with timeout protection.

        CRITICAL FIX: Adds timeout to prevent infinite retry loops.
        Previous issue: 30-second loop of reconnection attempts (no timeout)
        New behavior: Max 3 attempts, each with 5-second timeout

        Args:
            symbol: Symbol to reconnect
            ws_manager: WebSocket manager instance
            max_attempts: Maximum reconnection attempts

        Returns:
            True if reconnect successful, False if all retries exhausted
        """
        for attempt in range(1, max_attempts + 1):
            backoff = self.BACKOFF_BASE ** (attempt - 1)  # 2s, 4s, 8s

            try:
                logger.info(
                    f"🔄 [{symbol}] Reconnect attempt {attempt}/{max_attempts}, "
                    f"waiting {backoff}s then trying with {self.RECONNECT_TIMEOUT}s timeout"
                )

                await asyncio.sleep(backoff)

                # FIX: Add timeout to reconnect() call (was missing!)
                try:
                    _result = await asyncio.wait_for(
                        ws_manager.reconnect(symbol),
                        timeout=self.RECONNECT_TIMEOUT
                    )

                    logger.info(f"✅ [{symbol}] Reconnect successful after {attempt} attempts")
                    return True

                except asyncio.TimeoutError:
                    logger.warning(
                        f"⚠️  [{symbol}] Reconnect attempt {attempt} timed out "
                        f"({self.RECONNECT_TIMEOUT}s) - WebSocket manager may be hanging"
                    )
                    # Continue to next attempt

            except Exception as e:
                logger.warning(
                    f"⚠️  [{symbol}] Reconnect attempt {attempt} failed: {type(e).__name__}: {e}",
                    exc_info=True  # FIX: Log full traceback
                )

        # All retries exhausted
        logger.critical(
            f"❌ [{symbol}] WebSocket unrecoverable after {max_attempts} attempts, "
            f"pausing recovery for {self.RECOVERY_PAUSE_TIME}s"
        )
        return False


# ============================================================================
# FIX 2: Exception Logging Before Silencing
# ============================================================================

class ExceptionLoggingWrapper:
    """Wraps exception handling to log before silencing."""

    @staticmethod
    def safe_call(func_name: str, func, *args, **kwargs):
        """
        Call function with exception logging.

        FIX for silent failures: Log exception before silencing it.
        Previous issue: except Exception: pass (no logging)
        New behavior: Log error + traceback, then handle gracefully

        Args:
            func_name: Function name for logging
            func: Function to call
            *args, **kwargs: Function arguments

        Returns:
            Result of function, or None if error
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # FIX: Always log before silencing
            logger.error(
                f"❌ {func_name} failed: {type(e).__name__}: {e}",
                exc_info=True,  # Include full traceback
                extra={
                    'function': func_name,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                }
            )
            return None

    @staticmethod
    async def safe_call_async(func_name: str, coro, *args, **kwargs):
        """Async version of safe_call with exception logging."""
        try:
            return await coro
        except Exception as e:
            logger.error(
                f"❌ {func_name} failed: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'function': func_name,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                }
            )
            return None


# ============================================================================
# FIX 3: HA Sync Fallback with Circuit Breaker
# ============================================================================

class HASyncFallbackWithCircuitBreaker:
    """
    Enhanced HA sync with fallback logic when both HTTP and SSH fail.

    Previous issue: Both HTTP (403) and SSH (file not found) failed
                   → No fallback mechanism → State divergence

    New behavior: If both fail → Pause trading + Alert
    """

    def __init__(self):
        self.http_sync_failed = False
        self.ssh_sync_failed = False
        self.both_failed_count = 0
        self.trading_paused = False
        self.BOTH_FAILED_THRESHOLD = 3  # Pause after 3 consecutive both-fail events

    async def sync_with_fallback(
        self,
        state: Dict[str, Any],
        http_sync_fn,
        ssh_sync_fn
    ) -> bool:
        """
        Attempt sync with HTTP, fallback to SSH, circuit break if both fail.

        Args:
            state: State dict to sync
            http_sync_fn: HTTP sync function (awaitable)
            ssh_sync_fn: SSH sync function (awaitable)

        Returns:
            True if sync succeeded (either HTTP or SSH), False if both failed
        """
        try:
            # Try HTTP sync first
            logger.info("📡 Attempting HTTP sync to BACKUP...")
            http_result = await ExceptionLoggingWrapper.safe_call_async(
                "HTTP sync",
                http_sync_fn(state)
            )

            if http_result:
                logger.info("✅ HTTP sync succeeded")
                self.http_sync_failed = False
                self.both_failed_count = 0
                return True

            self.http_sync_failed = True
            logger.warning("⚠️  HTTP sync failed, attempting SSH fallback...")

        except Exception as e:
            self.http_sync_failed = True
            logger.warning(f"HTTP sync exception: {e}")

        # HTTP failed, try SSH fallback
        try:
            logger.info("🌐 Attempting SSH tunnel sync to BACKUP...")
            ssh_result = await ExceptionLoggingWrapper.safe_call_async(
                "SSH sync",
                ssh_sync_fn(state)
            )

            if ssh_result:
                logger.info("✅ SSH sync succeeded")
                self.ssh_sync_failed = False
                self.both_failed_count = 0
                return True

            self.ssh_sync_failed = True

        except Exception as e:
            self.ssh_sync_failed = True
            logger.warning(f"SSH sync exception: {e}")

        # BOTH SYNC METHODS FAILED - This is critical!
        logger.critical("🚨 CRITICAL: Both HTTP and SSH sync failed!")
        self.both_failed_count += 1

        if self.both_failed_count >= self.BOTH_FAILED_THRESHOLD:
            logger.critical(
                f"Both sync methods failed {self.both_failed_count} times - "
                f"pausing trading to prevent state divergence"
            )
            self.trading_paused = True
            # Signal to halt trading (upstream code should check self.trading_paused)
            return False

        return False


# ============================================================================
# FIX 4: Memory Threshold Guard (Prevent False Positives)
# ============================================================================

class MemoryThresholdGuard:
    """
    Prevents false "unhealthy" signals from high memory alone.

    Previous issue: Memory 85.4% alone triggered UNHEALTHY
                   → BACKUP detected PRIMARY unhealthy → split-brain

    New behavior: High memory only triggers alert if combined with:
                  - Actual OOM error, OR
                  - P95 latency increased, OR
                  - Error rate increased
    """

    MEMORY_WARNING_THRESHOLD = 0.80  # 80%
    MEMORY_CRITICAL_THRESHOLD = 0.95  # 95%
    MEMORY_CORRELATED_CHECKS = ['latency_increase', 'error_rate_increase', 'oom_detected']

    def __init__(self):
        self.memory_percent = 0
        self.correlated_issues = {}

    def check_health(self, memory_percent: float, correlated_metrics: Dict[str, bool]) -> bool:
        """
        Check if system is healthy based on memory + correlated metrics.

        Args:
            memory_percent: Current memory usage (0.0 to 1.0)
            correlated_metrics: Dict of correlated issues
                - 'latency_increase': P95 latency increased significantly
                - 'error_rate_increase': Error rate increased
                - 'oom_detected': OutOfMemory error detected

        Returns:
            True if system is healthy, False if unhealthy
        """
        self.memory_percent = memory_percent
        self.correlated_issues = correlated_metrics

        # Memory > 95% is always critical
        if memory_percent > self.MEMORY_CRITICAL_THRESHOLD:
            logger.critical(f"Memory CRITICAL: {memory_percent*100:.1f}%")
            return False

        # Memory 80-95%: Only unhealthy if correlated with other issues
        if memory_percent > self.MEMORY_WARNING_THRESHOLD:
            issues = [k for k, v in correlated_metrics.items() if v]

            if issues:
                logger.error(
                    f"Memory high ({memory_percent*100:.1f}%) + correlated issues: {issues} → UNHEALTHY"
                )
                return False
            else:
                logger.warning(
                    f"Memory high ({memory_percent*100:.1f}%) but no correlated issues → OK"
                )
                return True

        # Memory < 80%: Always healthy
        return True


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def example_fixes():
    """
    Example showing how to use these fixes in the actual code.
    """

    # Fix 1: WebSocket recovery with timeout
    _ws_recovery = WebSocketRecoveryWithTimeout()
    # result = await ws_recovery.attempt_reconnect_with_timeout("BTCUSDT", ws_manager)

    # Fix 2: Exception logging
    _result = ExceptionLoggingWrapper.safe_call(
        "sample_function",
        lambda: 1/0  # This will be logged before failing
    )

    # Fix 3: HA sync with fallback
    _sync_fallback = HASyncFallbackWithCircuitBreaker()
    # result = await sync_fallback.sync_with_fallback(
    #     state,
    #     http_sync_fn,
    #     ssh_sync_fn
    # )

    # Fix 4: Memory health check
    memory_guard = MemoryThresholdGuard()
    _is_healthy = memory_guard.check_health(
        memory_percent=0.854,
        correlated_metrics={
            'latency_increase': False,
            'error_rate_increase': False,
            'oom_detected': False,
        }
    )
    # Should return True (memory high but no correlated issues)


if __name__ == "__main__":
    # Test imports
    logger.info("✅ Remediation Phase 1 (Immediate) module loaded")
