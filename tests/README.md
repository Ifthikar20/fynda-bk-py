# Fynda API Test Suite

Run API payload validation, load testing, and stress tests against any environment.

## Quick Start

```bash
# Start your server first
python manage.py runserver

# Run all tests
./tests/run_tests.sh

# Or individual suites
./tests/run_tests.sh payloads    # payload validation
./tests/run_tests.sh load        # concurrent load test
./tests/run_tests.sh brands      # brand endpoint stress test
./tests/run_tests.sh heavy       # 50 users, 30s duration
```

## Targeting a Remote Server

```bash
export TEST_BASE_URL=https://staging.outfi.ai
./tests/run_tests.sh
```

## Authenticated Tests

Some tests (brand likes, saved deals) need auth credentials:

```bash
export TEST_USER_EMAIL=test@example.com
export TEST_USER_PASSWORD=yourpassword
./tests/run_tests.sh
```

## Test Scripts

| Script | What it tests |
|--------|---------------|
| `test_payloads.py` | Every endpoint — valid, invalid, XSS, SQL injection, pagination, auth |
| `test_loadtest.py` | Concurrent users hitting all GET endpoints — measures avg/P95/P99 response times, throughput, error rate |
| `test_brands_stress.py` | Brand listing under load, like/unlike race conditions, sort determinism |

## Load Test Flags

```bash
python tests/test_loadtest.py --users 50 --duration 30 --ramp-up 5
```

| Flag | Default | Description |
|------|---------|-------------|
| `--users` | 20 | Concurrent virtual users |
| `--duration` | 15 | Test duration (seconds) |
| `--ramp-up` | 2 | Gradual ramp-up period (seconds) |

## Pass/Fail Thresholds

- **Error rate** > 5% → FAIL
- **Median response** > 2s → FAIL
