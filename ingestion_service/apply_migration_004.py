#!/usr/bin/env python3
"""
Apply migration 004 to Railway database.
Simplifies order tables to remove order tracking requirements.
"""
import sys
sys.path.insert(0, ".")

from app.database import Database
from sqlalchemy import text

# Read migration SQL
with open('../database/migrations/004_simplify_order_tables.sql', 'r') as f:
    migration_sql = f.read()

print("Applying Migration 004: Simplify Order Tables")
print("=" * 60)

db = Database()

try:
    with db.get_connection() as conn:
        # Check current state
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sales_orders'
            AND column_name = 'id'
        """))
        has_id = result.fetchone() is not None

        if has_id:
            print("✅ Migration already applied (id column exists)")
            sys.exit(0)

        # Apply migration
        print("Executing migration...")
        trans = conn.begin()
        conn.execute(text(migration_sql))
        trans.commit()

        # Verify
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sales_orders'
            AND column_name = 'id'
        """))
        if result.fetchone():
            print("✅ sales_orders.id column created")

        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'purchase_orders'
            AND column_name = 'id'
        """))
        if result.fetchone():
            print("✅ purchase_orders.id column created")

        print()
        print("=" * 60)
        print("Migration 004 applied successfully!")
        print("=" * 60)

except Exception as e:
    print()
    print("=" * 60)
    print(f"ERROR: {e}")
    print("=" * 60)
    sys.exit(1)
