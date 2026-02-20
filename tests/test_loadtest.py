#!/usr/bin/env python3
"""
API Load & Scale Tests
======================
Hammers endpoints with concurrent requests to measure response times,
throughput, and error rates. No external dependencies — uses stdlib only.

Run:
    python tests/test_loadtest.py                          # defaults
    python tests/test_loadtest.py --users 50 --duration 30 # heavier

Env vars:
    TEST_BASE_URL  — target server (default: http://localhost:8000)
"""

import sys
import os
import time
import argparse
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from conftest import API_V1, DEFAULT_TIMEOUT, get_session


# ── Endpoints to load-test (GET-only for safety) ──────
ENDPOINTS = [
    {"name": "Health", "method": "GET", "path": "/health/"},
    {"name": "CSRF", "method": "GET", "path": "/csrf/"},
    {"name": "Featured", "method": "GET", "path": "/featured/"},
    {"name": "Brands List", "method": "GET", "path": "/brands/"},
    {"name": "Brands (most_liked)", "method": "GET", "path": "/brands/?sort=most_liked"},
    {"name": "Brands (trending)", "method": "GET", "path": "/brands/?sort=trending"},
    {"name": "Vendor Status", "method": "GET", "path": "/vendors/status/"},
    {"name": "Instant Search", "method": "GET", "path": "/search/instant/?q=dress"},
    {"name": "Explore (women)", "method": "GET", "path": "/explore/?category=women"},
    {"name": "Search (shoes)", "method": "GET", "path": "/search/?q=shoes&limit=5"},
]


class LoadTestResult:
    """Tracks per-request metrics for a single endpoint."""

    def __init__(self, name):
        self.name = name
        self.response_times = []
        self.status_codes = defaultdict(int)
        self.errors = 0

    @property
    def total(self):
        return len(self.response_times) + self.errors

    @property
    def success_rate(self):
        if self.total == 0:
            return 0
        return (self.total - self.errors) / self.total * 100

    def add(self, elapsed, status_code):
        self.response_times.append(elapsed)
        self.status_codes[status_code] += 1

    def add_error(self):
        self.errors += 1

    def report(self):
        if not self.response_times:
            return f"  {self.name}: NO DATA (all errors)"

        times = sorted(self.response_times)
        avg = statistics.mean(times)
        med = statistics.median(times)
        p95 = times[int(len(times) * 0.95)] if len(times) >= 2 else times[-1]
        p99 = times[int(len(times) * 0.99)] if len(times) >= 2 else times[-1]
        mn, mx = min(times), max(times)

        status_str = ", ".join(f"{code}:{count}" for code, count in sorted(self.status_codes.items()))

        return (
            f"  {self.name}:\n"
            f"    Requests:  {self.total} ({self.errors} errors, {self.success_rate:.1f}% success)\n"
            f"    Avg:       {avg*1000:.0f}ms | Median: {med*1000:.0f}ms\n"
            f"    P95:       {p95*1000:.0f}ms | P99:    {p99*1000:.0f}ms\n"
            f"    Min/Max:   {mn*1000:.0f}ms / {mx*1000:.0f}ms\n"
            f"    Status:    {status_str}"
        )


def fire_request(session, endpoint):
    """Fire a single request and return (elapsed_seconds, status_code) or None on error."""
    url = f"{API_V1}{endpoint['path']}"
    start = time.perf_counter()
    try:
        r = session.get(url, timeout=DEFAULT_TIMEOUT)
        elapsed = time.perf_counter() - start
        return elapsed, r.status_code
    except Exception:
        return None


