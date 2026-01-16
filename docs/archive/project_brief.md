# Project: SAP B1 Inventory & Forecast Analyzer (Snapshot v1)

**Goal:** A local Python tool to forecast unconstrained demand, calculate TCO (Total Cost of Ownership), and recommend "Stock" vs "Special Order" classification using SAP B1 .tsv exports.

## 1. Data Logic & Schema
### A. Demand Signal (Source: Sales Orders / ORDR)
* **Philosophy:** Forecast on *Bookings* (what customers wanted), not Invoices (what we shipped).
* **Net Demand Logic:** Sum of `OrderedQty` from `sales.tsv`.
* **Exclusion Rule:** IF `Linked_SpecialOrder_Num` (`U_SORDNUM`) IS NOT NULL, flag row as `is_linked_special_order`. These are excluded from "Stock Forecasts" as they are bought-to-order.
* **Regional Parsing:** Demand must be assigned to a Region based on the Item Code Suffix (see Section 3).

### B. Supply Chain (Source: Unified Supply / OPDN + OPOR)
* **File:** `supply.tsv` contains both History (Received) and Schedule (Open POs).
* **Currency Rule:** ALWAYS normalize costs to CAD: `RowValue_CAD = RowValue_SourceCurrency * ExchangeRate`.
* **History Logic (DataType='History'):** Used to train Lead Time Models. Calculate `LeadTime = EventDate (GRPO) - PO_Date`.
* **Schedule Logic (DataType='OpenPO'):**
    * Ignore SAP `EventDate` (ShipDate) as it is often unreliable.
    * **Extrapolation:** `Predicted_Arrival = PO_Date + Vendor_Median_Lead_Time`.

### C. Inventory Snapshots (Source: Item Master / OITW)
* **Scope:** Stock is specific to Warehouses. Do not aggregate globally.
* **Vendor Hierarchy (Source of Truth):**
    1. **Active History:** Use vendor from `supply.tsv` if purchased in last 12 months.
    2. **Fallback 1:** Use `LastVendorCode_Fallback` (UDF `U_LPVENDC`).
    3. **Fallback 2:** Use `PreferredVendor` (SAP Standard).
* **Costing:** Use `UnitCost` (AvgPrice) for TCO calculations. Note: `LastPurchasePrice_Fallback` (`U_LPPRICE`) is text and must be cleaned (strip '$', ',').

## 2. Business Formulas (The "Tournament")
### Forecasting Engine
* **Strategy:** Rolling Origin Cross-Validation (Train on oldest 80%, Test on recent 20%).
* **Contenders:**
    * *Simple Moving Avg (SMA):* For items with < 12 months history.
    * *Prophet:* For seasonal/volatile items (robust to trends).
    * *Croston’s Method:* For intermittent "lumpy" demand.
* **Selection:** The model with the lowest RMSE (Error) wins and generates the 6-month forecast.

### Optimization Engine (TCO)
* **Carrying Cost:** Calculated via `config.yaml` (Capital + Storage + Risk).
* **Stock vs. Special Order Logic:**
    * *Cost to Stock* = (Carrying Cost % * Unit Cost) + (Standard Freight % * COGS).
    * *Cost to Special Order* = (Special Order Surcharge + High Freight %) * Annual Demand.
    * **Decision:** If *Cost to Stock* < *Cost to Special Order* -> **STOCK**. Else -> **SPECIAL ORDER**.

## 3. Region Mapping Rules
Parse the `ItemCode` suffix to assign a Region.

| Suffix | Region Name |
| :--- | :--- |
| *-DEL* | Delta |
| *-CGY* | Calgary |
| *-EDM* | Edmonton |
| *-SAS* | Saskatoon |
| *-REG* | Regina |
| *-WPG* | Winnipeg |
| *-TOR* | Toronto |
| *-VGH* | Vaughan |
| *-MTL* | Montreal |
| *(None)* | **Delta (Default / Equipment)** |

### UoM Conversion Logic
- **Calculation Engine:** All forecasting and stock comparison happens in **Base Units** (InvQty).
- **Recommendation Display:** - When recommending a reorder, convert the Base Unit Qty back to Purchasing Units.
  - Formula: `Recommended_Pails = Recommended_Liters / QtyPerPurchUoM`.
  - Display both values (e.g., "Buy 189L (10 Pails)").

## 4. Technical Stack
* **Ingestion:** Pandas (Load .tsv, parse dates, enforce types).
* **Forecasting:** `statsmodels`, `prophet`.
* **UI:** Streamlit (Dashboard showing Shortages by Region and Cost Analysis).
* **Constraint:** Handle dirty data (nulls, zero costs). Filter `LeadTime > 365 days` as outliers.