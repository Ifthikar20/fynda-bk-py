# Outfi Application Architecture

> **Last Updated**: February 5, 2026  
> **Status**: Production

## System Overview

```mermaid
graph TB
    subgraph "Cloudflare CDN"
        CF[Cloudflare Proxy]
    end
    
    subgraph "AWS EC2 Instance"
        subgraph "Docker Compose Stack"
            NGINX[Nginx :80/:443]
            API[Django API :8000]
            ML[ML Service :8001]
            CELERY[Celery Worker]
            REDIS[Redis :6379]
            DB[(PostgreSQL :5432)]
        end
        FRONTEND[/var/www/frontend Vue SPA]
    end
    
    CF --> NGINX
    NGINX --> FRONTEND
    NGINX --> API
    API --> ML
    API --> DB
    API --> REDIS
    CELERY --> REDIS
    CELERY --> DB
```

---

## Domain Architecture

| Domain | Purpose | Handler |
|--------|---------|---------|
| `outfi.ai` | Main Vue SPA + Blog | Nginx → Vue static / Django SSR |
| `api.outfi.ai` | REST API + Admin | Nginx → Django container |
| `blog.outfi.ai` | Redirects to `/blog/` | 301 → `outfi.ai/blog/` |

---

## Components

### 1. Frontend (Vue 3 + Vite)
**Location**: `/var/www/frontend/` on EC2

| Feature | Implementation |
|---------|----------------|
| Text Search | `GET /api/search/?q=<query>` |
| Image Search | `POST /api/upload/` (multipart) |
| Auth | JWT via `/api/auth/` endpoints |
| Storyboard | Canvas-based fashion board |

**Key Files**:
- `src/components/HomePage.vue` - Main search UI
- `src/stores/dealsStore.js` - Search state management
- `.env.production` - API URLs

### 2. Django API
**Container**: `fynda-api` on port 8000

| App | Purpose |
|-----|---------|
| `deals` | Search, image upload, affiliate aggregation |
| `users` | Auth, profiles, JWT tokens |
| `blog` | SSR blog posts for SEO |
| `emails` | Email subscriptions |

**Key Endpoints**:
```
GET  /api/search/?q=<query>     → Text search (affiliates)
POST /api/upload/               → Image → ML → Search
GET  /api/auth/user/            → Current user
POST /api/auth/login/           → JWT login
GET  /blog/<slug>               → SSR blog post
```

### 3. ML Service (Internal)
**Container**: `fynda-ml` on port 8001

> ⚠️ **Internal only** - Not exposed to public

| Endpoint | Purpose |
|----------|---------|
| `/api/extract-attributes` | Caption, colors, textures from image |
| `/api/visual-search` | FAISS similarity search |
| `/health` | Health check |

**Flow**: Frontend → Django `/api/upload/` → ML Service (internal) → Response

### 4. Background Services

| Service | Container | Purpose |
|---------|-----------|---------|
| Celery | `fynda-celery` | Async email, analytics |
| Redis | `fynda-redis` | Cache, message broker |
| PostgreSQL | `fynda-db` | Primary database |

---

## Data Flow

### Text Search
```
User → Search Box → /api/search/?q=jacket
                           ↓
                    Django orchestrator.search()
                           ↓
              ┌────────────┴────────────┐
              ↓            ↓            ↓
           CJ API    Rakuten API   ShareASale
              ↓            ↓            ↓
              └────────────┬────────────┘
                           ↓
                    Merged & Ranked
                           ↓
                    JSON Response
```

### Image Search
```
User → Upload Image → /api/upload/ (FormData)
                            ↓
                     Django ImageUploadView
                            ↓
                     ML Service (internal)
                     - extract-attributes
                     - generate search queries
                            ↓
                     orchestrator.search(query)
                            ↓
                     JSON Response (deals)
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vue 3, Vite, Pinia |
| Backend | Django 5, DRF, Celery |
| ML | FastAPI, EfficientNet, FAISS |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Proxy | Nginx |
| Container | Docker Compose |
| CDN | Cloudflare |
| Hosting | AWS EC2 |

---

## Security

- **Admin**: Only at `api.outfi.ai/admin/` (404 on other domains)
- **CORS**: Configured in Django settings
- **Rate Limiting**: Nginx zone + DRF throttling
- **SSL**: Let's Encrypt + Cloudflare

---

## File Structure
```
FB_APP/
├── frontend/          # Vue 3 SPA
│   ├── src/
│   └── dist/          # Built output
├── deals/             # Search & affiliate APIs
├── users/             # Auth & profiles
├── blog/              # SSR blog
├── emails/            # Email service
├── fynda/             # Django settings
├── FYNDA_ML_Services/ # ML service (separate repo)
├── nginx/             # Nginx config
└── docker-compose.local.yml
```
