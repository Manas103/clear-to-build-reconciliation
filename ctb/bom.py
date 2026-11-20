"""Multi-level BOM explosion: a fast, memoized per-unit aggregator diffed
against a deliberately naive, unoptimized recursive implementation (the
reference oracle required for anything where correctness is non-obvious).
"""


def _children(dataset, item_id):
    return dataset["bom_index"].get(item_id, [])


def _per_unit_leaf_requirements(dataset, item_id, memo):
    if item_id in memo:
        return memo[item_id]
    lines = _children(dataset, item_id)
    if not lines:
        result = {item_id: 1.0}
        memo[item_id] = result
        return result
    result = {}
    for line in lines:
        if line.child_item_id not in dataset["items"]:
            continue  # bom_orphan_reference: flagged separately, not expanded
        if line.qty_per <= 0:
            continue  # invalid_bom_quantity: flagged separately, contributes nothing
        child_reqs = _per_unit_leaf_requirements(dataset, line.child_item_id, memo)
        for leaf_id, per_unit in child_reqs.items():
            result[leaf_id] = result.get(leaf_id, 0.0) + per_unit * line.qty_per
    memo[item_id] = result
    return result


def explode_fast(dataset, item_id, qty, memo=None):
    """Per-unit leaf requirements are memoized per item id, so a raw part
    shared by hundreds of subassemblies is only ever walked once no matter
    how many work orders or parents reference it, when `memo` is reused
    across calls."""
    memo = {} if memo is None else memo
    per_unit = _per_unit_leaf_requirements(dataset, item_id, memo)
    return {leaf_id: amount * qty for leaf_id, amount in per_unit.items()}


def explode_naive(dataset, item_id, qty):
    """Plain recursion with no memoization anywhere: every shared subtree is
    re-walked from scratch each time it is reached. Used only to verify
    explode_fast by exact diff, not at full-scale benchmark volume."""
    totals = {}

    def walk(current_id, current_qty):
        lines = _children(dataset, current_id)
        if not lines:
            totals[current_id] = totals.get(current_id, 0.0) + current_qty
            return
        for line in lines:
            if line.child_item_id not in dataset["items"]:
                continue
            if line.qty_per <= 0:
                continue
            walk(line.child_item_id, current_qty * line.qty_per)

    walk(item_id, qty)
    return totals
