#!/usr/bin/env python3
"""
Brand API Stress Test
=====================
Focused stress test on the new brands endpoints:
  - Brand listing under concurrent load
  - Like/unlike race conditions
  - Sort parameter switching

Run:
    python tests/test_brands_stress.py
    python tests/test_brands_stress.py --users 30 --rounds 50

Env vars:
    TEST_BASE_URL       — target server
    TEST_USER_EMAIL     — required for like tests
    TEST_USER_PASSWORD  — required for like tests
"""

import sys
import os
import time
import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from conftest import API_V1, DEFAULT_TIMEOUT, get_session


def test_concurrent_brand_listing(users=20, rounds=30):
    """Hit /brands/ with different sort params concurrently."""
    print(f"\n── Concurrent Brand Listing ({users} users × {rounds} rounds) ──")

    sorts = ["trending", "most_liked", "newest"]
    categories = [None, "womens", "mens", "shoes", "beauty"]
    results = {"success": 0, "fail": 0, "times": []}

    def worker(_):
        s = get_session()
        for _ in range(rounds):
            sort = random.choice(sorts)
            cat = random.choice(categories)
            params = {"sort": sort}
            if cat:
                params["category"] = cat

            start = time.perf_counter()
            try:
                r = s.get(f"{API_V1}/brands/", params=params, timeout=DEFAULT_TIMEOUT)
                elapsed = time.perf_counter() - start
                results["times"].append(elapsed)

                if r.status_code == 200:
                    data = r.json()
                    assert "brands" in data
                    results["success"] += 1
                else:
                    results["fail"] += 1
            except Exception:
                results["fail"] += 1

    with ThreadPoolExecutor(max_workers=users) as executor:
        list(executor.map(worker, range(users)))

    total = results["success"] + results["fail"]
    avg_ms = (sum(results["times"]) / len(results["times"]) * 1000) if results["times"] else 0
    print(f"  Total:   {total} requests")
    print(f"  Success: {results['success']} ({results['success']/total*100:.1f}%)")
    print(f"  Avg:     {avg_ms:.0f}ms")

    if results["times"]:
        sorted_t = sorted(results["times"])
        p95 = sorted_t[int(len(sorted_t) * 0.95)] * 1000
        print(f"  P95:     {p95:.0f}ms")

    return results["fail"] == 0


def test_like_race_condition(users=10, rounds=20):
    """
    Multiple users liking/unliking the same brand simultaneously.
    Checks that likes_count stays consistent.
    """
    print(f"\n── Like Race Condition ({users} users × {rounds} rounds) ──")

    # Check if we have auth
    if not os.getenv("TEST_USER_EMAIL"):
        print("  ⏭  Skipped — set TEST_USER_EMAIL/TEST_USER_PASSWORD")
        return True

    auth_session = get_session(authenticate=True)
    slug = "gymshark"

    # Get initial count
    r = auth_session.get(f"{API_V1}/brands/", timeout=DEFAULT_TIMEOUT)
    brands = r.json().get("brands", [])
    target = next((b for b in brands if b["slug"] == slug), None)
    if not target:
        print(f"  ⏭  Brand '{slug}' not found, skipping")
        return True

    initial_count = target["likes_count"]
    print(f"  Initial likes_count for {slug}: {initial_count}")

    errors = []

    def toggle_like(_):
        s = get_session(authenticate=True)
        for _ in range(rounds):
            try:
                # Like
                r1 = s.post(f"{API_V1}/brands/{slug}/like/", timeout=DEFAULT_TIMEOUT)
                if r1.status_code not in (200, 201):
                    errors.append(f"Like failed: {r1.status_code}")

                # Unlike
                r2 = s.delete(f"{API_V1}/brands/{slug}/like/", timeout=DEFAULT_TIMEOUT)
                if r2.status_code != 200:
                    errors.append(f"Unlike failed: {r2.status_code}")
            except Exception as e:
                errors.append(str(e))

    with ThreadPoolExecutor(max_workers=users) as executor:
        list(executor.map(toggle_like, range(users)))

    # Check final count — should be back to initial since each user liked then unliked
    r = auth_session.get(f"{API_V1}/brands/", timeout=DEFAULT_TIMEOUT)
    brands = r.json().get("brands", [])
    target = next((b for b in brands if b["slug"] == slug), None)
    final_count = target["likes_count"] if target else -1

    print(f"  Final likes_count: {final_count} (expected: {initial_count})")
    print(f"  Errors: {len(errors)}")

    if errors:
        print(f"  First 5 errors: {errors[:5]}")

    ok = final_count == initial_count and len(errors) == 0
    print(f"  {'✅ PASS' if ok else '⚠️  COUNT DRIFT — possible race condition'}")
    return ok


def test_sort_consistency(rounds=10):
    """Verify sort order is deterministic across repeated calls."""
    print(f"\n── Sort Consistency ({rounds} rounds) ──")

    session = get_session()
    issues = 0

    for sort_by in ["most_liked", "trending", "newest"]:
        prev_order = None
        for _ in range(rounds):
            r = session.get(
                f"{API_V1}/brands/",
                params={"sort": sort_by},
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code != 200:
                issues += 1
                continue

            slugs = [b["slug"] for b in r.json().get("brands", [])]
            if prev_order is not None and slugs != prev_order:
                issues += 1
                print(f"  ⚠️  Sort={sort_by}: order changed between requests")
            prev_order = slugs

    if issues == 0:
        print(f"  ✅ All sort orders are deterministic")
    else:
        print(f"  ⚠️  {issues} inconsistencies found")

    return issues == 0


def main():
    parser = argparse.ArgumentParser(description="Brand API Stress Test")
    parser.add_argument("--users", type=int, default=20, help="Concurrent users (default: 20)")
    parser.add_argument("--rounds", type=int, default=30, help="Rounds per user (default: 30)")
    args = parser.parse_args()

    print(f"🎯 Brand Stress Tests — Target: {API_V1}")

    all_passed = True
    all_passed &= test_concurrent_brand_listing(args.users, args.rounds)
    all_passed &= test_like_race_condition(min(args.users, 10), min(args.rounds, 20))
    all_passed &= test_sort_consistency()

    print(f"\n{'='*50}")
    print(f"  {'✅ ALL PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print(f"{'='*50}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