def run_load_test(users, duration, ramp_up=2):
    """
    Simulate `users` concurrent virtual users hitting all endpoints
    for `duration` seconds.
    """
    print(f"\n{'='*60}")
    print(f"  Fynda API Load Test")
    print(f"  Target:     {API_V1}")
    print(f"  Users:      {users}")
    print(f"  Duration:   {duration}s")
    print(f"  Ramp-up:    {ramp_up}s")
    print(f"  Endpoints:  {len(ENDPOINTS)}")
    print(f"{'='*60}\n")

    # Create per-endpoint results
    results = {ep["name"]: LoadTestResult(ep["name"]) for ep in ENDPOINTS}
    total_requests = 0

    session = get_session()
    start_time = time.time()

    def worker(endpoint):
        """Worker that repeatedly hits an endpoint until duration expires."""
        nonlocal total_requests
        local_count = 0
        s = get_session()  # each worker gets its own session

        while time.time() - start_time < duration:
            result = fire_request(s, endpoint)
            if result is not None:
                elapsed, status = result
                results[endpoint["name"]].add(elapsed, status)
            else:
                results[endpoint["name"]].add_error()
            local_count += 1
            # Small jitter to avoid thundering herd
            time.sleep(0.01)

        return local_count

    # Distribute workers across endpoints
    tasks = []
    workers_per_endpoint = max(1, users // len(ENDPOINTS))
    remaining = users - (workers_per_endpoint * len(ENDPOINTS))

    task_list = []
    for ep in ENDPOINTS:
        count = workers_per_endpoint + (1 if remaining > 0 else 0)
        remaining -= 1
        for _ in range(count):
            task_list.append(ep)

    # Ramp up workers gradually
    print(f"  Ramping up {len(task_list)} workers...")

    with ThreadPoolExecutor(max_workers=len(task_list)) as executor:
        futures = {}
        for i, ep in enumerate(task_list):
            futures[executor.submit(worker, ep)] = ep["name"]
            # Ramp-up delay
            if ramp_up > 0:
                time.sleep(ramp_up / len(task_list))

        # Wait for all workers
        for future in as_completed(futures):
            total_requests += future.result()

    elapsed_total = time.time() - start_time
    rps = total_requests / elapsed_total if elapsed_total > 0 else 0

    # ── Report ──
    print(f"\n{'='*60}")
    print(f"  RESULTS (total: {total_requests} requests in {elapsed_total:.1f}s)")
    print(f"  Throughput: {rps:.1f} req/s")
    print(f"{'='*60}\n")

    all_times = []
    all_errors = 0
    for ep in ENDPOINTS:
        r = results[ep["name"]]
        print(r.report())
        print()
        all_times.extend(r.response_times)
        all_errors += r.errors

    # ── Overall summary ──
    if all_times:
        print(f"{'─'*60}")
        print(f"  OVERALL SUMMARY")
        print(f"    Total Requests:   {total_requests}")
        print(f"    Total Errors:     {all_errors}")
        print(f"    Success Rate:     {((total_requests - all_errors) / total_requests * 100):.1f}%")
        print(f"    Throughput:       {rps:.1f} req/s")
        print(f"    Avg Response:     {statistics.mean(all_times)*1000:.0f}ms")
        print(f"    Median Response:  {statistics.median(all_times)*1000:.0f}ms")
        p95 = sorted(all_times)[int(len(all_times) * 0.95)]
        print(f"    P95 Response:     {p95*1000:.0f}ms")
        print(f"{'─'*60}")

    # ── Pass/Fail thresholds ──
    passed = True
    if all_errors / max(total_requests, 1) > 0.05:
        print("\n  ⚠️  FAIL: Error rate > 5%")
        passed = False
    if all_times and statistics.median(all_times) > 2.0:
        print("\n  ⚠️  FAIL: Median response time > 2s")
        passed = False
    if passed:
        print("\n  ✅ PASS: All thresholds met")

    return passed


def main():
    parser = argparse.ArgumentParser(description="Fynda API Load Test")
    parser.add_argument("--users", type=int, default=20, help="Concurrent virtual users (default: 20)")
    parser.add_argument("--duration", type=int, default=15, help="Test duration in seconds (default: 15)")
    parser.add_argument("--ramp-up", type=int, default=2, help="Ramp-up period in seconds (default: 2)")
    args = parser.parse_args()

    passed = run_load_test(args.users, args.duration, args.ramp_up)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
