#!/usr/bin/env python3
"""
Send all test data to Railway ingestion service.
"""
import requests
import json
from pathlib import Path

# Configuration
INGESTION_URL = "https://ingestion-service-production-6947.up.railway.app/api/ingest"
API_KEY = "BzYlIYXKMxzN49K28NBSDP1jK0FcvTQsuXIR5p0XgeM"
TEST_DATA_DIR = Path(__file__).parent

def send_payload(filename):
    """Send encrypted payload to ingestion service."""
    print(f"Sending {filename}...")

    with open(TEST_DATA_DIR / filename, 'r') as f:
        payload = json.load(f)

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(INGESTION_URL, json=payload, headers=headers)
    result = response.json()

    if result.get('success'):
        print(f"  [OK] {result.get('records_processed', 0)} records processed")
    else:
        print(f"  [FAIL] {result.get('message', 'Unknown error')}")
        if result.get('errors'):
            for error in result['errors']:
                print(f"    - {error}")

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
    print(f"Results: {success_count}/{len(files)} successful")
    print("=" * 70)

if __name__ == "__main__":
    main()
