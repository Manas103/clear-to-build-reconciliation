import random

from ctb import bom
from ctb.config import RNG_SEED
from ctb.datagen import generate_dataset
from ctb.model import BomLine, Item


def _diamond_dataset():
    """A hand-built diamond dependency: FG needs 2 SUB1 + 3 SUB2, both SUB1
    and SUB2 need 1 RAW each, so FG needs 2*1 + 3*1 = 5 RAW per unit."""
    items = {
        "FG": Item("FG", "finished good", "finished", "EA", ["A"], "A"),
        "SUB1": Item("SUB1", "sub 1", "subassembly", "EA", ["A"], "A"),
        "SUB2": Item("SUB2", "sub 2", "subassembly", "EA", ["A"], "A"),
        "RAW": Item("RAW", "raw part", "raw", "EA", ["A"], "A"),
    }
    lines = [
        BomLine("FG", "SUB1", 2.0, "EA"),
        BomLine("FG", "SUB2", 3.0, "EA"),
        BomLine("SUB1", "RAW", 1.0, "EA"),
        BomLine("SUB2", "RAW", 1.0, "EA"),
    ]
    bom_index = {"FG": lines[:2], "SUB1": [lines[2]], "SUB2": [lines[3]]}
    return {"items": items, "bom_lines": lines, "bom_index": bom_index}


def test_explode_fast_aggregates_shared_leaf():
    dataset = _diamond_dataset()
    result = bom.explode_fast(dataset, "FG", 10)
    assert result == {"RAW": 50.0}


def test_explode_fast_matches_naive_on_diamond():
    dataset = _diamond_dataset()
    assert bom.explode_fast(dataset, "FG", 7) == bom.explode_naive(dataset, "FG", 7)


def test_explode_fast_matches_naive_on_generated_dataset_sample():
    dataset = generate_dataset(seed=RNG_SEED)
    rng = random.Random(1)
    for wo in rng.sample(dataset["work_orders"], 30):
        fast = bom.explode_fast(dataset, wo.item_id, wo.qty_required, {})
        naive = bom.explode_naive(dataset, wo.item_id, wo.qty_required)
        assert fast == naive, f"mismatch on {wo.wo_id}"


def test_explode_skips_orphan_and_invalid_lines():
    dataset = _diamond_dataset()
    dataset["bom_lines"][2].child_item_id = "MISSING"  # SUB1 -> MISSING, orphan
    dataset["bom_index"]["SUB1"] = [dataset["bom_lines"][2]]
    result = bom.explode_fast(dataset, "SUB1", 5)
    assert result == {}  # the only child is an orphan reference, contributes nothing
