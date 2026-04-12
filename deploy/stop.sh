#!/bin/bash
# =============================================================================
# Helper script to stop all services
# =============================================================================

cd "$(dirname "$0")/.."

echo "Stopping all Outfi services..."
docker compose -f docker-compose.prod.yml --env-file .env.production down

echo "Done!"
