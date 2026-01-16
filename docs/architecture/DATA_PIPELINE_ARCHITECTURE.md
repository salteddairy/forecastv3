# Data Pipeline Architecture

## Principle: Single Entry Point

**ALL data writes to the database MUST go through the ingestion service.**

No direct database writes from:
- ❌ TSV migration scripts
- ❌ Admin tools
- ❌ Frontend applications

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
├─────────────────────────────────────────────────────────────────┤
│  1. SAP B1 (via SAP Middleware)                                │
│  2. Manual TSV uploads (Admin interface)                       │
│  3. Legacy data migrations (One-time via ingestion API)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              INGESTION SERVICE (FastAPI on Railway)            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Endpoint: POST /api/ingest                             │   │
│  │  - Validates API key                                    │   │
│  │  - Decrypts payload (Fernet)                            │   │
│  │  - Validates data schema                                │   │
│  │  - Cleans/normalizes data                               │   │
│  │  - Writes to PostgreSQL (ONLY ENTRY POINT)              │   │
│  │  - Returns success/error response                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Railway PostgreSQL Database                        │
│  - 11 tables                                                    │
│  - Materialized views                                          │
│  - ONLY written to by ingestion service                        │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              │ (Read-only)
┌─────────────────────────────────────────────────────────────────┐
│              Next.js Frontend (Vercel)                          │
│  - Direct PostgreSQL queries (read-only)                       │
│  - NO write operations                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Scenarios

### Scenario 1: SAP Middleware (Automated)

```
SAP B1 → SAP Middleware → Encrypted HTTP POST → Ingestion Service → PostgreSQL
```

1. SAP Middleware extracts data from SAP B1
2. Middleware encrypts payload with shared key
3. Middleware POSTs to `/api/ingest`
4. Ingestion service decrypts, validates, writes to DB

### Scenario 2: Manual TSV Upload (Admin)

```
Admin → Uploads TSV → Ingestion Service → Process → PostgreSQL
```

1. Admin uploads TSV via web interface (Future: Next.js admin panel)
2. Frontend sends TSV to ingestion service endpoint
3. Ingestion service parses TSV, validates, writes to DB

### Scenario 3: Initial Migration (One-time)

```
Existing TSV files → Ingestion Service → PostgreSQL
```

1. Use test harness to encrypt TSV data
2. POST to `/api/ingest` endpoint
3. Ingestion service processes and writes to DB

## Security Model

### Encryption
- **In transit:** HTTPS/TLS (automatic with Railway/Vercel)
- **At rest:** PostgreSQL encryption (Railway managed)
- **Payload:** Fernet symmetric encryption (AES-128)

### Authentication
- **API Key:** Required for all ingestion endpoints
- **Source IP:** Optional whitelist (Railway networking)
- **Rate limiting:** Per-source (to be implemented)

### Data Validation
- Schema validation (Pydantic models)
- Type checking
- Business rule validation
- Duplicate detection

## Benefits of Single Entry Point

1. **Security:** One place to implement authentication, encryption, validation
2. **Auditability:** All writes logged in one place
3. **Consistency:** Same validation rules for all data sources
4. **Maintainability:** Changes to data handling logic in one location
5. **Testing:** Single service to test for all data flows

## Migration Scripts (Updated)

**Old approach:** Direct database writes from migration scripts
```
TSV files → Python script → Direct PostgreSQL write ❌
```

**New approach:** All data through ingestion service
```
TSV files → Encrypt → POST /api/ingest → PostgreSQL ✓
```

### Legacy Migration Script Updates

The existing migration scripts should be updated to:
1. Read TSV files
2. Format data as ingestion payloads
3. Encrypt payloads
4. POST to ingestion service
5. Handle responses

This ensures even legacy migrations go through the same validation and encryption.

## Database Permissions

### Ingestion Service (Railway)
- **PostgreSQL Role:** `ingestion_writer`
- **Permissions:** INSERT, UPDATE on all tables
- **Permissions:** REFRESH MATERIALIZED VIEWS

### Frontend (Vercel)
- **PostgreSQL Role:** `frontend_reader`
- **Permissions:** SELECT only
- **Permissions:** NO WRITE ACCESS

### Admin (Local development)
- **PostgreSQL Role:** `admin`
- **Permissions:** ALL (for schema migrations, manual fixes)

## Next Steps

1. ✓ Create ingestion service (FastAPI on Railway)
2. ✓ Implement encryption (Fernet)
3. ✓ Create test harness (simulate middleware)
4. ✓ Update migration scripts to use ingestion API
5. ⏳ Deploy ingestion service to Railway
6. ⏳ Test with sample data
7. ⏳ Configure SAP Middleware endpoint
8. ⏳ Create admin upload interface (Next.js)

---

**Last Updated:** 2026-01-16
**Status:** Architecture approved, implementation in progress
