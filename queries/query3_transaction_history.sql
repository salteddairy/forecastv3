-- ============================================================================
-- SAP B1 Query: Transaction History (Query 3)
-- Shows recent sales and purchases with full details
-- ============================================================================

DECLARE @ItemCode NVARCHAR(20);

-- Set the item code to analyze
SET @ItemCode = 'BX010155-EDM';  -- CHANGE THIS for different items

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
