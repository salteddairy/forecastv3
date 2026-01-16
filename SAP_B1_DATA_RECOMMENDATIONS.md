# SAP Business One Data Enhancement Recommendations

**Date:** 2026-01-13
**Status:** Strategic Data Analysis

---

## Current Data Import Summary

### ✅ Currently Imported from SAP B1

**1. Items Master (OITM)**
- Item identification: No., Description, ItemGroup
- UoM: BaseUoM, PurchUoM, QtyPerPurchUoM, SalesUoM, QtyPerSalesUoM
- Vendor: PreferredVendor, LastVendor (Code, Name, Date, Price)
- Stock: Warehouse, CurrentStock, IncomingStock, CommittedStock
- Cost/Ordering: UnitCost, MOQ, OrderMultiple

**2. Sales Orders (ORDR/RDR1)**
- Dates: Posting Date, PromiseDate
- Customer: CustomerCode
- Item: Item No., Description, OrderedQty, BacklogQty
- Value: RowValue
- Warehouse: Warehouse
- Flags: Linked_SpecialOrder_Num, Document Type

**3. Supply Chain (OPDN/OPOR)**
- Type: History (Receipts) / Schedule (Open POs)
- Vendor: VendorCode, VendorName
- Dates: PO_Date, EventDate
- Lead Time: LeadTimeDays
- Quantity/Value: Quantity, RowValue, Currency, ExchangeRate
- Logistics: FreightTerms, FOB

---

## 🎯 High Priority Additions (Quick Wins)

### 1. **Item Properties for Better Forecasting** ⭐⭐⭐

**SAP B1 Tables:** `OITM`, `OITB`

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Item Lifecycle Status** | `OITM.ValidFor`, `OITM.Frozen` | High | Exclude obsolete items from forecasts |
| **Item Creation Date** | `OITM.CreateDate` | High | Calculate product age, new product ramp-up |
| **Item Tree/Category Path** | `OITB.ItmsGrpCod`, hierarchy | High | Group forecasting by category |
| **Sales Item Flag** | `OITM.SellItem` | Medium | Filter out non-sales items (services, labor) |
| **Inventory Item Flag** | `OITM.PrchseItem` | Medium | Differently forecast purchased vs manufactured items |
| **Active Flag** | `OITM.LogInventory` | High | Only track items requiring inventory tracking |

**SQL Query for B1UP:**
```sql
SELECT
    T0."ItemCode",
    T0."ItemCode" AS "Item No.",
    T0."ItemName",
    T0."ItemName" AS "Item Description",
    T0."ItmsGrpCod",
    T1."ItmsGrpNam",
    T1."ItmsGrpNam" AS "ItemGroup",
    T0."SalUnitMsr",
    T0."SalUnitMsr" AS "SalesUoM",
    T0."NumInSale",
    T0."NumInSale" AS "QtyPerSalesUoM",
    -- EXISTING FIELDS...
    T0."CreateTS",
    T0."CreateTS" AS "CreateDate",
    T0."ValidFor",
    T0."Frozen",
    T0."LogInventory",
    T0."SellItem",
    T0."PrchseItem",
    T0."TreeType",
    T0."CardCode",
    T0."CardCode" AS "PreferredVendor"
FROM OITM T0
LEFT JOIN OITB T1 ON T0."ItmsGrpCod" = T1."ItmsGrpCod"
WHERE T0."LogInventory" = 'Y'  -- Only inventory items
  AND T0."ValidFor" = 'Y'      -- Only valid items
```

**Implementation Effort:** 1-2 hours (SQL query + update to ingestion.py)

---

### 2. **Customer Information for Demand Segmentation** ⭐⭐⭐

**SAP B1 Tables:** `OCRD` (Business Partners)

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Customer Type** | `OCRD.CardType` | High | Forecast differently for B2B vs B2C |
| **Customer Group** | `OCRD.GroupCode` | High | Segment by customer tier (Gold/Silver/Bronze) |
| **Customer Region/Territory** | `OCRD.County`, `OCRD.Territory` | Medium | Regional demand patterns |
| **Industry Code** | `OCRD.IndCode` | Medium | Industry-specific demand curves |
| **Credit Rating** | `OCRD.CreditLine` | Low | Prioritize fulfillment for high-credit customers |

