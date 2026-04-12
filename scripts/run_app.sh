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
cd "$(dirname "$0")/../Flutter_outfi_app"
flutter run -d "$DEVICE"

cleanup
