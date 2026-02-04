#!/bin/bash
# =============================================================================
# SSL Certificate Setup Script
# Run this AFTER DNS is pointing to your EC2 instance
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_DIR"

# Your domains (update these)
DOMAINS=("api.fynda.shop" "blog.fynda.shop")
EMAIL="admin@fynda.shop"  # Update with your email

echo "=========================================="
echo "SSL Certificate Setup"
echo "=========================================="

# Check if certificates already exist
for domain in "${DOMAINS[@]}"; do
    if [ -d "/etc/letsencrypt/live/$domain" ]; then
        echo -e "${YELLOW}Certificate for $domain already exists${NC}"
    fi
done

# =============================================================================
# Method 1: Using standalone mode (stop nginx first)
# =============================================================================
echo ""
echo -e "${YELLOW}Stopping nginx temporarily for certificate generation...${NC}"

docker compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true

# Generate certificates
for domain in "${DOMAINS[@]}"; do
    echo ""
    echo -e "${YELLOW}Generating certificate for $domain...${NC}"
    
    docker run --rm \
        -v "$(docker volume inspect fynda_certbot_conf --format '{{ .Mountpoint }}')":/etc/letsencrypt \
        -v "$(docker volume inspect fynda_certbot_www --format '{{ .Mountpoint }}')":/var/www/certbot \
        -p 80:80 \
        certbot/certbot certonly \
        --standalone \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$domain" \
        || echo -e "${RED}Failed to generate cert for $domain${NC}"
done

# Restart nginx
echo ""
echo -e "${YELLOW}Restarting nginx...${NC}"
docker compose -f docker-compose.prod.yml up -d nginx

echo ""
echo -e "${GREEN}=========================================="
echo "SSL Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Certificates will auto-renew via the certbot container."
echo "Test your sites at:"
for domain in "${DOMAINS[@]}"; do
    echo "  https://$domain"
done
