#!/usr/bin/env python3
"""
API Payload Tests
=================
Validates every public endpoint with valid, invalid, and edge-case payloads.

Run:
    python tests/test_payloads.py

Env vars:
    TEST_BASE_URL       — target server (default: http://localhost:8000)
    TEST_USER_EMAIL     — email for auth-required tests
    TEST_USER_PASSWORD  — password for auth-required tests
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from conftest import API_V1, DEFAULT_TIMEOUT, get_session, TestResult


def test_health(session, results):
    """GET /api/v1/health/ — should always return 200."""
    print("\n── Health Check ──")
    r = session.get(f"{API_V1}/health/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 200, "Health returns 200", f"status={r.status_code}")
    data = r.json()
    results.check(data.get("status") == "healthy", "Status is healthy")
    results.check("version" in data, "Contains version field")


def test_csrf(session, results):
    """GET /api/v1/csrf/ — should set CSRF cookie and return token."""
    print("\n── CSRF Token ──")
    r = session.get(f"{API_V1}/csrf/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 200, "CSRF returns 200")
    data = r.json()
    results.check(bool(data.get("csrfToken")), "Token present", f"len={len(data.get('csrfToken', ''))}")
    results.check("csrftoken" in session.cookies or "csrftoken" in r.cookies, "CSRF cookie set")


def test_search_valid(session, results):
    """GET /api/v1/search/?q=dress — valid search."""
    print("\n── Search (valid) ──")
    r = session.get(f"{API_V1}/search/", params={"q": "dress"}, timeout=30)
    results.check(r.status_code == 200, "Search returns 200", f"status={r.status_code}")
    data = r.json()
    results.check("deals" in data, "Response contains 'deals' key")
    results.check(isinstance(data.get("deals"), list), "Deals is a list")
    if data.get("deals"):
        deal = data["deals"][0]
        results.check("title" in deal, "Deal has 'title'")
        results.check("price" in deal, "Deal has 'price'")
        results.check("url" in deal, "Deal has 'url'")


def test_search_empty_query(session, results):
    """GET /api/v1/search/?q= — should return 400."""
    print("\n── Search (empty query) ──")
    r = session.get(f"{API_V1}/search/", params={"q": ""}, timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 400, "Empty query returns 400", f"status={r.status_code}")


def test_search_short_query(session, results):
    """GET /api/v1/search/?q=a — should return 400 (min 2 chars)."""
    print("\n── Search (too short) ──")
    r = session.get(f"{API_V1}/search/", params={"q": "a"}, timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 400, "1-char query returns 400", f"status={r.status_code}")


def test_search_long_query(session, results):
    """GET /api/v1/search/?q=<250 chars> — should return 400 (max 200 chars)."""
    print("\n── Search (too long) ──")
    long_q = "a" * 250
    r = session.get(f"{API_V1}/search/", params={"q": long_q}, timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 400, "Over-length query returns 400", f"status={r.status_code}")


def test_search_xss_payload(session, results):
    """GET /api/v1/search/?q=<script>alert(1)</script> — should sanitise."""
    print("\n── Search (XSS payload) ──")
    r = session.get(
        f"{API_V1}/search/",
        params={"q": '<script>alert("xss")</script>'},
        timeout=DEFAULT_TIMEOUT,
    )
    # Should either 400 (rejected) or 200 with no script tags in response
    results.check(r.status_code in (200, 400), "XSS query handled", f"status={r.status_code}")
    if r.status_code == 200:
        results.check("<script>" not in r.text, "No script tags in response")


def test_search_sql_injection(session, results):
    """GET /api/v1/search/?q=' OR 1=1 -- — should not crash."""
    print("\n── Search (SQL injection) ──")
    r = session.get(
        f"{API_V1}/search/",
        params={"q": "' OR 1=1 --"},
        timeout=DEFAULT_TIMEOUT,
    )
    results.check(r.status_code in (200, 400), "SQL injection handled gracefully", f"status={r.status_code}")
    results.check(r.status_code != 500, "No 500 error on SQL injection")


