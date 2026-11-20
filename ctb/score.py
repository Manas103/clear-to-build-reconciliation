"""Scores detector output against injected ground truth, per discrepancy
class, using each class's own natural key.
"""

_KEY_FNS = {
    "part_number_mismatch": lambda d: d["erp_item_id"],
    "uom_mismatch": lambda d: d["erp_item_id"],
    "revision_skew": lambda d: d["wo_id"],
    "bom_orphan_reference": lambda d: (d["parent_item_id"], d["child_item_id"]),
    "invalid_bom_quantity": lambda d: (d["parent_item_id"], d["child_item_id"]),
    "on_hand_shortage": lambda d: (d["wo_id"], d["item_id"]),
}


def count_catches(ground_truth, detected):
    catches = 0
    misses = []
    for gt in ground_truth:
        cls = gt["class"]
        key_fn = _KEY_FNS[cls]
        found_keys = {key_fn(f) for f in detected.get(cls, [])}
        if key_fn(gt) in found_keys:
            catches += 1
        else:
            misses.append(gt)
    return catches, misses
