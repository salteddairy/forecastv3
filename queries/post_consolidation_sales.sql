-- ============================================================================
-- SAP B1 Query: Sales Order History (Post-Consolidation)
-- Purpose: Export sales with historical regional variant mapping
--          Maps historical regional variants to consolidated item codes
-- ============================================================================

SELECT
    T0.DocNum AS 'DocNum',
    T0.DocDate AS 'Posting Date',
    T0.DocDueDate AS 'PromiseDate',
    T0.CardCode AS 'CustomerCode',
    T1.CardName AS 'CustomerName',

    -- Item Code (Consolidated)
    T2.ItemCode AS 'Item No.',

    -- Historical Regional Mapping (for forecast continuity)
    -- Note: After consolidation, ItemCode no longer has suffix
    -- We preserve the warehouse to maintain regional context
    T3.WhsCode AS 'Warehouse',

    CASE
        WHEN T3.WhsCode LIKE '%-TOR%' THEN 'Toronto'
        WHEN T3.WhsCode LIKE '%-CGY%' THEN 'Calgary'
        WHEN T3.WhsCode LIKE '%-EDM%' THEN 'Edmonton'
        WHEN T3.WhsCode LIKE '%-REG%' THEN 'Regina'
        WHEN T3.WhsCode LIKE '%-SAS%' THEN 'Saskatoon'
        WHEN T3.WhsCode LIKE '%-WPG%' THEN 'Winnipeg'
        WHEN T3.WhsCode LIKE '%-DEL%' THEN 'Delta'
        WHEN T3.WhsCode LIKE '%-VGH%' THEN 'Vaughan'
        WHEN T3.WhsCode LIKE '%-MTL%' THEN 'Montreal'
        ELSE 'Unknown'
    END AS 'Region',

    T2.ItemName AS 'Description',
    T2.Quantity AS 'OrderedQty',
    T2.OpenQty AS 'BacklogQty',
    T2.LineTotal AS 'RowValue',

    -- Special Order Flag
    T0.U_SORDNUM AS 'Linked_SpecialOrder_Num',

    -- Document Type
    CASE
        WHEN T0.CANCELED = 'Y' THEN 'Cancelled'
        WHEN T2.LineStatus = 'C' THEN 'Closed'
        WHEN T2.LineStatus = 'O' THEN 'Open'
        ELSE 'Other'
    END AS 'Document Type'

FROM ORDR T0
INNER JOIN RDR1 T2 ON T0.DocEntry = T2.DocEntry
INNER JOIN OCRD T1 ON T0.CardCode = T1.CardCode
-- Get warehouse from row level (IMPORTANT: Different warehouses per line item!)
LEFT JOIN OITW T3 ON T2.ItemCode = T3.ItemCode AND T2.WhsCode = T3.WhsCode

WHERE T0.CANCELED = 'N'  -- Exclude cancelled orders
  AND T2.LineStatus <> 'C'  -- Exclude closed lines (optional)
  AND T0.DocDate >= DATEADD(YEAR, -3, GETDATE())  -- Last 3 years

ORDER BY T0.DocDate DESC, T0.DocNum, T2.LineNum;

-- ============================================================================
-- Key Concept: Historical Data Mapping
-- ============================================================================
--
-- BEFORE Consolidation:
--   Item No.: 30555C-DEL, Warehouse: 1
--   Item No.: 30555C-REG, Warehouse: 60
--
-- AFTER Consolidation:
--   Item No.: 30555C, Warehouse: 000-DEL1  (was 30555C-DEL)
--   Item No.: 30555C, Warehouse: 060-REG1  (was 30555C-REG)
--
-- FORECAST ALIGNMENT:
--   Historical sales for 30555C-DEL → 30555C + Warehouse 000-DEL1
--   Historical sales for 30555C-REG → 30555C + Warehouse 060-REG1
--
-- The warehouse code becomes the regional identifier after consolidation!

-- ============================================================================
-- Alternative: Historical View (Pre-Consolidation Data Export)
-- ============================================================================

-- If you need to export historical data BEFORE consolidation and map it:
-- This query adds a 'Consolidated_Item_Code' column for future reference

SELECT
    T0.DocNum AS 'DocNum',
    T0.DocDate AS 'Posting Date',
    T0.CardCode AS 'CustomerCode',
    T1.CardName AS 'CustomerName',

    -- Original Item Code (with regional suffix)
    T2.ItemCode AS 'Original_Item_Code',

    -- Consolidated Item Code (suffix removed)
    CASE
        WHEN CHARINDEX('-', T2.ItemCode) > 0 THEN
            SUBSTRING(T2.ItemCode, 1, CHARINDEX('-', T2.ItemCode) - 1)
        ELSE T2.ItemCode
    END AS 'Consolidated_Item_Code',

    -- Warehouse
    T2.WhsCode AS 'Warehouse',

    -- Regional Mapping
    CASE
        WHEN T2.ItemCode LIKE '%-TOR' THEN 'Toronto'
        WHEN T2.ItemCode LIKE '%-CGY' THEN 'Calgary'
        WHEN T2.ItemCode LIKE '%-EDM' THEN 'Edmonton'
        WHEN T2.ItemCode LIKE '%-REG' THEN 'Regina'
        WHEN T2.ItemCode LIKE '%-SAS' THEN 'Saskatoon'
        WHEN T2.ItemCode LIKE '%-WPG' THEN 'Winnipeg'
        WHEN T2.ItemCode LIKE '%-DEL' THEN 'Delta'
        WHEN T2.ItemCode LIKE '%-VGH' THEN 'Vaughan'
        WHEN T2.ItemCode LIKE '%-MTL' THEN 'Montreal'
        ELSE 'Unknown'
    END AS 'Region',

    T2.Quantity AS 'OrderedQty',
    T2.LineTotal AS 'RowValue'

FROM ORDR T0
INNER JOIN RDR1 T2 ON T0.DocEntry = T2.DocEntry
INNER JOIN OCRD T1 ON T0.CardCode = T1.CardCode

WHERE T0.CANCELED = 'N'
  AND T0.DocDate >= DATEADD(YEAR, -3, GETDATE())

ORDER BY T0.DocDate DESC;

-- ============================================================================
-- Mapping Logic for Historical Data Import
-- ============================================================================
--
-- When importing historical sales data after consolidation:
--
-- 1. For each historical record with regional item code (e.g., 30555C-DEL):
--    a. Extract base item code: 30555C
--    b. Extract region from suffix: DEL → Delta
--    c. Map to new warehouse code: DEL → 000-DEL1
--    d. Import as: Item No. = 30555C, Warehouse = 000-DEL1
--
-- 2. This preserves regional sales patterns in the forecast!
--
-- Example mapping:
--   Historical: 30555C-DEL → 100 units sold from Warehouse 1
--   Mapped:     30555C + Warehouse 000-DEL1 → 100 units
--
--   Historical: 30555C-REG → 50 units sold from Warehouse 60
--   Mapped:     30555C + Warehouse 060-REG1 → 50 units
