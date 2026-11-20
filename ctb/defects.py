"""Deliberate, ground-truth-tracked defect injection for the
240-seeded-discrepancy benchmark (40 per class across the 6 classes).
Sampling pools are disjoint within each source table so no single row is
double-injected, which would make the 40-per-class count ambiguous.
"""
from .config import PER_CLASS_DEFECTS


def inject_all_defects(dataset, rng, explode_fn):
    ground_truth = []

    erp_item_ids = list(dataset["erp_items"].keys())
    rng.shuffle(erp_item_ids)
    pnm_targets = erp_item_ids[:PER_CLASS_DEFECTS]
    uom_targets = erp_item_ids[PER_CLASS_DEFECTS:2 * PER_CLASS_DEFECTS]

    bom_lines = list(dataset["bom_lines"])
    rng.shuffle(bom_lines)
    orphan_targets = bom_lines[:PER_CLASS_DEFECTS]
    invalid_qty_targets = bom_lines[PER_CLASS_DEFECTS:2 * PER_CLASS_DEFECTS]

    work_orders = list(dataset["work_orders"])
    rng.shuffle(work_orders)
    revision_targets = work_orders[:PER_CLASS_DEFECTS]
    shortage_targets = work_orders[PER_CLASS_DEFECTS:2 * PER_CLASS_DEFECTS]

    for item_id in pnm_targets:
        dataset["erp_items"][item_id].plm_item_id = f"{item_id}-UNMAPPED"
        ground_truth.append({"class": "part_number_mismatch", "erp_item_id": item_id})

    for item_id in uom_targets:
        item = dataset["items"][item_id]
        erp = dataset["erp_items"][item_id]
        erp.erp_uom = next(u for u in ("L", "KG", "EA") if u != item.plm_uom)
        ground_truth.append({"class": "uom_mismatch", "erp_item_id": item_id})

    for wo in revision_targets:
        item = dataset["items"][wo.item_id]
        stale = [r for r in item.approved_revisions if r != item.current_approved_revision]
        wo.revision_used = stale[0] if stale else "X"
        ground_truth.append({"class": "revision_skew", "wo_id": wo.wo_id})

    for i, line in enumerate(orphan_targets):
        line.child_item_id = f"P-9{i:06d}"
        ground_truth.append({
            "class": "bom_orphan_reference",
            "parent_item_id": line.parent_item_id, "child_item_id": line.child_item_id,
        })

    for line in invalid_qty_targets:
        line.qty_per = rng.choice([0.0, -1.0])
        ground_truth.append({
            "class": "invalid_bom_quantity",
            "parent_item_id": line.parent_item_id, "child_item_id": line.child_item_id,
        })

    # on_hand_shortage is injected last since it reads the BOM structure that
    # the orphan/invalid-quantity injections above may already have altered,
    # which explode_fn must (and does) tolerate. A leaf part shared by two
    # different work orders must only be shrunk once: shrinking it again for
    # a second work order can silently raise it back above the first work
    # order's requirement, which is exactly the kind of self-defeating seed
    # this benchmark exists to avoid, so each leaf item is used for at most
    # one seeded shortage.
    used_leaf_items = set()
    for wo in shortage_targets:
        requirements = explode_fn(dataset, wo.item_id, wo.qty_required, {})
        leaf_item_id = next((lid for lid in requirements if lid not in used_leaf_items), None)
        if leaf_item_id is None:
            continue
        used_leaf_items.add(leaf_item_id)
        needed = requirements[leaf_item_id]
        dataset["on_hand"][leaf_item_id].qty_on_hand = max(0.0, needed - rng.randint(1, 20))
        ground_truth.append({"class": "on_hand_shortage", "wo_id": wo.wo_id, "item_id": leaf_item_id})

    return ground_truth
