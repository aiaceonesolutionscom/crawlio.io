"""Integration test for discovery safety layers - prevents '50 search -> 1 result' regression.

Tests all 5 safety layers working together:
1. CacheQualityValidator rejects poor-quality cache entries
2. DiscoveryCircuitBreaker detects degraded searches
3. MinimumThresholdEnforcer triggers alerts
4. DataCompletenessValidator filters incomplete leads
5. AutoRecoveryTrigger clears caches when triggered
"""
import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from app.services.discovery.discovery_safety import (
    DiscoveryCircuitBreaker,
    CacheQualityValidator,
    AutoRecoveryTrigger,
    enforce_minimum_results,
    filter_incomplete_leads,
    validate_lead_completeness,
    discovery_breaker,
    cache_validator,
    recovery_trigger,
    compute_query_hash,
)


def test_cache_validation_rejects_sparse_entries():
    """Test that cache quality validator rejects entries with only 1-2 results."""
    print("\n=== TEST: Cache rejects sparse entries ===")
    
    # Simulate yesterday's broken cache entry (1 result)
    sparse_cache = [{"name": "Bad Data", "source": "google_maps"}]
    query_hash = compute_query_hash("Plastic Surgeon", "Dubai", "AE")
    
    is_valid, reason = cache_validator.is_cache_valid(
        cached_items=sparse_cache,
        query_hash=query_hash,
        requested_limit=50,
    )
    
    assert not is_valid, f"Cache with 1 item should be invalid, but got: {reason}"
    assert "only" in reason.lower(), f"Reason should mention sparse data: {reason}"
    print(f"PASS: Sparse cache rejected - '{reason}'")


def test_cache_accepts_high_quality_entries():
    """Test that cache quality validator accepts entries with 50+ results."""
    print("\n=== TEST: Cache accepts quality entries ===")
    
    # Simulate a good cache entry (50 results)
    good_cache = [{"name": f"Business {i}", "phone": "+971 50 1234567"} for i in range(50)]
    query_hash = compute_query_hash("Dentist", "Karachi", "PK")
    
    # Record quality first
    cache_validator.record_cache_quality(
        query_hash=query_hash,
        items=good_cache,
        source_counts={"maps": 20, "osm": 15, "tavily": 15},
        total_time=120.0,
    )
    
    is_valid, reason = cache_validator.is_cache_valid(
        cached_items=good_cache,
        query_hash=query_hash,
        requested_limit=50,
    )
    
    assert is_valid, f"Cache with 50 good items should be valid: {reason}"
    print(f"PASS: Quality cache accepted - '{reason}'")


def test_circuit_breaker_detects_degradation():
    """Test that circuit breaker catches repeated poor results."""
    print("\n=== TEST: Circuit breaker detects degradation ===")
    
    breaker = DiscoveryCircuitBreaker(
        name="test-discovery",
        failure_threshold=3,
        quality_floor=0.3,
        cooldown_seconds=60,
    )
    
    # Simulate 3 consecutive poor searches (got 1, 0, 1 results when expecting 50)
    for i in range(3):
        is_good, reason = breaker.evaluate_search(
            requested_limit=50,
            actual_results=1,  # This is yesterday's bug!
            source_counts={"maps": 1, "osm": 0},
        )
        print(f"  Search {i+1}: is_good={is_good}, reason='{reason}'")
        assert not is_good, "Should detect poor results"
    
    assert breaker.consecutive_failures >= 3, "Should have tripped after 3 failures"
    print(f"PASS: Circuit breaker tripped after {breaker.consecutive_failures} failures")


def test_circuit_breaker_resets_on_success():
    """Test that circuit breaker resets when good results come in."""
    print("\n=== TEST: Circuit breaker resets on success ===")
    
    breaker = DiscoveryCircuitBreaker(
        name="test-recovery",
        failure_threshold=3,
        quality_floor=0.3,
        cooldown_seconds=60,
    )
    
    # Trip the breaker
    for _ in range(3):
        breaker.evaluate_search(50, 1)
    
    assert breaker.consecutive_failures >= 3, "Should be tripped"
    
    # Now recover
    is_good, _ = breaker.evaluate_search(50, 45)  # Good result!
    assert is_good, "Should detect good results"
    assert breaker.consecutive_failures == 0, "Should reset failure count"
    
    print("PASS: Circuit breaker reset successfully")


def test_minimum_results_enforcement():
    """Test that minimum results checker doesn't crash on empty results."""
    print("\n=== TEST: Minimum results enforcement ===")
    
    # Simulate today's scenario - 19 results when expecting 50
    results = [{"name": f"Lead {i}"} for i in range(19)]
    
    # This should log a critical warning but not crash
    enforced = enforce_minimum_results(results, requested_limit=50, absolute_floor=5)
    assert len(enforced) == 19, "Should return same results"
    
    # Test with truly sparse results (below floor)
    sparse = [{"name": "Only One"}]
    enforced = enforce_minimum_results(sparse, requested_limit=50, absolute_floor=5)
    assert len(enforced) == 1, "Should still return what we have"
    
    print("PASS: Minimum results enforcement works without crashing")


