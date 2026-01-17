# SAP Middleware Integration Guide

**Project:** SAP B1 Inventory & Forecast Analyzer
**Last Updated:** 2026-01-17
**Version:** 2.0 (Schema Simplified)

---

## Quick Start

### API Endpoint
```
POST https://ingestion-service-production-6947.up.railway.app/api/ingest
```

### Authentication
```
X-API-Key: BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM
```

### Payload Format
```json
{
  "encrypted_payload": "<Fernet encrypted data>"
}
```

---

## Important Changes (v2.0)

### ✅ Order Tracking Removed

**For forecasting purposes, order numbers are NO LONGER REQUIRED:**

- `sales_orders`: `order_number` and `line_number` are **OPTIONAL**
- `purchase_orders`: `po_number` and `line_number` are **OPTIONAL**
- You can send sales/purchase data WITHOUT order identifiers

**Why?** This simplifies integration. The system only needs:
- **What** was sold/purchased (item_code)
- **When** it happened (posting_date/po_date)
- **How much** (quantity)
- **Where** (warehouse_code)

---

## Data Type Specifications

### 1. Items (Master Data)

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "item_description": "Industrial Widget A",
  "item_group": "WIDGETS",
  "base_uom": "EA",
  "is_active": true
}
```

**Optional Fields:**
- `region` (extracted from item code suffix if not provided)
- `purch_uom`, `sales_uom`, `qty_per_purch_uom`, `qty_per_sales_uom`
- `preferred_vendor_code`, `last_vendor_code`
- `moq`, `order_multiple`

---

### 2. Vendors (Master Data)

**Required Fields:**
```json
{
  "vendor_code": "VENDOR001",
  "vendor_name": "Acme Industrial Supplies Inc."
}
```

**Optional Fields:**
- `contact_name`, `email`, `phone`

---

### 3. Warehouses (Master Data)

**Required Fields:**
```json
{
  "warehouse_code": "WH01",
  "warehouse_name": "Main Distribution Center"
}
```

**Optional Fields:**
- `region`, `is_active`

---

### 4. Inventory Current

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "warehouse_code": "WH01",
  "on_hand_qty": 1500.0
}
```

**Optional Fields:**
- `on_order_qty` (default: 0)
- `committed_qty` (default: 0)
- `uom` (default: "EA")

**Calculated Fields (do not send):**
- `available_qty` = on_hand_qty + on_order_qty - committed_qty

---

### 5. Sales Orders ⭐ (UPDATED)

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "posting_date": "2024-01-15",
  "ordered_qty": 100.0
}
```

**Optional Fields:**
- `order_number` (NOT REQUIRED for forecasting)
- `line_number` (NOT REQUIRED for forecasting)
- `promise_date`
- `customer_code`, `customer_name`
- `item_description`
- `shipped_qty` (default: 0)
- `row_value`
- `warehouse_code`
- `document_type`

**Business Key (UPSERT):**
- Duplicate detection based on: `(item_code, posting_date, warehouse_code, customer_code)`
- If same item/date/warehouse/customer is sent again, it will UPDATE instead of INSERT

---

### 6. Purchase Orders ⭐ (UPDATED)

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "po_date": "2024-01-15",
  "vendor_code": "VENDOR001",
  "ordered_qty": 500.0
}
```

**Optional Fields:**
- `po_number` (NOT REQUIRED for forecasting)
- `line_number` (NOT REQUIRED for forecasting)
- `event_date`
- `vendor_name`
- `received_qty` (default: 0)
- `row_value`
- `warehouse_code`
- `currency` (default: "CAD")
- `exchange_rate` (default: 1.0)
- `freight_terms`, `fob`
- `lead_time_days`

**Business Key (UPSERT):**
- Duplicate detection based on: `(item_code, po_date, warehouse_code, vendor_code)`
- If same item/date/warehouse/vendor is sent again, it will UPDATE instead of INSERT

---

### 7. Costs

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "unit_cost": 25.50,
  "effective_date": "2024-01-01"
}
```

**Optional Fields:**
- `vendor_code`
- `freight` (default: 0)
- `duty` (default: 0)
- `total_landed_cost` (auto-calculated if not provided)
- `currency` (default: "USD")

**Business Key (UPSERT):**
- Duplicate detection based on: `(item_code, effective_date, COALESCE(vendor_code, ''))`

---

### 8. Pricing

**Required Fields:**
```json
{
  "item_code": "ITEM001",
  "price_level": "List",
  "unit_price": 45.00,
  "effective_date": "2024-01-01"
}
```

**Optional Fields:**
- `region` (use NULL for global pricing)
- `currency` (default: "USD")
- `expiry_date`
- `price_source`
- `is_active` (default: true)

**Business Key (UPSERT):**
- Duplicate detection based on: `(item_code, price_level, COALESCE(region, ''), effective_date)`

---

## Encryption

All payloads must be encrypted using **Fernet symmetric encryption** (AES-128).

### Encryption Key
```
RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=
```

### Key Transformation
The encryption key must be hashed with SHA-256 and base64-encoded:

```python
import hashlib
import base64
from cryptography.fernet import Fernet

