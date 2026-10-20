# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv-bin
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

# Copy configuration and source files required for installation
COPY pyproject.toml ./
COPY app/ ./app/

# Install dependencies AND the local app package in editable mode
RUN /uv-bin pip install --system --no-cache -e .[dev] || \
    /uv-bin pip install --system --no-cache -e .

# --- Stage 2: Runtime ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed python packages/environment from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Ensure Python looks into /app for modules
ENV PYTHONPATH=/app

# Create a non-root user for security
RUN useradd -u 1000 appuser && chown -R appuser:appuser /app
# Note: For local development with live-reloading volumes, running as root or handling volume permissions is common, 
# but if keeping appuser, ensure volume mounts match. For simplicity in local dev, you can omit USER appuser or configure permissions.

EXPOSE 8000