#!/bin/bash
# ==============================================================================
# Outfi — Comprehensive Log Monitor
# ==============================================================================
# Usage (run from your Mac — SSHs into EC2 automatically):
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
#   ./scripts/logs.sh status       # Container status overview
#   ./scripts/logs.sh health       # API & site health checks
# ==============================================================================

set -euo pipefail

# --- Remote Config ---
EC2_HOST="ubuntu@54.81.148.134"
SSH_KEY="$HOME/.ssh/fynda-api-key.pem"
PROJECT_DIR="/home/ubuntu/fynda"
COMPOSE_FILE="docker-compose.prod.yml"
TAIL_LINES=100

# Container names
API="fynda-api"
ML="fynda-ml"
NGINX="fynda-nginx"
CELERY="fynda-celery"
DB="fynda-db"
REDIS="fynda-redis"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# --- Helpers ---
ssh_cmd() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$EC2_HOST" "$@"
}

header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  📋 $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# --- Commands ---
case "${1:-all}" in

    api)
        header "API LOGS ($API)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $API"
        ;;

    ml)
        header "ML SERVICE LOGS ($ML)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $ML"
        ;;

    nginx)
        header "NGINX LOGS ($NGINX)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $NGINX"
        ;;

    celery)
        header "CELERY WORKER LOGS ($CELERY)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $CELERY"
        ;;

    db)
        header "DATABASE LOGS ($DB)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $DB"
        ;;

    redis)
        header "REDIS LOGS ($REDIS)"
        ssh_cmd "docker logs -f --tail $TAIL_LINES $REDIS"
        ;;

    all)
        header "ALL SERVICES — LIVE LOGS (Ctrl+C to stop)"
        echo -e "  ${YELLOW}Tip: Use './scripts/logs.sh api' to filter by service${NC}"
        echo ""
        ssh_cmd "docker logs -f --tail 30 $API"    2>&1 | sed "s/^/[API]    /" &
        ssh_cmd "docker logs -f --tail 10 $NGINX"  2>&1 | sed "s/^/[NGINX]  /" &
        ssh_cmd "docker logs -f --tail 10 $CELERY" 2>&1 | sed "s/^/[CELERY] /" &
        ssh_cmd "docker logs -f --tail  5 $ML"     2>&1 | sed "s/^/[ML]     /" &
        ssh_cmd "docker logs -f --tail  5 $REDIS"  2>&1 | sed "s/^/[REDIS]  /" &
        ssh_cmd "docker logs -f --tail  5 $DB"     2>&1 | sed "s/^/[DB]     /" &

        trap "kill 0" INT TERM
        wait
        ;;

    errors)
        header "ERRORS ACROSS ALL SERVICES"
        echo -e "  Scanning last 500 lines from each container...\n"
        for container in $API $ML $NGINX $CELERY $DB $REDIS; do
            errors=$(ssh_cmd "docker logs --tail 500 $container 2>&1" | grep -iE "error|exception|traceback|critical|fatal" | tail -10)
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
        echo -e "  ${YELLOW}Filtering API logs for search/Amazon requests...${NC}\n"
        ssh_cmd "docker logs -f --tail 10 $API 2>&1" | grep --line-buffered -iE "search|amazon|orchestrator|parsed query|fetched|products for"
        ;;

    deploy)
        header "DEPLOYMENT / STARTUP LOGS"
        echo -e "  ${YELLOW}Last 50 lines from each service startup...${NC}\n"
        for container in $API $ML $NGINX $CELERY; do
            echo -e "  ${CYAN}━━━ $container ━━━${NC}"
            ssh_cmd "docker logs --tail 50 $container 2>&1" | head -20 | sed 's/^/    /'
            echo ""
        done
        ;;

    status)
        header "SERVICE STATUS"
        ssh_cmd "cd $PROJECT_DIR && docker compose -f $COMPOSE_FILE ps --format 'table {{.Name}}\t{{.Status}}'"
        ;;

    health)
        header "HEALTH CHECKS"
        echo -ne "  API:   "
        code=$(curl -s -o /dev/null -w "%{http_code}" "https://api.outfi.ai/api/health/" 2>/dev/null)
        [ "$code" = "200" ] && echo -e "${GREEN}$code OK${NC}" || echo -e "${RED}$code FAIL${NC}"
        echo -ne "  Site:  "
        code=$(curl -s -o /dev/null -w "%{http_code}" "https://outfi.ai/" 2>/dev/null)
        [ "$code" = "200" ] && echo -e "${GREEN}$code OK${NC}" || echo -e "${RED}$code FAIL${NC}"
        echo ""
        ;;

    *)
        echo ""
        echo -e "${WHITE}Outfi Log Monitor${NC} (runs via SSH to EC2)"
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
