"""Grafana dashboard provisioning JSON. Documented, not run live: there is
no Grafana instance on this build machine, the same precedent this
portfolio's pharma-supply-kpi-lakehouse sibling sets for a documented Power
BI star schema with no live .pbix. The drill-down the resume claims is
proven by db.drill_query, which is the exact query each panel's drill-down
link below would issue against the DuckDB tables in db.py.
"""


def build_dashboard_json():
    return {
        "title": "Clear-to-Build Reconciliation",
        "panels": [
            {
                "id": 1,
                "title": "Shortages by work order",
                "type": "table",
                "targets": [{
                    "rawSql": "select wo_id, item_id, required, on_hand, shortfall "
                              "from on_hand_shortage_discrepancies order by shortfall desc",
                }],
                "links": [{
                    "title": "Drill to source",
                    "url": "/d/ctb-source/source?var-wo_id=${__data.fields.wo_id}"
                           "&var-item_id=${__data.fields.item_id}",
                }],
            },
            {
                "id": 2,
                "title": "Source drill-down",
                "type": "table",
                "targets": [
                    {"rawSql": "select * from mes_work_orders where wo_id = '$wo_id'"},
                    {"rawSql": "select * from plm_items where item_id = '$item_id'"},
                    {"rawSql": "select * from erp_on_hand where erp_item_id = '$item_id'"},
                ],
                "templating": {"list": [
                    {"name": "wo_id", "type": "textbox"},
                    {"name": "item_id", "type": "textbox"},
                ]},
            },
            {
                "id": 3,
                "title": "Discrepancies by class",
                "type": "barchart",
                "targets": [{"rawSql": "select class, count(*) from discrepancies group by class"}],
            },
        ],
    }
