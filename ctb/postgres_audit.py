"""Optional PostgreSQL publish of a clear-to-build run (discrepancy counts
per class). Kafka/PostgreSQL are not installed as standing services on this
machine (see playbooks/BUILDER.md section 3); this module documents the
stand-up command and catches the connection error, reporting "skipped"
rather than failing, the same pattern model-validation-alerting and
spreadsheet-lakehouse-reconciliation-gate use.

Stand-up command for a local instance this would target:
  postgres listening on 127.0.0.1:5432, database `ctb`, user `mvuser`.
"""
import os


class PostgresUnavailable(Exception):
    pass


def publish_run(discrepancy_counts):
    try:
        import psycopg2
    except ImportError as exc:
        raise PostgresUnavailable(f"psycopg2 not installed: {exc}")
    try:
        conn = psycopg2.connect(
            host=os.environ.get("CTB_PG_HOST", "127.0.0.1"),
            port=os.environ.get("CTB_PG_PORT", "5432"),
            dbname=os.environ.get("CTB_PG_DB", "ctb"),
            user=os.environ.get("CTB_PG_USER", "mvuser"),
            password=os.environ.get("CTB_PG_PASSWORD", "mvpass"),
            connect_timeout=2,
        )
    except Exception as exc:
        raise PostgresUnavailable(str(exc))
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                create table if not exists ctb_runs (
                    run_at timestamp default now(),
                    discrepancy_class varchar,
                    count integer
                )
            """)
            for cls, count in discrepancy_counts.items():
                cur.execute(
                    "insert into ctb_runs (discrepancy_class, count) values (%s, %s)",
                    (cls, count),
                )
    finally:
        conn.close()
