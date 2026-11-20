"""The six discrepancy detectors, run over the simulated PLM/ERP/MES
dataset. Each detector names its class and returns enough of the
originating rows (item id, BOM line, work order id, ERP row) to drill back
to the exact source, which is the same information the Grafana board's
drill-down panels query (see dashboard.py and db.py).
"""
from .config import UOM_CONVERSIONS


def detect_part_number_mismatch(dataset):
    found = []
    for item_id, erp in dataset["erp_items"].items():
        if erp.plm_item_id not in dataset["items"]:
            found.append({
                "class": "part_number_mismatch", "erp_item_id": item_id,
                "source_rows": {"erp_item_master": item_id, "plm_item": erp.plm_item_id},
            })
    return found


def detect_uom_mismatch(dataset):
    found = []
    for item_id, erp in dataset["erp_items"].items():
        if erp.plm_item_id not in dataset["items"]:
            continue  # already part_number_mismatch's territory, not double counted
        plm_uom = dataset["items"][erp.plm_item_id].plm_uom
        if erp.erp_uom == plm_uom:
            continue
        if (erp.erp_uom, plm_uom) in UOM_CONVERSIONS:
            continue
        found.append({
            "class": "uom_mismatch", "erp_item_id": item_id,
            "source_rows": {"erp_item_master": item_id, "plm_item": erp.plm_item_id},
            "plm_uom": plm_uom, "erp_uom": erp.erp_uom,
        })
    return found


def detect_revision_skew(dataset):
    found = []
    for wo in dataset["work_orders"]:
        item = dataset["items"].get(wo.item_id)
        if item is None:
            continue
        if wo.revision_used != item.current_approved_revision:
            found.append({
                "class": "revision_skew", "wo_id": wo.wo_id,
                "source_rows": {"mes_work_order": wo.wo_id, "plm_item": wo.item_id},
                "revision_used": wo.revision_used,
                "current_approved_revision": item.current_approved_revision,
            })
    return found


def detect_bom_orphan_reference(dataset):
    found = []
    for line in dataset["bom_lines"]:
        if line.child_item_id not in dataset["items"]:
            found.append({
                "class": "bom_orphan_reference",
                "parent_item_id": line.parent_item_id, "child_item_id": line.child_item_id,
                "source_rows": {"plm_bom_line": (line.parent_item_id, line.child_item_id)},
            })
    return found


def detect_invalid_bom_quantity(dataset):
    found = []
    for line in dataset["bom_lines"]:
        if line.qty_per <= 0:
            found.append({
                "class": "invalid_bom_quantity",
                "parent_item_id": line.parent_item_id, "child_item_id": line.child_item_id,
                "qty_per": line.qty_per,
                "source_rows": {"plm_bom_line": (line.parent_item_id, line.child_item_id)},
            })
    return found


def detect_on_hand_shortage(dataset, explode_fn, memo=None):
    memo = {} if memo is None else memo
    found = []
    for wo in dataset["work_orders"]:
        if wo.item_id not in dataset["items"]:
            continue
        requirements = explode_fn(dataset, wo.item_id, wo.qty_required, memo)
        for leaf_item_id, needed in requirements.items():
            on_hand = dataset["on_hand"].get(leaf_item_id)
            available = on_hand.qty_on_hand if on_hand else 0.0
            if needed > available:
                found.append({
                    "class": "on_hand_shortage", "wo_id": wo.wo_id, "item_id": leaf_item_id,
                    "required": needed, "on_hand": available,
                    "source_rows": {"mes_work_order": wo.wo_id, "erp_on_hand": leaf_item_id},
                })
    return found


DETECTORS = {
    "part_number_mismatch": detect_part_number_mismatch,
    "uom_mismatch": detect_uom_mismatch,
    "revision_skew": detect_revision_skew,
    "bom_orphan_reference": detect_bom_orphan_reference,
    "invalid_bom_quantity": detect_invalid_bom_quantity,
}


def run_all_detectors(dataset, explode_fn):
    results = {name: fn(dataset) for name, fn in DETECTORS.items()}
    results["on_hand_shortage"] = detect_on_hand_shortage(dataset, explode_fn)
    return results