def test_search_pagination(session, results):
    """GET /api/v1/search/?q=shoes&page=1&limit=5 — pagination works."""
    print("\n── Search (pagination) ──")
    r = session.get(
        f"{API_V1}/search/",
        params={"q": "shoes", "page": 1, "limit": 5},
        timeout=30,
    )
    results.check(r.status_code == 200, "Paginated search returns 200")
    data = r.json()
    results.check(len(data.get("deals", [])) <= 5, "Respects limit param", f"got {len(data.get('deals', []))}")
    results.check("has_more" in data, "Contains 'has_more' pagination field")


def test_instant_search(session, results):
    """GET /api/v1/search/instant/?q=jeans — fast cache lookup."""
    print("\n── Instant Search ──")
    r = session.get(f"{API_V1}/search/instant/", params={"q": "jeans"}, timeout=5)
    results.check(r.status_code == 200, "Instant search returns 200")
    data = r.json()
    results.check("deals" in data, "Response has 'deals'")
    results.check("cached" in data, "Response has 'cached' flag")


def test_featured_content(session, results):
    """GET /api/v1/featured/ — curated content."""
    print("\n── Featured Content ──")
    r = session.get(f"{API_V1}/featured/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 200, "Featured returns 200")
    data = r.json()
    results.check("featured_brands" in data, "Has 'featured_brands'")
    results.check("search_prompts" in data, "Has 'search_prompts'")
    results.check("categories" in data, "Has 'categories'")


def test_explore(session, results):
    """GET /api/v1/explore/?category=women — explore products."""
    print("\n── Explore ──")
    r = session.get(f"{API_V1}/explore/", params={"category": "women"}, timeout=30)
    results.check(r.status_code == 200, "Explore returns 200")
    data = r.json()
    results.check("deals" in data, "Has 'deals' list")
    results.check(data.get("category") == "women", "Category echoed back")


def test_vendor_status(session, results):
    """GET /api/v1/vendors/status/ — vendor health."""
    print("\n── Vendor Status ──")
    r = session.get(f"{API_V1}/vendors/status/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 200, "Vendor status returns 200")
    data = r.json()
    results.check("vendors" in data, "Has 'vendors'")
    results.check("total_enabled" in data, "Has 'total_enabled'")


def test_brands_list(session, results):
    """GET /api/v1/brands/ — brand listing with sorting."""
    print("\n── Brands List ──")

    # Default sort (trending)
    r = session.get(f"{API_V1}/brands/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 200, "Brand list returns 200")
    data = r.json()
    results.check("brands" in data, "Has 'brands' list")
    results.check(data.get("total", 0) > 0, "Has brands", f"total={data.get('total')}")

    if data.get("brands"):
        brand = data["brands"][0]
        results.check("name" in brand, "Brand has 'name'")
        results.check("slug" in brand, "Brand has 'slug'")
        results.check("likes_count" in brand, "Brand has 'likes_count'")
        results.check("is_liked" in brand, "Brand has 'is_liked'")
        results.check("category" in brand, "Brand has 'category'")

    # Sort params
    for sort_by in ["most_liked", "newest", "trending"]:
        r2 = session.get(f"{API_V1}/brands/", params={"sort": sort_by}, timeout=DEFAULT_TIMEOUT)
        results.check(r2.status_code == 200, f"Sort={sort_by} returns 200")
        results.check(r2.json().get("sort") == sort_by, f"Sort={sort_by} echoed")

    # Category filter
    r3 = session.get(f"{API_V1}/brands/", params={"category": "womens"}, timeout=DEFAULT_TIMEOUT)
    results.check(r3.status_code == 200, "Category filter returns 200")


def test_brands_like_unauthenticated(session, results):
    """POST /api/v1/brands/<slug>/like/ — should require auth."""
    print("\n── Brand Like (unauth) ──")
    r = session.post(f"{API_V1}/brands/fashion-nova/like/", timeout=DEFAULT_TIMEOUT)
    results.check(
        r.status_code in (401, 403),
        "Like without auth rejected",
        f"status={r.status_code}",
    )


def test_brands_like_authenticated(auth_session, results):
    """POST + DELETE /api/v1/brands/<slug>/like/ — like/unlike flow."""
    print("\n── Brand Like (auth) ──")
    if auth_session is None:
        results.fail("Brand like (auth)", "No auth session — set TEST_USER_EMAIL/TEST_USER_PASSWORD")
        return

    # Like
    r1 = auth_session.post(f"{API_V1}/brands/fashion-nova/like/", timeout=DEFAULT_TIMEOUT)
    results.check(r1.status_code in (200, 201), "Like returns 200/201", f"status={r1.status_code}")
    if r1.ok:
        data = r1.json()
        results.check(data.get("liked") is True, "liked=true")
        results.check(isinstance(data.get("likes_count"), int), "likes_count is int")

    # Unlike
    r2 = auth_session.delete(f"{API_V1}/brands/fashion-nova/like/", timeout=DEFAULT_TIMEOUT)
    results.check(r2.status_code == 200, "Unlike returns 200", f"status={r2.status_code}")
    if r2.ok:
        data = r2.json()
        results.check(data.get("liked") is False, "liked=false")


def test_brands_like_nonexistent(auth_session, results):
    """POST /api/v1/brands/does-not-exist/like/ — should 404."""
    print("\n── Brand Like (nonexistent) ──")
    if auth_session is None:
        results.fail("Brand like 404", "No auth session")
        return

    r = auth_session.post(f"{API_V1}/brands/does-not-exist-brand-xyz/like/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 404, "Nonexistent brand returns 404", f"status={r.status_code}")


def test_upload_no_image(session, results):
    """POST /api/v1/upload/ — should reject empty body."""
    print("\n── Upload (no image) ──")
    r = session.post(f"{API_V1}/upload/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 400, "No image returns 400", f"status={r.status_code}")


def test_saved_deals_unauthenticated(session, results):
    """GET /api/v1/saved/ — should require auth."""
    print("\n── Saved Deals (unauth) ──")
    r = session.get(f"{API_V1}/saved/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code in (401, 403), "Saved deals requires auth", f"status={r.status_code}")


def test_storyboard_invalid_token(session, results):
    """GET /api/v1/storyboard/share/<bad-token>/ — should 404."""
    print("\n── Storyboard (bad token) ──")
    r = session.get(f"{API_V1}/storyboard/share/nonexistenttokenabc/", timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code == 404, "Invalid token returns 404", f"status={r.status_code}")


def test_large_payload(session, results):
    """POST large JSON to search — should not crash."""
    print("\n── Large Payload ──")
    big_payload = {"q": "dress", "extra": "x" * 50000}
    r = session.get(f"{API_V1}/search/", params=big_payload, timeout=DEFAULT_TIMEOUT)
    results.check(r.status_code in (200, 400, 414), "Large payload handled", f"status={r.status_code}")
    results.check(r.status_code != 500, "No 500 on large payload")


# ── Runner ───────────────────────────────────────────
def main():
    print(f"🎯 Fynda API Payload Tests")
    print(f"   Target: {API_V1}\n")

    results = TestResult()
    session = get_session(authenticate=False)
    auth_session = None

    # Try to get authenticated session
    if os.getenv("TEST_USER_EMAIL"):
        auth_session = get_session(authenticate=True)

    # Run all tests
    tests = [
        (test_health, session),
        (test_csrf, session),
        (test_search_valid, session),
        (test_search_empty_query, session),
        (test_search_short_query, session),
        (test_search_long_query, session),
        (test_search_xss_payload, session),
        (test_search_sql_injection, session),
        (test_search_pagination, session),
        (test_instant_search, session),
        (test_featured_content, session),
        (test_explore, session),
        (test_vendor_status, session),
        (test_brands_list, session),
        (test_brands_like_unauthenticated, session),
        (test_upload_no_image, session),
        (test_saved_deals_unauthenticated, session),
        (test_storyboard_invalid_token, session),
        (test_large_payload, session),
    ]

    auth_tests = [
        (test_brands_like_authenticated, auth_session),
        (test_brands_like_nonexistent, auth_session),
    ]

    for fn, sess in tests:
        try:
            fn(sess, results)
        except Exception as e:
            results.fail(fn.__name__, str(e))

    for fn, sess in auth_tests:
        try:
            fn(sess, results)
        except Exception as e:
            results.fail(fn.__name__, str(e))

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
