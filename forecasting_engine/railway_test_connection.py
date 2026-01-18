"""
Railway Database Connection Test Script

Run this script within Railway's network to test the database connection.
Can be run using: railway run python railway_test_connection.py
"""
import os
import sys

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

print('=' * 60)
print('RAILWAY DATABASE CONNECTION TEST')
print('=' * 60)
print()

if not DATABASE_URL:
    print('[ERROR] DATABASE_URL environment variable not set')
    print('Please run this within Railway infrastructure')
    sys.exit(1)

print(f'DATABASE_URL: {DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else "unknown"}')
print()

# Test connection
try:
    from forecasting_engine.db import test_connection, get_database_version, get_session
    from sqlalchemy import text

    print('Testing database connection...')
    result = test_connection()

    if result:
        print('[OK] Database connection successful')

        # Get database version
        version = get_database_version()
        print(f'[OK] Database version: {version}')
        print()

        # Test sales_orders table
        with get_session() as session:
            print('Testing sales_orders table...')

            # Check if table exists
            exists = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'sales_orders'
                )
            """)).scalar()

            if exists:
                print('[OK] sales_orders table exists')

                # Get record count
                count = session.execute(text('SELECT COUNT(*) FROM sales_orders')).scalar()
                print(f'[OK] {count:,} sales records')

                # Get date range
                result = session.execute(text("""
                    SELECT
                        MIN(posting_date) as min_date,
                        MAX(posting_date) as max_date,
                        COUNT(DISTINCT item_code) as unique_items
                    FROM sales_orders
                """)).fetchone()

                print(f'[OK] Date range: {result[0]} to {result[1]}')
                print(f'[OK] Unique items: {result[2]:,}')

                # Get sample data
                samples = session.execute(text("""
                    SELECT
                        item_code,
                        posting_date,
                        ordered_qty,
                        warehouse_code
                    FROM sales_orders
                    ORDER BY posting_date DESC
                    LIMIT 5
                """)).fetchall()

                print()
                print('Sample sales_orders data:')
                for i, row in enumerate(samples, 1):
                    print(f'  {i}. {row[0]} | {row[1]} | Qty: {row[2]} | Whse: {row[3]}')
            else:
                print('[WARN] sales_orders table does not exist')

            print()

            # Test forecasts table
            print('Testing forecasts table...')
            exists = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'forecasts'
                )
            """)).scalar()

            if exists:
                print('[OK] forecasts table exists')

                # Count existing forecasts
                count = session.execute(text('SELECT COUNT(*) FROM forecasts')).scalar()
                print(f'[OK] {count:,} forecast records')

                # Check active forecasts
                active = session.execute(text("""
                    SELECT COUNT(*) FROM forecasts WHERE status = 'Active'
                """)).scalar()
                print(f'[OK] {active:,} active forecasts')
            else:
                print('[WARN] forecasts table does not exist')

            print()

            # Test forecast_accuracy table
            print('Testing forecast_accuracy table...')
            exists = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'forecast_accuracy'
                )
            """)).scalar()

            if exists:
                print('[OK] forecast_accuracy table exists')

                # Count records
                count = session.execute(text('SELECT COUNT(*) FROM forecast_accuracy')).scalar()
                print(f'[OK] {count:,} accuracy records')
            else:
                print('[WARN] forecast_accuracy table does not exist')

            print()

            # Test materialized views
            print('Testing materialized views...')
            views = session.execute(text("""
                SELECT matviewname FROM pg_matviews
                WHERE matviewname IN (
                    'mv_forecast_summary',
                    'mv_forecast_accuracy_summary',
                    'mv_latest_costs',
                    'mv_latest_pricing',
                    'mv_vendor_lead_times'
                )
                ORDER BY matviewname
            """)).fetchall()

            if views:
                print(f'[OK] Found {len(views)} materialized views:')
                for view in views:
                    print(f'     - {view[0]}')
            else:
                print('[WARN] No materialized views found')

        print()
        print('=' * 60)
        print('✅ ALL TESTS PASSED - READY FOR FORECASTING')
        print('=' * 60)
        sys.exit(0)

    else:
        print('[FAIL] Database connection failed')
        sys.exit(1)

except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
