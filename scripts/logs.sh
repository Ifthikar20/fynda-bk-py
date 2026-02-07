#!/bin/bash
# ==============================================================================
# Fynda — Comprehensive Log Monitor
# ==============================================================================
# Usage:
#   ./scripts/logs.sh              # All services (default)
#   ./scripts/logs.sh api          # API only
#   ./scripts/logs.sh ml           # ML service only
#   ./scripts/logs.sh nginx        # Nginx only
#   ./scripts/logs.sh celery       # Celery worker only
#   ./scripts/logs.sh db           # PostgreSQL only
#   ./scripts/logs.sh redis        # Redis only
#   ./scripts/logs.sh errors       # Errors from ALL services
#   ./scripts/logs.sh search       # Live search request tracking
#   ./scripts/logs.sh deploy       # Deployment / startup logs
# ==============================================================================

set -euo pipefail

# --- Config ---
COMPOSE_FILE="docker-compose.local.yml"
PROJECT_DIR="/opt/fynda"
TAIL_LINES=100

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Container names
API="fynda-api"
ML="fynda-ml"
NGINX="fynda-nginx"
CELERY="fynda-celery"
DB="fynda-db"
REDIS="fynda-redis"

# --- Helpers ---
header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  📋 $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

status_check() {
    header "SERVICE STATUS"
    echo -e "  ${WHITE}Container          Status              Ports${NC}"
    echo -e "  ${CYAN}─────────────────  ──────────────────  ─────────────${NC}"

    for container in $API $ML $NGINX $CELERY $DB $REDIS; do
        status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not found")
        uptime=$(docker inspect -f '{{.State.StartedAt}}' "$container" 2>/dev/null | cut -d'T' -f1,2 | cut -d'.' -f1 || echo "-")
        ports=$(docker port "$container" 2>/dev/null | head -1 || echo "-")

        if [ "$status" = "running" ]; then
            color=$GREEN
            icon="✅"
        elif [ "$status" = "not found" ]; then
            color=$RED
            icon="❌"
        else
            color=$YELLOW
            icon="⚠️"
        fi

        printf "  ${icon} ${color}%-18s %-20s %s${NC}\n" "$container" "$status" "$ports"
    done
    echo ""
}

# --- Commands ---
case "${1:-all}" in

    # ---- Individual services ----
    api)
        header "API LOGS ($API)"
        docker logs -f --tail "$TAIL_LINES" "$API" 2>&1
        ;;

    ml)
        header "ML SERVICE LOGS ($ML)"
        docker logs -f --tail "$TAIL_LINES" "$ML" 2>&1
        ;;

    nginx)
        header "NGINX LOGS ($NGINX)"
        docker logs -f --tail "$TAIL_LINES" "$NGINX" 2>&1
        ;;

    celery)
        header "CELERY WORKER LOGS ($CELERY)"
        docker logs -f --tail "$TAIL_LINES" "$CELERY" 2>&1
        ;;

    db)
        header "DATABASE LOGS ($DB)"
        docker logs -f --tail "$TAIL_LINES" "$DB" 2>&1
        ;;

    redis)
        header "REDIS LOGS ($REDIS)"
        docker logs -f --tail "$TAIL_LINES" "$REDIS" 2>&1
        ;;

    # ---- Aggregated views ----
    all)
        status_check
        header "ALL SERVICES — LIVE LOGS (Ctrl+C to stop)"
        echo -e "  ${YELLOW}Tip: Use './scripts/logs.sh api' to filter by service${NC}"
        echo ""
        docker logs -f --tail 30 "$API"    2>&1 | sed "s/^/[${GREEN}API${NC}]    /" &
        docker logs -f --tail 30 "$ML"     2>&1 | sed "s/^/[${MAGENTA}ML${NC}]     /" &
        docker logs -f --tail 10 "$NGINX"  2>&1 | sed "s/^/[${BLUE}NGINX${NC}]  /" &
        docker logs -f --tail 10 "$CELERY" 2>&1 | sed "s/^/[${YELLOW}CELERY${NC}] /" &
        docker logs -f --tail  5 "$REDIS"  2>&1 | sed "s/^/[${RED}REDIS${NC}]  /" &
        docker logs -f --tail  5 "$DB"     2>&1 | sed "s/^/[${CYAN}DB${NC}]     /" &
        wait
        ;;

    errors)
        header "ERRORS ACROSS ALL SERVICES"
        echo -e "  Scanning last 500 lines from each container...\n"
        for container in $API $ML $NGINX $CELERY $DB $REDIS; do
            errors=$(docker logs --tail 500 "$container" 2>&1 | grep -iE "error|exception|traceback|critical|fatal" | tail -10)
            if [ -n "$errors" ]; then
                echo -e "  ${RED}━━━ $container ━━━${NC}"
                echo "$errors" | sed 's/^/    /'
                echo ""
            fi
        done
        echo -e "  ${GREEN}Scan complete.${NC}"
        ;;

    search)
        header "LIVE SEARCH TRACKING"
        echo -e "  ${YELLOW}Filtering API logs for search/upload requests...${NC}\n"
        docker logs -f --tail 10 "$API" 2>&1 | grep --line-buffered -iE "search|upload|amazon|orchestrator|parsed query|fetched|products for"
        ;;

    deploy)
        header "DEPLOYMENT / STARTUP LOGS"
        echo -e "  ${YELLOW}Last 50 lines from each service startup...${NC}\n"
        for container in $API $ML $NGINX $CELERY; do
            echo -e "  ${CYAN}━━━ $container ━━━${NC}"
            docker logs --tail 50 "$container" 2>&1 | head -20 | sed 's/^/    /'
            echo ""
        done
        ;;

    status)
        status_check
        ;;

    health)
        header "HEALTH CHECKS"
        echo -ne "  API:   "
        curl -s -o /dev/null -w "%{http_code}" https://api.fynda.shop/api/health/ 2>/dev/null && echo -e " ${GREEN}OK${NC}" || echo -e " ${RED}FAIL${NC}"
        echo -ne "  Site:  "
        curl -s -o /dev/null -w "%{http_code}" https://fynda.shop/ 2>/dev/null && echo -e " ${GREEN}OK${NC}" || echo -e " ${RED}FAIL${NC}"
        echo ""
        ;;

    *)
        echo ""
        echo -e "${WHITE}Fynda Log Monitor${NC}"
        echo ""
        echo "  Usage: ./scripts/logs.sh [command]"
        echo ""
        echo "  Commands:"
        echo "    all       All services combined (default)"
        echo "    api       Django API logs"
        echo "    ml        ML Service logs"
        echo "    nginx     Nginx reverse proxy logs"
        echo "    celery    Celery worker logs"
        echo "    db        PostgreSQL logs"
        echo "    redis     Redis cache logs"
        echo "    errors    Scan all services for errors"
        echo "    search    Live search request tracking"
        echo "    deploy    Startup / deployment logs"
        echo "    status    Container status overview"
        echo "    health    API & site health checks"
        echo ""
        ;;
esac
