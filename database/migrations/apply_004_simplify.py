#!/usr/bin/env python3
"""
Apply migration 004 to Railway PostgreSQL database.
Simplifies sales_orders and purchase_orders to remove order tracking requirements.
"""
import sys
import os
from pathlib import Path

# Add ingestion_service to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ingestion_service"))

try:
    from sqlalchemy import create_engine, text
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Install: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


def get_database_url():
    """Get database URL from Railway environment variable."""
    # Try to get from environment
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        return database_url

    # If not in environment, try Railway CLI
    print("DATABASE_URL not found in environment variables.")
    print("Attempting to get from Railway CLI...")

    try:
        import subprocess
        result = subprocess.run(
            ['railway', 'variables'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent / "ingestion_service"
        )

        if result.returncode == 0:
            # Parse Railway output to find DATABASE_URL
            for line in result.stdout.split('\n'):
                if 'DATABASE_URL' in line:
                    # Extract URL from Railway table format
                    parts = line.split('│')
                    if len(parts) >= 3:
                        url = parts[2].strip()
                        if url.startswith('postgresql://'):
                            return url
    except Exception as e:
        print(f"Warning: Could not get DATABASE_URL from Railway CLI: {e}")

    print("\nERROR: Could not determine DATABASE_URL")
    print("\nPlease set DATABASE_URL environment variable:")
    print("  export DATABASE_URL='postgresql://...'")
    print("\nOr run from the Railway project directory where railway.toml exists")
    sys.exit(1)


def apply_migration():
    """Apply migration 004 to Railway database."""
    database_url = get_database_url()

    print(f"Database URL: {database_url[:40]}...")

    # Read migration SQL
    migration_file = Path(__file__).parent / "004_simplify_order_tables.sql"
    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    print("=" * 70)
    print("Applying Migration 004: Simplify Order Tables")
    print("=" * 70)
    print()

    try:
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            # Check current state
            print("Checking current schema...")

            # Check for id column in sales_orders
            result = conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'sales_orders'
                AND column_name IN ('id', 'order_number', 'line_number')
                ORDER BY column_name
            """))
            print("\nsales_orders columns:")
            for row in result:
                nullable = "NULL" if row[1] == 'YES' else "NOT NULL"
                print(f"  - {row[0]}: {nullable}")

            # Check for id column in purchase_orders
            result = conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'purchase_orders'
                AND column_name IN ('id', 'po_number', 'line_number')
                ORDER BY column_name
            """))
            print("\npurchase_orders columns:")
            for row in result:
                nullable = "NULL" if row[1] == 'YES' else "NOT NULL"
                print(f"  - {row[0]}: {nullable}")

            # Execute migration
            print("\nExecuting migration...")
            conn.execute(text(migration_sql))

            # Verify changes
            print("\nVerifying migration...")

            result = conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'sales_orders'
                AND column_name = 'id'
            """))
            if result.fetchone():
                print("✅ sales_orders.id column added")
            else:
                print("❌ sales_orders.id column NOT added")

            result = conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'purchase_orders'
                AND column_name = 'id'
            """))
            if result.fetchone():
                print("✅ purchase_orders.id column added")
            else:
                print("❌ purchase_orders.id column NOT added")

            # Check unique indexes
            result = conn.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'sales_orders'
                AND indexname LIKE '%business_key%'
            """))
            print("\n✅ Business key indexes created for sales_orders")

            result = conn.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'purchase_orders'
                AND indexname LIKE '%business_key%'
            """))
            print("✅ Business key indexes created for purchase_orders")

            # Commit transaction
            trans.commit()

            print()
            print("=" * 70)
            print("Migration 004 applied successfully!")
            print("=" * 70)
            print()
            print("Schema changes:")
            print("  - Added auto-increment 'id' column as primary key")
            print("  - Made order_number, line_number, po_number optional (nullable)")
            print("  - Created business key indexes for UPSERT conflict resolution")
            print()

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
