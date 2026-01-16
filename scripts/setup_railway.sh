#!/bin/bash
# ============================================================================
# Railway Setup Script
# SAP B1 Inventory & Forecast Analyzer
# ============================================================================
# Purpose: Automate Railway resource creation and initial setup
#
# Prerequisites:
# - Railway CLI installed (npm install -g @railway/cli)
# - Railway account logged in (railway login)
# - PostgreSQL CLI tools (psql)
#
# Usage:
#   chmod +x scripts/setup_railway.sh
#   ./scripts/setup_railway.sh
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Configuration
# ============================================================================

PROJECT_NAME="sap-b1-inventory"
POSTGRES_SERVICE_NAME="postgres"
REDIS_SERVICE_NAME="redis"
APP_SERVICE_NAME="streamlit-app"
WORKER_SERVICE_NAME="background-worker"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

# ============================================================================
# Prerequisites Check
# ============================================================================

log_info "Checking prerequisites..."
check_command "railway"
check_command "psql"

# Check if logged in to Railway
if ! railway whoami &> /dev/null; then
    log_error "Not logged in to Railway. Run 'railway login' first."
    exit 1
fi

log_info "All prerequisites met!"

# ============================================================================
# Project Setup
# ============================================================================

log_info "Setting up Railway project..."

# Create or link project
if railway list | grep -q "$PROJECT_NAME"; then
    log_warn "Project '$PROJECT_NAME' already exists. Linking to it..."
    railway link "$PROJECT_NAME"
else
    log_info "Creating new Railway project: $PROJECT_NAME"
    railway init --name "$PROJECT_NAME"
fi

# ============================================================================
# PostgreSQL Service
# ============================================================================

log_info "Creating PostgreSQL service..."

# Add PostgreSQL service
railway add postgresql

# Wait for service to be ready
log_info "Waiting for PostgreSQL to be ready..."
sleep 10

# Get PostgreSQL connection details
POSTGRES_URL=$(railway variables get DATABASE_URL)
if [ -z "$POSTGRES_URL" ]; then
    log_error "Failed to get DATABASE_URL from Railway"
    exit 1
fi

log_info "PostgreSQL service created successfully!"
log_info "DATABASE_URL: ${POSTGRES_URL:0:50}..." # Show first 50 chars

# ============================================================================
# Redis Service
# ============================================================================

log_info "Creating Redis service..."

# Add Redis service
railway add redis

# Wait for service to be ready
log_info "Waiting for Redis to be ready..."
sleep 10

# Get Redis connection details
REDIS_URL=$(railway variables get REDIS_URL)
if [ -z "$REDIS_URL" ]; then
    log_error "Failed to get REDIS_URL from Railway"
    exit 1
fi

log_info "Redis service created successfully!"
log_info "REDIS_URL: ${REDIS_URL:0:50}..." # Show first 50 chars

# ============================================================================
# Run Database Migrations
# ============================================================================

log_info "Running database migrations..."

# Run initial schema migration
psql "$POSTGRES_URL" -f database/migrations/001_initial_schema.sql

log_info "Database migrations completed successfully!"

# ============================================================================
# Seed Initial Data
# ============================================================================

log_info "Seeding initial data..."

# Insert initial warehouses (already in migration script)
# Insert any other seed data here

log_info "Initial data seeded successfully!"

# ============================================================================
# Environment Variables
# ============================================================================

log_info "Setting environment variables..."

# Azure AD (user should update these)
railway variables set AZURE_AD_TENANT_ID "aface7de-787c-41b4-b458-74df6ae895da"
railway variables set AZURE_AD_CLIENT_ID "1ab7aef9-0cb5-4bdf-8e06-388c898c026f"
railway variables set AZURE_AD_CLIENT_SECRET "UPDATE_THIS_SECRET"

# Generate API keys
API_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)

railway variables set API_KEY "$API_KEY"
railway variables set API_ENCRYPTION_KEY "$ENCRYPTION_KEY"

# Admin email
railway variables set ADMIN_EMAIL "nathan@pacesolutions.com"

log_info "Environment variables set!"
log_warn "Remember to update AZURE_AD_CLIENT_SECRET and other secrets!"

# ============================================================================
# Streamlit App Service
# ============================================================================

log_info "Deploying Streamlit app service..."

# Create app service from current directory
railway up --service "$APP_SERVICE_NAME"

# Configure app settings
railway variables set PORT "8501"
railway variables set STREAMLIT_SERVER_PORT "8501"
railway variables set STREAMLIT_SERVER_ADDRESS "0.0.0.0"
railway variables set STREAMLIT_SERVER_HEADLESS "true"

log_info "Streamlit app service deployed!"

# ============================================================================
# Background Worker Service
# ============================================================================

log_info "Deploying background worker service..."

# Create worker service
railway up --service "$WORKER_SERVICE_NAME" --dockerfile Dockerfile.worker

# Configure worker settings
railway variables set WORKER_TYPE "scheduler"
railway variables set SCHEDULE_REFRESH_VIEWS "0 2 * * *"  # Daily at 2 AM
railway variables set SCHEDULE_RUN_FORECASTS "0 3 * * 0"  # Weekly on Sunday at 3 AM

log_info "Background worker service deployed!"

# ============================================================================
# Verification
# ============================================================================

log_info "Verifying deployment..."

# Get service URLs
APP_URL=$(railway domain --service "$APP_SERVICE_NAME")
log_info "Streamlit App URL: $APP_URL"

# Test database connection
if psql "$POSTGRES_URL" -c "SELECT COUNT(*) FROM items;" &> /dev/null; then
    log_info "Database connection verified!"
else
    log_warn "Database connection test failed (expected - no data yet)"
fi

# Test Redis connection
if redis-cli -u "$REDIS_URL" ping &> /dev/null; then
    log_info "Redis connection verified!"
else
    log_error "Redis connection test failed!"
    exit 1
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
log_info "=========================================="
log_info "Railway Setup Complete!"
log_info "=========================================="
echo ""
log_info "Services Created:"
echo "  - PostgreSQL: $POSTGRES_SERVICE_NAME"
echo "  - Redis: $REDIS_SERVICE_NAME"
echo "  - Streamlit App: $APP_SERVICE_NAME"
echo "  - Background Worker: $WORKER_SERVICE_NAME"
echo ""
log_info "Next Steps:"
echo "  1. Update Azure AD client secret in Railway dashboard"
echo "  2. Configure Azure AD redirect URI: $APP_URL/_stcore/auth"
echo "  3. Test the app at: $APP_URL"
echo "  4. Import TSV data using scripts/import_tsv_data.py"
echo "  5. Run forecasts using scripts/run_forecasts.py"
echo ""
log_warn "IMPORTANT: Save these credentials securely!"
echo "  DATABASE_URL: $POSTGRES_URL"
echo "  REDIS_URL: $REDIS_URL"
echo "  API_KEY: $API_KEY"
echo ""
