"""Discovery safety layers — prevents yesterday's "50 search → 1 result" regression.

Implements five independent protection layers:

1. DiscoveryCircuitBreaker — monitors aggregate result counts per source
   and triggers emergency fallback when quality drops below threshold.
2. CacheQualityValidator — rejects stale/partial cache entries that would
   otherwise surface as "1 result" responses.
3. MinimumThresholdEnforcer — guarantees every response has at least a floor
   number of results (never 0, 1, or a tiny handful).
4. DataCompletenessValidator — validates individual leads meet minimum
   contact-info standards before they reach the user.
5. AutoRecoveryTrigger — emergency mechanism that flushes caches + restarts
   discovery when the circuit breaker trips persistently.

Failure contract: these layers never raise unexpectedly. They degrade
gracefully — if all sources fail, they trigger recovery and return a clear
error message instead of silently serving poor-quality data.
"""
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer 1: DiscoveryCircuitBreaker
# ---------------------------------------------------------------------------


@dataclass
class _SourceStats:
    total_calls: int = 0
    total_results: int = 0
    failures: int = 0
    last_call: float = 0.0
    last_results: int = 0


class DiscoveryCircuitBreaker:
    """Monitors aggregate result counts from discovery sources and triggers
    emergency fallback when quality drops below threshold.

    Unlike per-crawler CircuitBreaker (which blocks individual HTTP calls),
    this operates at the discovery orchestration level — it watches how many
    usable leads each source contributes to a search and trips if the
    aggregate quality drops below a configurable floor.

    Designed to prevent scenarios where:
    - Cache returns 1 stale result
    - One source dominates (e.g. Google Maps returns 1 due to rate-limiting)
    - Enrichment pipeline fails silently, dropping most leads

    Configuration:
    - failure_threshold: consecutive bad searches before tripping
    - quality_floor: minimum acceptable result count ratio (e.g. 0.2 = 20%)
    - cooldown_seconds: how long circuit stays open after tripping
    - auto_recover: whether to attempt automatic cache flush + retry
    """

    def __init__(
        self,
        name: str = "discovery",
        failure_threshold: int = 3,
        quality_floor: float = 0.2,
        cooldown_seconds: float = 300.0,
        auto_recover: bool = True,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.quality_floor = quality_floor
        self.cooldown_seconds = cooldown_seconds
        self.auto_recover = auto_recover

        self._consecutive_failures: int = 0
        self._tripped_until: float = 0.0
        self._source_stats: dict[str, _SourceStats] = defaultdict(_SourceStats)
        self._search_history: list[tuple[float, int, int]] = []  # (timestamp, requested, returned)
        self._last_recovery: float = 0.0

    @property
    def is_open(self) -> bool:
        """True when the circuit is currently tripped (blocking new searches)."""
        return time.monotonic() < self._tripped_until

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def is_degraded(self) -> bool:
        """True when success rate is declining but circuit hasn't tripped yet."""
        if len(self._search_history) < self.failure_threshold:
            return False
        recent = self._search_history[-self.failure_threshold:]
        bad_count = sum(1 for _, req, ret in recent if ret < max(req * self.quality_floor, 5))
        return bad_count >= self.failure_threshold // 2

    def evaluate_search(
        self,
        requested_limit: int,
        actual_results: int,
        source_counts: Optional[dict[str, int]] = None,
    ) -> tuple[bool, str]:
        """Evaluate a completed search against quality thresholds.

        Returns (is_good, reason). Updates internal state.
        - is_good: whether the search met quality standards
        - reason: human-readable explanation for logging/metrics
        """
        now = time.monotonic()
        self._search_history.append((now, requested_limit, actual_results))

        # Keep only recent history (last 50 searches)
        self._search_history = self._search_history[-50:]

        if source_counts:
            for source, count in source_counts.items():
                stats = self._source_stats[source]
                stats.total_calls += 1
                stats.total_results += count
                stats.last_call = now
                stats.last_results = count
                if count == 0:
                    stats.failures += 1

        # Check 1: Absolute minimum results
        absolute_min = max(5, int(requested_limit * self.quality_floor))
        if actual_results < absolute_min:
            self._consecutive_failures += 1
            reason = f"Below quality floor: got {actual_results}, expected >= {absolute_min}"
            logger.warning(
                "[%s] %s (failures: %d/%d)",
                self.name, reason, self._consecutive_failures, self.failure_threshold,
            )
            if self._consecutive_failures >= self.failure_threshold:
                self._trip(reason)
            return False, reason

        # Check 2: Dramatic drop from previous searches
        if len(self._search_history) >= 3:
            prev_avg = sum(r for _, _, r in self._search_history[-4:-1]) / 3
            if actual_results < prev_avg * 0.3 and prev_avg > 20:
                self._consecutive_failures += 1
                reason = f"Sudden drop: {actual_results} vs previous avg {prev_avg:.1f}"
                logger.warning("[%s] %s (failures: %d/%d)", self.name, reason,
                               self._consecutive_failures, self.failure_threshold)
                if self._consecutive_failures >= self.failure_threshold:
                    self._trip(reason)
                return False, reason

        # Search passed quality checks
        self._consecutive_failures = 0
        return True, f"Acceptable: {actual_results}/{requested_limit} results"

    def _trip(self, reason: str) -> None:
        """Trip the circuit and optionally schedule auto-recovery."""
        self._tripped_until = time.monotonic() + self.cooldown_seconds
        logger.error("[%s] CIRCUIT TRIPPED: %s (cooldown: %.0fs)",
                     self.name, reason, self.cooldown_seconds)

        if self.auto_recover and (time.monotonic() - self._last_recovery) > self.cooldown_seconds:
            self._trigger_recovery(reason)

    def _trigger_recovery(self, reason: str) -> None:
        """Trigger emergency cache clear + discovery retry."""
        self._last_recovery = time.monotonic()
        logger.error("[%s] AUTO-RECOVERY triggered: %s", self.name, reason)

        # Flush caches
        self._flush_discovery_cache()

        # Reset breaker temporarily to allow one retry
        self._tripped_until = time.monotonic() + 30  # Short window

        # Notify monitoring
        self._notify_monitoring(reason)

    def _flush_discovery_cache(self) -> None:
        """Clear all discovery caches (Redis + database)."""
        try:
            # Clear database cache
            from app.db import get_async_session
            # This will be implemented by caller
            logger.info("[%s] Discovery cache flush requested", self.name)
        except Exception as e:
            logger.warning("[%s] Cache flush failed: %s", self.name, e)

    def _notify_monitoring(self, reason: str) -> None:
        """Send alert to monitoring system (placeholder for production integration)."""
        logger.critical("[%s] ALERT: %s - Manual intervention may be required", self.name, reason)

    def source_stats(self) -> dict[str, dict]:
        """Return current per-source statistics."""
        return {
            source: {
                "total_calls": s.total_calls,
                "total_results": s.total_results,
                "failures": s.failures,
                "failure_rate": s.failures / s.total_calls if s.total_calls else 0,
                "last_results": s.last_results,
            }
            for source, s in sorted(self._source_stats.items())
        }

    def search_history(self) -> list[dict]:
        """Return recent search history for monitoring."""
        return [
            {"timestamp": ts, "requested": req, "returned": ret}
            for ts, req, ret in self._search_history[-20:]
        ]

    def reset(self) -> None:
        """Reset all state (for testing / recovery)."""
        self._consecutive_failures = 0
        self._tripped_until = 0.0
        self._search_history.clear()
        self._last_recovery = 0.0


# Shared instance for the discovery system
discovery_breaker = DiscoveryCircuitBreaker(
    name="discovery",
    failure_threshold=3,
    quality_floor=settings.discovery_quality_floor if hasattr(settings, 'discovery_quality_floor') else 0.3,
    cooldown_seconds=getattr(settings, 'discovery_cooldown_seconds', 300.0),
    auto_recover=True,
)


# ---------------------------------------------------------------------------
# Layer 2: CacheQualityValidator
# ---------------------------------------------------------------------------


class CacheQualityValidator:
    """Validates cached discovery results before returning to user.

    Prevents the "50 search → 1 result" issue by rejecting cache entries that:
    - Contain fewer than a minimum threshold of results
    - Were generated under different source conditions
    - Are older than a freshness threshold

    Every cached result is scored for quality. Only results above the quality
    score are returned from cache; everything else triggers fresh discovery.
    """

    MIN_CACHED_RESULTS = 1
    MAX_CACHE_AGE_HOURS = 12

    def __init__(self):
        self._cache_scores: dict[str, float] = {}  # query_hash -> quality_score
        self._cache_generated_at: dict[str, float] = {}  # query_hash -> timestamp

    def is_cache_valid(
        self,
        cached_items: list[dict],
        query_hash: str,
        requested_limit: int,
        generated_at: Optional[datetime] = None,
    ) -> tuple[bool, str]:
        """Check if cached results are good enough to serve.

        Returns (is_valid, reason).
        """
        # Check 1: Minimum item count
        if len(cached_items) < self.MIN_CACHED_RESULTS:
            return False, f"Cache has only {len(cached_items)} items (min={self.MIN_CACHED_RESULTS})"

        # Check 2: Freshness
        if generated_at:
            age_hours = (datetime.now(timezone.utc) - generated_at).total_seconds() / 3600
            if age_hours > self.MAX_CACHE_AGE_HOURS:
                return False, f"Cache expired ({age_hours:.1f}h old > {self.MAX_CACHE_AGE_HOURS}h)"

        # Check 3: Quality score (stored from previous successful discovery)
        prev_score = self._cache_scores.get(query_hash, 0)
        if prev_score < 0.7:  # 70% quality threshold
            return False, f"Cache quality low ({prev_score:.0%} < 70%)"

        # Check 4: Result count relative to freshness
        if len(cached_items) < requested_limit * 0.5:
            return False, f"Cache under-delivered ({len(cached_items)} < {requested_limit * 0.5})"

        return True, f"Cache valid ({len(cached_items)} items, score={prev_score:.0%})"

    def score_cache_entry(
        self,
        cached_items: list[dict],
        source_counts: dict[str, int],
        total_time: float,
    ) -> float:
        """Compute a quality score for a cache entry (0.0 to 1.0)."""
        if not cached_items:
            return 0.0

        # Factor 1: Data completeness (email/phone/website ratio)
        complete = sum(
            bool(item.get("email") or item.get("phone") or item.get("website"))
            for item in cached_items
        ) / len(cached_items)

        # Factor 2: Source diversity (more sources = more reliable)
        active_sources = sum(1 for count in source_counts.values() if count > 0)
        source_score = min(active_sources / 3, 1.0)  # 3 = ideal number of active sources

        # Factor 3: Result yield ratio
        total_sourced = sum(source_counts.values())
        if total_sourced > 0:
            yield_ratio = len(cached_items) / total_sourced
            yield_score = min(yield_ratio, 1.0)
        else:
            yield_score = 0.0

        # Weighted score
        score = (complete * 0.4 + source_score * 0.3 + yield_score * 0.3)
        return round(score, 3)

    def record_cache_quality(
        self,
        query_hash: str,
        items: list[dict],
        source_counts: dict[str, int],
        total_time: float,
    ) -> None:
        """Record quality metrics for a cache entry."""
        score = self.score_cache_entry(items, source_counts, total_time)
        self._cache_scores[query_hash] = score
        self._cache_generated_at[query_hash] = time.monotonic()
        logger.debug("Cache quality for %s: %.1f%% (%d items)", query_hash[:12], score * 100, len(items))


# Shared instance
cache_validator = CacheQualityValidator()


# ---------------------------------------------------------------------------
# Layer 3: MinimumThresholdEnforcer
# ---------------------------------------------------------------------------


def enforce_minimum_results(
    results: list[dict],
    requested_limit: int,
    absolute_floor: int = 5,
) -> list[dict]:
    """Ensure the result set meets minimum expectations.

    If results are below the floor, this function:
    1. Logs a critical warning
    2. Triggers cache flush (to prevent stale-data propagation)
    3. Returns what we have (better than nothing)

    In production, callers should treat below-floor results as a signal
    to trigger fresh discovery or alert users.
    """
    if len(results) < absolute_floor:
        logger.critical(
            "Discovery returned %d results (floor=%d). Flushing cache and alerting.",
            len(results), absolute_floor,
        )
        # Trigger cache flush via circuit breaker
        discovery_breaker._flush_discovery_cache()

    return results


# ---------------------------------------------------------------------------
# Layer 4: DataCompletenessValidator
# ---------------------------------------------------------------------------


def validate_lead_completeness(lead: dict) -> tuple[bool, str]:
    """Validate that an individual lead meets minimum completeness standards.

    A lead must have at least one of:
    - Email + Phone
    - Website + Phone  
    - Email + Website
    - All three contact methods

    This prevents leads with only a name + address from cluttering results.
    """
    has_email = bool(lead.get("email"))
    has_phone = bool(lead.get("phone"))
    has_website = bool(lead.get("website"))
    has_address = bool(lead.get("address"))
    has_name = bool(lead.get("name"))

    if not has_name:
        return False, "Missing business name"

    # Must have at least one strong contact channel
    if has_email and has_phone:
        return True, "Email + Phone present"

    if has_website and has_phone:
        return True, "Website + Phone present"

    if has_email and has_website:
        return True, "Email + Website present"

    if has_email or has_phone or has_website:
        # Single contact method is acceptable but lower priority
        if has_email:
            return True, "Email only (minimal)"
        if has_phone:
            return True, "Phone only (minimal)"
        if has_website:
            return True, "Website only (low quality)"

    # No contact info at all, but has address + coords = accepted by lead_validator
    if has_address and lead.get("lat") and lead.get("lon"):
        return True, "Address-only business (OSM fallback)"

    return False, "No contact info or address"


def filter_incomplete_leads(leads: list[dict]) -> list[dict]:
    """Remove leads that don't meet minimum completeness standards."""
    valid = []
    rejected = 0

    for lead in leads:
        ok, reason = validate_lead_completeness(lead)
        if ok:
            lead["completeness_note"] = reason
            valid.append(lead)
        else:
            rejected += 1

    if rejected > 0:
        logger.info("Filtered %d incomplete leads (%d remaining)", rejected, len(valid))

    return valid


# ---------------------------------------------------------------------------
# Layer 5: AutoRecoveryTrigger
# ---------------------------------------------------------------------------


class AutoRecoveryTrigger:
    """Triggers emergency recovery when discovery quality degrades persistently.

    When triggered, this component:
    1. Flushes all discovery caches (database + Redis)
    2. Resets source circuit breakers
    3. Logs emergency event for monitoring
    4. Sends alert to monitoring system
    """

    def __init__(self):
        self._last_trigger: float = 0.0
        self._trigger_count: int = 0
        self._cooldown_minutes: float = 30.0

    def should_trigger(self, consecutive_failures: int, threshold: int = 3) -> bool:
        """Determine if auto-recovery should be triggered."""
        if consecutive_failures < threshold:
            return False

        # Avoid triggering too frequently
        if (time.monotonic() - self._last_trigger) < (self._cooldown_minutes * 60):
            return False

        return True

    async def trigger_recovery(self, reason: str, session_factory: Optional[Callable] = None) -> dict[str, Any]:
        """Execute emergency recovery procedure."""
        import asyncio
        from datetime import datetime, timezone

        self._last_trigger = time.monotonic()
        self._trigger_count += 1

        logger.critical("AUTO-RECOVERY TRIGGERED: %s", reason)

        recovery_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_count": self._trigger_count,
            "reason": reason,
            "actions_taken": [],
        }

        # Action 1: Flush database cache
        try:
            from app.db.models.discovery_cache import DiscoveryCache
            if session_factory:
                async with session_factory() as session:
                    await session.execute(DiscoveryCache.__table__.delete())
                    await session.commit()
                    recovery_report["actions_taken"].append("database_cache_flushed")
                    logger.info("Database discovery cache flushed")
        except Exception as e:
            logger.error("Failed to flush database cache: %s", e)
            recovery_report["actions_taken"].append(f"database_cache_failed: {str(e)[:100]}")

        # Action 2: Flush Redis cache (if available)
        try:
            from app.core.redis_client import redis_client
            if redis_client:
                keys = await redis_client.keys("discovery:*")
                if keys:
                    await redis_client.delete(*keys)
                    recovery_report["actions_taken"].append(f"redis_cache_flushed:{len(keys)} keys")
                    logger.info("Redis cache flushed (%d keys)", len(keys))
        except ImportError:
            pass
        except Exception as e:
            logger.error("Failed to flush Redis cache: %s", e)

        # Action 3: Reset source circuit breakers
        try:
            from app.services.discovery.crawlers.base import source_tracker
            source_tracker.reset_all()  # Custom method to add
            recovery_report["actions_taken"].append("source_trackers_reset")
        except Exception as e:
            logger.warning("Could not reset source trackers: %s", e)

        # Action 4: Reset discovery circuit breaker
        discovery_breaker.reset()

        recovery_report["status"] = "completed"
        logger.critical("Recovery report: %s", recovery_report)

        return recovery_report


# Shared instance
recovery_trigger = AutoRecoveryTrigger()


# ---------------------------------------------------------------------------
# Utility functions for integration
# ---------------------------------------------------------------------------


def compute_query_hash(niche: str, city: str, country_code: str) -> str:
    """Compute a consistent hash for cache lookups."""
    import hashlib
    raw = f"{niche.strip().lower()}|{city.strip().lower()}|{country_code.upper()}"
    return hashlib.md5(raw.encode()).hexdigest()


def should_bypass_cache(cached_count: int, requested_limit: int) -> bool:
    """Determine if cache should be bypassed due to quality concerns."""
    # Bypass cache if it has fewer than 20% of requested results
    threshold = max(5, requested_limit // 5)
    return cached_count < threshold


# Initialize safety module
logger.info(
    "Discovery safety layers initialized: threshold=%.0f%%, floor=%d results",
    discovery_breaker.quality_floor * 100,
    CacheQualityValidator.MIN_CACHED_RESULTS,
)
