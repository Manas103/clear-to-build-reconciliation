from ctb.config import RNG_SEED
from ctb.datagen import generate_dataset
from ctb.incremental import measure_incremental_ratio


def test_incremental_ratio_is_small_fraction_of_full_reload():
    dataset = generate_dataset(seed=RNG_SEED)
    result = measure_incremental_ratio(dataset, seed=RNG_SEED, days=90)
    assert result["incremental_rows"] > 0
    assert result["incremental_rows"] < result["total_rows"]
    assert 0 < result["ratio_pct"] < 10  # a single day out of 90 should be a small slice


def test_incremental_ratio_shrinks_as_history_window_grows():
    dataset = generate_dataset(seed=RNG_SEED)
    shorter = measure_incremental_ratio(dataset, seed=RNG_SEED, days=30)
    longer = measure_incremental_ratio(dataset, seed=RNG_SEED, days=120)
    assert longer["ratio_pct"] < shorter["ratio_pct"]
