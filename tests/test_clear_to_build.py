from ctb.bom import explode_fast
from ctb.clear_to_build import clear_to_build, compute_all
from ctb.model import BomLine, Item, OnHand, WorkOrder


def _dataset():
    items = {
        "FG": Item("FG", "fg", "finished", "EA", ["A"], "A"),
        "RAW": Item("RAW", "raw", "raw", "EA", ["A"], "A"),
    }
    line = BomLine("FG", "RAW", 2.0, "EA")
    return {
        "items": items,
        "bom_index": {"FG": [line]},
        "bom_lines": [line],
        "on_hand": {"RAW": OnHand("RAW", 100.0, "EA")},
    }


def test_clear_status_when_on_hand_covers_requirement():
    dataset = _dataset()
    wo = WorkOrder("WO1", "FG", "A", 10, "day-0")
    result = clear_to_build(dataset, wo, explode_fast)
    assert result["status"] == "CLEAR"
    assert result["shortages"] == []


def test_short_status_and_traceable_source_rows():
    dataset = _dataset()
    dataset["on_hand"]["RAW"].qty_on_hand = 5.0
    wo = WorkOrder("WO1", "FG", "A", 10, "day-0")  # needs 20 RAW, only 5 on hand
    result = clear_to_build(dataset, wo, explode_fast)
    assert result["status"] == "SHORT"
    assert len(result["shortages"]) == 1
    shortage = result["shortages"][0]
    assert shortage["item_id"] == "RAW"
    assert shortage["shortfall"] == 15.0
    assert shortage["source_rows"]["mes_work_order"] == "WO1"
    assert shortage["source_rows"]["erp_on_hand"] == "RAW"


def test_compute_all_returns_one_result_per_work_order():
    dataset = _dataset()
    dataset["work_orders"] = [WorkOrder("WO1", "FG", "A", 1, "day-0"),
                               WorkOrder("WO2", "FG", "A", 1, "day-0")]
    results = compute_all(dataset, explode_fast)
    assert {r["wo_id"] for r in results} == {"WO1", "WO2"}
