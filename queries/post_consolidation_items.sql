-- ============================================================================
-- SAP B1 Query: Item Master Export (Post-Consolidation)
-- Purpose: Export items with warehouse-specific data
-- Format: One row per item/warehouse combination
-- Date: After item master consolidation (regional suffixes removed)
-- ============================================================================

SELECT
    T0.ItemCode AS 'Item No.',
    T0.ItemName AS 'Description',
    T0.ItemGroup AS 'ItemGroup',
    T0.InvntryUom AS 'BaseUoM',
    T0.BuyUnitMsr AS 'PurchUoM',
    T0.SalUnitMsr AS 'SalesUoM',
    T1.Factor AS 'QtyPerSalesUoM',
    T2.Factor AS 'QtyPerPurchUoM',
    T1.AltUoM AS 'Sales_UoM_Label',
    T2.AltUoM AS 'Purch_UoM_Label',

    -- Warehouse-Specific Data
    T3.WhsCode AS 'Warehouse',
    T3.OnHand AS 'CurrentStock',
    T3.OnOrder AS 'IncomingStock',
    T3.IsCommited AS 'CommittedStock',
    T3.AvgPrice AS 'UnitCost',

    -- Vendor Data
    T0.CardCode AS 'VendorCode',
    T4.CardName AS 'VendorName',

    -- Regional Mapping (for historical data alignment)
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

    -- MOQ and Ordering
    T0.MINLEVEL AS 'MinLevel',
    T0.MAXLEVEL AS 'MaxLevel',
    T0.ORDRTY AS 'OrderMultiple',

    -- Item Status
    T0.LogInventory AS 'Frozen',
    T0.ValidFor AS 'ValidFor',
    T0.TreeType AS 'ItemType'

FROM OITM T0
-- Get Sales UoM conversion factor
LEFT JOIN UGP1 T1 ON T0.UgpEntry = T1.UoMEntry AND T1.AltUoM = T0.SalUnitMsr
-- Get Purchasing UoM conversion factor
LEFT JOIN UGP1 T2 ON T0.UgpEntry = T2.UoMEntry AND T2.AltUoM = T0.BuyUnitMsr
-- Get warehouse data (ONE ROW PER WAREHOUSE)
INNER JOIN OITW T3 ON T0.ItemCode = T3.ItemCode
-- Get vendor name
LEFT JOIN OCRD T4 ON T0.CardCode = T4.CardCode

WHERE T0.ValidFor = 'Y'  -- Only active items
  AND T3.OnHand > 0      -- Only items with stock

ORDER BY T0.ItemCode, T3.WhsCode;

-- ============================================================================
-- Expected Output Format (Post-Consolidation):
-- ============================================================================
--
-- Item No. | Description      | Warehouse  | CurrentStock | PurchUoM | Region
-- ---------|------------------|------------|--------------|----------|--------
-- 30555C   | Widget Product   | 050-TOR1   | 50           | Pail     | Toronto
-- 30555C   | Widget Product   | 030-CGY1   | 25           | Pail     | Calgary
-- 30555C   | Widget Product   | 000-DEL1   | 100          | Pail     | Delta
--
-- Note: Item no longer has regional suffix (-TOR, -CGY, etc.)
--       Instead, multiple rows exist for the same item (one per warehouse)
--       Region is derived from warehouse code for historical alignment

-- ============================================================================
-- Alternative Query: Include Items Without Stock
-- ============================================================================

SELECT
    T0.ItemCode AS 'Item No.',
    T0.ItemName AS 'Description',
    T0.ItemGroup AS 'ItemGroup',
    T0.InvntryUom AS 'BaseUoM',
    T0.BuyUnitMsr AS 'PurchUoM',
    T0.SalUnitMsr AS 'SalesUoM',
    T1.Factor AS 'QtyPerSalesUoM',

    -- Warehouse Data (NULL if no warehouse/stock)
    T2.WhsCode AS 'Warehouse',
    COALESCE(T2.OnHand, 0) AS 'CurrentStock',
    COALESCE(T2.OnOrder, 0) AS 'IncomingStock',
    COALESCE(T2.IsCommited, 0) AS 'CommittedStock',

    -- Regional Mapping
    CASE
        WHEN T2.WhsCode LIKE '%-TOR%' THEN 'Toronto'
        WHEN T2.WhsCode LIKE '%-CGY%' THEN 'Calgary'
        WHEN T2.WhsCode LIKE '%-EDM%' THEN 'Edmonton'
        WHEN T2.WhsCode LIKE '%-REG%' THEN 'Regina'
        WHEN T2.WhsCode LIKE '%-SAS%' THEN 'Saskatoon'
        WHEN T2.WhsCode LIKE '%-WPG%' THEN 'Winnipeg'
        WHEN T2.WhsCode LIKE '%-DEL%' THEN 'Delta'
        WHEN T2.WhsCode LIKE '%-VGH%' THEN 'Vaughan'
        WHEN T2.WhsCode LIKE '%-MTL%' THEN 'Montreal'
        ELSE 'Unknown'
    END AS 'Region'

FROM OITM T0
LEFT JOIN UGP1 T1 ON T0.UgpEntry = T1.UoMEntry AND T1.AltUoM = T0.SalUnitMsr
LEFT JOIN OITW T2 ON T0.ItemCode = T2.ItemCode

WHERE T0.ValidFor = 'Y'

ORDER BY T0.ItemCode, T2.WhsCode;
