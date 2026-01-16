# SAP B1 Ingestion Service

**FastAPI service for receiving, validating, and storing SAP B1 data.**

Single entry point for all database writes from SAP middleware and admin uploads.

---

## Features

- ✅ **Encrypted Payloads:** Fernet symmetric encryption (AES-128)
- ✅ **API Key Authentication:** Secure endpoint access
- ✅ **Data Validation:** Pydantic schema validation
- ✅ **Database Connection:** SQLAlchemy with connection pooling
- ✅ **Health Monitoring:** `/health` endpoint for status checks
- ✅ **Batch Processing:** Process multiple data types in one request
- ✅ **Materialized Views:** Auto-refresh after data ingestion
- ✅ **Comprehensive Logging:** Request/response logging with performance metrics

---

## Quick Start

### 1. Install Dependencies

```bash
cd ingestion_service
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Test Endpoint

```bash
# Health check
curl http://localhost:8000/health

# Ingest data (using test harness)
python ../tests/test_ingestion_harness.py --generate-payloads
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-12345" \
  -d @../tests/test_data/items_encrypted.json
```

---

## API Endpoints

### POST /api/ingest

Main ingestion endpoint for encrypted data payloads.

**Request:**
```json
{
  "encrypted_payload": "<base64 encrypted JSON>"
}
```

**Decrypted Payload Format:**
```json
{
  "data_type": "items",
  "source": "SAP_B1",
  "timestamp": "2026-01-16T12:00:00",
  "records": [
    {
      "item_code": "ITEM001",
      "item_description": "Sample Item",
      "item_group": "Electronics",
      "region": "North",
      "uom": "EA",
      "is_active": true
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully ingested 1 items records",
  "records_processed": 1,
  "errors": [],
  "data_type": "items"
}
```

### POST /api/ingest/batch

Batch ingestion for multiple data types.

**Decrypted Payload Format:**
```json
{
  "batch": [
    {
      "data_type": "items",
      "source": "SAP_B1",
      "timestamp": "2026-01-16T12:00:00",
      "records": [...]
    },
    {
      "data_type": "inventory_current",
      "source": "SAP_B1",
      "timestamp": "2026-01-16T12:00:00",
      "records": [...]
    }
  ]
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "healthy",
  "timestamp": "2026-01-16T12:00:00"
}
```

---

## Supported Data Types

| Data Type | Description | Primary Key |
|-----------|-------------|-------------|
| `items` | Item master data | `item_code` |
| `vendors` | Vendor master data | `vendor_code` |
| `warehouses` | Warehouse locations | `warehouse_code` |
| `inventory_current` | Current inventory levels | `item_code`, `warehouse_code` |
| `sales_orders` | Sales order history | `order_id` |
| `purchase_orders` | Purchase order history | `order_id` |
| `costs` | Cost data | `item_code`, `effective_date`, `vendor_code` |
| `pricing` | Pricing data | `item_code`, `price_level`, `region` |

---

## Security

### Encryption

- **Algorithm:** Fernet (symmetric encryption, AES-128)
- **Key Management:** Environment variable `ENCRYPTION_KEY`
- **Key Generation:**
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

### API Keys

- **Header:** `X-API-Key`
- **Validation:** All requests must include valid API key
- **Configuration:** Comma-separated list in `API_KEYS` environment variable

### CORS

Configure allowed origins in `CORS_ORIGINS` environment variable.

---

## Deployment

### Railway (Recommended)

```bash
# From project root
cd ingestion_service

# Link to Railway project
railway link

# Set environment variables
railway variables set ENCRYPTION_KEY=<your-key>
railway variables set API_KEYS=<your-api-keys>
railway variables set DATABASE_URL=<your-database-url>

# Deploy
railway up
```

### Docker

```bash
docker build -t sap-ingestion-service .
docker run -p 8000:8000 --env-file .env sap-ingestion-service
```

---

## Testing

### Using Test Harness

```bash
# Generate test payloads
python ../tests/test_ingestion_harness.py --generate-payloads

# Test items endpoint
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-12345" \
  -d @../tests/test_data/items_encrypted.json

# Test batch endpoint
curl -X POST http://localhost:8000/api/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-12345" \
  -d @batch_payload.json
```

### Automated Tests

```bash
pytest tests/
```

---

## Monitoring

### Logs

```bash
# Railway
railway logs

# Docker
docker logs <container-id>
```

### Health Checks

The `/health` endpoint returns:
- Service status
- Service version
- Database connectivity
- Current timestamp

---

## Troubleshooting

### Common Issues

**1. Decryption fails**
- Check that `ENCRYPTION_KEY` matches between middleware and service
- Verify key is exactly 32 bytes base64-encoded

**2. API key rejected**
- Verify `X-API-Key` header is set
- Check key is in `API_KEYS` environment variable

**3. Database connection fails**
- Verify `DATABASE_URL` is correct
- Check Railway PostgreSQL service is running
- Ensure network allows connection

---

## Architecture

```
┌─────────────────┐
│  SAP Middleware │
└────────┬────────┘
         │ Encrypted POST
         ▼
┌─────────────────────────────┐
│  FastAPI Ingestion Service  │
│  - Validate API Key         │
│  - Decrypt Payload          │
│  - Validate Schema          │
│  - Write to PostgreSQL      │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Railway PostgreSQL         │
│  - 11 tables                │
│  - Materialized Views       │
└─────────────────────────────┘
```

---

## Documentation

- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Architecture:** See `docs/architecture/DATA_PIPELINE_ARCHITECTURE.md`
- **Test Harness:** See `tests/test_ingestion_harness.py`

---

**Version:** 1.0.0
**Last Updated:** 2026-01-16
