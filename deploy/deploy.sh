#!/bin/bash
# =============================================================================
# Fynda Deployment Script
# Run this for each deployment/update
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_DIR"

echo "=========================================="
echo "Fynda Deployment"
echo "=========================================="
echo "Project directory: $PROJECT_DIR"
echo ""

# =============================================================================
# Pre-flight checks
# =============================================================================
echo -e "${YELLOW}[1/6] Running pre-flight checks...${NC}"

# Check .env.production exists
if [ ! -f .env.production ]; then
    echo -e "${RED}ERROR: .env.production not found!${NC}"
    echo "Copy .env.production.example to .env.production and configure it first."
    exit 1
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-flight checks passed${NC}"

# =============================================================================
# Pull latest code (if git repo)
# =============================================================================
echo -e "${YELLOW}[2/6] Checking for updates...${NC}"

if [ -d .git ]; then
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u})
    
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "Pulling latest changes..."
        git pull origin main
    else
        echo "Already up to date"
    fi
fi

# =============================================================================
# Build containers
# =============================================================================
echo -e "${YELLOW}[3/6] Building containers...${NC}"

docker compose -f "$COMPOSE_FILE" --env-file .env.production build --parallel

# =============================================================================
# Stop existing containers
# =============================================================================
echo -e "${YELLOW}[4/6] Stopping existing containers...${NC}"

docker compose -f "$COMPOSE_FILE" --env-file .env.production down --remove-orphans

# =============================================================================
# Start containers
# =============================================================================
echo -e "${YELLOW}[5/6] Starting containers...${NC}"

docker compose -f "$COMPOSE_FILE" --env-file .env.production up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# =============================================================================
# Run migrations
# =============================================================================
echo -e "${YELLOW}[6/6] Running Django migrations...${NC}"

docker compose -f "$COMPOSE_FILE" --env-file .env.production exec -T api python manage.py migrate --noinput

# Collect static files
docker compose -f "$COMPOSE_FILE" --env-file .env.production exec -T api python manage.py collectstatic --noinput

# =============================================================================
# Health check
# =============================================================================
echo ""
echo "Running health checks..."

# Check container status
echo ""
docker compose -f "$COMPOSE_FILE" ps

# Test API endpoint
echo ""
if curl -s --max-time 5 http://localhost:8000/api/health/ > /dev/null; then
    echo -e "${GREEN}✓ API is responding${NC}"
else
    echo -e "${YELLOW}⚠ API health check failed (may still be starting)${NC}"
fi



# =============================================================================
# Done!
# =============================================================================
echo ""
echo -e "${GREEN}=========================================="
echo "Deployment complete!"
echo "==========================================${NC}"
echo ""
echo "View logs: docker compose -f docker-compose.prod.yml logs -f"
echo "View status: docker compose -f docker-compose.prod.yml ps"
