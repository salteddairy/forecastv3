#!/usr/bin/env python3
"""
Generate test data for SAP middleware to send to Railway ingestion service.
Creates encrypted payloads for all supported data types.
"""
import sys
import json
import hashlib
import base64
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Error: cryptography package required")
    print("Install: pip install cryptography")
    sys.exit(1)

sys.stdout.reconfigure(encoding='utf-8')


# ============================================================================
# Configuration (matches Railway ingestion service)
# ============================================================================
ENCRYPTION_KEY = "RLeqML3xLZBrghpFDBCs7q9aqcLr4FEoGxtBCL3DFfA="
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
INGESTION_URL = "https://ingestion-service-production-6947.up.railway.app/api/ingest"


def get_fernet_key(key: str) -> bytes:
    """Transform raw key to Fernet-compatible format."""
    hashed = hashlib.sha256(key.encode()).digest()
    return base64.b64encode(hashed)


def encrypt_payload(data: dict, key: str) -> str:
    """Encrypt payload using Fernet symmetric encryption."""
    fernet_key = get_fernet_key(key)
    fernet = Fernet(fernet_key)
    json_data = json.dumps(data).encode('utf-8')
    encrypted = fernet.encrypt(json_data)
    return encrypted.decode('utf-8')


def create_ingestion_payload(data_type: str, records: list) -> dict:
    """Create ingestion payload with timestamp and metadata."""
    return {
        "data_type": data_type,
        "source": "SAP_B1",
        "timestamp": datetime.now().isoformat(),
        "records": records
    }


# ============================================================================
# Sample Data Generators
# ============================================================================

def generate_items_data():
    """Generate sample items master data."""
    return [
        {
            "item_code": "ITEM001",
            "item_description": "Industrial Widget A - Premium Grade",
            "item_group": "WIDGETS",
            "region": "NORTH_AMERICA",
            "base_uom": "EA",
            "purch_uom": "EA",
            "qty_per_purch_uom": 1,
            "sales_uom": "EA",
            "qty_per_sales_uom": 1,
            "preferred_vendor_code": "VENDOR001",
            "is_active": True
        },
        {
            "item_code": "ITEM002",
            "item_description": "Hydraulic Piston Assembly - 50mm",
            "item_group": "HYDRAULICS",
            "region": "NORTH_AMERICA",
            "base_uom": "EA",
            "purch_uom": "EA",
            "qty_per_purch_uom": 1,
            "sales_uom": "EA",
            "qty_per_sales_uom": 1,
            "preferred_vendor_code": "VENDOR002",
            "is_active": True
        },
        {
            "item_code": "ITEM003",
            "item_description": "Steel Bearing - 20mm Diameter",
            "item_group": "BEARINGS",
            "region": "EUROPE",
            "base_uom": "EA",
            "purch_uom": "BX",
            "qty_per_purch_uom": 100,
            "sales_uom": "EA",
            "qty_per_sales_uom": 1,
            "preferred_vendor_code": "VENDOR001",
            "is_active": True
        }
    ]


def generate_vendors_data():
    """Generate sample vendors master data."""
    return [
        {
            "vendor_code": "VENDOR001",
            "vendor_name": "Acme Industrial Supplies Inc.",
            "contact_name": "John Smith",
            "email": "john.smith@acmeindustrial.com",
            "phone": "+1-555-0101"
        },
        {
            "vendor_code": "VENDOR002",
            "vendor_name": "Global Parts Manufacturing LLC",
            "contact_name": "Sarah Johnson",
            "email": "sarah.johnson@globalparts.com",
            "phone": "+1-555-0102"
        },
        {
            "vendor_code": "VENDOR003",
            "vendor_name": "EuroTech Components GmbH",
            "contact_name": "Hans Mueller",
            "email": "hans.mueller@eurotech.de",
            "phone": "+49-30-123456"
        }
    ]


def generate_warehouses_data():
    """Generate sample warehouse/location data."""
    return [
        {
            "warehouse_code": "WH01",
            "warehouse_name": "Main Distribution Center",
            "region": "NORTH_AMERICA",
            "is_active": True
        },
        {
            "warehouse_code": "WH02",
            "warehouse_name": "West Coast Warehouse",
            "region": "NORTH_AMERICA",
            "is_active": True
        },
        {
            "warehouse_code": "WH03",
            "warehouse_name": "European Distribution Hub",
            "region": "EUROPE",
            "is_active": True
        }
    ]


