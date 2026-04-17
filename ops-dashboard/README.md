# Ops Command Center

A standalone, real-time infrastructure monitoring dashboard for Outfi & FetchBot services.

> **This is a completely independent project** — it has zero code dependencies on the Outfi Django backend. Move it anywhere you like.

## What It Monitors

| Component | Source |
|-----------|--------|
| **System Vitals** | CPU, memory, disk usage via server API |
| **Docker Containers** | All 6 containers (API, DB, Redis, Celery, Nginx, Certbot) |
| **Service Health** | Redis, PostgreSQL, Celery worker connectivity & latency |
| **Endpoint Status** | HTTP response codes + latency for outfi.ai & api.outfi.ai |
| **Activity Feed** | Auto-detected status changes (container restart, service down, etc.) |

## Quick Start

### Option A: Open directly
```bash
open index.html
```

### Option B: Use a local server (recommended for CORS)
```bash
npx serve .
# or
python3 -m http.server 5500
```

Then open `http://localhost:5500` in your browser.

### Configure API Endpoint
Click the ⚙️ settings button in the top-right to set your API URL:
```
https://api.outfi.ai/internal/ops/status/
```

## Backend Endpoint

The dashboard polls a single JSON endpoint. The corresponding Django view lives at:
```
FB_APP/core/ops_views.py → /internal/ops/status/
```

This endpoint is NOT part of this project — it lives in the Outfi Django backend and needs to be deployed separately.

## Tech Stack

- **Pure HTML/CSS/JS** — no build step, no dependencies
- **Dark glassmorphism** design with animated ring charts
- **Auto-refresh** every 15 seconds (configurable)
- **Demo mode** when API is unreachable (for development)

## License

Internal tool — not for distribution.
