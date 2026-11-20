from ctb.config import LEVEL_COUNTS, RNG_SEED
from ctb.datagen import generate_dataset


def test_item_counts_match_level_counts():
    dataset = generate_dataset(seed=RNG_SEED)
    assert len(dataset["items"]) == sum(LEVEL_COUNTS.values()) == 12000
    for level, count in LEVEL_COUNTS.items():
        assert len(dataset["pools"][level]) == count


def test_bom_lines_only_reference_lower_levels():
    dataset = generate_dataset(seed=RNG_SEED)
    level_rank = {"raw": 0, "component": 1, "subassembly": 2, "finished": 3}
    for line in dataset["bom_lines"]:
        parent_level = dataset["items"][line.parent_item_id].level
        child_level = dataset["items"][line.child_item_id].level
        assert level_rank[child_level] < level_rank[parent_level]


def test_one_work_order_per_finished_good():
    dataset = generate_dataset(seed=RNG_SEED)
    assert len(dataset["work_orders"]) == len(dataset["pools"]["finished"]) == 600


def test_deterministic_with_fixed_seed():
    a = generate_dataset(seed=RNG_SEED)
    b = generate_dataset(seed=RNG_SEED)
    assert list(a["items"].keys()) == list(b["items"].keys())
    assert [(l.parent_item_id, l.child_item_id, l.qty_per) for l in a["bom_lines"]] == \
           [(l.parent_item_id, l.child_item_id, l.qty_per) for l in b["bom_lines"]]
