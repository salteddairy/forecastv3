-- ============================================================================
-- SAP B1 Query: Regional Variants Analysis (Query 2)
-- Shows all variants of this base item (what will consolidate together)
-- ============================================================================

DECLARE @BaseItemCode NVARCHAR(20);

-- Extract base item code (remove suffix)
SET @BaseItemCode = 'BX010155';  -- CHANGE THIS for different items

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
        WHEN '05' THEN '005-FIN1'
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
