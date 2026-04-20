#!/usr/bin/env bash
# =============================================================================
# run-dev.sh — Launch the Outfi backend (Django) and the Outfi iOS Flutter app
#              side by side, streaming every line to a dated log bundle.
#
# Usage:
#   ./run-dev.sh                # run both (default)
#   ./run-dev.sh --backend-only # just the Django stack
#   ./run-dev.sh --flutter-only # just the Flutter app
#   ./run-dev.sh --device DEV_ID# pin Flutter to a specific iOS device/sim
#   ./run-dev.sh --no-migrate   # skip the pre-flight migrate step
#   ./run-dev.sh --fresh        # docker compose down -v first
#
# Environment:
#   FLUTTER_APP_DIR   path to the outfi_flt_app checkout (default: ../outfi_flt_app)
#   BACKEND_PORT      host port the API should bind to (default: 8000)
#   FLUTTER_DEVICE    iOS simulator/device id (default: auto-pick first iOS device)
#   LOG_ROOT          override the log bundle root (default: ./logs/dev)
#
# Output:
#   logs/dev/<timestamp>/
#     backend.log        docker compose up (API + DB + redis + celery + nginx)
#     backend-migrate.log  output of manage.py migrate
#     flutter.log        flutter run output
#     run.log            this script's own trace
# =============================================================================

set -Eeuo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLUTTER_APP_DIR="${FLUTTER_APP_DIR:-${HERE}/../outfi_flt_app}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
LOG_ROOT="${LOG_ROOT:-${HERE}/logs/dev}"
TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="${LOG_ROOT}/${TS}"
BACKEND_LOG="${RUN_DIR}/backend.log"
MIGRATE_LOG="${RUN_DIR}/backend-migrate.log"
FLUTTER_LOG="${RUN_DIR}/flutter.log"
SCRIPT_LOG="${RUN_DIR}/run.log"

COMPOSE_FILE="${HERE}/docker-compose.local.yml"
COMPOSE_PROJECT="outfi-dev"
API_SERVICE="api"
HEALTH_URL="http://localhost:${BACKEND_PORT}/api/health/"

RUN_BACKEND=1
RUN_FLUTTER=1
DO_MIGRATE=1
FRESH=0
FLUTTER_DEVICE="${FLUTTER_DEVICE:-}"

# ── Colors ──────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[0;31m'; C_BLUE=$'\033[0;34m'; C_DIM=$'\033[2m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""; C_DIM=""
fi

ts()   { date +"%H:%M:%S"; }
log()  { printf "%s[+] %s%s %s\n" "$C_GREEN"  "$(ts)" "$C_RESET" "$*" | tee -a "$SCRIPT_LOG"; }
info() { printf "%s[i] %s%s %s\n" "$C_BLUE"   "$(ts)" "$C_RESET" "$*" | tee -a "$SCRIPT_LOG"; }
warn() { printf "%s[!] %s%s %s\n" "$C_YELLOW" "$(ts)" "$C_RESET" "$*" | tee -a "$SCRIPT_LOG"; }
err()  { printf "%s[x] %s%s %s\n" "$C_RED"    "$(ts)" "$C_RESET" "$*" | tee -a "$SCRIPT_LOG" 1>&2; }

# ── Parse flags ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only) RUN_FLUTTER=0 ;;
    --flutter-only) RUN_BACKEND=0 ;;
    --device)       FLUTTER_DEVICE="$2"; shift ;;
    --no-migrate)   DO_MIGRATE=0 ;;
    --fresh)        FRESH=1 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) err "Unknown flag: $1"; exit 2 ;;
  esac
  shift
done

# ── Prep log bundle ─────────────────────────────────────────────────────────
mkdir -p "$RUN_DIR"
: > "$SCRIPT_LOG"
info "Log bundle: ${RUN_DIR}"
info "Backend: ${BACKEND_LOG}"
info "Flutter: ${FLUTTER_LOG}"

# ── Pre-flight ──────────────────────────────────────────────────────────────
preflight() {
  log "Pre-flight checks…"
  if (( RUN_BACKEND )); then
    command -v docker >/dev/null || { err "docker not found in PATH"; exit 1; }
    docker info >/dev/null 2>&1  || { err "Docker daemon not reachable"; exit 1; }
    [[ -f "$COMPOSE_FILE" ]]     || { err "Missing $COMPOSE_FILE"; exit 1; }
    [[ -f "${HERE}/.env" ]]      || warn ".env missing — compose will fall back to defaults"
  fi
  if (( RUN_FLUTTER )); then
    command -v flutter >/dev/null || { err "flutter not in PATH"; exit 1; }
    [[ -d "$FLUTTER_APP_DIR" ]]   || { err "Flutter repo not at ${FLUTTER_APP_DIR} (set FLUTTER_APP_DIR)"; exit 1; }
    [[ -f "${FLUTTER_APP_DIR}/pubspec.yaml" ]] || { err "No pubspec.yaml in ${FLUTTER_APP_DIR}"; exit 1; }
  fi
  log "Pre-flight OK"
}

