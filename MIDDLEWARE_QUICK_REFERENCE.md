# Quick Reference: SAP Middleware Integration

## 🚀 One-Page Summary

**API Endpoint:** `POST https://ingestion-service-production-6947.up.railway.app/api/ingest`

**API Key:** `BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM`

**Encryption Key:** `RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA=`

---

## ⭐ IMPORTANT CHANGE (v2.0)

**Order Numbers NO LONGER REQUIRED!**

You can now send sales and purchase data WITHOUT:
- ❌ `order_number`
- ❌ `po_number`
- ❌ `line_number`

**Only send:**
- ✅ `item_code` (what)
- ✅ `posting_date`/`po_date` (when)
- ✅ `quantity` (how much)

---

## 📋 Minimal Payload Examples

### Sales Orders (Simplified)
```json
{
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
```

### Purchase Orders (Simplified)
```json
{
  "data_type": "purchase_orders",
  "source": "SAP_B1",
  "timestamp": "2024-01-17T10:30:00",
  "records": [
    {
      "item_code": "ITEM001",
      "po_date": "2024-01-15",
      "ordered_qty": 500.0,
      "vendor_code": "VENDOR001"
    }
  ]
}
```

---

## 🔒 Encryption (Required)

```python
import hashlib, base64
from cryptography.fernet import Fernet

key = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
hashed = hashlib.sha256(key.encode()).digest()
fernet_key = base64.b64encode(hashed)
fernet = Fernet(fernet_key)

payload = {...}  # Your data
encrypted = fernet.encrypt(json.dumps(payload).encode()).decode()
```

Send: `{"encrypted_payload": encrypted}`

---

## ✅ Response

**Success:**
```json
{"success": true, "records_processed": 1}
```

**Error:**
```json
{"success": false, "errors": ["error message"]}
```

---

## 📞 Full Documentation

See: `SAP_MIDDLEWARE_INTEGRATION_GUIDE.md`

---

**Last Updated:** 2026-01-17
**Status:** ✅ Ready for Integration
