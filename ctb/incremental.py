"""Full reload vs. incremental sync: every row in the three systems is
assigned an `updated_at` day index spread uniformly across a simulated
operational history; incremental sync reads only the most recent day's
rows, keyed off a per-table watermark, instead of reading every row.
"""
import random


def _assign_days(rng, keys, days):
    return {k: rng.randint(0, days - 1) for k in keys}


def build_update_days(dataset, seed, days):
    rng = random.Random(seed)
    tables = {
        "items": list(dataset["items"].keys()),
        "bom_lines": [(l.parent_item_id, l.child_item_id) for l in dataset["bom_lines"]],
        "work_orders": [wo.wo_id for wo in dataset["work_orders"]],
        "erp_items": list(dataset["erp_items"].keys()),
        "on_hand": list(dataset["on_hand"].keys()),
        "purchase_orders": [po.po_id for po in dataset["purchase_orders"]],
    }
    return {table: _assign_days(rng, keys, days) for table, keys in tables.items()}


def measure_incremental_ratio(dataset, seed, days):
    update_days = build_update_days(dataset, seed, days)
    total_rows = sum(len(v) for v in update_days.values())
    latest_day = days - 1
    incremental_rows = sum(
        sum(1 for d in v.values() if d == latest_day) for v in update_days.values()
    )
    return {
        "days": days,
        "total_rows": total_rows,
        "incremental_rows": incremental_rows,
        "ratio_pct": 100.0 * incremental_rows / total_rows,
    }
