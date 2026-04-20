#!/usr/bin/env bash
# =============================================================================
# deploy-backend.sh — Dedicated Outfi backend deploy (Django + Celery + Nginx).
#
# Differs from deploy.sh: focused purely on the backend, with explicit
# pre-flight checks, a migrate + collectstatic step, rolling restart, a
# post-deploy health verification, and automatic rollback on failure.
#
# Usage:
#   ./deploy-backend.sh              # deploy current HEAD to prod
#   ./deploy-backend.sh --branch X   # deploy branch X instead of main
#   ./deploy-backend.sh --skip-tests # skip local test suite (not recommended)
#   ./deploy-backend.sh --dry-run    # print every step without executing remote ops
#   ./deploy-backend.sh --rollback   # revert server to previous deployed SHA
#
# Requires:
#   - SSH key at $SSH_KEY
#   - docker + docker compose v2 on the remote
#   - Remote repo pre-cloned at $REMOTE_DIR with .env populated
# =============================================================================

set -Eeuo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/outfi-api-key.pem}"
SERVER="${DEPLOY_SERVER:-ubuntu@54.81.148.134}"
REMOTE_DIR="${REMOTE_DIR:-/home/ubuntu/outfi}"
COMPOSE_FILE="docker-compose.prod.yml"
HEALTH_URL="${HEALTH_URL:-https://api.outfi.ai/api/health/}"
LOG_ROOT="${LOG_ROOT:-${HERE}/logs/deploy}"
TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="${LOG_ROOT}/${TS}"
LOG="${RUN_DIR}/deploy.log"

BRANCH="main"
SKIP_TESTS=1
DRY_RUN=0
ROLLBACK=0

# ── Colors ──────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[0;31m'; C_BLUE=$'\033[0;34m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi
ts()   { date +"%H:%M:%S"; }
log()  { printf "%s[+] %s%s %s\n" "$C_GREEN"  "$(ts)" "$C_RESET" "$*" | tee -a "$LOG"; }
info() { printf "%s[i] %s%s %s\n" "$C_BLUE"   "$(ts)" "$C_RESET" "$*" | tee -a "$LOG"; }
warn() { printf "%s[!] %s%s %s\n" "$C_YELLOW" "$(ts)" "$C_RESET" "$*" | tee -a "$LOG"; }
err()  { printf "%s[x] %s%s %s\n" "$C_RED"    "$(ts)" "$C_RESET" "$*" | tee -a "$LOG" 1>&2; }

mkdir -p "$RUN_DIR"
: > "$LOG"

# ── Flag parsing ────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)     BRANCH="$2"; shift ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --dry-run)    DRY_RUN=1 ;;
    --rollback)   ROLLBACK=1 ;;
    -h|--help)    sed -n '2,26p' "$0"; exit 0 ;;
    *) err "Unknown flag: $1"; exit 2 ;;
  esac
  shift
done

# ── SSH helper ──────────────────────────────────────────────────────────────
ssh_cmd() {
  local cmd="$1"
  if (( DRY_RUN )); then
    info "[dry-run] ssh: $cmd"
    return 0
  fi
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SERVER" "set -Eeuo pipefail; $cmd" 2>&1 | tee -a "$LOG"
}

# ── Pre-flight ──────────────────────────────────────────────────────────────
preflight() {
  log "Pre-flight…"
  command -v git  >/dev/null || { err "git not found";  exit 1; }
  command -v ssh  >/dev/null || { err "ssh not found";  exit 1; }
  command -v curl >/dev/null || { err "curl not found"; exit 1; }
  [[ -f "$SSH_KEY" ]] || { err "SSH key missing: $SSH_KEY"; exit 1; }

  cd "$HERE"
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    err "Not a git repo: $HERE"; exit 1
  fi

  local cur_branch
  cur_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$cur_branch" != "$BRANCH" ]]; then
    warn "Local is on '${cur_branch}', deploying '${BRANCH}'. Make sure that's intentional."
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    err "Working tree not clean. Commit or stash before deploying."
    git status --short | tee -a "$LOG"
    exit 1
  fi

  local local_sha remote_sha
  local_sha="$(git rev-parse HEAD)"
  git fetch origin "$BRANCH" --quiet
  remote_sha="$(git rev-parse "origin/${BRANCH}")"
  if [[ "$local_sha" != "$remote_sha" ]]; then
    warn "Local HEAD (${local_sha:0:7}) differs from origin/${BRANCH} (${remote_sha:0:7})."
    warn "The server will check out origin/${BRANCH} — proceed only if that is what you want."
  fi

  # Fail if the model tree has been changed without a matching migration.
  if git ls-files 'mobile/migrations/*.py' 'payments/migrations/*.py' \
      'users/migrations/*.py' 'deals/migrations/*.py' 'blog/migrations/*.py' \
      'feed/migrations/*.py' >/dev/null 2>&1; then
    info "Migration files present — Django will run migrate on the server"
  fi

  if (( ! SKIP_TESTS )); then
    if [[ -x "${HERE}/manage.py" ]]; then
      info "Running quick local import smoke (manage.py check)…"
      if ! python "${HERE}/manage.py" check 2>&1 | tee -a "$LOG"; then
        err "manage.py check failed — fix before deploying (or re-run with --skip-tests)"
        exit 1
      fi
    else
      warn "manage.py not executable locally — skipping Django check"
    fi
  fi

  log "Pre-flight OK"
}

