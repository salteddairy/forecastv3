#!/usr/bin/env python3
"""
Apply migration 003 to Railway PostgreSQL database.
Uses ingestion_service config to get DATABASE_URL.
"""
import sys
import os
from pathlib import Path

# Add ingestion_service to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ingestion_service"))

try:
    from sqlalchemy import create_engine, text
    from app.config import get_settings
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    sys.exit(1)


def apply_migration():
    """Apply migration 003 to Railway database."""
    settings = get_settings()
    database_url = settings.database_url

    print(f"Database URL: {database_url[:30]}...")

    # Read migration SQL
    migration_file = Path(__file__).parent / "003_add_line_number_columns.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    print("=" * 70)
    print("Applying Migration 003: Add line_number Columns")
    print("=" * 70)
    print()

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            # Execute migration
            print("Executing migration...")
            conn.execute(text(migration_sql))

            # Verify sales_orders
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'sales_orders' AND column_name = 'line_number'
            """))
            if result.fetchone():
                print("✅ sales_orders.line_number column exists")
            else:
                print("❌ sales_orders.line_number column NOT found")

            # Verify purchase_orders
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'purchase_orders' AND column_name = 'line_number'
            """))
            if result.fetchone():
                print("✅ purchase_orders.line_number column exists")
            else:
                print("❌ purchase_orders.line_number column NOT found")

            # Commit transaction
            trans.commit()
            print()
            print("=" * 70)
            print("Migration 003 applied successfully!")
            print("=" * 70)

    except Exception as e:
        print()
        print("=" * 70)
        print(f"ERROR: Migration failed!")
        print(f"Error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    apply_migration()
