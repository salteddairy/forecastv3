# Forecasting Tool Integration Guide
## UoM Conversion & Item Master Consolidation

**Document Purpose:** Explain item master consolidation to AI forecasting tool developers
**Status:** Consolidation in progress - tool must handle BOTH states
**Date:** 2025-01-15

---

## Executive Summary

**Critical Alert:** The SAP B1 item master is undergoing a major consolidation that changes how units of measure (UoM) work. Your forecasting tool **must be designed to handle both the current state and future state** to avoid breaking when consolidation occurs.

**Timeline:**
- **Current State:** Active NOW
- **Consolidation Date:** TBD (awaiting conversion factor confirmation)
- **Transition Period:** Tool should work in BOTH states during migration

---

## Current State (Before Consolidation)

### Item Code Structure

**Regional Item Codes:** `BASECODE-REG` format

Examples:
- `30027C-TOR` (Toronto variant)
- `30027C-CGY` (Calgary variant)
- `30027C-DEL` (Delta variant)

**Base Items (non-regional):** `BASECODE` only

Example:
- `30027C` (consolidated item, if already exists)

### Unit of Measure (UoM) Structure

**Current UoM Hierarchy:**
```
Inventory UoM (Base Unit):  Litre, KG
Purchasing UoM:             Pail, Drum, Tote, Ea, Bag, Bottle, etc.
Sales UoM:                  Matches purchasing UoM typically
```

**Critical Characteristic:**
- **Item costs are in BASE units** (cost per Litre, cost per KG)
- **Inventory quantities are in BASE units** (Litres in stock, KG in stock)
- **Purchasing UoM is a LABEL only** - does NOT affect cost/quantity calculations

**Example:**
```
Item Code:        30027C-TOR
Item Description: Widget Product
Inventory UoM:    Litre      (base unit)
Purchasing UoM:   Pail       (label for purchasing)
Sales UoM:        Pail       (label for sales)
Item Cost:        $1.50      (PER LITRE - base unit)
In Stock:         1000       (LITRES - base unit)
```

**Key Point:** Even though Purchasing UoM says "Pail", the cost ($1.50) and quantity (1000) are still in **Litres** (base unit).

### Regional Warehouses

**Current Warehouse Codes:**
```
TOR → Warehouse 50
CGY → Warehouse 30
DEL → Warehouse 1, 3, 4, 5, 7, 9, 11, 12, 15, 21, 23, 25
EDM → Warehouse 40
REG → Warehouse 60
```

Each regional variant is linked to its specific warehouse.

### Costing Logic

**Current State Costs:**
- **Weighted Average:** Calculated per regional item
- **Cost Basis:** Per BASE unit (Litre, KG)
- **No UoM conversion applied** in current state

**Formula:**
```
Cost per Base Unit = Total Inventory Value / Total Quantity in Base Units
```

---

## Future State (After Consolidation)

### Item Code Structure

**Consolidated Item Codes:** `BASECODE` only (regional suffixes removed)

**Before:**
- `30027C-TOR`, `30027C-CGY`, `30027C-DEL` (3 separate items)

**After:**
- `30027C` (single consolidated item)

### Unit of Measure (UoM) Structure

**Future UoM Hierarchy:**
```
Inventory UoM:             Pail, Drum, Tote (PURCHASING units)
Purchasing UoM:            Pail, Drum, Tote (same as inventory)
Sales UoM:                 Pail, Drum, Tote (same as inventory)
```

**Critical Change:**
- **Item costs are in PURCHASING units** (cost per Pail, cost per Drum)
- **Inventory quantities are in PURCHASING units** (Pails in stock, Drums in stock)
- **Purchasing UoM now defines the ACTUAL unit** for all calculations

**Example (Same Item After Conversion):**
```
Item Code:        30027C
Item Description: Widget Product
Inventory UoM:    Pail       (now the base unit)
Purchasing UoM:   Pail       (same as inventory)
Sales UoM:        Pail       (same as inventory)
Item Cost:        $30.00     (PER PAIL - purchasing unit)
In Stock:         50         (PAILS - purchasing unit)

Conversion Factor: 1 Pail = 20 Litres
Original Value:    $1.50/Litre × 1000 Litres = $1,500
Converted Value:   $30.00/Pail × 50 Pails = $1,500 (preserved)
```

**Key Point:** Costs and quantities are NOW in purchasing units (Pail), not base units (Litre).

### Regional Warehouses (New Codes)

**Future Warehouse Codes:**
```
TOR → Warehouse 050-TOR1
CGY → Warehouse 030-CGY1
DEL → Warehouse 000-DEL1
EDM → Warehouse 040-EDM1
REG → Warehouse 060-REG1
```

