"""
Ops Command Center — Backend Status API

Provides a unified health-check endpoint that aggregates:
- System vitals (CPU, memory, disk)
- Docker container statuses
- Service connectivity (Redis, Postgres, Celery)
- External endpoint monitoring

Protected by staff authentication.
"""

import json
import time
import subprocess
import logging
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run_cmd(cmd, timeout=5):
    """Run a shell command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _get_system_vitals():
    """Collect CPU, memory, disk stats via /proc and df."""
    vitals = {
        "hostname": _run_cmd("hostname") or "unknown",
        "uptime": _run_cmd("uptime -p") or "unknown",
        "cpu_percent": 0,
        "memory": {"total_mb": 0, "used_mb": 0, "percent": 0},
        "disk": {"total_gb": 0, "used_gb": 0, "percent": 0},
    }

    # CPU usage — 1-second sample via /proc/stat
    try:
        raw = _run_cmd(
            "grep 'cpu ' /proc/stat && sleep 1 && grep 'cpu ' /proc/stat",
            timeout=3,
        )
        if raw:
            lines = raw.strip().split("\n")
            if len(lines) == 2:
                v1 = list(map(int, lines[0].split()[1:]))
                v2 = list(map(int, lines[1].split()[1:]))
                idle1, idle2 = v1[3], v2[3]
                total1, total2 = sum(v1), sum(v2)
                cpu = (1 - (idle2 - idle1) / max(total2 - total1, 1)) * 100
                vitals["cpu_percent"] = round(cpu, 1)
    except Exception:
        pass

    # Memory via /proc/meminfo
    try:
        mem_raw = _run_cmd("cat /proc/meminfo")
        if mem_raw:
            mem = {}
            for line in mem_raw.split("\n"):
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])  # kB
                    mem[key] = val
            total = mem.get("MemTotal", 0) / 1024
            available = mem.get("MemAvailable", 0) / 1024
            used = total - available
            vitals["memory"] = {
                "total_mb": round(total),
                "used_mb": round(used),
                "percent": round(used / max(total, 1) * 100, 1),
            }
    except Exception:
        pass

    # Disk via df
    try:
        df_raw = _run_cmd("df -BG / | tail -1")
        if df_raw:
            parts = df_raw.split()
            vitals["disk"] = {
                "total_gb": int(parts[1].rstrip("G")),
                "used_gb": int(parts[2].rstrip("G")),
                "percent": int(parts[4].rstrip("%")),
            }
    except Exception:
        pass

    return vitals


def _get_container_statuses():
    """Get Docker container status via docker ps."""
    containers = []
    raw = _run_cmd(
        'docker ps -a --format \'{"name":"{{.Names}}","status":"{{.Status}}",'
        '"image":"{{.Image}}","ports":"{{.Ports}}","state":"{{.State}}"}\''
    )
    if not raw:
        return containers

    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        try:
            c = json.loads(line)
            # Parse health from status string
            health = "unknown"
            if "(healthy)" in c.get("status", ""):
                health = "healthy"
            elif "(unhealthy)" in c.get("status", ""):
                health = "unhealthy"
            elif c.get("state") == "running":
                health = "running"
            elif c.get("state") == "exited":
                health = "exited"

            containers.append({
                "name": c.get("name", ""),
                "image": c.get("image", ""),
                "state": c.get("state", ""),
                "status": c.get("status", ""),
                "health": health,
                "ports": c.get("ports", ""),
            })
        except json.JSONDecodeError:
            continue

    return containers


def _get_service_health():
    """Check connectivity to Redis, Postgres, and Celery."""
    services = {}

    # Redis
    try:
        start = time.monotonic()
        from django.core.cache import cache
        cache.set("__ops_ping", "1", 5)
        val = cache.get("__ops_ping")
        latency = round((time.monotonic() - start) * 1000, 1)
        services["redis"] = {
            "status": "ok" if val == "1" else "degraded",
            "latency_ms": latency,
        }
    except Exception as e:
        services["redis"] = {"status": "down", "error": str(e), "latency_ms": -1}

    # Postgres
    try:
        from django.db import connection
        start = time.monotonic()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency = round((time.monotonic() - start) * 1000, 1)
        services["postgres"] = {"status": "ok", "latency_ms": latency}
    except Exception as e:
        services["postgres"] = {"status": "down", "error": str(e), "latency_ms": -1}

    # Celery
    try:
        from outfi.celery import app as celery_app
        start = time.monotonic()
        inspect = celery_app.control.inspect(timeout=3)
        ping = inspect.ping()
        latency = round((time.monotonic() - start) * 1000, 1)
        if ping:
            worker_count = len(ping)
            # Get active tasks
            active = inspect.active() or {}
            active_count = sum(len(tasks) for tasks in active.values())
            services["celery"] = {
                "status": "ok",
                "workers": worker_count,
                "active_tasks": active_count,
                "latency_ms": latency,
            }
        else:
            services["celery"] = {
                "status": "down",
                "workers": 0,
                "active_tasks": 0,
                "latency_ms": latency,
            }
    except Exception as e:
        services["celery"] = {
            "status": "down",
            "error": str(e),
            "workers": 0,
            "active_tasks": 0,
            "latency_ms": -1,
        }

    return services


def _check_endpoints():
    """Ping external endpoints and measure response time."""
    import urllib.request
    import ssl

    endpoints = [
        {"url": "https://outfi.ai", "label": "Outfi Landing"},
        {"url": "https://api.outfi.ai/api/v1/health/", "label": "API Health"},
    ]

    results = []
    ctx = ssl.create_default_context()

    for ep in endpoints:
        try:
            start = time.monotonic()
            req = urllib.request.Request(ep["url"], method="GET")
            req.add_header("User-Agent", "OpsCommandCenter/1.0")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                status_code = resp.status
            latency = round((time.monotonic() - start) * 1000)
            results.append({
                "url": ep["url"],
                "label": ep["label"],
                "status": status_code,
                "latency_ms": latency,
                "ok": 200 <= status_code < 400,
            })
        except Exception as e:
            results.append({
                "url": ep["url"],
                "label": ep["label"],
                "status": 0,
                "latency_ms": -1,
                "ok": False,
                "error": str(e)[:120],
            })

    return results


# ─── Main View ────────────────────────────────────────────────────────────────

@require_GET
def ops_status_view(request):
    """
    GET /internal/ops/status/

    Returns comprehensive system health data as JSON.
    Protected in urls.py by staff_member_required.
    """
    # Allow CORS for ops dashboard (when running locally)
    data = {
        "server": _get_system_vitals(),
        "containers": _get_container_statuses(),
        "services": _get_service_health(),
        "endpoints": _check_endpoints(),
        "timestamp": timezone.now().isoformat(),
        "version": "1.0.0",
    }

    response = JsonResponse(data)
    # Allow cross-origin for local dashboard development
    origin = request.META.get("HTTP_ORIGIN", "")
    if origin in ("http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000", "null"):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Ops-Key"
    return response
