-- ============================================================================
-- SAP B1 Query: Multi-Warehouse Item Analysis (FIXED)
-- Purpose: Analyze an item that exists in multiple warehouses
-- Item: BX010155-EDM
-- Version: 2.1 - Fixed for actual SAP B1 column names
-- ============================================================================

-- ============================================================================
-- QUERY 1: Complete Item Analysis (with CTEs)
-- Combines: Item master, warehouse data, sales summary, purchase summary, lead times
-- ============================================================================

DECLARE @ItemCode NVARCHAR(20);
DECLARE @BaseItemCode NVARCHAR(20);

-- Set the item code to analyze
SET @ItemCode = 'BX010155-EDM';

-- Extract base item code (remove suffix for consolidation analysis)
SET @BaseItemCode = CASE
    WHEN CHARINDEX('-', @ItemCode) > 0
    THEN SUBSTRING(@ItemCode, 1, CHARINDEX('-', @ItemCode) - 1)
    ELSE @ItemCode
END;

-- Main CTE combining all analysis
WITH ItemMaster AS (
    -- Item master data
    SELECT
        T0.ItemCode,
        T0.ItemName,
        T0.ItmsGrpCod AS 'Item_Group_Code',
        T0.InvntryUom AS 'Base_UoM',
        T0.BuyUnitMsr AS 'Purchasing_UoM',
        T0.SalUnitMsr AS 'Sales_UoM',
        T0.CardCode AS 'Vendor_Code',
        T3.CardName AS 'Vendor_Name',
        ISNULL(T1.UoMEntry, 0) AS 'UoMEntry',
        ISNULL(T1.UoMEntry, 0) AS 'SalesUoMEntry',
        ISNULL(T2.UoMEntry, 0) AS 'PurchUoMEntry'
    FROM OITM T0
    LEFT JOIN OUOM T1 ON T0.SalUnitMsr = T1.UoMEntry
    LEFT JOIN OUOM T2 ON T0.BuyUnitMsr = T2.UoMEntry
    LEFT JOIN OCRD T3 ON T0.CardCode = T3.CardCode
    WHERE T0.ItemCode = @ItemCode
),

WarehouseData AS (
    -- Current warehouse quantities
    SELECT
        T4.WhsCode AS 'Warehouse_Code',
        T5.WhsName AS 'Warehouse_Name',
        T4.OnHand AS 'On_Hand',
        T4.OnOrder AS 'On_Order',
        T4.IsCommited AS 'Committed',
        T4.AvgPrice AS 'Unit_Cost',
        (T4.OnHand - T4.IsCommited) AS 'Available',
        (T4.OnHand * T4.AvgPrice) AS 'Inventory_Value'
    FROM OITM T0
    INNER JOIN OITW T4 ON T0.ItemCode = T4.ItemCode
    LEFT JOIN OWHS T5 ON T4.WhsCode = T5.WhsCode
    WHERE T0.ItemCode = @ItemCode
),

SalesSummary AS (
    -- Sales aggregated by warehouse (last 12 months)
    SELECT
        T2.WhsCode AS 'Warehouse_Code',
        COUNT(DISTINCT T0.DocNum) AS 'Order_Count',
        SUM(T2.Quantity) AS 'Total_Ordered',
        SUM(T2.DelivrdQty) AS 'Total_Shipped',
        SUM(T2.LineTotal) AS 'Total_Value'
    FROM ORDR T0
    INNER JOIN RDR1 T2 ON T0.DocEntry = T2.DocEntry
    WHERE T2.ItemCode = @ItemCode
      AND T0.CANCELED = 'N'
      AND T0.DocDate >= DATEADD(YEAR, -1, GETDATE())
    GROUP BY T2.WhsCode
),

PurchaseSummary AS (
    -- Purchases aggregated by warehouse/vendor (last 12 months)
    SELECT
        T2.WhsCode AS 'Warehouse_Code',
        T0.CardCode AS 'Vendor_Code',
        COUNT(DISTINCT T0.DocNum) AS 'PO_Count',
        SUM(T2.Quantity) AS 'Total_Ordered',
        SUM(T2.LineTotal) AS 'Total_Value'
    FROM OPOR T0
    INNER JOIN POR1 T2 ON T0.DocEntry = T2.DocEntry
    WHERE T2.ItemCode = @ItemCode
      AND T0.CANCELED = 'N'
      AND T0.DocDate >= DATEADD(YEAR, -1, GETDATE())
    GROUP BY T2.WhsCode, T0.CardCode
),