**Single Item, Multiple Warehouses:**
- One consolidated item code (`30027C`)
- Multiple OITW records (one per warehouse)
- Inventory distributed across regional warehouses

### Costing Logic

**Future State Costs:**
- **Weighted Average:** Calculated across ALL regional variants
- **Cost Basis:** Per PURCHASING unit (Pail, Drum, Tote)
- **UoM conversion APPLIED** before averaging

**Formula:**
```
For each regional variant:
  1. Convert to purchasing UoM:
     - Cost_Purch = Cost_Base × ConversionFactor
     - Qty_Purch = Qty_Base ÷ ConversionFactor

  2. Calculate weighted average:
     - Total_Value_Purch = Σ(Cost_Purch × Qty_Purch) for all variants
     - Total_Qty_Purch = Σ(Qty_Purch) for all variants
     - Avg_Cost_Purch = Total_Value_Purch / Total_Qty_Purch
```

**Example:**
```
Variant 1 (TOR):
  Base Cost: $1.50/Litre
  Base Qty:  1000 Litres
  Factor:    20 Litres/Pail
  Converted: $30.00/Pail × 50 Pails = $1,500

Variant 2 (CGY):
  Base Cost: $1.60/Litre
  Base Qty:  500 Litres
  Factor:    20 Litres/Pail
  Converted: $32.00/Pail × 25 Pails = $800

Weighted Average:
  Total Value: $1,500 + $800 = $2,300
  Total Qty:   50 + 25 = 75 Pails
  Avg Cost:    $2,300 / 75 = $30.67 per Pail
```

---

## Conversion Formulas (Critical for Forecasting)

### Price Conversion

```
New Price (Purchasing UoM) = Old Price (Base UoM) × Conversion Factor
```

**Example:**
```
Old: $1.50 per Litre
Factor: 20 Litres per Pail
New: $1.50 × 20 = $30.00 per Pail
```

### Quantity Conversion

```
New Quantity (Purchasing UoM) = Old Quantity (Base UoM) ÷ Conversion Factor
```

**Example:**
```
Old: 1000 Litres
Factor: 20 Litres per Pail
New: 1000 ÷ 20 = 50 Pails
```

### Inventory Value Preservation

```
Value (Base) = Value (Purchasing)
Old Price × Old Qty = New Price × New Qty
```

**Example:**
```
$1.50/Litre × 1000 Litres = $30.00/Pail × 50 Pails = $1,500
```

---

## Conversion Factors (Source of Truth)

### Where Factors Come From

**SAP B1 Tables:**
- **OITM.UgpEntry**: UoM Group Entry field on item master
- **UGP1.Factor**: Actual conversion factor
- **UGP1.BaseUom**: Base unit (Litre, KG)
- **UGP1.AltUoM**: Alternative unit (Pail, Drum, Tote)

**Query to Get Conversion Factors:**
```sql
SELECT
    T0.ItemCode,
    T0.InvntryUom AS 'Base_UoM',
    T0.BuyUnitMsr AS 'Purchasing_UoM',
    T1.Factor AS 'Conversion_Factor',
    T1.BaseUom AS 'Factor_Base_UoM',
    T1.AltUoM AS 'Factor_Alt_UoM'
FROM OITM T0
LEFT JOIN UGP1 T1 ON T0.UgpEntry = T1.UoMEntry
WHERE T0.ItemCode LIKE '%-[A-Z0-9][A-Z0-9][A-Z0-9]'
```

### Common Conversion Factors (Expected)

| From UoM | To UoM | Typical Factor | Item Count |
|----------|--------|----------------|------------|
| Litre | Pail | 20 | 991 |
| Litre | Drum | 200 | 422 |
| Kg | Pail | 25 | 322 |
| Kg | Drum | 250 | 239 |
| Kg | Tote | 1,000 | 85 |
| Litre | Tote | 1,000 | 44 |

**⚠️ IMPORTANT:** Actual factors come from SAP UGP1 table - do NOT hardcode!

---

## Impact on Forecasting Tool

### Critical Design Requirements

Your forecasting tool **MUST**:

#### 1. Detect Item Master State

**Detect Current State:**
```python
def is_current_state(item_code):
    """
    Returns True if item uses regional code structure (BASE-REG)
    """
    return '-' in item_code and len(item_code.split('-')[-1]) == 3
```

**Detect Future State:**
```python
def is_future_state(item_code):
    """
    Returns True if item is consolidated (no regional suffix)
    """
    return '-' not in item_code
```

