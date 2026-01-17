#!/usr/bin/env python3
"""
Test which Railway PostgreSQL service has the schema.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
import os

sys.stdout.reconfigure(encoding='utf-8')

# Test connections
database_urls = [
    "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@postgres.railway.internal:5432/railway",
    "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@interchange.proxy.rlwy.net:46687/railway",
]

print("Testing Railway PostgreSQL connections...\n")

for i, url in enumerate(database_urls, 1):
    print(f"[{i}] Testing: {url.split('@')[1] if '@' in url else url}")

    try:
        engine = create_engine(url, connect_args={'connect_timeout': 5})
        with engine.connect() as conn:
            # Check for items table
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'items'
                );
            """))
            has_items = result.scalar()

            if has_items:
                print(f"    ✓ Connected - Has 'items' table")

                # Count records
                count = conn.execute(text("SELECT COUNT(*) FROM items")).scalar()
                print(f"    - Items count: {count}")

            else:
                print(f"    ✓ Connected - No 'items' table (empty schema)")

    except Exception as e:
        print(f"    ✗ Failed: {str(e)[:100]}")

    print()
