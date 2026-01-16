# BX010155-EDM Analysis Results

**Date:** 2026-01-16
**Source:** SAP B1 Query Results

---

## Query 1 Results: Complete Item Analysis

### Item Master
- **Item Code:** BX010155-EDM
- **Description:** Bag Filters No. 2, 5 Micron
- **UoM:** EA (Base), Ea (Purchasing), Ea (Sales)
- **Vendor:** V00604 - ENERGY TECHNOLOGY PRODUCTS LTD. - ABTEC FILTERS

### Warehouse Data

| Warehouse | Name | On Hand | On Order | Committed | Available | Cost | Value | Future Code |
|-----------|------|---------|----------|-----------|-----------|------|-------|-------------|
| **40** | Edmonton | **12.00** | 0.00 | 0.00 | **12.00** | $0.00 | $0.00 | 040-EDM1 |
| 05 | Finished Goods | 0.00 | 0.00 | 0.00 | 0.00 | $0.00 | $0.00 | 005-FIN1 |

**Total Value:** $0.00 (Unit cost shows $0.00 - likely data issue)

### Sales (Last 12 Months)
- **Order Count:** 2 sales orders
- **Total Ordered:** 11 units
- **Total Shipped:** 11 units
- **Total Value:** $832.00

**Sales Price:** ~$75.64 per unit ($832 / 11)

### Purchases (Last 12 Months)
- **PO Count:** 2 purchase orders
- **Total Ordered:** 60 units
- **Total Value:** $288.00

**Purchase Price:** ~$4.80 per unit ($288 / 60)

### Lead Times
- **Data Missing** - No lead time data available

---

## Key Findings

### 1. Multi-Warehouse Confirmed ✅
BX010155-EDM exists in **2 warehouses**:
- Warehouse 40 (Edmonton) - Active location with stock
- Warehouse 05 (Finished Goods) - Empty

### 2. Unit Cost Issue ⚠️
- **Unit cost shows $0.00** - This is likely a data issue
- Purchase price from POs: **$4.80/unit** (from $288 / 60)
- Sales price from orders: **$75.64/unit** (from $832 / 11)
- **Gross margin:** ~93% (very healthy!)

### 3. Sales vs Purchases
- **Purchased:** 60 units (2 POs)
- **Sold:** 11 units (2 orders)
- **On hand:** 12 units
- **Implies:** 60 - 11 - 12 = 37 units unaccounted for
- **Possible:** Other sales not in last 12 months, or data gap

### 4. Regional Variants
Still need Query 2 results to see:
- BX010155-CGY (Calgary variant)
- BX010155-TOR (Toronto variant)
- Other regional variants

---

## Next Steps

1. ✅ Query 1 complete - Analyzing above
2. ⏳ Query 2 pending - Need to re-run with fixed SQL
3. ⏳ Query 3 pending - Need to re-run with fixed SQL

---

**Status:** Awaiting Query 2 and 3 results
