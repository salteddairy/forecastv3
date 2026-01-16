#!/usr/bin/env python3
"""
Test harness for SAP data ingestion service.
Simulates SAP middleware sending encrypted data.
"""
import os
import sys
import json
import base64
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Encryption key (should match Railway environment)
ENCRYPTION_KEY = os.environ.get("INGESTION_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_data(data: dict) -> str:
    """Encrypt data payload as middleware would."""
    json_str = json.dumps(data)
    return cipher.encrypt(json_str.encode()).decode()


def create_sample_items_data() -> dict:
    """Create sample items data for testing."""
    return {
        "data_type": "items",
        "source": "SAP_B1",
        "timestamp": datetime.now().isoformat(),
        "records": [
            {
                "item_code": "TEST001",
                "item_description": "Test Item 1",
                "item_group": "Electronics",
                "region": "North",
                "uom": "EA",
                "is_active": True
            },
            {
                "item_code": "TEST002",
                "item_description": "Test Item 2",
                "item_group": "Electronics",
                "region": "South",
                "uom": "EA",
                "is_active": True
            }
        ]
    }


def create_sample_inventory_data() -> dict:
    """Create sample inventory data for testing."""
    return {
        "data_type": "inventory_current",
        "source": "SAP_B1",
        "timestamp": datetime.now().isoformat(),
        "records": [
            {
                "item_code": "TEST001",
                "warehouse_code": "01",
                "on_hand_qty": 100.0,
                "on_order_qty": 50.0,
                "committed_qty": 25.0,
                "available_qty": 75.0,
                "uom": "EA"
            }
        ]
    }


def create_sample_sales_data() -> dict:
    """Create sample sales orders data for testing."""
    return {
        "data_type": "sales_orders",
        "source": "SAP_B1",
        "timestamp": datetime.now().isoformat(),
        "records": [
            {
                "order_id": "SO-2026-001",
                "item_code": "TEST001",
                "order_date": "2026-01-15",
                "quantity": 10.0,
                "uom": "EA",
                "warehouse_code": "01",
                "customer_code": "CUST001",
                "region": "North"
            }
        ]
    }


def test_encryption_decryption():
    """Test that encryption/decryption works."""
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing encryption/decryption...")

    sample = create_sample_items_data()
    encrypted = encrypt_data(sample)

    try:
        decrypted = cipher.decrypt(encrypted.encode()).decode()
        decrypted_data = json.loads(decrypted)

        assert decrypted_data == sample, "Decrypted data doesn't match original"
        print("  [OK] Encryption/decryption working")
        return True
    except Exception as e:
        print(f"  [FAIL] Encryption test failed: {e}")
        return False


def generate_test_payloads():
    """Generate all test payloads for manual testing."""
    payloads = {
        "items_encrypted.json": encrypt_data(create_sample_items_data()),
        "inventory_encrypted.json": encrypt_data(create_sample_inventory_data()),
        "sales_encrypted.json": encrypt_data(create_sample_sales_data()),
    }
    
    # Save to test data directory
    test_dir = Path(__file__).parent / "test_data"
    test_dir.mkdir(exist_ok=True)
    
    for filename, payload in payloads.items():
        filepath = test_dir / filename
        with open(filepath, 'w') as f:
            json.dump({"encrypted_payload": payload}, f, indent=2)
        print(f"  Created: {filepath}")
    
    # Also save unencrypted versions for reference
    unencrypted = {
        "items_sample.json": create_sample_items_data(),
        "inventory_sample.json": create_sample_inventory_data(),
        "sales_sample.json": create_sample_sales_data(),
    }
    
    for filename, data in unencrypted.items():
        filepath = test_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Created: {filepath}")


def print_curl_commands(ingestion_url: str):
    """Print curl commands for manual testing."""
    test_dir = Path(__file__).parent / "test_data"
    
    print("\n" + "="*60)
    print("CURL COMMANDS FOR MANUAL TESTING")
    print("="*60)
    
    for encrypted_file in ["items_encrypted.json", "inventory_encrypted.json", "sales_encrypted.json"]:
        filepath = test_dir / encrypted_file
        if filepath.exists():
            print(f"\n# Test {encrypted_file}:")
            print(f"curl -X POST {ingestion_url} \\")
            print(f"  -H 'Content-Type: application/json' \\")
            print(f"  -H 'X-API-Key: YOUR_API_KEY' \\")
            print(f"  -d @{filepath.absolute()}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test harness for ingestion service")
    parser.add_argument("--test-encryption", action="store_true", help="Test encryption only")
    parser.add_argument("--generate-payloads", action="store_true", help="Generate test payloads")
    parser.add_argument("--url", default="http://localhost:8000/api/ingest", help="Ingestion endpoint URL")
    
    args = parser.parse_args()
    
    print("="*60)
    print("SAP DATA INGESTION TEST HARNESS")
    print("="*60)
    
    if args.test_encryption:
        test_encryption_decryption()
    elif args.generate_payloads:
        test_encryption_decryption()
        generate_test_payloads()
        print_curl_commands(args.url)
    else:
        # Run all tests
        test_encryption_decryption()
        generate_test_payloads()
        print_curl_commands(args.url)
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. Start your ingestion service (see docs/ingestion-service.md)")
        print("2. Use the curl commands above to test each endpoint")
        print("3. Check Railway database for inserted records")
        print("4. Verify encryption/decryption worked correctly")
