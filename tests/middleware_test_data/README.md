# SAP Middleware Test Data

Generated: 2026-01-17 12:50:15

## Files

This directory contains encrypted test payloads for all supported data types:

- items_encrypted.json | - vendors_encrypted.json | - warehouses_encrypted.json | - inventory_current_encrypted.json | - sales_orders_encrypted.json | - purchase_orders_encrypted.json | - costs_encrypted.json | - pricing_encrypted.json

## How to Use

### 1. Send to Railway Ingestion Service

```bash
curl -X POST "https://ingestion-service-production-6947.up.railway.app/api/ingest" \
  -H "X-API-Key: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM" \
  -H "Content-Type: application/json" \
  -d @<filename>
```

Example:
```bash
curl -X POST "https://ingestion-service-production-6947.up.railway.app/api/ingest" \
  -H "X-API-Key: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM" \
  -H "Content-Type: application/json" \
  -d @items_encrypted.json
```

### 2. Using Python

```python
import requests
import json

url = "https://ingestion-service-production-6947.up.railway.app/api/ingest"
headers = {
    "X-API-Key": "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM",
    "Content-Type": "application/json"
}

with open("items_encrypted.json", "r") as f:
    payload = json.load(f)

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

### 3. Using PowerShell

```powershell
$headers = @{
    "X-API-Key" = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
    "Content-Type" = "application/json"
}

$body = Get-Content "items_encrypted.json" -Raw
Invoke-RestMethod -Uri "https://ingestion-service-production-6947.up.railway.app/api/ingest" -Method Post -Headers $headers -Body $body
```

## Configuration

- **Ingestion URL**: https://ingestion-service-production-6947.up.railway.app/api/ingest
- **API Key**: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM
- **Encryption Key**: RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=
- **Encryption Method**: Fernet (AES-128)

## Data Types

1. **items**: Item master data (products/SKUs)
2. **vendors**: Vendor/supplier master data
3. **warehouses**: Warehouse and location definitions
4. **inventory_current**: Current inventory levels
5. **sales_orders**: Historical sales orders
6. **purchase_orders**: Historical purchase orders
7. **costs**: Product cost data
8. **pricing**: Sales pricing data

## Payload Format

All payloads are encrypted using Fernet symmetric encryption with the key above.

Original format (before encryption):
```json
{
    "data_type": "items",
    "source": "SAP_B1",
    "timestamp": "2025-01-16T10:30:00",
    "records": [...]
}
```

Encrypted format (sent to API):
```json
{
    "encrypted_payload": "gAAAAABh..."
}
```

## Verification

After sending, verify the data was ingested:

```bash
# Check health
curl https://ingestion-service-production-6947.up.railway.app/api/ingest/health

# Response should show:
# {"status": "healthy", "database": "healthy", ...}
```
