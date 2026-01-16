"""
Pydantic models for data validation and schema enforcement.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class DataType(str, Enum):
    """Supported data types."""
    ITEMS = "items"
    VENDORS = "vendors"
    WAREHOUSES = "warehouses"
    INVENTORY_CURRENT = "inventory_current"
    SALES_ORDERS = "sales_orders"
    PURCHASE_ORDERS = "purchase_orders"
    COSTS = "costs"
    PRICING = "pricing"


# ============================================================================
# Base Models
# ============================================================================

class IngestionPayload(BaseModel):
    """Base payload structure for all ingestion requests."""
    data_type: DataType
    source: str = Field(default="SAP_B1", description="Data source system")
    timestamp: str = Field(description="ISO format timestamp")
    records: List[dict]

    @validator('timestamp')
    def parse_timestamp(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}")


class IngestionResponse(BaseModel):
    """Response from ingestion endpoint."""
    success: bool
    message: str
    records_processed: int = 0
    errors: List[str] = []
    data_type: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    timestamp: str


# ============================================================================
# Domain Models (for validation)
# ============================================================================

class ItemRecord(BaseModel):
    """Item master data record."""
    item_code: str = Field(..., max_length=50)
    item_description: str = Field(..., max_length=500)
    item_group: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    base_uom: Optional[str] = Field("EA", max_length=10)
    purch_uom: Optional[str] = Field("EA", max_length=10)
    qty_per_purch_uom: Optional[float] = Field(1)
    sales_uom: Optional[str] = Field("EA", max_length=10)
    qty_per_sales_uom: Optional[float] = Field(1)
    preferred_vendor_code: Optional[str] = Field(None, max_length=50)
    is_active: bool = True


class VendorRecord(BaseModel):
    """Vendor master data record."""
    vendor_code: str = Field(..., max_length=50)
    vendor_name: str = Field(..., max_length=500)
    contact_name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class WarehouseRecord(BaseModel):
    """Warehouse/location record."""
    warehouse_code: str = Field(..., max_length=20)
    warehouse_name: str = Field(..., max_length=200)
    region: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class InventoryRecord(BaseModel):
    """Inventory current level record."""
    item_code: str = Field(..., max_length=50)
    warehouse_code: str = Field(..., max_length=20)
    on_hand_qty: float = Field(ge=0)
    on_order_qty: float = Field(default=0, ge=0)
    committed_qty: float = Field(default=0, ge=0)
    available_qty: float = Field(ge=0)
    uom: str = Field(default="EA", max_length=10)


class SalesOrderRecord(BaseModel):
    """Sales order record."""
    order_id: str = Field(..., max_length=50)
    item_code: str = Field(..., max_length=50)
    order_date: str  # ISO format date
    quantity: float = Field(gt=0)
    uom: str = Field(default="EA", max_length=10)
    warehouse_code: str = Field(..., max_length=20)
    customer_code: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=100)


class PurchaseOrderRecord(BaseModel):
    """Purchase order record."""
    order_id: str = Field(..., max_length=50)
    item_code: str = Field(..., max_length=50)
    order_date: str  # ISO format date
    quantity: float = Field(gt=0)
    uom: str = Field(default="EA", max_length=10)
    vendor_code: str = Field(..., max_length=50)
    warehouse_code: str = Field(..., max_length=20)


class CostRecord(BaseModel):
    """Cost data record."""
    item_code: str = Field(..., max_length=50)
    unit_cost: float = Field(ge=0)
    freight: float = Field(default=0, ge=0)
    duty: float = Field(default=0, ge=0)
    total_landed_cost: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=10)
    effective_date: str  # ISO format date
    vendor_code: Optional[str] = Field(None, max_length=50)


class PricingRecord(BaseModel):
    """Pricing data record."""
    item_code: str = Field(..., max_length=50)
    price_level: str = Field(..., max_length=50)
    region: Optional[str] = Field(None, max_length=100)
    unit_price: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=10)
    effective_date: str  # ISO format date
    is_active: bool = True


# ============================================================================
# Validation by Data Type
# ============================================================================

VALIDATORS = {
    DataType.ITEMS: ItemRecord,
    DataType.VENDORS: VendorRecord,
    DataType.WAREHOUSES: WarehouseRecord,
    DataType.INVENTORY_CURRENT: InventoryRecord,
    DataType.SALES_ORDERS: SalesOrderRecord,
    DataType.PURCHASE_ORDERS: PurchaseOrderRecord,
    DataType.COSTS: CostRecord,
    DataType.PRICING: PricingRecord,
}


def validate_records(data_type: DataType, records: List[dict]) -> tuple[List[dict], List[str]]:
    """
    Validate records against their schema.

    Args:
        data_type: Type of data being validated
        records: List of record dictionaries

    Returns:
        Tuple of (validated_records, errors)
    """
    validator_class = VALIDATORS.get(data_type)
    if not validator_class:
        return records, [f"No validator found for data_type: {data_type}"]

    validated = []
    errors = []

    for i, record in enumerate(records):
        try:
            validated_record = validator_class(**record).dict()
            validated.append(validated_record)
        except Exception as e:
            errors.append(f"Record {i}: {str(e)}")

    return validated, errors
