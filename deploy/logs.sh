#!/bin/bash
# =============================================================================
# Helper script to view logs
# =============================================================================

cd "$(dirname "$0")/.."

SERVICE=${1:-""}

if [ -z "$SERVICE" ]; then
    echo "Showing logs for all services..."
    docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
else
    echo "Showing logs for $SERVICE..."
    docker compose -f docker-compose.prod.yml --env-file .env.production logs -f "$SERVICE"
fi
