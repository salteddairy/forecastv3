#!/usr/bin/env python3
"""
Find which Railway PostgreSQL service has the schema.
"""
import sys
import subprocess
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

services = ['Postgres-qBea', 'Postgres-B08X']

for service_name in services:
    print(f"\nTesting {service_name}...")

    # Get DATABASE_PUBLIC_URL from Railway
    result = subprocess.run(
        ['railway', 'variables', '--service', service_name, '--json'],
        capture_output=True,
        text=True,
        cwd='ingestion_service'
    )

    if result.returncode != 0:
        print(f"  [ERROR] Could not get variables")
        continue

    try:
        data = json.loads(result.stdout)
        db_url = data.get('DATABASE_PUBLIC_URL')

        if not db_url:
            print(f"  [SKIP] No DATABASE_PUBLIC_URL")
            continue

        print(f"  URL: {db_url.split('@')[1] if '@' in db_url else db_url}")

        # Try to connect
        engine = create_engine(db_url, connect_args={'connect_timeout': 10})

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
                # Count records
                count = conn.execute(text("SELECT COUNT(*) FROM items")).scalar()
                print(f"  [SUCCESS] Has 'items' table with {count} records")
            else:
                print(f"  [INFO] Connected but no 'items' table")

    except json.JSONDecodeError:
        print(f"  [ERROR] Could not parse JSON response")
    except Exception as e:
        print(f"  [ERROR] {str(e)[:100]}")

print("\nDone.")