LeadTimeAnalysis AS (
    -- Lead times by warehouse/vendor
    SELECT
        T2.WhsCode AS 'Warehouse_Code',
        T0.CardCode AS 'Vendor_Code',
        AVG(DATEDIFF(DAY, T0.DocDate, T3.DocDate)) AS 'Avg_Lead_Time_Days',
        MIN(DATEDIFF(DAY, T0.DocDate, T3.DocDate)) AS 'Min_Lead_Time_Days',
        MAX(DATEDIFF(DAY, T0.DocDate, T3.DocDate)) AS 'Max_Lead_Time_Days',
        COUNT(*) AS 'Receipt_Count'
    FROM OPOR T0
    INNER JOIN POR1 T2 ON T0.DocEntry = T2.DocEntry
    LEFT JOIN PDN1 T3 ON T2.DocEntry = T3.BaseEntry AND T2.LineNum = T3.BaseLine
    WHERE T2.ItemCode = @ItemCode
      AND T0.CANCELED = 'N'
      AND T3.DocDate IS NOT NULL
      AND T0.DocDate >= DATEADD(YEAR, -1, GETDATE())
    GROUP BY T2.WhsCode, T0.CardCode
)

-- Final combined result
SELECT
    -- Item Information
    IM.ItemCode AS 'Item_Code',
    IM.ItemName AS 'Description',
    IM.Base_UoM,
    IM.Purchasing_UoM,
    IM.Sales_UoM,
    IM.Vendor_Code,
    IM.Vendor_Name,

    -- Warehouse Information
    WD.Warehouse_Code,
    WD.Warehouse_Name,
    WD.On_Hand,
    WD.On_Order,
    WD.Committed,
    WD.Available,
    WD.Unit_Cost,
    WD.Inventory_Value,

    -- Sales Metrics (last 12 months)
    ISNULL(SS.Order_Count, 0) AS 'Sales_Order_Count',
    ISNULL(SS.Total_Ordered, 0) AS 'Sales_Total_Ordered',
    ISNULL(SS.Total_Shipped, 0) AS 'Sales_Total_Shipped',
    ISNULL(SS.Total_Value, 0) AS 'Sales_Total_Value',

    -- Purchase Metrics (last 12 months)
    ISNULL(PS.PO_Count, 0) AS 'Purchase_PO_Count',
    ISNULL(PS.Total_Ordered, 0) AS 'Purchase_Total_Ordered',
    ISNULL(PS.Total_Value, 0) AS 'Purchase_Total_Value',

    -- Lead Time Metrics
    ISNULL(LT.Avg_Lead_Time_Days, 0) AS 'Avg_Lead_Time_Days',
    ISNULL(LT.Min_Lead_Time_Days, 0) AS 'Min_Lead_Time_Days',
    ISNULL(LT.Max_Lead_Time_Days, 0) AS 'Max_Lead_Time_Days',
    ISNULL(LT.Receipt_Count, 0) AS 'Receipt_Count',

    -- Future warehouse code (post-consolidation)
    CASE WD.Warehouse_Code
        WHEN '40' THEN '040-EDM1'
        WHEN '1' THEN '000-DEL1'
        WHEN '3' THEN '000-DEL3'
        WHEN '5' THEN '000-DEL5'
        WHEN '7' THEN '000-DEL7'
        WHEN '9' THEN '000-DEL9'
        WHEN '11' THEN '000-DEL11'
        WHEN '12' THEN '000-DEL12'
        WHEN '15' THEN '000-DEL15'
        WHEN '21' THEN '000-DEL21'
        WHEN '23' THEN '000-DEL23'
        WHEN '25' THEN '000-DEL25'
        WHEN '50' THEN '050-TOR1'
        WHEN '30' THEN '030-CGY1'
        WHEN '60' THEN '060-REG1'
        WHEN '20' THEN '020-SAS1'
        WHEN '10' THEN '010-WPG1'
        WHEN 'VGH' THEN 'VGH-VGH1'
        WHEN 'MTL' THEN 'MTL-MTL1'
        ELSE WD.Warehouse_Code
    END AS 'Future_Warehouse_Code'

FROM ItemMaster IM
CROSS JOIN WarehouseData WD
LEFT JOIN SalesSummary SS ON WD.Warehouse_Code = SS.Warehouse_Code
LEFT JOIN PurchaseSummary PS ON WD.Warehouse_Code = PS.Warehouse_Code
LEFT JOIN LeadTimeAnalysis LT ON WD.Warehouse_Code = LT.Warehouse_Code

ORDER BY WD.On_Hand DESC;


-- ============================================================================
-- QUERY 2: Regional Variants Analysis
-- Shows all variants of this base item (what will consolidate together)
-- ============================================================================

SELECT
    T0.ItemCode AS 'Variant_Code',
    T0.ItemName AS 'Description',
    T4.WhsCode AS 'Current_Warehouse',
    T5.WhsName AS 'Warehouse_Name',
    T4.OnHand AS 'Stock',
    T4.OnOrder AS 'On_Order',
    T4.AvgPrice AS 'Unit_Cost',
    (T4.OnHand * T4.AvgPrice) AS 'Inventory_Value',

    -- Future warehouse code (post-consolidation)
    CASE T4.WhsCode
        WHEN '40' THEN '040-EDM1'
        WHEN '1' THEN '000-DEL1'
        WHEN '3' THEN '000-DEL3'
        WHEN '50' THEN '050-TOR1'
        WHEN '30' THEN '030-CGY1'
        WHEN '60' THEN '060-REG1'
        WHEN '20' THEN '020-SAS1'
        WHEN '10' THEN '010-WPG1'
        ELSE T4.WhsCode
    END AS 'Future_Warehouse_Code',

    -- After consolidation: all become BX010155 (no suffix)
    CASE
        WHEN CHARINDEX('-', T0.ItemCode) > 0
        THEN SUBSTRING(T0.ItemCode, 1, CHARINDEX('-', T0.ItemCode) - 1)
        ELSE T0.ItemCode
    END AS 'Consolidated_Item_Code'

