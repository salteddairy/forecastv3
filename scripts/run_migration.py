#!/usr/bin/env python3
"""Run database migration from SQL file."""
import sys
from pathlib import Path

import psycopg2

# Database connection
DATABASE_URL = "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@interchange.proxy.rlwy.net:46687/railway"

# Migration file path
MIGRATION_FILE = Path(__file__).parent.parent / "database" / "migrations" / "001_initial_schema.sql"


def run_migration():
    """Execute the SQL migration file."""
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    print(f"Reading migration file: {MIGRATION_FILE}")
    with open(MIGRATION_FILE, 'r') as f:
        sql = f.read()

    print("Executing migration...")
    # Split by semicolon and execute each statement
    statements = []
    current = []
    for line in sql.split('\n'):
        # Skip comments
        if line.strip().startswith('--'):
            continue
        current.append(line)
        if line.strip().endswith(';'):
            statements.append('\n'.join(current))
            current = []

    # Add any remaining statement
    if current:
        statements.append('\n'.join(current))

    executed = 0
    for statement in statements:
        statement = statement.strip()
        if statement and not statement.startswith('--'):
            try:
                cursor.execute(statement)
                executed += 1
            except Exception as e:
                # Check if it's a "already exists" error, which is OK
                if "already exists" in str(e):
                    print(f"  [OK] Already exists: {str(e)[:100]}...")
                    executed += 1
                else:
                    print(f"  [X] Error: {e}")
                    print(f"  Statement: {statement[:200]}...")

    print(f"\nMigration complete! Executed {executed} statements.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    run_migration()
