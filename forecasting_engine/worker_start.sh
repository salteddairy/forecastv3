#!/bin/bash
################################################################################
# Railway Forecasting Worker - Startup Script
# Runs forecasting jobs on a schedule using cron
################################################################################

set -e  # Exit on error

echo "=========================================="
echo "Starting Railway Forecasting Worker"
echo "=========================================="
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Current time: $(date -u +%Y-%m-%d\ %H:%M:%S\ UTC)"
echo ""

# Display environment (sanitized)
echo "Environment Configuration:"
echo "----------------------------------------"
if [ -n "$DATABASE_URL" ]; then
    # Show only host, not credentials
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\).*/\1/p')
    echo "DATABASE_URL: postgresql://****@${DB_HOST}"
else
    echo "DATABASE_URL: NOT SET"
fi
echo "RAILWAY_CRON: ${RAILWAY_CRON:-0 2 * * *}"
echo "ONE_SHOT: ${ONE_SHOT:-false}"
echo "FORECAST_MIN_MONTHS_HISTORY: ${FORECAST_MIN_MONTHS_HISTORY:-6}"
echo "FORECAST_MAX_MONTHS_HISTORY: ${FORECAST_MAX_MONTHS_HISTORY:-24}"
echo "FORECAST_USE_ADVANCED_MODELS: ${FORECAST_USE_ADVANCED_MODELS:-true}"
echo "FORECAST_PARALLEL_THRESHOLD: ${FORECAST_PARALLEL_THRESHOLD:-10}"
echo "========================================"
echo ""

# Validate DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    echo "This is required for database operations"
    echo "Please set DATABASE_URL in Railway variables"
    exit 1
fi

# Test database connection
echo "Testing database connection..."
if python -m forecasting_engine.cli health > /dev/null 2>&1; then
    echo "Database connection: OK"
else
    echo "ERROR: Database connection failed"
    echo "Please check DATABASE_URL and database status"
    exit 1
fi
echo ""

# One-shot mode (for testing)
if [ "$ONE_SHOT" = "true" ]; then
    echo "=========================================="
    echo "Running in ONE_SHOT mode"
    echo "=========================================="
    echo "This will run once and exit (for testing)"
    echo ""

    # Run forecast job
    python -m forecasting_engine.cli forecast \
        --source database \
        ${FORECAST_USE_ADVANCED_MODELS:+--advanced-models} \
        --auto-confirm

    EXIT_CODE=$?
    echo ""
    echo "Forecast job completed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi

# Scheduled mode (production)
echo "=========================================="
echo "Scheduled Mode"
echo "=========================================="

# Parse cron schedule (default: daily at 2 AM UTC)
SCHEDULE="${RAILWAY_CRON:-0 2 * * *}"
echo "Cron schedule: $SCHEDULE"
echo "Timezone: UTC"
echo ""

# Install cron if not present
if ! command -v cron &> /dev/null; then
    echo "Installing cron..."
    apt-get update -qq && apt-get install -y -qq cron
    echo "Cron installed successfully"
else
    echo "Cron already installed"
fi
echo ""

# Create logs directory
mkdir -p /app/logs
echo "Log directory: /app/logs"

# Build the forecast command
FORECAST_CMD="python -m forecasting_engine.cli forecast --source database --auto-confirm"

# Add advanced models flag if enabled
if [ "$FORECAST_USE_ADVANCED_MODELS" != "false" ]; then
    FORECAST_CMD="$FORECAST_CMD --advanced-models"
fi

# Create crontab entry
echo "Creating cron entry..."
cat > /etc/cron.d/forecast-worker << EOF
$SCHEDULE root cd /app && $FORECAST_CMD >> /app/logs/forecast.log 2>&1
EOF

# Fix cron permissions
chmod 0644 /etc/cron.d/forecast-worker

# Install crontab
crontab /etc/cron.d/forecast-worker

# Show crontab
echo "Active crontab:"
echo "----------------------------------------"
crontab -l
echo "----------------------------------------"
echo ""

# Test cron syntax
if crontab -l | crontab - ; then
    echo "Crontab syntax: VALID"
else
    echo "ERROR: Invalid crontab syntax"
    exit 1
fi
echo ""

# Start cron in foreground
echo "=========================================="
echo "Starting Cron Daemon"
echo "=========================================="
echo "Forecasting jobs will run according to schedule"
echo "Next run: Check cron schedule"
echo "Log file: /app/logs/forecast.log"
echo ""
echo "To view logs: railway logs"
echo "To test run: railway variables set ONE_SHOT=true && railway up"
echo ""
echo "Worker is now running..."
echo "=========================================="

# Start cron (will keep container running)
cron -f
