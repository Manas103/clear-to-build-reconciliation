"""End-to-end benchmark: generates the simulated dataset, seeds 240
discrepancies across 6 classes, runs every detector, measures the
false-positive rate on an independent 1,000-record clean holdout, computes
clear-to-build for every work order, measures the incremental-sync row
ratio, proves the mock Oracle Fusion Cloud SCM REST path end to end, and
proves the DuckDB-backed drill-down. Writes docs/benchmark_output.txt and
docs/grafana_dashboard.json.

Run with: python scripts/run_benchmark.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ctb import bom, clear_to_build, dashboard, db, defects, fusion_client, mock_fusion_api, reconcile
from ctb.clean_sample import count_false_positives, generate_clean_sample
from ctb.config import RNG_SEED
from ctb.datagen import generate_dataset
from ctb.incremental import measure_incremental_ratio
from ctb.score import count_catches


def main():
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    rng = random.Random(RNG_SEED)
    dataset = generate_dataset(seed=RNG_SEED)
    log(f"Generated {len(dataset['items'])} PLM items, {len(dataset['bom_lines'])} BOM lines, "
        f"{len(dataset['work_orders'])} work orders, {len(dataset['erp_items'])} ERP item-master rows, "
        f"{len(dataset['purchase_orders'])} open POs.")

    ground_truth = defects.inject_all_defects(dataset, rng, bom.explode_fast)
    log(f"Seeded {len(ground_truth)} discrepancies across "
        f"{len(set(g['class'] for g in ground_truth))} classes.")

    shared_memo = {}
    detected = reconcile.run_all_detectors(
        dataset, lambda ds, iid, q, memo=None: bom.explode_fast(ds, iid, q, shared_memo)
    )
    catches, misses = count_catches(ground_truth, detected)
    log(f"Seeded discrepancies caught: {catches}/{len(ground_truth)}")
    for cls in sorted(set(g["class"] for g in ground_truth)):
        cls_total = sum(1 for g in ground_truth if g["class"] == cls)
        cls_missed = sum(1 for m in misses if m["class"] == cls)
        log(f"  {cls}: {cls_total - cls_missed}/{cls_total}")

    clean_records = generate_clean_sample(seed=RNG_SEED + 1, n=1000)
    false_positives = count_false_positives(clean_records, bom.explode_fast)
    log(f"False positives on {len(clean_records)} clean records: {false_positives}")

    ctb_results = clear_to_build.compute_all(dataset, bom.explode_fast)
    n_clear = sum(1 for r in ctb_results if r["status"] == "CLEAR")
    n_short = sum(1 for r in ctb_results if r["status"] == "SHORT")
    log(f"Clear-to-build computed for {len(ctb_results)} work orders: {n_clear} CLEAR, {n_short} SHORT")

    sample_wos = rng.sample(dataset["work_orders"], 50)
    mismatches = 0
    for wo in sample_wos:
        fast = bom.explode_fast(dataset, wo.item_id, wo.qty_required, {})
        naive = bom.explode_naive(dataset, wo.item_id, wo.qty_required)
        if fast != naive:
            mismatches += 1
    log(f"Reference-oracle diff (explode_fast vs explode_naive), 50 sampled work orders: "
        f"{mismatches} mismatches")

    attempts = []
    for days in (60, 90, 83):
        result = measure_incremental_ratio(dataset, seed=RNG_SEED, days=days)
        attempts.append(result)
        log(f"Incremental sync attempt ({days}-day history): {result['incremental_rows']}/"
            f"{result['total_rows']} rows = {result['ratio_pct']:.4f}%")

    resources = {
        "items": [{"ItemNumber": i.item_id, "UOMCode": i.plm_uom}
                  for i in list(dataset["items"].values())[:500]],
        "workOrders": [{"WorkOrderNumber": w.wo_id, "ItemNumber": w.item_id}
                        for w in dataset["work_orders"][:200]],
    }
    server, thread = mock_fusion_api.start_server(resources)
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        fetched_items = fusion_client.fetch_all(base_url, "items", page_size=50)
        fetched_wos = fusion_client.fetch_all(base_url, "workOrders", page_size=50)
        log(f"Mock Oracle Fusion Cloud SCM REST pull: {len(fetched_items)}/{len(resources['items'])} "
            f"items, {len(fetched_wos)}/{len(resources['workOrders'])} work orders, paginated "
            f"offset/limit, hasMore cursor.")
    finally:
        mock_fusion_api.stop_server(server, thread)

    con = db.load_duckdb(dataset, detected)
    shortage_examples = detected["on_hand_shortage"][:1]
    if shortage_examples:
        example = shortage_examples[0]
        drill = db.drill_query(con, example["wo_id"], example["item_id"])
        log(f"Drill-down proof for shortage {example['wo_id']}/{example['item_id']}: "
            f"{len(drill['work_order'])} work-order row(s), {len(drill['plm_item'])} PLM item row(s), "
            f"{len(drill['erp_on_hand'])} on-hand row(s), {len(drill['shortage'])} shortage row(s) "
            f"resolved via SQL.")

    try:
        from ctb import postgres_audit
        discrepancy_counts = {cls: len(found) for cls, found in detected.items()}
        postgres_audit.publish_run(discrepancy_counts)
        log("PostgreSQL audit publish: live, 6 discrepancy-class counts written to ctb_runs.")
    except Exception as exc:
        log(f"PostgreSQL audit publish: skipped ({exc})")

    repo_root = Path(__file__).resolve().parents[1]
    (repo_root / "docs" / "benchmark_output.txt").write_text("\n".join(lines) + "\n")
    (repo_root / "docs" / "grafana_dashboard.json").write_text(
        json.dumps(dashboard.build_dashboard_json(), indent=2)
    )


if __name__ == "__main__":
    main()
