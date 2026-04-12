#!/bin/bash
# =============================================================================
# Outfi Deployment Script
# Usage:
#   ./deploy.sh frontend    — Build & deploy frontend only
#   ./deploy.sh backend     — Build & deploy backend (API + Celery)
#   ./deploy.sh all         — Deploy everything
#   ./deploy.sh clear-cache — Clear server-side cache & rate limits
# =============================================================================

set -e

SSH_KEY="$HOME/.ssh/outfi-api-key.pem"
SERVER="ubuntu@54.81.148.134"
REMOTE_DIR="/home/ubuntu/outfi"
FRONTEND_DIR="$HOME/FB_APP/frontend"
DEPLOY_DIR="/var/www/frontend"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

ssh_cmd() {
    ssh -i "$SSH_KEY" "$SERVER" "$1"
}

# ─── Frontend Deploy ───────────────────────────────────────────────────
deploy_frontend() {
    log "Building frontend..."
    cd "$FRONTEND_DIR"
    npm run build

    local ANALYTICS_HASH
    ANALYTICS_HASH=$(ls dist/assets/AnalyticsPage-*.js 2>/dev/null | head -1)
    log "Built: $(basename "$ANALYTICS_HASH")"

    log "Uploading to server..."
    ssh_cmd "rm -rf /tmp/frontend-deploy && mkdir -p /tmp/frontend-deploy"
    scp -i "$SSH_KEY" -r dist/* "$SERVER:/tmp/frontend-deploy/"

    log "Deploying files..."
    ssh_cmd "sudo rm -rf ${DEPLOY_DIR}/* && \
             sudo cp -r /tmp/frontend-deploy/* ${DEPLOY_DIR}/ && \
             sudo chown -R www-data:www-data ${DEPLOY_DIR}/"

    # Verify
    local SERVER_HASH
    SERVER_HASH=$(ssh_cmd "ls ${DEPLOY_DIR}/assets/AnalyticsPage-*.js 2>/dev/null")
    log "Server has: $(basename "$SERVER_HASH")"

    log "Restarting nginx..."
    ssh_cmd "cd ${REMOTE_DIR} && sudo docker compose -f docker-compose.prod.yml restart nginx"

    log "Frontend deployed! 🚀"
}

# ─── Backend Deploy ────────────────────────────────────────────────────
deploy_backend() {
    log "Pushing to GitHub..."
    cd "$HOME/FB_APP"
    git add -A
    git commit -m "deploy: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || warn "Nothing to commit"
    git push origin main

    log "Pulling on server & building..."
    ssh_cmd "cd ${REMOTE_DIR} && \
             git pull origin main && \
             sudo docker compose -f docker-compose.prod.yml build api && \
             sudo docker compose -f docker-compose.prod.yml up -d api celery"

    log "Backend deployed! 🚀"
}

# ─── Clear Cache ───────────────────────────────────────────────────────
clear_cache() {
    log "Clearing server cache & rate limits..."
    ssh_cmd "cd ${REMOTE_DIR} && \
             sudo docker compose -f docker-compose.prod.yml exec -T api \
             python manage.py shell -c 'from django.core.cache import cache; cache.clear(); print(\"Cache cleared\")'"
    log "Cache cleared! 🧹"
}

# ─── Main ──────────────────────────────────────────────────────────────
case "${1:-all}" in
    frontend|fe|f)
        deploy_frontend
        ;;
    backend|be|b)
        deploy_backend
        ;;
    all|a)
        deploy_backend
        deploy_frontend
        clear_cache
        ;;
    clear-cache|cc)
        clear_cache
        ;;
    *)
        echo "Usage: ./deploy.sh [frontend|backend|all|clear-cache]"
        exit 1
        ;;
esac
