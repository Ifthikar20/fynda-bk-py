# Outfi Deployment Guide

> **Last Updated**: February 5, 2026  
> **Target**: AWS EC2 (Ubuntu) with Docker

---

## Infrastructure Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLOUDFLARE                           │
│  outfi.ai → EC2:80 (Proxied, SSL at Cloudflare)       │
│  api.outfi.ai → EC2:443 (Direct SSL on EC2)           │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    EC2 INSTANCE                         │
│  IP: 54.227.94.35                                       │
│  User: ubuntu                                           │
├─────────────────────────────────────────────────────────┤
│  Docker Compose Services:                               │
│  ├─ nginx (80, 443)                                     │
│  ├─ api (8000) - Django                                 │
│  ├─ ml (8001) - ML Service                              │
│  ├─ celery - Background worker                          │
│  ├─ redis (6379) - Cache                                │
│  └─ db (5432) - PostgreSQL                              │
├─────────────────────────────────────────────────────────┤
│  Static Files:                                          │
│  ├─ /var/www/frontend/ - Vue SPA                        │
│  ├─ /var/www/static/ - Django static                    │
│  └─ /var/www/media/ - Uploaded images                   │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Commands

### SSH Access
```bash
ssh ubuntu@54.227.94.35
```

### Admin Access (SSH Tunnel)
```bash
ssh -L 8888:localhost:8000 ubuntu@54.227.94.35
# Then open: http://localhost:8888/admin/
```

---

## 🚀 CI/CD Deployment (Primary Method)

> **Push to `main` branch triggers automatic deployment via GitHub Actions**

### Backend Deployment
```bash
# Commit and push to fynda-bk-py
git add .
git commit -m "your message"
git push origin main
# → GitHub Actions: test → build → deploy to EC2
```

### Frontend Deployment
```bash
# In frontend directory (separate repo: fynda-frontend-vue)
cd frontend
git add .
git commit -m "your message"  
git push origin main
# → Deploys via S3/CloudFront or needs manual sync to EC2
```

### Monitor Deployment
- GitHub Actions: https://github.com/Ifthikar20/fynda-bk-py/actions
- Check run status, logs, and health check results

---

## Deployment Steps

### 1. Deploy Frontend Only
```bash
# Local: Build frontend
cd /Users/ifthikaraliseyed/FB_APP/frontend
npm run build

# Upload to EC2
scp -r dist/* ubuntu@54.227.94.35:/var/www/frontend/

# SSH to EC2 and reload nginx
ssh ubuntu@54.227.94.35 "sudo nginx -t && sudo systemctl reload nginx"
```

### 2. Deploy Backend (Full Stack)
```bash
# SSH to EC2
ssh ubuntu@54.227.94.35
cd /opt/fynda

# Pull latest code
git pull origin main

# Rebuild and restart containers
docker-compose -f docker-compose.local.yml down
docker-compose -f docker-compose.local.yml up -d --build

# Run migrations
docker exec fynda-api python manage.py migrate

# Collect static files
docker exec fynda-api python manage.py collectstatic --noinput
```

### 3. Deploy Blog Updates
```bash
# SSH to EC2
ssh ubuntu@54.227.94.35
cd /opt/fynda

git pull origin main
docker-compose -f docker-compose.local.yml restart api
docker exec fynda-api python manage.py collectstatic --noinput
```

---

## Docker Services

| Container | Internal Port | Purpose |
|-----------|---------------|---------|
| `fynda-nginx` | 80, 443 | Reverse proxy, SSL |
| `fynda-api` | 8000 | Django REST API |
| `fynda-ml` | 8001 | ML service (internal) |
| `fynda-celery` | - | Background tasks |
| `fynda-redis` | 6379 | Cache & broker |
| `fynda-db` | 5432 | PostgreSQL |

### Service Commands
```bash
# View logs
docker logs -f fynda-api

# Restart specific service
docker-compose -f docker-compose.local.yml restart api

# Shell into container
docker exec -it fynda-api bash
```

---

## Environment Files

### Backend (.env)
```
SECRET_KEY=<django-secret>
DEBUG=False
ALLOWED_HOSTS=outfi.ai,api.outfi.ai
DB_NAME=fynda
DB_USER=fynda
DB_PASSWORD=<password>
OPENAI_API_KEY=<key>
CJ_API_TOKEN=<token>
RAKUTEN_API_TOKEN=<token>
```

### Frontend (.env.production)
```
VITE_API_URL=https://api.outfi.ai
VITE_MIXPANEL_TOKEN=<token>
```

---

## SSL Certificates

### api.outfi.ai (Let's Encrypt)
```bash
# Inside nginx container or certbot
certbot certonly --webroot -w /var/www/certbot \
  -d api.outfi.ai -d blog.outfi.ai
```

### outfi.ai (Cloudflare)
- SSL handled by Cloudflare (Proxied mode)
- EC2 receives HTTP on port 80

---

## Troubleshooting

### Check Service Health
```bash
# API
curl https://api.outfi.ai/api/health/

# All containers
docker ps

# Container logs
docker logs fynda-api --tail 100
```

### Common Issues

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Restart API: `docker-compose restart api` |
| Static files missing | Run `collectstatic` |
| DB connection error | Check PostgreSQL container |
| SSL error on api.* | Renew certbot certificates |

---

## Backup

### Database
```bash
docker exec fynda-db pg_dump -U fynda fynda > backup.sql
```

### Media Files
```bash
tar -czf media-backup.tar.gz /var/www/media/
```