# Transform key
raw_key = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
hashed = hashlib.sha256(raw_key.encode()).digest()
fernet_key = base64.b64encode(hashed)

# Encrypt data
fernet = Fernet(fernet_key)
json_data = json.dumps(your_payload).encode('utf-8')
encrypted = fernet.encrypt(json_data)
encrypted_str = encrypted.decode('utf-8')
```

---

## Complete Request Example

### Python Example

```python
import requests
import json
import hashlib
import base64
from cryptography.fernet import Fernet

# Configuration
API_URL = "https://ingestion-service-production-6947.up.railway.app/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="

# Prepare data
payload = {
    "data_type": "sales_orders",
    "source": "SAP_B1",
    "timestamp": "2024-01-17T10:30:00",
    "records": [
        {
            "item_code": "ITEM001",
            "posting_date": "2024-01-15",
            "ordered_qty": 100.0,
            "customer_code": "CUST001"
        }
    ]
}

# Encrypt
hashed = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
fernet_key = base64.b64encode(hashed)
fernet = Fernet(fernet_key)
json_data = json.dumps(payload).encode('utf-8')
encrypted = fernet.encrypt(json_data)
encrypted_str = encrypted.decode('utf-8')

# Send
response = requests.post(
    API_URL,
    json={"encrypted_payload": encrypted_str},
    headers={"X-API-Key": API_KEY}
)

print(response.json())
```

---

## Response Format

### Success Response
```json
{
  "success": true,
  "message": "Data ingested successfully",
  "records_processed": 3,
  "data_type": "sales_orders",
  "errors": []
}
```

### Error Response
```json
{
  "success": false,
  "message": "Validation errors",
  "records_processed": 0,
  "errors": [
    "Record 0: 'item_code' is a required field",
    "Record 1: Invalid date format"
  ]
}
```

---

## Data Type Reference

| Data Type | Purpose | Required Fields | Optional Fields |
|-----------|---------|-----------------|-----------------|
| `items` | Item master data | item_code, item_description | item_group, base_uom, region |
| `vendors` | Vendor master data | vendor_code, vendor_name | contact_name, email, phone |
| `warehouses` | Warehouse data | warehouse_code, warehouse_name | region |
| `inventory_current` | Current inventory | item_code, warehouse_code, on_hand_qty | on_order_qty, committed_qty, uom |
| `sales_orders` | Sales history | item_code, posting_date, ordered_qty | **order_number** ❌, **line_number** ❌, customer_code |
| `purchase_orders` | Purchase history | item_code, po_date, ordered_qty, vendor_code | **po_number** ❌, **line_number** ❌, warehouse_code |
| `costs` | Cost data | item_code, unit_cost, effective_date | vendor_code, freight, duty |
| `pricing` | Pricing data | item_code, price_level, unit_price, effective_date | region, expiry_date |

**❌ = Order tracking fields NO LONGER REQUIRED**

---

## Field Data Types

| Field Name | Type | Format | Example |
|------------|------|--------|---------|
| `item_code` | string | Max 50 chars | "ITEM001" |
| `item_description` | string | Max 500 chars | "Industrial Widget A" |
| `warehouse_code` | string | Max 20 chars | "WH01" |
| `posting_date` / `po_date` | date | ISO 8601 | "2024-01-15" |
| `ordered_qty` | number | Positive decimal | 100.0 |
| `unit_cost` | number | Non-negative decimal | 25.50 |
| `unit_price` | number | Positive decimal | 45.00 |
| `effective_date` | date | ISO 8601 | "2024-01-01" |

---

## Best Practices

### 1. Send Master Data First
```
Order: warehouses → vendors → items → inventory_current
Then: costs → pricing
Finally: sales_orders → purchase_orders
```

### 2. Batch Recommendations
- Send 100-1000 records per batch
- Use background jobs for large datasets
- Implement exponential backoff on errors

### 3. Error Handling
- Check `success` field in response
- Review `errors` array for details
- Log failed records for retry

### 4. Idempotency
- Sending the same data twice is safe (UPSERT)
- Business keys prevent duplicates
- Last write wins for duplicates

---

## Testing

### Health Check
```bash
curl https://ingestion-service-production-6947.up.railway.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "healthy",
  "timestamp": "2024-01-17T10:30:00"
}
```

### Test Ingestion
See `tests/middleware_test_data/` directory for:
- Encrypted test payloads for all 8 data types
- `send_all_test_data.py` - Python test script
- `README.md` - Testing instructions

---

## Support

**Questions?** Contact:
- **Email:** nathan@pacesolutions.com
- **Documentation:** See project README.md
- **Status Page:** STATUS.md

---

**Version History:**
- **v1.0** (2026-01-16): Initial release with order tracking
- **v2.0** (2026-01-17): Simplified schema, order tracking removed

**Document Status:** ✅ Production Ready
