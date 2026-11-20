"""Synthetic PLM, ERP and MES data generation for the clear-to-build
benchmark. All data is simulated with a fixed RNG seed; nothing here talks
to a real Oracle Fusion Cloud, Teamcenter or MES instance.
"""
import random

from .config import LEVEL_COUNTS, RNG_SEED
from .model import BomLine, ErpItem, Item, OnHand, PurchaseOrder, WorkOrder

FULL_RELOAD_DAYS = 90  # operational history span used by incremental.py


def _item_id(level_prefix, n):
    return f"P-{level_prefix}{n:06d}"


def build_items(rng):
    items = {}
    counters = {"raw": 0, "component": 0, "subassembly": 0, "finished": 0}
    prefixes = {"raw": "0", "component": "1", "subassembly": "2", "finished": "3"}
    pools = {"raw": [], "component": [], "subassembly": [], "finished": []}
    for level, count in LEVEL_COUNTS.items():
        for _ in range(count):
            counters[level] += 1
            item_id = _item_id(prefixes[level], counters[level])
            uom = rng.choice(["EA", "KG", "L"])
            rev = rng.choice(["A", "B"])
            approved = ["A", "B"] if rev == "B" else ["A"]
            items[item_id] = Item(
                item_id=item_id,
                description=f"{level} part {item_id}",
                level=level,
                plm_uom=uom,
                approved_revisions=approved,
                current_approved_revision=rev,
            )
            pools[level].append(item_id)
    return items, pools


def build_bom_lines(rng, pools):
    bom_lines = []
    bom_index = {}  # parent_item_id -> list[BomLine]
    child_pool_for = {
        "component": pools["raw"],
        "subassembly": pools["component"] + pools["raw"],
        "finished": pools["subassembly"] + pools["component"],
    }
    for level in ("component", "subassembly", "finished"):
        candidates = child_pool_for[level]
        for parent_id in pools[level]:
            n_children = rng.randint(2, 5)
            children = rng.sample(candidates, min(n_children, len(candidates)))
            lines = []
            for child_id in children:
                qty = rng.randint(1, 8)
                line = BomLine(parent_item_id=parent_id, child_item_id=child_id,
                               qty_per=float(qty), line_uom="EA")
                bom_lines.append(line)
                lines.append(line)
            bom_index[parent_id] = lines
    return bom_lines, bom_index


def build_work_orders(rng, items, pools):
    work_orders = []
    for i, item_id in enumerate(pools["finished"], start=1):
        item = items[item_id]
        wo_id = f"WO-{i:06d}"
        qty = rng.randint(5, 50)
        due_day = rng.randint(0, FULL_RELOAD_DAYS - 1)
        work_orders.append(WorkOrder(
            wo_id=wo_id, item_id=item_id, revision_used=item.current_approved_revision,
            qty_required=qty, due_date=f"day-{due_day}",
        ))
    return work_orders


def build_erp(items):
    erp_items = {}
    on_hand = {}
    for item_id, item in items.items():
        erp_items[item_id] = ErpItem(erp_item_id=item_id, plm_item_id=item_id, erp_uom=item.plm_uom)
        on_hand[item_id] = OnHand(erp_item_id=item_id, qty_on_hand=100000.0, uom=item.plm_uom)
    return erp_items, on_hand


def build_purchase_orders(rng, items, count=3000):
    pos = []
    item_ids = list(items.keys())
    for i in range(count):
        item_id = rng.choice(item_ids)
        item = items[item_id]
        day = rng.randint(0, FULL_RELOAD_DAYS - 1)
        pos.append(PurchaseOrder(
            po_id=f"PO-{i + 1:06d}", erp_item_id=item_id, qty_ordered=float(rng.randint(10, 500)),
            uom=item.plm_uom, promise_date=f"day-{day}", status="open",
        ))
    return pos


def generate_dataset(seed=RNG_SEED):
    rng = random.Random(seed)
    items, pools = build_items(rng)
    bom_lines, bom_index = build_bom_lines(rng, pools)
    work_orders = build_work_orders(rng, items, pools)
    erp_items, on_hand = build_erp(items)
    purchase_orders = build_purchase_orders(rng, items)
    return {
        "items": items,
        "pools": pools,
        "bom_lines": bom_lines,
        "bom_index": bom_index,
        "work_orders": work_orders,
        "erp_items": erp_items,
        "on_hand": on_hand,
        "purchase_orders": purchase_orders,
    }
