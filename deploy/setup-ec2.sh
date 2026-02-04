#!/bin/bash
# =============================================================================
# Fynda EC2 Setup Script
# Run this ONCE on a fresh Ubuntu EC2 instance
# =============================================================================

set -e

echo "=========================================="
echo "Fynda Production Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

# =============================================================================
# 1. System Updates
# =============================================================================
echo -e "${YELLOW}[1/6] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# =============================================================================
# 2. Install Docker
# =============================================================================
echo -e "${YELLOW}[2/6] Installing Docker...${NC}"

# Remove old versions
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install prerequisites
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group
usermod -aG docker ubuntu

echo -e "${GREEN}Docker installed: $(docker --version)${NC}"

# =============================================================================
# 3. Create directories
# =============================================================================
echo -e "${YELLOW}[3/6] Creating directories...${NC}"

mkdir -p /opt/fynda
mkdir -p /var/log/fynda
chown -R ubuntu:ubuntu /opt/fynda
chown -R ubuntu:ubuntu /var/log/fynda

# =============================================================================
# 4. Configure firewall
# =============================================================================
echo -e "${YELLOW}[4/6] Configuring firewall...${NC}"

ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable

echo -e "${GREEN}Firewall configured${NC}"

# =============================================================================
# 5. Install additional tools
# =============================================================================
echo -e "${YELLOW}[5/6] Installing additional tools...${NC}"

apt-get install -y \
    htop \
    git \
    vim \
    fail2ban

# Configure fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# =============================================================================
# 6. Configure swap (for t2.micro with limited RAM)
# =============================================================================
echo -e "${YELLOW}[6/6] Configuring swap space...${NC}"

# Check if swap exists
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    echo -e "${GREEN}2GB swap created${NC}"
else
    echo "Swap already exists"
fi

# =============================================================================
# Done!
# =============================================================================
echo ""
echo -e "${GREEN}=========================================="
echo "Setup complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Clone your repository to /opt/fynda"
echo "2. Copy .env.production.example to .env.production and configure"
echo "3. Run: cd /opt/fynda && bash deploy/deploy.sh"
echo ""
echo "NOTE: Log out and back in for docker permissions to take effect"
