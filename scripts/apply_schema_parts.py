#!/usr/bin/env python3
"""
Apply database schema in parts to isolate errors.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
try:
    from sqlalchemy import create_engine, text
except ImportError as e:
    print(f"Error: Required package not found: {e}")
    sys.exit(1)

sys.stdout.reconfigure(encoding='utf-8')

def apply_schema_part(database_url: str, schema_file: str, part_name: str):
    """Apply one part of the schema."""
    print(f"\nApplying {part_name}...")
    print(f"Reading from: {schema_file}")

    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Remove PRINT statements (PostgreSQL doesn't support them)
        import re
        schema_sql = re.sub(r"PRINT '[^']*';", '', schema_sql)

        engine = create_engine(database_url)

        with engine.connect() as conn:
            conn.execute(text(schema_sql))
            conn.commit()

        print(f"[SUCCESS] {part_name} applied")
        return True

    except Exception as e:
        print(f"[ERROR] {part_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_schema_parts.py <DATABASE_URL>")
        sys.exit(1)

    database_url = sys.argv[1]
    migrations_dir = Path("database/migrations")

    parts = [
        ("001a_tables_only.sql", "Part 1: Tables"),
        ("001b_materialized_views.sql", "Part 2: Materialized Views"),
        ("001c_views.sql", "Part 3: Views"),
    ]

    print("Applying schema in parts...")

    all_success = True
    for filename, part_name in parts:
        schema_path = migrations_dir / filename
        if not schema_path.exists():
            print(f"[SKIP] {filename} not found")
            continue

        success = apply_schema_part(database_url, str(schema_path), part_name)
        if not success:
            all_success = False
            print(f"\nStopping due to error in {part_name}")
            break

    if all_success:
        print("\n[SUCCESS] All schema parts applied successfully!")
    else:
        print("\n[FAILED] Schema application incomplete")
        sys.exit(1)
