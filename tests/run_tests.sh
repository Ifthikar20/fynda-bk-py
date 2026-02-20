#!/bin/bash
# ──────────────────────────────────────────────────
#  Fynda API Test Runner
# ──────────────────────────────────────────────────
#
#  Usage:
#    ./tests/run_tests.sh                    # all tests against localhost
#    ./tests/run_tests.sh payloads           # payload tests only
#    ./tests/run_tests.sh load               # load test only
#    ./tests/run_tests.sh brands             # brands stress test only
#
#  Environment:
#    TEST_BASE_URL=https://staging.fynda.shop  — target server
#    TEST_USER_EMAIL=test@example.com           — for auth tests
#    TEST_USER_PASSWORD=secret                  — for auth tests
#
# ──────────────────────────────────────────────────

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
SUITE="${1:-all}"

echo "╔══════════════════════════════════════════╗"
echo "║       Fynda API Test Suite               ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Target: ${TEST_BASE_URL:-http://localhost:8000}"
echo "║  Suite:  $SUITE"
echo "╚══════════════════════════════════════════╝"
echo ""

EXIT_CODE=0

run_test() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Running: $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    python3 "$DIR/$2" "${@:3}" || EXIT_CODE=1
    echo ""
}

case "$SUITE" in
    payloads)
        run_test "Payload Tests" test_payloads.py
        ;;
    load)
        run_test "Load Test" test_loadtest.py --users 20 --duration 15
        ;;
    brands)
        run_test "Brands Stress Test" test_brands_stress.py
        ;;
    all)
        run_test "Payload Tests" test_payloads.py
        run_test "Load Test (light)" test_loadtest.py --users 10 --duration 10
        run_test "Brands Stress Test" test_brands_stress.py --users 10 --rounds 15
        ;;
    heavy)
        run_test "Payload Tests" test_payloads.py
        run_test "Load Test (heavy)" test_loadtest.py --users 50 --duration 30
        run_test "Brands Stress Test" test_brands_stress.py --users 30 --rounds 50
        ;;
    *)
        echo "Unknown suite: $SUITE"
        echo "Available: payloads | load | brands | all | heavy"
        exit 1
        ;;
esac

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "🎉 All test suites passed!"
else
    echo "💥 Some tests failed — see output above"
fi

exit $EXIT_CODE