def generate_inventory_data():
    """Generate sample inventory current levels."""
    return [
        {
            "item_code": "ITEM001",
            "warehouse_code": "WH01",
            "on_hand_qty": 1500.0,
            "on_order_qty": 500.0,
            "committed_qty": 200.0,
            "available_qty": 1300.0,
            "uom": "EA"
        },
        {
            "item_code": "ITEM001",
            "warehouse_code": "WH02",
            "on_hand_qty": 750.0,
            "on_order_qty": 0.0,
            "committed_qty": 100.0,
            "available_qty": 650.0,
            "uom": "EA"
        },
        {
            "item_code": "ITEM002",
            "warehouse_code": "WH01",
            "on_hand_qty": 200.0,
            "on_order_qty": 50.0,
            "committed_qty": 25.0,
            "available_qty": 175.0,
            "uom": "EA"
        }
    ]


def generate_sales_orders_data():
    """Generate sample sales orders."""
    base_date = datetime.now() - timedelta(days=30)
    return [
        {
            "posting_date": (base_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            "promise_date": (base_date + timedelta(days=8)).strftime('%Y-%m-%d'),
            "customer_code": "CUST001",
            "customer_name": "ABC Corporation",
            "item_code": "ITEM001",
            "item_description": "Industrial Widget A - Premium Grade",
            "ordered_qty": 100.0,
            "shipped_qty": 100.0,
            "row_value": 4500.00,
            "warehouse_code": "WH01",
            "document_type": "Document_Item"
        },
        {
            "posting_date": (base_date + timedelta(days=5)).strftime('%Y-%m-%d'),
            "promise_date": (base_date + timedelta(days=12)).strftime('%Y-%m-%d'),
            "customer_code": "CUST002",
            "customer_name": "XYZ Industries Ltd",
            "item_code": "ITEM002",
            "item_description": "Hydraulic Piston Assembly - 50mm",
            "ordered_qty": 50.0,
            "shipped_qty": 25.0,
            "row_value": 13750.00,
            "warehouse_code": "WH01",
            "document_type": "Document_Item"
        },
        {
            "posting_date": (base_date + timedelta(days=15)).strftime('%Y-%m-%d'),
            "promise_date": (base_date + timedelta(days=22)).strftime('%Y-%m-%d'),
            "customer_code": "CUST001",
            "customer_name": "ABC Corporation",
            "item_code": "ITEM001",
            "item_description": "Industrial Widget A - Premium Grade",
            "ordered_qty": 200.0,
            "shipped_qty": 0.0,
            "row_value": 9000.00,
            "warehouse_code": "WH02",
            "document_type": "Document_Item"
        }
    ]


def generate_purchase_orders_data():
    """Generate sample purchase orders."""
    base_date = datetime.now() - timedelta(days=45)
    return [
        {
            "po_date": (base_date + timedelta(days=2)).strftime('%Y-%m-%d'),
            "event_date": (base_date + timedelta(days=16)).strftime('%Y-%m-%d'),
            "vendor_code": "VENDOR001",
            "vendor_name": "Acme Industrial Supplies Inc.",
            "item_code": "ITEM001",
            "ordered_qty": 500.0,
            "received_qty": 500.0,
            "row_value": 14475.00,
            "currency": "CAD",
            "exchange_rate": 1.0,
            "warehouse_code": "WH01",
            "freight_terms": "FOB",
            "fob": "Origin",
            "lead_time_days": 14
        },
        {
            "po_date": (base_date + timedelta(days=10)).strftime('%Y-%m-%d'),
            "event_date": None,
            "vendor_code": "VENDOR002",
            "vendor_name": "Global Parts Manufacturing LLC",
            "item_code": "ITEM002",
            "ordered_qty": 50.0,
            "received_qty": 0.0,
            "row_value": 7875.00,
            "currency": "CAD",
            "exchange_rate": 1.0,
            "warehouse_code": "WH01",
            "freight_terms": "Prepaid",
            "fob": "Destination",
            "lead_time_days": 21
        }
    ]


def generate_costs_data():
    """Generate sample cost data."""
    base_date = datetime.now() - timedelta(days=60)
    return [
        {
            "item_code": "ITEM001",
            "unit_cost": 25.50,
            "freight": 2.30,
            "duty": 1.15,
            "total_landed_cost": 28.95,
            "currency": "USD",
            "effective_date": (base_date + timedelta(days=30)).strftime('%Y-%m-%d'),
            "vendor_code": "VENDOR001"
        },
        {
            "item_code": "ITEM002",
            "unit_cost": 145.00,
            "freight": 12.50,
            "duty": 0.00,
            "total_landed_cost": 157.50,
            "currency": "USD",
            "effective_date": (base_date + timedelta(days=45)).strftime('%Y-%m-%d'),
            "vendor_code": "VENDOR002"
        },
        {
            "item_code": "ITEM003",
            "unit_cost": 8.75,
            "freight": 0.85,
            "duty": 1.75,
            "total_landed_cost": 11.35,
            "currency": "USD",
            "effective_date": (base_date + timedelta(days=20)).strftime('%Y-%m-%d'),
            "vendor_code": "VENDOR001"
        }
    ]


def generate_pricing_data():
    """Generate sample pricing data."""
    base_date = datetime.now() - timedelta(days=90)
    return [
        {
            "item_code": "ITEM001",
            "price_level": "List",
            "region": "NORTH_AMERICA",
            "unit_price": 45.00,
            "currency": "CAD",
            "effective_date": (base_date + timedelta(days=60)).strftime('%Y-%m-%d'),
            "expiry_date": None,
            "price_source": "SAP_B1",
            "is_active": True
        },
        {
            "item_code": "ITEM001",
            "price_level": "Wholesale",
            "region": "NORTH_AMERICA",
            "unit_price": 38.25,
            "currency": "CAD",
            "effective_date": (base_date + timedelta(days=60)).strftime('%Y-%m-%d'),
            "expiry_date": None,
            "price_source": "SAP_B1",
            "is_active": True
        },
        {
            "item_code": "ITEM002",
            "price_level": "List",
            "region": None,
            "unit_price": 275.00,
            "currency": "CAD",
            "effective_date": (base_date + timedelta(days=45)).strftime('%Y-%m-%d'),
            "expiry_date": None,
            "price_source": "SAP_B1",
            "is_active": True
        },
        {
            "item_code": "ITEM003",
            "price_level": "List",
            "region": "EUROPE",
            "unit_price": 18.50,
            "currency": "EUR",
            "effective_date": (base_date + timedelta(days=30)).strftime('%Y-%m-%d'),
            "expiry_date": None,
            "price_source": "SAP_B1",
            "is_active": True
        }
    ]


# ============================================================================
# Main Generator
# ============================================================================

def main():
    """Generate all test data files."""
    print("=" * 70)
    print("SAP Middleware Test Data Generator")
    print("=" * 70)
    print()

    # Define output directory
    output_dir = Path(__file__).parent / "middleware_test_data"
    output_dir.mkdir(exist_ok=True)

    # Data generators
    data_generators = {
        "items": generate_items_data,
        "vendors": generate_vendors_data,
        "warehouses": generate_warehouses_data,
        "inventory_current": generate_inventory_data,
        "sales_orders": generate_sales_orders_data,
        "purchase_orders": generate_purchase_orders_data,
        "costs": generate_costs_data,
        "pricing": generate_pricing_data,
    }

    # Generate encrypted payloads for each data type
    for data_type, generator in data_generators.items():
        print(f"Generating {data_type}...")

        # Create ingestion payload
        records = generator()
        ingestion_payload = create_ingestion_payload(data_type, records)

        # Encrypt payload
        encrypted = encrypt_payload(ingestion_payload, ENCRYPTION_KEY)

        # Create final payload
        final_payload = {"encrypted_payload": encrypted}

        # Save to file
        filename = output_dir / f"{data_type}_encrypted.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_payload, f, indent=2)

        print(f"  [OK] {len(records)} records -> {filename.name}")

    # Generate README
    readme_content = f"""# SAP Middleware Test Data

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Files

This directory contains encrypted test payloads for all supported data types:

{" | ".join([f"- {dt}_encrypted.json" for dt in data_generators.keys()])}

## How to Use

### 1. Send to Railway Ingestion Service

```bash
curl -X POST "{INGESTION_URL}" \\
  -H "X-API-Key: {API_KEY}" \\
  -H "Content-Type: application/json" \\
  -d @<filename>
```

Example:
```bash
curl -X POST "{INGESTION_URL}" \\
  -H "X-API-Key: {API_KEY}" \\
  -H "Content-Type: application/json" \\
  -d @items_encrypted.json
```

### 2. Using Python

```python
import requests
import json

url = "{INGESTION_URL}"
headers = {{
    "X-API-Key": "{API_KEY}",
    "Content-Type": "application/json"
}}

with open("items_encrypted.json", "r") as f:
    payload = json.load(f)

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

### 3. Using PowerShell

```powershell
$headers = @{{
    "X-API-Key" = "{API_KEY}"
    "Content-Type" = "application/json"
}}

$body = Get-Content "items_encrypted.json" -Raw
Invoke-RestMethod -Uri "{INGESTION_URL}" -Method Post -Headers $headers -Body $body
```

## Configuration

- **Ingestion URL**: {INGESTION_URL}
- **API Key**: {API_KEY}
- **Encryption Key**: {ENCRYPTION_KEY}
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
{{
    "data_type": "items",
    "source": "SAP_B1",
    "timestamp": "2025-01-16T10:30:00",
    "records": [...]
}}
```

Encrypted format (sent to API):
```json
{{
    "encrypted_payload": "gAAAAABh..."
}}
```

## Verification

After sending, verify the data was ingested:

```bash
# Check health
curl {INGESTION_URL}/health

# Response should show:
# {{"status": "healthy", "database": "healthy", ...}}
```
"""

    readme_path = output_dir / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print()
    print(f"[OK] README.md created")

    # Create a master test script that sends all data
    test_script = f"""#!/usr/bin/env python3
\"\"\"
Send all test data to Railway ingestion service.
\"\"\"
import requests
import json
from pathlib import Path

# Configuration
INGESTION_URL = "{INGESTION_URL}"
API_KEY = "{API_KEY}"
TEST_DATA_DIR = Path(__file__).parent

def send_payload(filename):
    \"\"\"Send encrypted payload to ingestion service.\"\"\"
    print(f"Sending {{filename}}...")

    with open(TEST_DATA_DIR / filename, 'r') as f:
        payload = json.load(f)

    headers = {{
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }}

    response = requests.post(INGESTION_URL, json=payload, headers=headers)
    result = response.json()

    if result.get('success'):
        print(f"  [OK] {{result.get('records_processed', 0)}} records processed")
    else:
        print(f"  [FAIL] {{result.get('message', 'Unknown error')}}")
        if result.get('errors'):
            for error in result['errors']:
                print(f"    - {{error}}")

    return result.get('success', False)

def main():
    print("=" * 70)
    print("Sending Test Data to Railway Ingestion Service")
    print("=" * 70)
    print()

    # Order matters - send master data first
    files = [
        "warehouses_encrypted.json",
        "vendors_encrypted.json",
        "items_encrypted.json",
        "inventory_current_encrypted.json",
        "costs_encrypted.json",
        "pricing_encrypted.json",
        "sales_orders_encrypted.json",
        "purchase_orders_encrypted.json",
    ]

    success_count = 0
    for filename in files:
        if send_payload(filename):
            success_count += 1
        print()

    print("=" * 70)
    print(f"Results: {{success_count}}/{{len(files)}} successful")
    print("=" * 70)

if __name__ == "__main__":
    main()
"""

    script_path = output_dir / "send_all_test_data.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(test_script)

    print(f"[OK] send_all_test_data.py created")
    print()
    print("=" * 70)
    print(f"All test data generated successfully!")
    print(f"Location: {output_dir}")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Review the encrypted JSON files")
    print("2. Read README.md for usage instructions")
    print("3. Run 'python send_all_test_data.py' to send all data")
    print(f"4. Or send individual files using curl commands in README.md")


if __name__ == "__main__":
    main()
