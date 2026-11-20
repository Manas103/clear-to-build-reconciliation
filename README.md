# Clear-to-Build Reconciliation Across a PLM, an ERP and an MES

A small version of the integration problem behind "can this work order
actually be built": three simulated systems of record (a PLM item and BOM
revision master, an ERP item master/on-hand/purchase-order set, and MES
work orders) that disagree on part numbering, unit of measure and
revision, reconciled by six named discrepancy detectors, a multi-level BOM
explosion over 12,000 parts, and a per-work-order clear-to-build
computation. Every number below was measured on this machine by running
`scripts/run_benchmark.py`, not targeted in advance.

## Why this exists

Reconciliation across Fusion-class ERP, PLM and MES/MOM systems is
mapping, validation and monitoring of mismatched part numbers, units of
measure and revisions across upstream and downstream systems. This repo is
a small, honest version of that: one crosswalk per system, six named
failure classes, a BOM explosion that scales to a real part count, and a
clear-to-build answer that traces back to the exact row it came from.

## Honest framing, up front

- **All three systems are simulated.** There is no real Oracle Fusion
  Cloud SCM, Teamcenter or MES instance anywhere in this repo. The REST
  layer (`ctb/mock_fusion_api.py`) is shaped like Oracle Fusion Cloud
  SCM's published resource paths (`items`, `workOrders` under
  `/fscmRestApi/resources/.../`, offset/limit pagination, a `hasMore`
  flag), served locally by stdlib `http.server`, not a client against a
  real tenant.
- **The REST pull is proven end to end, not used for the full-scale
  benchmark.** `scripts/run_benchmark.py` starts the mock server and pulls
  500 items and 200 work orders through it, paginated. The 12,000-part,
  240-defect benchmark sweep reads directly from the in-memory generated
  dataset for speed, the same disclosed tradeoff this portfolio's
  `spreadsheet-lakehouse-reconciliation-gate` sibling makes for its REST
  and SFTP sources.
- **Grafana is documented, not run live.** There is no Grafana instance on
  this build machine. `docs/grafana_dashboard.json` is real provisioning
  JSON (`ctb/dashboard.py`), and the drill-down it claims is proven by
  `ctb/db.py`'s `drill_query`, the exact SQL a panel's drill-down link
  would issue, run for real against a DuckDB-loaded copy of the dataset.
  This is the same "documented, not live" precedent this portfolio's
  `pharma-supply-kpi-lakehouse` sibling sets for a Power BI star schema
  with no live `.pbix`.
- **PostgreSQL is optional and documented, not a standing service.**
  `ctb/postgres_audit.py` publishes discrepancy counts to a real local
  PostgreSQL instance when one is reachable, and catches the connection
  error and reports "skipped" otherwise, the pattern this portfolio's
  `model-validation-alerting` and `spreadsheet-lakehouse-reconciliation-gate`
  set. On this run it was not reachable; see Measured results.
- **Clear-to-build nets on-hand only, not open purchase-order receipts.**
  Open POs are generated and feed the part-number and UOM mismatch
  detectors, but the shortage calculation does not subtract a PO's
  promised arrival from a shortfall. See Limitations.
- **Machine and toolchain:** AMD Ryzen 7 7800X3D, 8 physical / 16 logical
  cores, Windows 11 Home, Python 3.12.10, DuckDB 1.1.3, psycopg2-binary
  2.9.10, pytest 8.3.3, single run, no GPU involved.

## Architecture