#### 2. Handle Both UoM States

**Current State Logic:**
```python
# Current: Costs/quantities in BASE units (Litre, KG)
if is_current_state(item_code):
    unit = item_data['InvntryUom']  # Returns: "Litre", "KG"
    cost = item_data['AvgPrice']     # Cost per BASE unit
    quantity = item_data['OnHand']   # Quantity in BASE units
```

**Future State Logic:**
```python
# Future: Costs/quantities in PURCHASING units (Pail, Drum, Tote)
if is_future_state(item_code):
    unit = item_data['BuyUnitMsr']   # Returns: "Pail", "Drum", "Tote"
    cost = item_data['AvgPrice']     # Cost per PURCHASING unit
    quantity = item_data['OnHand']   # Quantity in PURCHASING units
```

#### 3. Apply UoM Conversion (if needed)

**If Forecasting in Different Units:**
```python
def convert_uom(quantity, from_uom, to_uom, conversion_factor):
    """
    Convert quantity between UoMs using conversion factor

    Example:
        convert_uom(1000, 'Litre', 'Pail', 20) → 50
        convert_uom(50, 'Pail', 'Litre', 20) → 1000
    """
    if from_uom == to_uom:
        return quantity

    # Base → Purchasing: divide by factor
    # Purchasing → Base: multiply by factor
    if from_uom in ['Litre', 'KG'] and to_uom in ['Pail', 'Drum', 'Tote']:
        return quantity / conversion_factor
    else:
        return quantity * conversion_factor
```

#### 4. Handle Warehouse Mapping

**Current State:**
```python
# Warehouse embedded in item code suffix
warehouse = extract_warehouse_from_item_code(item_code)
# Returns: "TOR" from "30027C-TOR"
```

**Future State:**
```python
# Warehouse in OITW table (multiple records per item)
warehouses = get_warehouses_for_item(item_code)
# Returns: ["050-TOR1", "030-CGY1", "000-DEL1"]
```

#### 5. Preserve Inventory Values

**Critical Rule:**
```python
# Before consolidation (current state)
inventory_value_base = cost_base_unit × quantity_base_units

# After consolidation (future state)
inventory_value_purchasing = cost_purchasing_unit × quantity_purchasing_units

# These MUST be equal!
assert inventory_value_base == inventory_value_purchasing
```

---

## Forecasting Scenarios

### Scenario 1: Demand Forecasting

**Current State:**
```
Item: 30027C-TOR
Historical Demand: 1000 Litres/month
UoM: Litre (base unit)
```

**Future State:**
```
Item: 30027C
Historical Demand: 50 Pails/month (1000 ÷ 20)
UoM: Pail (purchasing unit)
```

**Tool Logic:**
```python
def forecast_demand(item_code, historical_data):
    if is_current_state(item_code):
        # Demand in base units (Litre, KG)
        demand_base = historical_data['avg_monthly_demand']
        return demand_base, historical_data['uom']

    if is_future_state(item_code):
        # Demand in purchasing units (Pail, Drum, Tote)
        # May need to convert historical data from base units
        conversion_factor = get_conversion_factor(item_code)
        demand_base = historical_data['avg_monthly_demand_base']
        demand_purch = demand_base / conversion_factor
        return demand_purch, 'Pail'
```

### Scenario 2: Purchase Order Forecasting

**Current State:**
```
Order: 10,000 Litres (base unit)
Vendor sells in: Pails (20 Litres each)
Order quantity in vendor UoM: 10,000 ÷ 20 = 500 Pails
```

**Future State:**
```
Order: 500 Pails (purchasing unit)
Vendor sells in: Pails
Order quantity in vendor UoM: 500 Pails (no conversion needed)
```

**Tool Logic:**
```python
def calculate_purchase_order(item_code, demand_quantity):
    if is_current_state(item_code):
        # Demand in base units, convert to purchasing UoM
        factor = get_conversion_factor(item_code)
        po_quantity = demand_quantity / factor
        return po_quantity, item_data['BuyUnitMsr']

    if is_future_state(item_code):
        # Demand already in purchasing UoM
        return demand_quantity, item_data['BuyUnitMsr']
```

### Scenario 3: Inventory Planning

**Current State:**
```
Item: 30027C-TOR
On Hand: 1000 Litres
Safety Stock: 200 Litres
Max Level: 1500 Litres
```

**Future State:**
```
Item: 30027C
On Hand: 50 Pails (1000 ÷ 20)
Safety Stock: 10 Pails (200 ÷ 20)
Max Level: 75 Pails (1500 ÷ 20)
```

