from ctb.db import drill_query, load_duckdb
from ctb.model import Item, OnHand, WorkOrder


def test_drill_query_resolves_shortage_to_source_rows():
    dataset = {
        "items": {"FG": Item("FG", "fg", "finished", "EA", ["A"], "A")},
        "work_orders": [WorkOrder("WO1", "FG", "A", 10, "day-0")],
        "on_hand": {"FG": OnHand("FG", 5.0, "EA")},
    }
    discrepancies = {"on_hand_shortage": [{"wo_id": "WO1", "item_id": "FG", "required": 10.0, "on_hand": 5.0}]}
    con = load_duckdb(dataset, discrepancies)
    drill = drill_query(con, "WO1", "FG")
    assert len(drill["work_order"]) == 1
    assert len(drill["plm_item"]) == 1
    assert len(drill["erp_on_hand"]) == 1
    assert len(drill["shortage"]) == 1


def test_drill_query_empty_for_unknown_ids():
    con = load_duckdb({"items": {}, "work_orders": [], "on_hand": {}}, {})
    drill = drill_query(con, "NOPE", "NOPE")
    assert drill["work_order"] == [] and drill["plm_item"] == [] and drill["erp_on_hand"] == []