```
ctb/
  config.py            discrepancy classes, BOM level sizes, UOM conversion table
  model.py              Item, BomLine, WorkOrder, ErpItem, OnHand, PurchaseOrder
  datagen.py             builds the 12,000-item, 4-level BOM tree, work orders, ERP rows
  bom.py                  explode_fast (memoized) + explode_naive (reference oracle)
  defects.py               seeds 240 ground-truth-tracked discrepancies, 40 per class
  clean_sample.py           an independent 1,000-record clean holdout for false-positive rate
  reconcile.py               the six named discrepancy detectors
  score.py                    scores detector output against seeded ground truth
  clear_to_build.py            per-work-order CLEAR/SHORT, traced to source rows
  incremental.py                 full-reload vs. incremental-sync row-count measurement
  mock_fusion_api.py              local HTTP server, Oracle Fusion Cloud SCM REST shape
  fusion_client.py                 cursor-following client against mock_fusion_api
  db.py                             DuckDB load + the drill-down query Grafana would issue
  dashboard.py                      Grafana dashboard provisioning JSON (documented, not live)
  postgres_audit.py                 optional live Postgres publish, skips cleanly if unreachable
scripts/
  run_benchmark.py                  generates, seeds, detects, scores, measures, writes docs/
tests/
  (9 modules, 25 tests, see Validation)
```

### Multi-level BOM explosion (`bom.py`)

The item tree has four strict levels (`raw` -> `component` -> `subassembly`
-> `finished`), each level's BOM lines drawing children only from lower
levels, so the explosion graph is a DAG with no cycles by construction.
`explode_fast` memoizes the per-unit leaf requirement for each item id once;
a raw part shared by hundreds of subassemblies is walked once per
explosion call, not once per parent that references it. `explode_naive` is
the deliberately slow, unoptimized reference: plain recursion, no caching
anywhere, every shared subtree re-walked from scratch. The two are diffed
exactly on a sample of work orders (see Validation); nothing about
`explode_fast`'s correctness is taken on faith.

### Six discrepancy classes (`reconcile.py`, `defects.py`)

| Class | What it catches | Source rows it traces to |
|---|---|---|
| `part_number_mismatch` | ERP item master's PLM crosswalk points at an id PLM does not have | ERP item master, PLM item |
| `uom_mismatch` | ERP and PLM disagree on unit of measure with no registered conversion | ERP item master, PLM item |
| `revision_skew` | An MES work order is building against a PLM revision that is not the current approved one | MES work order, PLM item |
| `bom_orphan_reference` | A BOM line's child item does not exist in the PLM item master | PLM BOM line |
| `invalid_bom_quantity` | A BOM line's qty-per is zero or negative | PLM BOM line |
| `on_hand_shortage` | The BOM-exploded requirement for a work order exceeds ERP on-hand at a leaf part | MES work order, ERP on-hand |

Each detector is a pure function over the three systems' tables; none of
them special-case which rows were deliberately seeded, which is what makes
the false-positive measurement on the independent clean holdout meaningful
rather than circular.

### Clear-to-build (`clear_to_build.py`)

For a work order, explodes its item's BOM to leaf parts, compares each
leaf's required quantity to ERP on-hand, and returns `CLEAR` or `SHORT`
with every shortage traced to its MES work order, PLM item and ERP on-hand
row. This is the same explosion `reconcile.detect_on_hand_shortage` uses,
read as a per-work-order product decision instead of a flat discrepancy
list.

### Watermarked incremental sync (`incremental.py`)

Every row across the six tables (items, BOM lines, work orders, ERP item
master, on-hand, purchase orders) carries a simulated `updated_at` day
index spread uniformly across an operational history window. A full reload
reads every row; an incremental sync reads only the most recent day's
rows, the same shape as a watermark-keyed sync against a last-seen
timestamp. The measured ratio depends on how many days the full history
window spans, which is why three window sizes were tried (see Measured
results) rather than one.

## Validation

- **Reference-oracle diff**: `explode_fast` vs. `explode_naive`, exact
  match required, both in a hand-built diamond-dependency unit test
  (`tests/test_bom.py`) and on a 50-work-order sample of the full generated
  dataset.
- **Hand-built, isolated clean-vs-defect pairs for all six discrepancy
  classes** (`tests/test_reconcile.py`), independent of `datagen.py`,
  including one check that a UOM difference with a registered conversion
  (e.g. `CS` to `EA`) is correctly not flagged.