**SQL Query for B1UP:**
```sql
SELECT
    T0."DocDate" AS "Posting Date",
    T0."DocDueDate" AS "PromiseDate",
    T1."CardCode" AS "CustomerCode",
    T1."CardCode" AS "CustomerCode",
    T2."CardName",
    T2."CardName" AS "CustomerName",
    T2."CardType",
    T2."CardType" AS "CustomerType",  -- 'C' for Customer, 'L' for Lead
    T2."GroupCode",
    T2."GroupCode" AS "CustomerGroup",
    T3."GroupName",
    T3."GroupName" AS "CustomerGroupName",
    T2."County",
    T2."County" AS "CustomerRegion",
    T1."ItemCode",
    T1."ItemCode" AS "Item No.",
    T1."Dscription",
    T1."Dscription" AS "Description",
    T1."Quantity",
    T1."Quantity" AS "OrderedQty",
    T1."OpenQty",
    T1."OpenQty" AS "BacklogQty",
    T1."LineTotal",
    T1."LineTotal" AS "RowValue",
    T1."WhsCode",
    T1."WhsCode" AS "Warehouse"
FROM ORDR T0
INNER JOIN RDR1 T1 ON T0."DocEntry" = T1."DocEntry"
LEFT JOIN OCRD T2 ON T1."CardCode" = T2."CardCode"
LEFT JOIN OCRG T3 ON T2."GroupCode" = T3."GroupCode"
WHERE T0."CANCELED" = 'N'
  -- Add date filter for last 3 years
  AND T0."DocDate" >= DATEADD(YEAR, -3, GETDATE())
```

**Implementation Effort:** 2-3 hours (SQL query + update to sales.tsv + modify forecasting by customer segment)

---

### 3. **Warehouse Dimensions for Space Optimization** ⭐⭐⭐

