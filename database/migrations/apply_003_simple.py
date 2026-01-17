#!/usr/bin/env python3
"""
Apply migration 003 to Railway PostgreSQL database.
Uses DATABASE_URL environment variable or Railway CLI connection.
"""
import sys
import os
from pathlib import Path

# Railway PostgreSQL connection string from environment variable
# Set via: export DATABASE_URL="postgresql://user:pass@host:port/database"
# Or use Railway CLI to get connection string
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable not set")
    print("Set it using: export DATABASE_URL='postgresql://user:password@host:port/database'")
    print("Or get it from Railway CLI: railway domain --json")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not available")
    print("Install: pip install psycopg2-binary")
    sys.exit(1)


def apply_migration():
    """Apply migration 003 to Railway database."""
    # Read migration SQL
    migration_file = Path(__file__).parent / "003_add_line_number_columns.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    print("=" * 70)
    print("Applying Migration 003: Add line_number Columns")
    print("=" * 70)
    print()

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()

        # Execute migration
        print("Executing migration...")
        cursor.execute(migration_sql)

        # Verify sales_orders
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sales_orders' AND column_name = 'line_number'
        """)
        if cursor.fetchone():
            print("✅ sales_orders.line_number column exists")
        else:
            print("❌ sales_orders.line_number column NOT found")

        # Verify purchase_orders
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'purchase_orders' AND column_name = 'line_number'
        """)
        if cursor.fetchone():
            print("✅ purchase_orders.line_number column exists")
        else:
            print("❌ purchase_orders.line_number column NOT found")

        # Commit transaction
        conn.commit()
        print()
        print("=" * 70)
        print("Migration 003 applied successfully!")
        print("=" * 70)

        cursor.close()
        conn.close()

    except Exception as e:
        print()
        print("=" * 70)
        print(f"ERROR: Migration failed!")
        print(f"Error: {e}")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    apply_migration()