# ── Backend lifecycle ───────────────────────────────────────────────────────
backend_up() {
  log "Starting backend (compose project=${COMPOSE_PROJECT})…"
  if (( FRESH )); then
    warn "Fresh start requested — wiping volumes"
    docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" down -v 2>&1 | tee -a "$BACKEND_LOG" >/dev/null || true
  fi
  # Build (cached) + bring up detached.
  (
    cd "$HERE"
    docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" up -d --build 2>&1
  ) | tee -a "$BACKEND_LOG"
  # Stream container logs in the background so everything lands in backend.log.
  ( docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" logs -f --no-color \
      >> "$BACKEND_LOG" 2>&1 & echo $! > "${RUN_DIR}/.backend-logs.pid" ) || true
}

backend_wait() {
  log "Waiting for API health (${HEALTH_URL})…"
  local max=60
  for ((i=1; i<=max; i++)); do
    if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
      log "API is healthy"
      return 0
    fi
    if (( i % 5 == 0 )); then info "  still waiting… (${i}s)"; fi
    sleep 1
  done
  err "API did not become healthy in ${max}s — tail of backend.log:"
  tail -n 40 "$BACKEND_LOG" | sed 's/^/  /' || true
  exit 1
}

backend_migrate() {
  (( DO_MIGRATE )) || { warn "Skipping migrate (--no-migrate)"; return; }
  log "Running Django migrations…"
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" \
    exec -T "$API_SERVICE" python manage.py migrate --noinput 2>&1 | tee -a "$MIGRATE_LOG"
}

# ── Flutter lifecycle ───────────────────────────────────────────────────────
flutter_pick_device() {
  if [[ -n "$FLUTTER_DEVICE" ]]; then
    echo "$FLUTTER_DEVICE"; return
  fi
  # Prefer first booted iOS simulator; fall back to the first iOS entry.
  flutter devices --machine 2>/dev/null \
    | python3 -c "
import json, sys
try:
    arr = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ios = [d for d in arr if str(d.get('targetPlatform','')).startswith('ios') or d.get('platform')=='ios']
if not ios: sys.exit(0)
# Booted sim first, else first iOS device
ios.sort(key=lambda d: 0 if 'booted' in str(d.get('emulator','')).lower() or d.get('isSupported') else 1)
print(ios[0].get('id',''))
" 2>/dev/null || true
}

flutter_up() {
  log "Starting Flutter app (iOS)…"
  local dev
  dev="$(flutter_pick_device || true)"
  if [[ -z "$dev" ]]; then
    err "No iOS device / simulator available. Open Simulator.app or plug in a device."
    exit 1
  fi
  info "Using device: ${dev}"
  (
    cd "$FLUTTER_APP_DIR"
    # --verbose prints engine + plugin logs; -d pins the device.
    flutter run --verbose -d "$dev" 2>&1
  ) | tee -a "$FLUTTER_LOG" &
  echo $! > "${RUN_DIR}/.flutter.pid"
}

# ── Shutdown ────────────────────────────────────────────────────────────────
shutdown() {
  local code=${1:-0}
  warn "Shutting down…"
  if [[ -f "${RUN_DIR}/.flutter.pid" ]]; then
    kill "$(cat "${RUN_DIR}/.flutter.pid")" 2>/dev/null || true
    rm -f "${RUN_DIR}/.flutter.pid"
  fi
  if [[ -f "${RUN_DIR}/.backend-logs.pid" ]]; then
    kill "$(cat "${RUN_DIR}/.backend-logs.pid")" 2>/dev/null || true
    rm -f "${RUN_DIR}/.backend-logs.pid"
  fi
  if (( RUN_BACKEND )); then
    info "Stopping compose stack (logs preserved)…"
    docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" down 2>&1 \
      | tee -a "$BACKEND_LOG" >/dev/null || true
  fi
  log "Bundle saved at ${RUN_DIR}"
  exit "$code"
}
trap 'shutdown 130' INT TERM
trap 'err "Error on line $LINENO"; shutdown 1' ERR

# ── Main ────────────────────────────────────────────────────────────────────
preflight

if (( RUN_BACKEND )); then
  backend_up
  backend_wait
  backend_migrate
fi

if (( RUN_FLUTTER )); then
  flutter_up
fi

log "Everything is running."
info "Tail live:  tail -F ${RUN_DIR}/*.log"
info "Press Ctrl+C to stop everything."

# Block until any foreground child exits (flutter) or signal arrives.
if (( RUN_FLUTTER )); then
  wait || true
else
  # Backend-only mode — just sleep until signalled.
  while :; do sleep 3600; done
fi

shutdown 0
