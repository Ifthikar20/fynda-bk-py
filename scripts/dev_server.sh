#!/bin/bash
# ─── Outfi Dev Server — Detailed Live Logs ───
#
# Usage: ./scripts/dev_server.sh
#
# Shows ALL request/response details, SQL queries, errors, and image search pipeline.
# Ctrl+C to stop.

cd "$(dirname "$0")/.."

# Activate venv
source venv/bin/activate

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Outfi Dev Server — Verbose Logging${NC}"
echo -e "${GREEN}  API: http://0.0.0.0:8000${NC}"
echo -e "${GREEN}  LAN: http://$(ipconfig getifaddr en0 2>/dev/null || echo 'unknown'):8000${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Run with verbose logging
DJANGO_LOG_LEVEL=DEBUG \
PYTHONUNBUFFERED=1 \
python manage.py runserver 0.0.0.0:8000 --verbosity 2 2>&1 | while IFS= read -r line; do
  # Color code by log level
  if echo "$line" | grep -qiE "error|exception|traceback|fail"; then
    echo -e "${RED}$line${NC}"
  elif echo "$line" | grep -qiE "warning|warn|quota"; then
    echo -e "${YELLOW}$line${NC}"
  elif echo "$line" | grep -qiE "POST|PUT|PATCH|DELETE"; then
    echo -e "${CYAN}$line${NC}"
  else
    echo "$line"
  fi
done
