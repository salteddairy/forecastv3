# Railway Worker Dockerfile
# Runs forecasting jobs on a schedule using cron
#
# Phase 8: Railway Deployment
# Forecasting Engine v1.0.0

FROM python:3.11-slim

# Metadata
LABEL maintainer="Claude (AI Assistant)"
LABEL description="SAP B1 Inventory Forecasting Engine - Railway Worker"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORECAST_MIN_MONTHS_HISTORY=6 \
    FORECAST_MAX_MONTHS_HISTORY=24 \
    FORECAST_FORECAST_HORIZON=12 \
    FORECAST_USE_ADVANCED_MODELS=true \
    FORECAST_PARALLEL_THRESHOLD=10 \
    RAILWAY_CRON="0 2 * * *" \
    ONE_SHOT=false

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cron \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY forecasting_engine/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache/pip

# Copy forecasting engine code
COPY forecasting_engine/ .

# Copy worker startup script
COPY forecasting_engine/worker_start.sh .
RUN chmod +x worker_start.sh

# Create logs directory
RUN mkdir -p /app/logs

# Verify installation
RUN python -c "from forecasting_engine import __version__; print(f'Forecasting Engine v{__version__}')" && \
    python -m forecasting_engine.cli config > /dev/null

# Set entrypoint
ENTRYPOINT ["/app/worker_start.sh"]

# Health check (Railway will call this periodically)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -m forecasting_engine.cli health || exit 1

# Default command (runs entrypoint)
CMD []
