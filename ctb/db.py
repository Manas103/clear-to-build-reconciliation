"""DuckDB storage: loads the simulated PLM/ERP/MES tables and the detected
discrepancies into real SQL tables, so dashboard.py's panel `rawSql` is a
query that actually runs, not just a string, and drill_query below is the
exact drill-down a Grafana panel link would issue.
"""
import duckdb


def _executemany_if_any(con, sql, rows):
    if rows:
        con.executemany(sql, rows)


def load_duckdb(dataset, discrepancies, con=None):
    con = con or duckdb.connect(":memory:")

    con.execute("""
        create table plm_items (item_id varchar, description varchar, level varchar,
                                 plm_uom varchar, current_approved_revision varchar)
    """)
    _executemany_if_any(con, "insert into plm_items values (?, ?, ?, ?, ?)", [
        (i.item_id, i.description, i.level, i.plm_uom, i.current_approved_revision)
        for i in dataset["items"].values()
    ])

    con.execute("""
        create table mes_work_orders (wo_id varchar, item_id varchar, revision_used varchar,
                                       qty_required integer, due_date varchar)
    """)
    _executemany_if_any(con, "insert into mes_work_orders values (?, ?, ?, ?, ?)", [
        (w.wo_id, w.item_id, w.revision_used, w.qty_required, w.due_date)
        for w in dataset["work_orders"]
    ])

    con.execute("create table erp_on_hand (erp_item_id varchar, qty_on_hand double, uom varchar)")
    _executemany_if_any(con, "insert into erp_on_hand values (?, ?, ?)", [
        (o.erp_item_id, o.qty_on_hand, o.uom) for o in dataset["on_hand"].values()
    ])

    con.execute("""
        create table on_hand_shortage_discrepancies (wo_id varchar, item_id varchar,
                                                       required double, on_hand double, shortfall double)
    """)
    _executemany_if_any(con, "insert into on_hand_shortage_discrepancies values (?, ?, ?, ?, ?)", [
        (d["wo_id"], d["item_id"], d["required"], d["on_hand"], d["required"] - d["on_hand"])
        for d in discrepancies.get("on_hand_shortage", [])
    ])

    con.execute("create table discrepancies (class varchar, detail varchar)")
    rows = []
    for cls, found in discrepancies.items():
        for f in found:
            rows.append((cls, str({k: v for k, v in f.items() if k != "source_rows"})))
    _executemany_if_any(con, "insert into discrepancies values (?, ?)", rows)

    return con


def drill_query(con, wo_id, item_id):
    """The exact query a Grafana drill-down link from a shortage row would
    issue: resolve the work order, the PLM item and the ERP on-hand row."""
    return {
        "work_order": con.execute(
            "select * from mes_work_orders where wo_id = ?", [wo_id]
        ).fetchall(),
        "plm_item": con.execute(
            "select * from plm_items where item_id = ?", [item_id]
        ).fetchall(),
        "erp_on_hand": con.execute(
            "select * from erp_on_hand where erp_item_id = ?", [item_id]
        ).fetchall(),
        "shortage": con.execute(
            "select * from on_hand_shortage_discrepancies where wo_id = ? and item_id = ?",
            [wo_id, item_id],
        ).fetchall(),
    }
