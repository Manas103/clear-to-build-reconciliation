"""Each discrepancy class gets a hand-built, isolated clean-vs-defect pair,
independent of datagen.py, the same shape as the sibling repo's contract
unit tests.
"""
from ctb import reconcile
from ctb.bom import explode_fast
from ctb.model import BomLine, ErpItem, Item, OnHand, WorkOrder


def _base_item(item_id, level="component", uom="EA", rev="B"):
    approved = ["A", "B"] if rev == "B" else ["A"]
    return Item(item_id, f"item {item_id}", level, uom, approved, rev)


def test_part_number_mismatch_clean_and_defect():
    items = {"P1": _base_item("P1")}
    clean = {"items": items, "erp_items": {"P1": ErpItem("P1", "P1", "EA")}}
    defect = {"items": items, "erp_items": {"P1": ErpItem("P1", "P1-UNMAPPED", "EA")}}
    assert reconcile.detect_part_number_mismatch(clean) == []
    found = reconcile.detect_part_number_mismatch(defect)
    assert len(found) == 1 and found[0]["erp_item_id"] == "P1"


def test_uom_mismatch_clean_and_defect():
    items = {"P1": _base_item("P1", uom="EA")}
    clean = {"items": items, "erp_items": {"P1": ErpItem("P1", "P1", "EA")}}
    defect = {"items": items, "erp_items": {"P1": ErpItem("P1", "P1", "L")}}  # EA<->L has no conversion
    assert reconcile.detect_uom_mismatch(clean) == []
    found = reconcile.detect_uom_mismatch(defect)
    assert len(found) == 1 and found[0]["erp_item_id"] == "P1"


def test_uom_mismatch_tolerates_registered_conversion():
    items = {"P1": _base_item("P1", uom="EA")}
    dataset = {"items": items, "erp_items": {"P1": ErpItem("P1", "P1", "CS")}}  # CS -> EA is registered
    assert reconcile.detect_uom_mismatch(dataset) == []


def test_revision_skew_clean_and_defect():
    items = {"P1": _base_item("P1", rev="B")}
    clean = {"items": items, "work_orders": [WorkOrder("WO1", "P1", "B", 1, "day-0")]}
    defect = {"items": items, "work_orders": [WorkOrder("WO1", "P1", "A", 1, "day-0")]}
    assert reconcile.detect_revision_skew(clean) == []
    found = reconcile.detect_revision_skew(defect)
    assert len(found) == 1 and found[0]["wo_id"] == "WO1"


def test_bom_orphan_reference_clean_and_defect():
    items = {"P1": _base_item("P1"), "C1": _base_item("C1", level="raw")}
    clean_line = BomLine("P1", "C1", 2.0, "EA")
    defect_line = BomLine("P1", "GHOST", 2.0, "EA")
    assert reconcile.detect_bom_orphan_reference({"items": items, "bom_lines": [clean_line]}) == []
    found = reconcile.detect_bom_orphan_reference({"items": items, "bom_lines": [defect_line]})
    assert len(found) == 1 and found[0]["child_item_id"] == "GHOST"


def test_invalid_bom_quantity_clean_and_defect():
    clean_line = BomLine("P1", "C1", 2.0, "EA")
    defect_line = BomLine("P1", "C1", 0.0, "EA")
    assert reconcile.detect_invalid_bom_quantity({"bom_lines": [clean_line]}) == []
    found = reconcile.detect_invalid_bom_quantity({"bom_lines": [defect_line]})
    assert len(found) == 1 and found[0]["qty_per"] == 0.0


def test_on_hand_shortage_clean_and_defect():
    items = {"FG": _base_item("FG", level="finished"), "RAW": _base_item("RAW", level="raw")}
    line = BomLine("FG", "RAW", 1.0, "EA")
    dataset = {
        "items": items,
        "bom_index": {"FG": [line]},
        "bom_lines": [line],
        "work_orders": [WorkOrder("WO1", "FG", "B", 10, "day-0")],
        "on_hand": {"RAW": OnHand("RAW", 10.0, "EA")},
    }
    assert reconcile.detect_on_hand_shortage(dataset, explode_fast) == []

    dataset["on_hand"]["RAW"].qty_on_hand = 5.0
    found = reconcile.detect_on_hand_shortage(dataset, explode_fast)
    assert len(found) == 1 and found[0]["wo_id"] == "WO1" and found[0]["item_id"] == "RAW"