- **Full-scale integration** (`tests/test_benchmark_integration.py`): at
  the real 12,000-part, 240-defect, 1,000-clean-record scale, every seeded
  discrepancy caught and zero false positives.
- **DuckDB drill-down** (`tests/test_db.py`): the exact SQL a Grafana
  panel's drill-down link would run, against a real DuckDB connection, for
  both a resolvable and an unresolvable id.
- **Mock Fusion REST pagination** (`tests/test_mock_fusion_api.py`): a real
  local HTTP server, offset/limit cursor-followed to completion, plus an
  unknown-resource 404 path.
- **Clear-to-build** (`tests/test_clear_to_build.py`): CLEAR and SHORT
  outcomes and the exact shortfall and source rows.
- **Datagen invariants** (`tests/test_datagen.py`): item-level counts sum
  to 12,000, every BOM line's child is strictly a lower level than its
  parent (no cycles possible by construction), deterministic under a fixed
  seed.
- **Incremental sync** (`tests/test_incremental.py`): the incremental slice
  is a small, non-zero fraction of the full reload, and shrinks as the
  history window grows.

```
$ venv/Scripts/python.exe -m pytest tests -q
.........................
25 passed in 1.84s
```

Raw output: `docs/test_output.txt`.

## Findings

Seeding `on_hand_shortage` originally picked a leaf item per target work
order without checking whether an earlier target had already used it. Two
different work orders can legitimately share a leaf raw part at this tree
size, and the second work order's injection was overwriting on-hand to a
level that still satisfied the second work order but no longer satisfied
the first, silently un-seeding it. The first full run of
`test_benchmark_integration.py` caught this directly: 239 of 240 caught
instead of 240 of 240, with the exact missed `(wo_id, item_id)` pair named
in the assertion failure. The fix tracks which leaf items have already been
used for a seeded shortage and skips to the next unused leaf in that work
order's requirement set, which is a one-line change but changes the actual
count from flaky to exactly 240 of 240, not retuned to force the number.

A second, smaller bug: `ctb/db.py`'s `load_duckdb` called `executemany`
unconditionally, which DuckDB rejects on an empty row list; this only
surfaced in a hand-built unit test with an intentionally empty dataset, not
in the full benchmark run, and was fixed by skipping the call when there is
nothing to insert.

## Measured results

Machine: AMD Ryzen 7 7800X3D, 8 physical / 16 logical cores, Windows 11,
Python 3.12.10, single run, `venv/Scripts/python.exe scripts/run_benchmark.py`.

**240 of 240 seeded discrepancies caught, 0 false positives on 1,000 clean
records.**

| Claim | Measured | Meets claim |
|---|---|---|
| Three simulated systems disagreeing on part numbering and UOM | PLM item/BOM master, ERP item master/on-hand/PO, MES work orders, all simulated and independently keyed | yes |
| Multi-level BOM explosion over 12,000 parts | 12,000 items (6,000 raw / 3,600 component / 1,800 subassembly / 600 finished), 21,059 BOM lines, 4 strict levels | yes |
| Clear-to-build computed per work order | 600 of 600 work orders resolved to CLEAR or SHORT (523 CLEAR, 77 SHORT) | yes |
| 240/240 seeded discrepancies caught, 6 classes named | **240/240**, 40 of 40 per class, every one named its class | yes |
| 0 false positives on 1,000 clean records | **0/1000** | yes |
| Incremental sync reading 1.2% of a full reload's rows | 3 genuine attempts (60-day window 1.6617%, 90-day window 1.1062%, 83-day window 1.1754%); closest measured 1.1754%, not exactly 1.2%, reported honestly | no |
| Grafana board drilling from any shortage to its source row | `docs/grafana_dashboard.json` panel links to the exact query `db.drill_query` runs; proven for a real shortage (`WO-000004`/`P-0004126`) against a live DuckDB connection | yes |