**Tool Logic:**
```python
def plan_inventory(item_code, on_hand, safety_stock, max_level):
    if is_current_state(item_code):
        # All in base units - no conversion
        reorder_point = safety_stock
        order_qty = max_level - on_hand

    if is_future_state(item_code):
        # All in purchasing units - no conversion
        reorder_point = safety_stock
        order_qty = max_level - on_hand

    return reorder_point, order_qty
```

**Key Point:** Reorder points and max levels will ALSO be converted to purchasing units!

---

## Data Migration Considerations

### Historical Data Conversion

**When Consolidation Occurs:**

1. **Historical transactions** (ORDR, PDN1, etc.) remain in BASE units
2. **New transactions** will be in PURCHASING units
3. **Forecasting tool must handle BOTH** in historical analysis

**Recommended Approach:**
```python
def normalize_historical_data(transaction):
    """
    Convert all historical transactions to purchasing UoM for consistency
    """
    item_code = transaction['ItemCode']
    quantity = transaction['Quantity']
    uom = transaction['UoM']

    # Skip if already consolidated
    if '-' not in item_code:
        return quantity, uom

    # Convert historical data from base to purchasing UoM
    factor = get_conversion_factor(item_code)
    quantity_purch = quantity / factor
    uom_purch = get_purchasing_uom(item_code)

    return quantity_purch, uom_purch
```

### Forecast Calibration

**Before Consolidation:**
```
Train forecast model on historical data in BASE units
Validate against demand in BASE units
```

**After Consolidation:**
```
Option A: Retrain model on converted historical data (purchasing units)
Option B: Apply conversion factor to forecast outputs
Option C: Maintain dual forecasts (base + purchasing) during transition
```

**Recommended:** Option C - maintain both during transition period

---

## Compatibility Checklist

### ✅ MUST Support

- [ ] Detect item master state (current vs future)
- [ ] Handle BASE units (Litre, KG) - current state
- [ ] Handle PURCHASING units (Pail, Drum, Tote) - future state
- [ ] Apply UoM conversion when needed
- [ ] Map warehouse codes (old → new)
- [ ] Preserve inventory values across conversion
- [ ] Handle regional item codes (BASE-REG)
- [ ] Handle consolidated item codes (BASE)

### ⚠️ SHOULD Support

- [ ] Graceful degradation during consolidation transition
- [ ] Warning messages for mixed data states
- [ ] Conversion factor validation
- [ ] Historical data normalization
- [ ] Dual UoM display (base + purchasing)

### ❌ MUST NOT Do

- [ ] Hardcode conversion factors (must query from SAP)
- [ ] Assume single warehouse per item (future state has multiple)
- [ ] Ignore inventory value preservation
- [ ] Mix current/future data without conversion
- [ ] Break when consolidation occurs

---

## Testing Strategy

### Test Cases

**Test Case 1: Current State**
```
Input: 30027C-TOR, 1000 Litres, $1.50/Litre
Expected: Forecast in Litres, cost in $/Litre
```

**Test Case 2: Future State**
```
Input: 30027C, 50 Pails, $30.00/Pail
Expected: Forecast in Pails, cost in $/Pail
```

**Test Case 3: Conversion Accuracy**
```
Input: 1000 Litres, factor 20
Expected: 50 Pails
Verify: $1.50/L × 1000 L = $30.00/Pail × 50 Pail = $1,500
```

**Test Case 4: Mixed State (Transition)**
```
Input: Some items current, some future
Expected: Tool handles both correctly
```

**Test Case 5: Warehouse Mapping**
```
Current: 30027C-TOR → Warehouse 50
Future: 30027C → Warehouse 050-TOR1
Expected: Correct warehouse in both states
```

---

## Sample SQL Queries for Forecasting Tool

### Query 1: Get Conversion Factor

```sql
SELECT
    T0.ItemCode,
    T0.InvntryUom AS 'BaseUoM',
    T0.BuyUnitMsr AS 'PurchasingUoM',
    T1.Factor AS 'ConversionFactor'
FROM OITM T0
LEFT JOIN UGP1 T1 ON T0.UgpEntry = T1.UoMEntry
WHERE T0.ItemCode = 'YOUR_ITEM_CODE'
```

### Query 2: Get Item State

```sql
SELECT
    ItemCode,
    CASE
        WHEN ItemCode LIKE '%-[A-Z0-9][A-Z0-9][A-Z0-9]' THEN 'CURRENT'
        ELSE 'FUTURE'
    END AS 'ItemState',
    InvntryUom,
    BuyUnitMsr
FROM OITM
WHERE ItemCode = 'YOUR_ITEM_CODE'
```

