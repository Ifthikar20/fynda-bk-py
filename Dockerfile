# =============================================================================
# Optimized Python Base Image for Fynda API
# Uses multi-stage build for smaller final image
# =============================================================================

FROM python:3.12-slim as builder

# Build dependencies only
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# =============================================================================
# Final Production Image
# =============================================================================
FROM python:3.12-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=fynda.settings.production

WORKDIR /app

# Install only runtime dependencies (no gcc/build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy pre-built wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Create static files directory
RUN mkdir -p /app/staticfiles && chown appuser:appuser /app/staticfiles

# Switch to non-root user
USER appuser

# Collect static files (will fail silently if not configured)
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f -H "X-Forwarded-Proto: https" http://localhost:8000/api/health/ || exit 1

# Optimized gunicorn settings for t3.small (2 vCPU, 2GB RAM)
# Workers = 2 * CPU + 1, but capped for memory
CMD ["gunicorn", "fynda.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--worker-tmp-dir", "/dev/shm", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
