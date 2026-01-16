# SAP Query Results

This folder contains TSV files exported from SAP B1 queries.

## IMPORTANT - Use Separate SQL Query Files

**Query 1 (COMPLETE):** `queries/analyze_multi_warehouse_item_fixed.sql`
**Query 2:** `queries/query2_regional_variants.sql`
**Query 3:** `queries/query3_transaction_history.sql`

Each query is a separate file with its own variable declarations (SAP B1 requires this).

## Files

### query1_complete_item_analysis.tsv
Complete item analysis with:
- Item master data (UoM, vendor, conversion factors)
- Warehouse quantities
- Sales summary (12 months)
- Purchase summary (12 months)
- Lead time analysis
- Future warehouse code mapping

### query2_regional_variants.tsv
All regional variants of a base item that will consolidate:
- Current item codes (BX010155-EDM, BX010155-CGY, etc.)
- Stock levels by warehouse
- Future warehouse mapping
- Consolidated item code

### query3_transaction_history.tsv
Recent transaction history (last 6 months):
- Sales orders with customer info
- Purchase orders with vendor info and lead times
- Sorted by date descending

## Usage

1. Run the SQL queries in SAP B1 (using `queries/analyze_multi_warehouse_item_fixed.sql`)
2. Copy results to clipboard
3. Paste into the corresponding TSV file in this folder
4. Run the consolidation test script to validate

## Notes

- Use tab-separated values (TSV) format
- Include headers from SQL query output
- Ensure date formatting is consistent (YYYY-MM-DD)

## Troubleshooting

If you get errors about missing columns:
1. Check your SAP B1 version column names
2. The fixed SQL version handles most SAP B1 versions
3. Contact support if issues persist