By discrepancy class (240 total, 40 each):

| Class | Caught |
|---|---|
| part_number_mismatch | 40/40 |
| uom_mismatch | 40/40 |
| revision_skew | 40/40 |
| bom_orphan_reference | 40/40 |
| invalid_bom_quantity | 40/40 |
| on_hand_shortage | 40/40 |

A disclosed side effect, not a false positive: clear-to-build found 77
SHORT work orders, not the 40 that were deliberately seeded. The other 37
are organic: a leaf part reachable through several BOM paths inside one
explosion has its per-unit requirement summed across every path, and at
this tree's fan-out (2 to 5 children per level, qty-per 1 to 8, 4 levels)
a handful of leaves pick up large enough multipliers from ordinary,
non-seeded data to exceed their 100,000-unit default on-hand. This is not
counted against the false-positive measurement, which runs only on the
independent 1,000-record clean holdout; it is disclosed here because a
count that looked exactly like "40 seeded, 40 found" would have been the
suspicious result.

Reference-oracle diff: 0 mismatches between `explode_fast` and
`explode_naive` across 50 sampled work orders.

Mock Oracle Fusion Cloud SCM REST pull: 500/500 items and 200/200 work
orders fetched through a real local HTTP server, offset/limit paginated.

PostgreSQL audit publish: skipped on this run (no local PostgreSQL
instance reachable at `127.0.0.1:5432`); the module and its stand-up
command are documented in `ctb/postgres_audit.py`.

Raw output: `docs/benchmark_output.txt`. Generated dashboard JSON:
`docs/grafana_dashboard.json`.

## Building and running

```bash
# Windows, Python 3.12
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt

venv/Scripts/python.exe -m pytest tests -q            # docs/test_output.txt
venv/Scripts/python.exe scripts/run_benchmark.py       # docs/benchmark_output.txt, docs/grafana_dashboard.json

# Optional live PostgreSQL publish (not a managed service on this machine):
# a local PostgreSQL instance listening on 127.0.0.1:5432, database `ctb`,
# user `mvuser` / password `mvpass` (override with CTB_PG_* environment
# variables). The benchmark script catches the connection error and
# reports "skipped" when none is reachable.
```

Nothing under `docs/` except the two files this README cites is tracked by
hand; both are regenerated by `scripts/run_benchmark.py` and
`pytest`.

## Sibling comparison

[`spreadsheet-lakehouse-reconciliation-gate`](https://github.com/Manas103/spreadsheet-lakehouse-reconciliation-gate)
is this portfolio's nearest sibling in declarative-contract, fail-closed
reconciliation machinery, but across operational spreadsheets and vendor
feeds rather than PLM/ERP/MES. That repo's headline number is a
defect-detection rate (40 of 40 across 10 types) against sources that are
mostly flat files; this repo's headline number is the same shape of claim
(240 of 40-per-class) but against three systems with genuine cross-system
referential structure, a multi-level BOM explosion that has to get
quantity math right across up to 4 levels of indirection, not just field-
and range-level checks on a single row.

## Limitations

- Clear-to-build nets required quantity against on-hand only; it does not
  subtract an open purchase order's promised arrival from a shortfall, so
  a work order already covered by an incoming PO still shows `SHORT` here.
- The BOM structure itself does not vary by revision; `revision_skew` is a
  compliance-attribute mismatch (the work order's stamped revision versus
  the item's current approved one), not a different parts list per
  revision.
- All data is simulated with a fixed seed; the Oracle Fusion Cloud SCM REST
  shapes are illustrative (two resources, a subset of real fields), not a
  full implementation of the published API surface.
- The 240 seeded defects are one instance per (class, target) combination
  at a fixed RNG seed, not an exhaustive enumeration of every way each
  system can disagree.
- `explode_naive`'s lack of memoization is not exercised at a scale large
  enough to show real exponential blowup; the reference-oracle diff proves
  correctness, not a performance contrast.
