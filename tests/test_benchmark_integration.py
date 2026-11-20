"""Full-scale integration: the same generate -> inject -> detect -> score
pipeline scripts/run_benchmark.py runs, at the full 12,000-part dataset
size, asserting the headline claims: every seeded discrepancy caught, 0
false positives on the clean holdout.
"""
import random

from ctb import bom, defects, reconcile
from ctb.clean_sample import count_false_positives, generate_clean_sample
from ctb.config import RNG_SEED
from ctb.datagen import generate_dataset
from ctb.score import count_catches


def test_all_seeded_discrepancies_caught_and_zero_false_positives():
    rng = random.Random(RNG_SEED)
    dataset = generate_dataset(seed=RNG_SEED)
    ground_truth = defects.inject_all_defects(dataset, rng, bom.explode_fast)
    assert len(ground_truth) == 240

    memo = {}
    detected = reconcile.run_all_detectors(
        dataset, lambda ds, iid, q, m=None: bom.explode_fast(ds, iid, q, memo)
    )
    catches, misses = count_catches(ground_truth, detected)
    assert catches == 240, f"missed: {misses}"

    clean_records = generate_clean_sample(seed=RNG_SEED + 1, n=1000)
    assert count_false_positives(clean_records, bom.explode_fast) == 0
