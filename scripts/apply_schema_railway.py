#!/usr/bin/env python3
"""
Standalone script to apply database schema to Railway PostgreSQL.
Run this from the project root directory.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from sqlalchemy import create_engine, text
except ImportError as e:
    print(f"Error: Required package not found: {e}")
    print("Please install: pip install psycopg2-binary sqlalchemy")
    sys.exit(1)


def apply_schema(database_url: str, schema_file: str):
    """
    Apply database schema from SQL file to PostgreSQL database.

    Args:
        database_url: PostgreSQL connection URL
        schema_file: Path to schema SQL file
    """
    sys.stdout.reconfigure(encoding='utf-8')
    print("Connecting to Railway PostgreSQL...")

    try:
        # Read schema file
        schema_path = Path(schema_file)
        if not schema_path.exists():
            print(f"Schema file not found: {schema_file}")
            sys.exit(1)

        print(f"Reading schema from: {schema_file}")
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Connect and execute schema
        print("Applying schema to database...")
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Execute the schema
            conn.execute(text(schema_sql))
            conn.commit()

            # Check created tables
            result = conn.execute(text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename;
            """))
            tables = [row[0] for row in result]

            print(f"\nSchema applied successfully!")
            print(f"Created {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")

            # Check materialized views
            result = conn.execute(text("""
                SELECT matviewname
                FROM pg_matviews
                WHERE schemaname = 'public'
                ORDER BY matviewname;
            """))
            matviews = [row[0] for row in result]

            if matviews:
                print(f"\nCreated {len(matviews)} materialized views:")
                for mv in matviews:
                    print(f"   - {mv}")

            # Check regular views
            result = conn.execute(text("""
                SELECT viewname
                FROM pg_views
                WHERE schemaname = 'public'
                ORDER BY viewname;
            """))
            views = [row[0] for row in result]

            if views:
                print(f"\nCreated {len(views)} views:")
                for view in views:
                    print(f"   - {view}")

        print("\nDatabase schema setup complete!")

    except Exception as e:
        print(f"\nError applying schema: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')

    # Get DATABASE_URL from environment or Railway
    if len(sys.argv) > 1:
        database_url = sys.argv[1]
    else:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            print("DATABASE_URL not set!")
            print("\nUsage:")
            print("  python scripts/apply_schema_railway.py <DATABASE_URL>")
            print("\nOr set DATABASE_URL environment variable:")
            print("  set DATABASE_URL=postgresql://...")
            print("  python scripts/apply_schema_railway.py")
            sys.exit(1)

    schema_file = "database/migrations/001_initial_schema.sql"

    apply_schema(database_url, schema_file)
