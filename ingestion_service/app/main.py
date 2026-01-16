"""
FastAPI Ingestion Service - Main Application.
Single entry point for all data writes to Railway PostgreSQL.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
from typing import Optional
import sys

# Configure stdout encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

from app.config import get_settings
from app.security import validate_api_key, decrypt_payload, hash_api_key
from app.models import (
    IngestionPayload,
    IngestionResponse,
    HealthResponse,
    validate_records,
    DataType,
)
from app.database import insert_records, refresh_materialized_views, Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


# ============================================================================
# Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.now()

    # Log request
    logger.info(f"{request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Log response
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")

    return response


# ============================================================================
# Dependencies
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Verify API key from request header."""
    if not validate_api_key(x_api_key):
        logger.warning(f"Invalid API key attempt: {hash_api_key(x_api_key) if x_api_key else 'None'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return x_api_key


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - service information."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "ingest": "/api/ingest",
            "docs": "/docs",
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    db = Database()

    database_status = "healthy" if db.health() else "unhealthy"

    return HealthResponse(
        status="healthy" if database_status == "healthy" else "degraded",
        version=settings.app_version,
        database=database_status,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/ingest", response_model=IngestionResponse, tags=["Ingestion"])
async def ingest_data(
    payload: dict,
    api_key: str = Depends(verify_api_key),
):
    """
    Main ingestion endpoint.

    Accepts encrypted payload from SAP middleware containing:
    - data_type: Type of data (items, inventory, sales_orders, etc.)
    - source: Data source system (default: SAP_B1)
    - timestamp: ISO format timestamp
    - records: Array of data records

    Returns:
        IngestionResponse with success status and details
    """
    try:
        # Extract encrypted payload
        encrypted_data = payload.get("encrypted_payload")
        if not encrypted_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'encrypted_payload' field"
            )

        # Decrypt payload
        try:
            decrypted_data = decrypt_payload(encrypted_data)
        except ValueError as e:
            logger.error(f"Decryption failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decrypt payload: {str(e)}"
            )

        # Parse ingestion payload
        try:
            ingestion = IngestionPayload(**decrypted_data)
        except Exception as e:
            logger.error(f"Invalid payload structure: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload structure: {str(e)}"
            )

        # Validate records
        validated_records, validation_errors = validate_records(
            ingestion.data_type,
            ingestion.records
        )

        # Insert records into database
        try:
            records_inserted = insert_records(
                ingestion.data_type.value,
                validated_records
            )
        except Exception as e:
            logger.error(f"Database insertion failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to insert records: {str(e)}"
            )

        # Refresh materialized views
        try:
            refresh_materialized_views()
        except Exception as e:
            logger.warning(f"Failed to refresh materialized views: {e}")
            # Non-critical, don't fail the request

        # Build response
        all_errors = validation_errors
        if len(all_errors) == 0:
            message = f"Successfully ingested {records_inserted} {ingestion.data_type.value} records"
        else:
            message = f"Partially ingested {records_inserted}/{len(ingestion.records)} records. Some records had validation errors."

        return IngestionResponse(
            success=len(all_errors) == 0,
            message=message,
            records_processed=records_inserted,
            errors=all_errors,
            data_type=ingestion.data_type.value,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/api/ingest/batch", response_model=IngestionResponse, tags=["Ingestion"])
async def ingest_batch(
    payload: dict,
    api_key: str = Depends(verify_api_key),
):
    """
    Batch ingestion endpoint for multiple data types in one request.

    Payload format:
    {
        "encrypted_payload": "<base64 encrypted JSON>",
    }

    Where decrypted JSON contains:
    {
        "batch": [
            {"data_type": "items", "records": [...]},
            {"data_type": "inventory_current", "records": [...]},
        ]
    }
    """
    try:
        # Decrypt payload
        try:
            decrypted_data = decrypt_payload(payload.get("encrypted_payload"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decrypt payload: {str(e)}"
            )

        batch = decrypted_data.get("batch", [])
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty batch"
            )

        total_processed = 0
        all_errors = []

        for item in batch:
            try:
                # Validate each batch item
                ingestion = IngestionPayload(**item)

                # Validate records
                validated_records, validation_errors = validate_records(
                    ingestion.data_type,
                    ingestion.records
                )
                all_errors.extend(validation_errors)

                # Insert records
                records_inserted = insert_records(
                    ingestion.data_type.value,
                    validated_records
                )
                total_processed += records_inserted

            except Exception as e:
                all_errors.append(f"Batch item error: {str(e)}")

        # Refresh materialized views at the end
        try:
            refresh_materialized_views()
        except Exception as e:
            logger.warning(f"Failed to refresh materialized views: {e}")

        return IngestionResponse(
            success=len(all_errors) == 0,
            message=f"Batch ingestion complete: {total_processed} total records processed",
            records_processed=total_processed,
            errors=all_errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during batch ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database URL configured: {bool(settings.database_url)}")
    logger.info(f"API keys configured: {len(settings.api_keys_list)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down...")