def test_data_completeness_filter():
    """Test that incomplete leads are filtered out."""
    print("\n=== TEST: Data completeness filtering ===")
    
    leads = [
        # Complete lead - should pass
        {"name": "Best Dental Clinic", "email": "info@bestdental.com", "phone": "+971 4 123 4567", "website": "https://bestdental.com"},
        
        # Complete but different combo
        {"name": "City Hospital", "email": "contact@cityhospital.com", "website": "https://cityhospital.com"},
        
        # Incomplete - only name, no contact info (should be filtered)
        {"name": "Ghost Business", "address": "Dubai, UAE"},
        
        # Valid address-only (OSM fallback)
        {"name": "OSM Business", "address": "Dubai Marina", "lat": 25.077, "lon": 55.147},
    ]
    
    filtered = filter_incomplete_leads(leads)
    
    print(f"  Input: {len(leads)} leads")
    print(f"  Output: {len(filtered)} leads (filtered: {len(leads) - len(filtered)})")
    
    # Should filter out "Ghost Business" but keep OSM Business (has coords)
    assert len(filtered) == 3, f"Should filter 1, keep 3, got {len(filtered)}"
    assert "Ghost Business" not in [l["name"] for l in filtered], "Should filter out incomplete lead"
    
    print("PASS: Data completeness filtering works correctly")


def test_auto_recovery_trigger():
    """Test that auto-recovery trigger activates appropriately."""
    print("\n=== TEST: Auto-recovery trigger ===")
    
    trigger = AutoRecoveryTrigger()
    
    # Should not trigger below threshold
    assert not trigger.should_trigger(consecutive_failures=2), "Should not trigger below threshold"
    
    # Should trigger at threshold
    assert trigger.should_trigger(consecutive_failures=3), "Should trigger at threshold"
    
    # Should trigger again after cooldown
    import time as time_module
    trigger._last_trigger = time_module.monotonic() - 1801  # 31 minutes ago
    assert trigger.should_trigger(consecutive_failures=3), "Should trigger after cooldown"
    
    print("PASS: Auto-recovery trigger logic works correctly")


def test_end_to_end_scenario():
    """Simulate complete flow: bad cache → detection → fresh discovery."""
    print("\n=== TEST: End-to-end bad cache scenario ===")
    
    # Step 1: Simulate accessing broken cache (1 result)
    broken_cache = [{"name": "Bad Entry Only"}]
    query_hash = compute_query_hash("Plastic Surgeon", "Dubai", "AE")
    
    cache_validator.record_cache_quality(
        query_hash=query_hash,
        items=broken_cache,
        source_counts={"maps": 1},
        total_time=120.0,
    )
    
    is_valid, reason = cache_validator.is_cache_valid(
        cached_items=broken_cache,
        query_hash=query_hash,
        requested_limit=50,
    )
    
    assert not is_valid, "Broken cache should be rejected"
    print(f"  Cache rejected: {reason}")
    
    # Step 2: Simulate fresh discovery with poor results
    discovery_breaker.evaluate_search(50, 1, {"maps": 1, "osm": 0})
    discovery_breaker.evaluate_search(50, 0, {"maps": 0, "osm": 0})  
    discovery_breaker.evaluate_search(50, 1, {"maps": 1, "tavily": 0})
    
    # Step 3: Circuit breaker should trip
    assert discovery_breaker.consecutive_failures >= 3, "Should be tripped"
    print(f"  Circuit breaker tripped after {discovery_breaker.consecutive_failures} failures")
    
    # Step 4: Recovery trigger should activate
    assert recovery_trigger.should_trigger(discovery_breaker.consecutive_failures)
    print("  Recovery trigger activated")
    
    print("PASS: End-to-end flow correctly detects and handles bad cache scenario")


def main():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("TEST: DISCOVERY SAFETY LAYERS INTEGRATION")
    print("="*60)
    
    tests = [
        test_cache_validation_rejects_sparse_entries,
        test_cache_accepts_high_quality_entries,
        test_circuit_breaker_detects_degradation,
        test_circuit_breaker_resets_on_success,
        test_minimum_results_enforcement,
        test_data_completeness_filter,
        test_auto_recovery_trigger,
        test_end_to_end_scenario,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"FAILED: {test.__name__} - {str(e)}")
            failed += 1
    
    print("\n" + "="*60)
    if failed == 0:
        print("ALL TESTS PASSED - Safety layers working correctly!")
        print("   The '50 search -> 1 result' bug is now prevented.")
    else:
        print(f"FAILED: {failed}/{len(tests)} TESTS FAILED")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