FROM OITM T0
INNER JOIN OITW T4 ON T0.ItemCode = T4.ItemCode
LEFT JOIN OWHS T5 ON T4.WhsCode = T5.WhsCode

WHERE T0.ItemCode LIKE @BaseItemCode + '%'
  AND T4.OnHand > 0  -- Only show variants with stock

ORDER BY T0.ItemCode, T4.OnHand DESC;


-- ============================================================================
-- QUERY 3: Detailed Transaction History (Optional - for deep dive)
-- Shows recent sales and purchases with full details
-- ============================================================================

-- Recent Sales (last 6 months)
SELECT
    'SALE' AS 'Transaction_Type',
    T0.DocDate AS 'Date',
    CAST(T0.DocNum AS NVARCHAR(50)) AS 'Document_Number',
    T0.CardCode AS 'Customer_Code',
    T1.CardName AS 'Customer_Name',
    T2.WhsCode AS 'Warehouse',
    T2.Quantity AS 'Quantity',
    T2.DelivrdQty AS 'Shipped',
    T2.LineTotal AS 'Value',
    NULL AS 'Vendor_Code',
    NULL AS 'Vendor_Name',
    NULL AS 'Lead_Time_Days'
FROM ORDR T0
INNER JOIN RDR1 T2 ON T0.DocEntry = T2.DocEntry
LEFT JOIN OCRD T1 ON T0.CardCode = T1.CardCode
WHERE T2.ItemCode = @ItemCode
  AND T0.CANCELED = 'N'
  AND T0.DocDate >= DATEADD(MONTH, -6, GETDATE())

UNION ALL

-- Recent Purchases (last 6 months)
SELECT
    'PURCHASE' AS 'Transaction_Type',
    T0.DocDate AS 'Date',
    CAST(T0.DocNum AS NVARCHAR(50)) AS 'Document_Number',
    T0.CardCode AS 'Vendor_Code',
    T1.CardName AS 'Vendor_Name',
    T2.WhsCode AS 'Warehouse',
    T2.Quantity AS 'Quantity',
    T2.OpenQty AS 'Shipped',
    T2.LineTotal AS 'Value',
    T0.CardCode AS 'Vendor_Code',
    T1.CardName AS 'Vendor_Name',
    CAST(DATEDIFF(DAY, T0.DocDate, T3.DocDate) AS INT) AS 'Lead_Time_Days'
FROM OPOR T0
INNER JOIN POR1 T2 ON T0.DocEntry = T2.DocEntry
LEFT JOIN OCRD T1 ON T0.CardCode = T1.CardCode
LEFT JOIN PDN1 T3 ON T2.DocEntry = T3.BaseEntry AND T2.LineNum = T3.BaseLine
WHERE T2.ItemCode = @ItemCode
  AND T0.CANCELED = 'N'
  AND T0.DocDate >= DATEADD(MONTH, -6, GETDATE())

ORDER BY Date DESC;


-- ============================================================================
-- USAGE NOTES
-- ============================================================================
--
-- This version fixes column name issues for SAP B1:
--
-- CHANGES FROM ORIGINAL:
-- 1. Removed UGP1 table joins (column names vary by SAP version)
-- 2. Changed ItemGroup to ItmsGrpCod (correct SAP B1 column)
-- 3. Declared all variables at the top
-- 4. Simplified UoM lookups using OUOM instead of UGP1
-- 5. Added CAST for DocNum to avoid type issues
--
-- TO ANALYZE A DIFFERENT ITEM:
-- Change the value at line 19:
--   SET @ItemCode = 'YOUR_ITEM_CODE_HERE';
--
-- EXPECTED OUTPUT FOR BX010155-EDM:
-- -----------------------------------------------
--
-- Query 1 Returns (one row per warehouse):
--   Item_Code: BX010155-EDM
--   Warehouse: 40 | On_Hand: 12 | Sales: 6 orders | Avg Lead Time: X days
--
-- Query 2 Returns (one row per variant):
--   BX010155-CGY | Warehouse: 30 | Stock: 25
--   BX010155-EDM | Warehouse: 40 | Stock: 12
--
-- Query 3 Returns (recent transactions):
--   SALE | 2025-10-22 | C03922 | 1 unit | $720
--   PURCHASE | 2025-08-11 | V00604 | 10 units | $48
