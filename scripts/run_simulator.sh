#!/bin/bash
# ─── Outfi App — Run on iPhone Simulator ───
#
# Usage: ./scripts/run_simulator.sh [device_name]
#
# Examples:
#   ./scripts/run_simulator.sh                    # Default: iPhone 15 Pro Max
#   ./scripts/run_simulator.sh "iPhone 15 Pro"
#   ./scripts/run_simulator.sh "iPhone 15"
#
# This script:
#   1. Boots the simulator if not running
#   2. Switches API to localhost (simulator can reach localhost)
#   3. Starts the local Django server
#   4. Builds and runs the Flutter app with full logs

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

DEVICE_NAME="${1:-iPhone 15 Pro Max}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLUTTER_DIR="$PROJECT_DIR/Flutter_outfi_app"

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Outfi App — Simulator Runner${NC}"
echo -e "${GREEN}  Device: $DEVICE_NAME${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Find simulator UUID
SIM_ID=$(xcrun simctl list devices available | grep "$DEVICE_NAME" | head -1 | grep -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}')

if [ -z "$SIM_ID" ]; then
    echo -e "${RED}Simulator '$DEVICE_NAME' not found. Available:${NC}"
    xcrun simctl list devices available | grep -i iphone
    exit 1
fi

echo -e "${CYAN}Simulator ID: $SIM_ID${NC}"

# Boot simulator if not running
SIM_STATE=$(xcrun simctl list devices | grep "$SIM_ID" | grep -o "(Booted)\|(Shutdown)")
if echo "$SIM_STATE" | grep -q "Shutdown"; then
    echo -e "${YELLOW}Booting simulator...${NC}"
    xcrun simctl boot "$SIM_ID"
    open -a Simulator
    sleep 3
else
    echo -e "${GREEN}Simulator already running${NC}"
fi

# Switch API config to localhost for simulator
CONFIG_FILE="$FLUTTER_DIR/lib/config/api_config.dart"
echo -e "${YELLOW}Switching API to localhost for simulator...${NC}"

# Simulator can reach localhost directly (unlike real devices)
cd "$FLUTTER_DIR"

# Start local Django server in background
echo -e "${YELLOW}Starting local Django server...${NC}"
cd "$PROJECT_DIR"
source venv/bin/activate 2>/dev/null

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1

python manage.py runserver 0.0.0.0:8000 2>&1 | while IFS= read -r line; do
    echo -e "${CYAN}[SERVER] $line${NC}"
done &
SERVER_PID=$!
sleep 3

# Verify server is running
if curl -sf http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}Django server running on localhost:8000${NC}"
else
    echo -e "${RED}Django server failed to start${NC}"
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping server (PID $SERVER_PID)...${NC}"
    kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# Run Flutter on simulator
echo ""
echo -e "${GREEN}Building and launching app on simulator...${NC}"
echo ""
cd "$FLUTTER_DIR"
flutter run -d "$SIM_ID"

cleanup
