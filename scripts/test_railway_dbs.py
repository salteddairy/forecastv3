#!/usr/bin/env python3
"""
Test which Railway PostgreSQL service has the schema.
Uses DATABASE_URL environment variable.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
import os

sys.stdout.reconfigure(encoding='utf-8')

# Get Railway PostgreSQL connection string from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable not set")
    print("Set it using: export DATABASE_URL='postgresql://user:password@host:port/database'")
    print("Or get it from Railway CLI: railway domain --json")
    sys.exit(1)

print(f"Testing Railway PostgreSQL connection...\n")
print(f"Testing: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL, connect_args={'connect_timeout': 5})
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
