#!/bin/bash
# Deploy Ops Command Center to EC2
# Run: ssh -i ~/.ssh/fynda-api-key.pem ubuntu@54.81.148.134 < deploy_ops.sh

set -e
echo "=== Deploying Ops Command Center ==="

cd ~/FB_APP

# 1. Pull latest code
echo "→ Pulling latest code..."
git pull origin main

# 2. Install new dependency (psutil)
echo "→ Installing psutil..."
source venv/bin/activate 2>/dev/null || true
pip install psutil -q

# 3. Copy ops-dashboard static files to Nginx serve directory
echo "→ Deploying ops dashboard static files..."
sudo mkdir -p /var/www/ops-dashboard
sudo cp -r ops-dashboard/* /var/www/ops-dashboard/
sudo chown -R www-data:www-data /var/www/ops-dashboard/

# 4. Add Nginx location block for /ops/
# Check if already configured
if ! sudo grep -q "ops-dashboard" /etc/nginx/conf.d/*.conf 2>/dev/null && ! sudo grep -q "ops-dashboard" ~/FB_APP/nginx/conf.d/*.conf 2>/dev/null; then
    echo "→ NOTE: Nginx config for /ops/ needs to be added manually"
fi

# 5. Rebuild and restart the API container
echo "→ Rebuilding API container..."
docker compose -f docker-compose.prod.yml build api --no-cache
docker compose -f docker-compose.prod.yml up -d api

# 6. Wait for healthy
echo "→ Waiting for container health..."
sleep 10

# 7. Verify
echo "→ Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10

echo ""
echo "=== Deployment Complete ==="
echo "Dashboard will be served at: https://api.outfi.ai/ops/"
echo "Status API at: https://api.outfi.ai/internal/ops/status/"
