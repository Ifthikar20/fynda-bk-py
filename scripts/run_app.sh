#!/bin/bash
# ─── Outfi App — Run with Full Logs ───
#
# Usage: ./scripts/run_app.sh
#
# Builds, installs, and runs the Flutter app on your iPhone
# with full detailed API logs streaming in this terminal.
#
# Also tails the EC2 server logs in a background process.
#
# Ctrl+C to stop everything.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Outfi App — Full Debug Runner${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Find device
DEVICE=$(flutter devices 2>/dev/null | grep -o '[0-9a-f]\{8\}-[0-9a-f]\{16\}' | head -1)
if [ -z "$DEVICE" ]; then
    echo -e "${YELLOW}No wired device found, checking wireless...${NC}"
    DEVICE=$(flutter devices 2>/dev/null | grep -oE '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}' | head -1)
fi

if [ -z "$DEVICE" ]; then
    echo -e "${RED}No device found. Connect your iPhone and try again.${NC}"
    exit 1
fi

echo -e "${CYAN}Device: $DEVICE${NC}"
echo ""

# Start EC2 server logs in background (optional)
EC2_KEY="$HOME/.ssh/outfi-api-key.pem"
EC2_HOST="ubuntu@54.81.148.134"
if [ -f "$EC2_KEY" ]; then
    echo -e "${YELLOW}Starting EC2 server logs in background...${NC}"
    ssh -i "$EC2_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$EC2_HOST" \
        "docker logs -f outfi-api --tail 5 2>&1" 2>/dev/null | while IFS= read -r line; do
        echo -e "${CYAN}[SERVER] $line${NC}"
    done &
    SERVER_PID=$!
    echo -e "${GREEN}Server logs PID: $SERVER_PID${NC}"
    echo ""
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping...${NC}"
    [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# Run Flutter app
echo -e "${GREEN}Building and launching app...${NC}"
echo ""
# Source .env for secrets
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [[ -f "$ENV_FILE" ]]; then
  echo -e "${GREEN}Sourcing secrets from .env${NC}"
  set -a
  source "$ENV_FILE"
  set +a
else
  echo -e "${YELLOW}No .env found — using shell env / defaults${NC}"
fi

# Dart-define secrets (override with env vars)
OUTFI_API_KEY="${OUTFI_MOBILE_API_KEY:-}"
if [[ -z "$OUTFI_API_KEY" ]]; then
  echo -e "${YELLOW}Warning: OUTFI_MOBILE_API_KEY not set — mobile API auth will fail${NC}"
fi
STRIPE_KEY="${STRIPE_PUBLISHABLE_KEY:-pk_test_placeholder}"
STRIPE_MERCHANT="${STRIPE_MERCHANT_ID:-merchant.ai.outfi.app}"
GOOGLE_ID="${GOOGLE_CLIENT_ID:-placeholder}"
# Detect test vs live mode for Google Pay
STRIPE_TEST_MODE="false"
[[ "$STRIPE_KEY" == pk_test_* ]] && STRIPE_TEST_MODE="true"

DART_DEFINES=(
  --dart-define=OUTFI_MOBILE_API_KEY="$OUTFI_API_KEY"
  --dart-define=STRIPE_PUBLISHABLE_KEY="$STRIPE_KEY"
  --dart-define=STRIPE_MERCHANT_ID="$STRIPE_MERCHANT"
  --dart-define=STRIPE_TEST_MODE="$STRIPE_TEST_MODE"
  --dart-define=GOOGLE_CLIENT_ID="$GOOGLE_ID"
)

cd "$(dirname "$0")/../Flutter_outfi_app"
flutter run "${DART_DEFINES[@]}" -d "$DEVICE"


cleanup
