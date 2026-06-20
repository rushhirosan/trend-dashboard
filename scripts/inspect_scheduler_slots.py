#!/usr/bin/env python3
"""本番 scheduler_slot_run / snapshots / lock の状態確認（fly ssh 用）。"""
from database_config import TrendsCache

TODAY = "2026-06-20"


def main() -> None:
    db = TrendsCache()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            print("=== scheduler_slot_run (today) ===")
            cur.execute(
                """
                SELECT slot_key, started_at
                FROM scheduler_slot_run
                WHERE slot_key LIKE %s
                   OR slot_key LIKE %s
                ORDER BY started_at
                """,
                (f"%{TODAY}%", "oom_%"),
            )
            for row in cur.fetchall():
                print(row)

            print("=== trend_daily_snapshots (today) ===")
            cur.execute(
                """
                SELECT slot, COUNT(*) AS series_count, MAX(captured_at) AS last_cap
                FROM trend_daily_snapshots
                WHERE business_day = %s
                GROUP BY slot
                ORDER BY slot
                """,
                (TODAY,),
            )
            for row in cur.fetchall():
                print(row)

            print("=== scheduler_lock ===")
            cur.execute("SELECT holder_id, acquired_at, expires_at FROM scheduler_lock LIMIT 1")
            print(cur.fetchone())

            print("=== deploy_marker ===")
            cur.execute("SELECT last_deploy_at FROM deploy_marker LIMIT 1")
            print(cur.fetchone())


if __name__ == "__main__":
    main()
