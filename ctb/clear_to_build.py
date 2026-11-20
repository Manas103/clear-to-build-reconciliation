"""Clear-to-build status per work order: explode the BOM, compare required
quantity to on-hand at each leaf part, and report CLEAR or SHORT with every
leaf part traced back to its ERP on-hand row and the MES work order.

Limitation (disclosed, see README): this does not net open purchase-order
receipts against a shortage. Open POs are still generated and still feed
the part_number_mismatch / uom_mismatch detectors, but clear-to-build itself
compares required quantity to on-hand only.
"""


def clear_to_build(dataset, wo, explode_fn, memo=None):
    requirements = explode_fn(dataset, wo.item_id, wo.qty_required, memo if memo is not None else {})
    shortages = []
    for leaf_item_id, needed in requirements.items():
        on_hand = dataset["on_hand"].get(leaf_item_id)
        available = on_hand.qty_on_hand if on_hand else 0.0
        if needed > available:
            shortages.append({
                "item_id": leaf_item_id, "required": needed, "on_hand": available,
                "shortfall": needed - available,
                "source_rows": {"mes_work_order": wo.wo_id, "erp_on_hand": leaf_item_id,
                                 "plm_item": wo.item_id},
            })
    status = "SHORT" if shortages else "CLEAR"
    return {"wo_id": wo.wo_id, "item_id": wo.item_id, "status": status, "shortages": shortages}


def compute_all(dataset, explode_fn):
    memo = {}
    return [clear_to_build(dataset, wo, explode_fn, memo) for wo in dataset["work_orders"]]
