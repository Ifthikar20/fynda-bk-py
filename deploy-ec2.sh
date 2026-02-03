#!/bin/bash
# Fynda API Deployment Script for EC2

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python & dependencies
sudo apt-get install -y python3 python3-pip python3-venv nginx git postgresql postgresql-contrib

# Create app directory
sudo mkdir -p /opt/fynda
sudo chown ubuntu:ubuntu /opt/fynda
cd /opt/fynda

# Clone or upload code (you'll need to upload manually or use git)
# git clone <your-repo-url> .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Setup PostgreSQL
sudo -u postgres psql -c "CREATE DATABASE fynda;"
sudo -u postgres psql -c "CREATE USER fynda_user WITH PASSWORD 'fynda_secure_db_2026';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE fynda TO fynda_user;"

# Run migrations
python manage.py migrate
python manage.py collectstatic --noinput

# Create systemd service
sudo tee /etc/systemd/system/fynda.service > /dev/null <<EOF
[Unit]
Description=Fynda Django API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/fynda
ExecStart=/opt/fynda/venv/bin/gunicorn fynda.wsgi:application --bind 0.0.0.0:8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Setup Nginx
sudo tee /etc/nginx/sites-available/fynda > /dev/null <<EOF
server {
    listen 80;
    server_name api.fynda.shop;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /opt/fynda/static/;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/fynda /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Start Django service
sudo systemctl daemon-reload
sudo systemctl enable fynda
sudo systemctl start fynda

echo "Deployment complete! API running on port 8000"