**SAP B1 Tables:** `OWHS` (Warehouses)

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Warehouse Street/Address** | `OWHS.Street`, `OWHS.City` | Medium | Multi-location planning |
| **Warehouse Capacity** | `OWHS.WhsCode` (custom UDF) | High | Spatial optimization (you're manually tracking) |
| **Bin Location Data** | `OBIN` (Bin Locations) | High | Slotting optimization, pick efficiency |

**Recommendation:**
Add User Defined Fields (UDFs) to `OWHS` table:
- `U_TotalSkids` (Integer)
- `U_SkidLength` (Decimal)
- `U_SkidWidth` (Decimal)
- `U_MaxHeight` (Decimal)

**SQL Query:**
```sql
SELECT
    T0."WhsCode",
    T0."WhsCode" AS "Location",
    T0."WhsName",
    T0."WhsName" AS "Location Name",
    T0."Street",
    T0."City",
    T0."U_TotalSkids",
    T0."U_SkidLength",
    T0."U_SkidWidth",
    T0."U_MaxHeight"
FROM OWHS T0
WHERE T0."Inactive" = 'N'
```

**Implementation Effort:** 3-4 hours (Create UDFs in SAP B1 + update warehouse management to auto-import)

---

### 4. **Purchase Order Details for Vendor Analysis** ⭐⭐

**SAP B1 Tables:** `OPOR`, `POR1`

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Promised Delivery Date** | `POR1.TaxDate` (promise) | High | Vendor reliability (on-time delivery %) |
| **Actual Receipt Date** | `OPDN.DocDate` | High | Calculate actual lead time |
| **Vendor Item Code** | `POR1.SupplerCatNum` | Medium | Cross-reference vendor catalogs |
| **Manufacturer** | `OITM.FirmCode` | Medium | Dual sourcing by manufacturer |
| **Price List** | `POR1.PriceList` | Medium | Track price changes over time |

**Current Gap:** You're importing `PO_Date` and `EventDate`, but not:
- **Promised Date** (to calculate on-time delivery %)
- **Vendor Item Code** (for cross-referencing)

**Enhanced SQL Query:**
```sql
-- Add to supply.tsv query
SELECT
    -- EXISTING FIELDS...
    T1."ShipDate",
    T1."ShipDate" AS "PromisedDate",  -- When vendor promised to deliver
    T1."ItemCode",
    T1."SupplerCatNum",
    T1."SupplerCatNum" AS "VendorItemCode",  -- Vendor's SKU
    T1."Price",
    T1."Price" AS "UnitPrice",
    T1."Currency",
    T1."PriceList"
FROM OPOR T0
INNER JOIN POR1 T1 ON T0."DocEntry" = T1."DocEntry"
LEFT JOIN OCRD T2 ON T0."CardCode" = T2."CardCode"
LEFT JOIN OITM T3 ON T1."ItemCode" = T3."ItemCode"
WHERE T0."CANCELED" = 'N'
  AND T0."DocStatus" = 'O'  -- Only open POs
```

**Implementation Effort:** 2 hours (Add promised date, vendor item code to supply.tsv + update vendor_performance.py)

---

## 🚀 Medium Priority Additions (Advanced Analytics)

### 5. **Pricing and Discounts** ⭐⭐

**SAP B1 Tables:** `ITM1` (Price Lists), `OPLN` (Price Lists)

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Price List Number** | `OPLN.ListNum` | Medium | Identify retail vs wholesale pricing |
| **List Price** | `ITM1.Price` | Medium | Track price elasticity |
| **Discount %** | Calculated from `ITM1.Price` vs actual | Medium | Promotional impact on demand |

**Use Case:** Analyze if price changes affect demand (price elasticity forecasting)

---

### 6. **Production Planning (BOM)** ⭐⭐

**SAP B1 Tables:** `OITT` (BOM), `ITT1` (BOM Lines)

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **BOM Parent** | `OITT.Code` | High | Forecast components based on finished goods |
| **Component Quantity** | `ITT1.Quantity` | High | Component demand forecasting |
| **Scrap %** | `ITT1.Scrap` | Medium | Yield-adjusted requirements |

**Use Case:** If you manufacture/assemble products, forecast components based on finished goods demand

---

### 7. **Substitute/Alternative Items** ⭐

**SAP B1 Tables:** `OALt` (Alternative Items), `ITM1` cross-reference

| Field | SAP Field | Impact | Use Case |
|-------|-----------|--------|----------|
| **Alternative Item** | `OALt.AltItem` | Medium | Suggest substitutes during stockouts |
| **Substitute Priority** | `OALt.AltrNum` | Medium | Rank substitutes by preference |

**Use Case:** During shortage calculations, suggest alternative items that can fulfill demand

---

## 🔧 Low Priority / Nice to Have

### 8. **Sales Opportunities Pipeline** ⭐

**SAP B1 Tables:** `OOPP` (Sales Opportunities), `OPP1` (Opportunity Lines)

**Use Case:** Include future demand in forecasts (weighted probability)

---

### 9. **Service Calls / Returns** ⭐

**SAP B1 Tables:** `OSCL` (Service Calls), `ORIN` (Returns)

**Use Case:** Identify quality issues affecting demand

---

## 📊 Recommended Implementation Priority

### Phase 1: Quick Wins (This Week) ⚡
1. **Item properties** (lifecycle status, creation date) → Exclude obsolete items
2. **Customer groups** → Segment forecasting
3. **Warehouse UDFs** → Auto-import warehouse capacities

### Phase 2: Vendor Enhancement (Next 2 Weeks) 📈
4. **Promised delivery date** → Vendor on-time performance
5. **Vendor item codes** → Cross-reference catalogs

### Phase 3: Advanced Analytics (Next Quarter) 🎯
6. **Pricing data** → Price elasticity
7. **BOM data** → Component forecasting (if applicable)
8. **Substitute items** → Stockout alternatives

---

## 🚦 Critical Gaps Identified

### Missing Data That Would Significantly Improve Accuracy:

1. **Item Lifecycle Dates** - Cannot distinguish between:
   - Slow-moving items (low demand)
   - Obsolete items (should be excluded)
   - New items (insufficient history)

   **Recommendation:** Add `CreateDate`, `ValidFor`, `Frozen` to items.tsv

2. **Customer Segmentation** - Currently forecasting:
   - Aggregate demand across all customers
   - Not accounting for B2B vs B2C patterns

   **Recommendation:** Add `CustomerType`, `CustomerGroup` to sales.tsv

3. **Vendor Promised Dates** - Cannot calculate:
   - On-time delivery percentage
   - Vendor reliability score

   **Recommendation:** Add `PromisedDate` to supply.tsv

4. **Regional Demand** - Cannot analyze:
   - Geographic demand patterns
   - Warehouse-specific trends

   **Recommendation:** Add `CustomerRegion` to sales.tsv (if multiple warehouses)

---

## 💡 Data Quality Recommendations

### Current Data Quality Issues:

1. **Lead Time Data:**
   - ✅ Have: LeadTimeDays calculated
   - ❌ Missing: Promised vs Actual (to measure vendor performance)

2. **UoM Conversion:**
   - ✅ Fixed: SalesUoM conversion working
   - ⚠️ Need: Verify all items have valid QtyPerSalesUoM

3. **Item Master:**
   - ✅ Have: CurrentStock, IncomingStock
   - ❌ Missing: ReorderPoint, SafetyStock (if defined in SAP B1)

---

## 📋 Implementation Checklist

### For B1UP Query Updates:
- [ ] Add item lifecycle fields to items.tsv query
- [ ] Add customer fields to sales.tsv query
- [ ] Add promised date to supply.tsv query
- [ ] Create warehouse UDFs in SAP B1
- [ ] Update warehouse capacities query to import from OWHS

### For Python Code Updates:
- [ ] Update `src/ingestion.py` to handle new columns
- [ ] Update `src/vendor_performance.py` to calculate on-time delivery %
- [ ] Update `src/forecasting.py` to exclude obsolete items
- [ ] Update `app.py` to show customer segment forecasts
- [ ] Update warehouse management to import from SAP B1

### For Data Validation:
- [ ] Verify all active items have `ValidFor = 'Y'`
- [ ] Verify all stock items have `LogInventory = 'Y'`
- [ ] Check for items with missing `CreateDate`
- [ ] Verify customer groups are assigned

---

## 🎯 Estimated ROI for Each Addition

| Addition | Effort | Impact | ROI |
|----------|--------|--------|-----|
| Item lifecycle (exclude obsolete) | 2h | High | ⭐⭐⭐⭐⭐ |
| Customer segmentation | 4h | High | ⭐⭐⭐⭐ |
| Vendor promised dates | 2h | Medium | ⭐⭐⭐⭐ |
| Warehouse UDFs | 4h | Low | ⭐⭐⭐ |
| Vendor item codes | 1h | Low | ⭐⭐ |
| Pricing data | 6h | Medium | ⭐⭐⭐ |
| BOM (if applicable) | 8h | High | ⭐⭐⭐⭐ |

**Total High-ROI Effort:** ~10-15 hours for immediate improvements

---

**Next Steps:**
1. Review with stakeholders which data is most critical
2. Create UDFs in SAP B1 (for warehouse capacities, if needed)
3. Update B1UP queries with recommended fields
4. Modify ingestion.py to handle new columns
5. Update forecasting logic to use new attributes
6. Test with small dataset before full rollout

---

**Questions for Stakeholders:**
1. Do you have BOM data (manufacturing) or are all items purchased?
2. Do you want customer-segmented forecasting?
3. Should we track vendor on-time delivery percentage?
4. Are items categorized by seasonality in SAP B1?
5. Do you want to automate warehouse capacity imports from SAP B1?
