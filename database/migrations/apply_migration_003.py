#!/usr/bin/env python3
"""
Apply migration 003 to Railway PostgreSQL database.
Adds line_number column to sales_orders and purchase_orders tables.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from sqlalchemy import create_engine, text
    import os
except ImportError:
    print("Error: Required packages not available")
    print("Install: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


def apply_migration():
    """Apply migration 003 to Railway database."""
    # Get DATABASE_URL from environment or Railway CLI
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        # Try to get from Railway settings
        try:
            import subprocess
            result = subprocess.run(
                ['railway', 'variables', 'get', 'DATABASE_URL'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                database_url = result.stdout.strip()
        except Exception as e:
            print(f"Warning: Could not get DATABASE_URL from Railway CLI: {e}")

    if not database_url:
        print("Error: DATABASE_URL not found")
        print("Set DATABASE_URL environment variable or run from Railway project")
        sys.exit(1)

    engine = create_engine(database_url)

    # Read migration SQL
    migration_file = Path(__file__).parent / "003_add_line_number_columns.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    print("=" * 70)
    print("Applying Migration 003: Add line_number Columns")
    print("=" * 70)
    print()

    try:
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
        sys.exit(1)


if __name__ == "__main__":
    apply_migration()
