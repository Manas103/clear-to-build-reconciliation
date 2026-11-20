"""Row-level models for the three simulated systems of record."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Item:
    """A PLM item master row."""
    item_id: str
    description: str
    level: str
    plm_uom: str
    approved_revisions: List[str]
    current_approved_revision: str


@dataclass
class BomLine:
    """A PLM bill-of-material line: one (parent, child, qty_per) edge."""
    parent_item_id: str
    child_item_id: str
    qty_per: float
    line_uom: str


@dataclass
class WorkOrder:
    """An MES work order to build `qty_required` of `item_id`."""
    wo_id: str
    item_id: str
    revision_used: str
    qty_required: int
    due_date: str


@dataclass
class ErpItem:
    """An ERP item-master row. `plm_item_id` is the crosswalk back to PLM;
    a broken crosswalk points at an id that does not exist in PLM."""
    erp_item_id: str
    plm_item_id: Optional[str]
    erp_uom: str


@dataclass
class OnHand:
    """ERP on-hand inventory for one item."""
    erp_item_id: str
    qty_on_hand: float
    uom: str


@dataclass
class PurchaseOrder:
    """An ERP open purchase order line."""
    po_id: str
    erp_item_id: str
    qty_ordered: float
    uom: str
    promise_date: str
    status: str
