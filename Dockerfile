# ─────────────────────────────────────────────────────────────────────────────
# StockIQ — Multi-stage Dockerfile (FastAPI backend)
#
# Stage 1 (builder): Install all dependencies including build tools.
#                    Compiles C extensions (pandas, numpy, pandas-ta).
# Stage 2 (runtime): Copy only installed packages + app code.
#                    No build tools, no pip, no dev dependencies.
#                    Final image ~40% smaller than single-stage.
#
# Design decisions: ADR-005 — Docker strategy.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build tools needed for C extensions (pandas, numpy, pandas-ta)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker layer cache: this layer only invalidates
# when requirements.txt changes, not on every code edit.
COPY requirements.txt .

# Install into an isolated venv inside the builder stage.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Activate the venv from builder
    PATH="/opt/venv/bin:$PATH" \
    # Ensure project root is importable
    PYTHONPATH="/app"

WORKDIR /app

# Security: run as non-root user (never run production containers as root)
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --no-create-home appuser

# Copy venv from builder — no build tools included in final image
COPY --from=builder /opt/venv /opt/venv

# Copy application code (respects .dockerignore)
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

# Health check used by Docker Compose and container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# Production: 2 workers is safe for a single container
# --log-level info: structured JSON logs from structlog
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
