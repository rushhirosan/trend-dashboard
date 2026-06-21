#!/usr/bin/env python3
"""本番 scheduler_slot_run / snapshots / lock の状態確認（fly ssh 用）。"""
from __future__ import annotations

import argparse
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database_config import TrendsCache


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect scheduler slots and snapshots")
    parser.add_argument(
        "--business-day",
        default=None,
        help="YYYY-MM-DD（default: 今日 JST）",
    )
    args = parser.parse_args()

    if args.business_day:
        today = args.business_day
    else:
        import pytz
        from datetime import datetime

        today = datetime.now(pytz.timezone("Asia/Tokyo")).date().isoformat()

    db = TrendsCache()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            print(f"=== scheduler_slot_run ({today}) ===")
            cur.execute(
                """
                SELECT slot_key, started_at
                FROM scheduler_slot_run
                WHERE slot_key LIKE %s
                   OR slot_key LIKE %s
                ORDER BY started_at
                """,
                (f"%{today}%", "oom_%"),
            )
            for row in cur.fetchall():
                print(row)

            print(f"=== trend_daily_snapshots (business_day={today}) ===")
            cur.execute(
                """
                SELECT slot, COUNT(*) AS series_count, MAX(captured_at) AS last_cap
                FROM trend_daily_snapshots
                WHERE business_day = %s
                GROUP BY slot
                ORDER BY slot
                """,
                (today,),
            )
            for row in cur.fetchall():
                print(row)

            print("=== scheduler_lock ===")
            cur.execute("SELECT holder_id, acquired_at, expires_at FROM scheduler_lock LIMIT 1")
            print(cur.fetchone())

            print("=== deploy_marker ===")
            cur.execute("SELECT last_deploy_at FROM deploy_marker LIMIT 1")
            print(cur.fetchone())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
