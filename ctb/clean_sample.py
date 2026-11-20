"""A 1,000-record clean holdout, generated and checked independently of the
main 12,000-part dataset, so the false-positive rate is measured on data
that never shares state with whatever is seeded into the main corpus.
"""
import random

from .model import BomLine, ErpItem, Item, OnHand, WorkOrder
from . import reconcile


def generate_clean_sample(seed, n=1000):
    rng = random.Random(seed)
    records = []
    for i in range(n):
        item_id = f"CLN-{i:05d}"
        child_id = f"CLN-{i:05d}-C"
        uom = rng.choice(["EA", "KG", "L"])
        item = Item(item_id=item_id, description="clean sample item", level="component",
                    plm_uom=uom, approved_revisions=["A"], current_approved_revision="A")
        child = Item(item_id=child_id, description="clean sample child", level="raw",
                     plm_uom=uom, approved_revisions=["A"], current_approved_revision="A")
        line = BomLine(parent_item_id=item_id, child_item_id=child_id,
                       qty_per=float(rng.randint(1, 5)), line_uom=uom)
        wo = WorkOrder(wo_id=f"CLN-WO-{i:05d}", item_id=item_id, revision_used="A",
                       qty_required=rng.randint(1, 10), due_date="day-1")
        records.append({
            "items": {item_id: item, child_id: child},
            "bom_index": {item_id: [line]},
            "bom_lines": [line],
            "work_orders": [wo],
            "erp_items": {
                item_id: ErpItem(erp_item_id=item_id, plm_item_id=item_id, erp_uom=uom),
                child_id: ErpItem(erp_item_id=child_id, plm_item_id=child_id, erp_uom=uom),
            },
            "on_hand": {
                item_id: OnHand(erp_item_id=item_id, qty_on_hand=100000.0, uom=uom),
                child_id: OnHand(erp_item_id=child_id, qty_on_hand=100000.0, uom=uom),
            },
            "purchase_orders": [],
        })
    return records


def count_false_positives(clean_records, explode_fn):
    false_positives = 0
    for record in clean_records:
        results = reconcile.run_all_detectors(record, explode_fn)
        for found in results.values():
            false_positives += len(found)
    return false_positives
