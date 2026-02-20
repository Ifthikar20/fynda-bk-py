"""
Shared configuration for API tests.

Set BASE_URL via environment variable or defaults to localhost:8000.

Usage:
    export TEST_BASE_URL=https://your-staging-server.com
    python test_payloads.py
"""

import os
import time
import requests

# ── Configuration ──────────────────────────────────
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000").rstrip("/")
API_V1 = f"{BASE_URL}/api/v1"

# Optional auth credentials (email + password for Django session auth)
TEST_EMAIL = os.getenv("TEST_USER_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_USER_PASSWORD", "")

# Timeouts
DEFAULT_TIMEOUT = 15  # seconds


def get_session(authenticate=False):
    """Return a requests.Session, optionally authenticated."""
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
    })

    if authenticate and TEST_EMAIL and TEST_PASSWORD:
        # Get CSRF token first
        csrf_resp = s.get(f"{API_V1}/csrf/", timeout=DEFAULT_TIMEOUT)
        if csrf_resp.ok:
            csrf_token = csrf_resp.json().get("csrfToken", "")
            s.headers["X-CSRFToken"] = csrf_token

        # Login
        login_resp = s.post(
            f"{API_V1}/auth/login/",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=DEFAULT_TIMEOUT,
        )
        if login_resp.ok:
            print(f"  ✓ Authenticated as {TEST_EMAIL}")
        else:
            print(f"  ✗ Auth failed ({login_resp.status_code}): {login_resp.text[:200]}")

    return s


class TestResult:
    """Collect and report test results."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, detail=""):
        self.passed += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name, detail=""):
        self.failed += 1
        self.errors.append((name, detail))
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

    def check(self, condition, name, detail=""):
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, detail)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for name, detail in self.errors:
                print(f"  • {name}: {detail}")
        print(f"{'='*50}")
        return self.failed == 0