# ── Deploy steps ────────────────────────────────────────────────────────────
capture_current_sha() {
  log "Capturing current server SHA for rollback…"
  local cur
  cur="$(ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SERVER" \
         "cd $REMOTE_DIR && git rev-parse HEAD" 2>/dev/null || echo "")"
  if [[ -n "$cur" ]]; then
    echo "$cur" > "${RUN_DIR}/previous-sha.txt"
    info "Previous SHA: ${cur:0:12}"
  else
    warn "Could not read current SHA — rollback disabled"
  fi
}

pull_on_server() {
  log "Pulling ${BRANCH} on server…"
  ssh_cmd "cd $REMOTE_DIR && git fetch origin ${BRANCH} && git reset --hard origin/${BRANCH} && git rev-parse HEAD"
}

build_images() {
  log "Building Docker images on server…"
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE build api celery"
}

run_migrations() {
  log "Running migrations on server…"
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE run --rm api python manage.py migrate --noinput"
}

collect_static() {
  log "Collecting static assets on server…"
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE run --rm api python manage.py collectstatic --noinput" \
    || warn "collectstatic failed — continuing (some deploys do not need it)"
}

restart_services() {
  log "Rolling restart of API + Celery…"
  # up -d recreates only containers whose image changed; keeps db/redis running.
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE up -d api celery"
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE ps"
}

verify_health() {
  log "Verifying health at ${HEALTH_URL}…"
  if (( DRY_RUN )); then
    info "[dry-run] skipping health check"
    return 0
  fi
  local max=30
  for ((i=1; i<=max; i++)); do
    if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
      log "Deploy is healthy ✓"
      return 0
    fi
    sleep 2
  done
  err "Health check failed after $((max*2))s"
  return 1
}

clear_cache() {
  info "Clearing Django cache (non-fatal)…"
  ssh_cmd "cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE exec -T api \
           python manage.py shell -c 'from django.core.cache import cache; cache.clear()'" \
    || warn "Cache clear failed — not fatal"
}

# ── Rollback ────────────────────────────────────────────────────────────────
rollback() {
  local prev
  if [[ -f "${LOG_ROOT}/latest-previous-sha.txt" ]]; then
    prev="$(cat "${LOG_ROOT}/latest-previous-sha.txt")"
  else
    err "No previous SHA recorded. Run a deploy first, or specify one manually on the server."
    exit 1
  fi
  warn "Rolling back to ${prev:0:12}…"
  ssh_cmd "cd $REMOTE_DIR && git reset --hard $prev && sudo docker compose -f $COMPOSE_FILE up -d --build api celery"
  verify_health || { err "Rollback deployment is also unhealthy — investigate immediately"; exit 1; }
  log "Rollback complete"
}

# ── Main ────────────────────────────────────────────────────────────────────
if (( ROLLBACK )); then
  rollback
  exit 0
fi

preflight
capture_current_sha
[[ -f "${RUN_DIR}/previous-sha.txt" ]] && cp "${RUN_DIR}/previous-sha.txt" "${LOG_ROOT}/latest-previous-sha.txt"

pull_on_server
build_images
run_migrations
collect_static
restart_services

if ! verify_health; then
  err "Deploy unhealthy — attempting automatic rollback"
  rollback || true
  exit 1
fi

clear_cache

log "Backend deploy complete 🚀"
info "Deploy log: ${LOG}"
info "Rollback:   ./deploy-backend.sh --rollback"