### Query 3: Get Warehouses for Item

```sql
-- Current state: Warehouse embedded in code
SELECT
    ItemCode,
    SUBSTRING(ItemCode, CHARINDEX('-', ItemCode) + 1, 3) AS 'Warehouse'
FROM OITM
WHERE ItemCode LIKE '%-[A-Z0-9][A-Z0-9][A-Z0-9]'

-- Future state: Multiple warehouses per item
SELECT
    T0.ItemCode,
    T1.WhsCode AS 'Warehouse'
FROM OITM T0
INNER JOIN OITW T1 ON T0.ItemCode = T1.ItemCode
WHERE T0.ItemCode = 'YOUR_ITEM_CODE'
  AND T1.OnHand > 0
```

---

## API/Integration Recommendations

### Required Data Fields

**For Forecasting Calculations:**
```json
{
  "item_code": "30027C-TOR",
  "item_state": "CURRENT", // or "FUTURE"
  "base_uom": "Litre",
  "purchasing_uom": "Pail",
  "conversion_factor": 20,
  "current_cost": 1.50,
  "current_uom": "Litre",
  "on_hand": 1000,
  "on_hand_uom": "Litre"
}
```

### UoM Conversion Service

**Recommended API Endpoint:**
```python
POST /api/uom/convert
{
  "item_code": "30027C-TOR",
  "quantity": 1000,
  "from_uom": "Litre",
  "to_uom": "Pail"
}

Response:
{
  "converted_quantity": 50,
  "conversion_factor": 20,
  "item_state": "CURRENT"
}
```

---

## Common Pitfalls to Avoid

### ❌ Pitfall 1: Ignoring Item State

**Wrong:**
```python
# Always treats items as current state
demand = get_demand(item_code)  # Assumes base units
```

**Correct:**
```python
# Check state first
if is_current_state(item_code):
    demand = get_demand(item_code)  # Base units
else:
    demand = get_demand(item_code)  # Purchasing units
```

### ❌ Pitfall 2: Hardcoding Conversion Factors

**Wrong:**
```python
LITRES_PER_PAIL = 20  # Hardcoded!
qty_pail = qty_litre / LITRES_PER_PAIL
```

**Correct:**
```python
factor = get_conversion_factor_from_sap(item_code)
qty_pail = qty_litre / factor
```

### ❌ Pitfall 3: Not Preserving Values

**Wrong:**
```python
# Changes inventory value after conversion
new_value = old_value  # Lost value preservation!
```

**Correct:**
```python
# Preserve value across conversion
assert (old_price * old_qty) == (new_price * new_qty)
```

### ❌ Pitfall 4: Assuming Single Warehouse

**Wrong:**
```python
warehouse = get_warehouse_for_item(item_code)  # Only one!
```

**Correct:**
```python
if is_current_state(item_code):
    warehouse = extract_from_suffix(item_code)  # Single
else:
    warehouses = get_all_warehouses(item_code)  # Multiple
```

---

## Contact & Support

**Consolidation Team Questions:**
- UoM conversion logic: See `UOM_CONVERSION_COST_CALCULATION.md`
- Item consolidation details: See `IMPLEMENTATION_PLAN.md`
- Warehouse mapping: See `WAREHOUSE_MIGRATION.md`

**SAP Data Access:**
- Conversion factors: Query `OITM.UgpEntry` → `UGP1.Factor`
- Item state: Check for regional suffix pattern
- Warehouse codes: See `Q4_1_warehouses.tsv`

**Critical Dates:**
- Consolidation execution: TBD
- Cutover window: TBD
- Dual-operation period: Until all historical data converted

---

## Summary

**The forecasting tool MUST:**

1. ✅ Detect item master state (current vs future)
2. ✅ Handle both UoM systems (base vs purchasing)
3. ✅ Query conversion factors from SAP (never hardcode)
4. ✅ Preserve inventory values across conversion
5. ✅ Map warehouse codes correctly
6. ✅ Support transition period with both states

**The tool MUST NOT:**

1. ❌ Break when consolidation occurs
2. ❌ Hardcode conversion factors
3. ❌ Ignore inventory value preservation
4. ❌ Assume single warehouse per item
5. ❌ Mix data states without conversion

**Success Criteria:**

- ✅ Works correctly BEFORE consolidation (current state)
- ✅ Works correctly AFTER consolidation (future state)
- ✅ Handles transition period gracefully
- ✅ Preserves data integrity across conversion
- ✅ No manual intervention required during cutover
