#!/usr/bin/env python3
"""
直近の business_day について、スナップショット行が無い定時スロットをキャッシュから backfill。

OOM 後の手動/定時補完用。本番: fly ssh console -a trends-dashboard -C \\
  "cd /app && PYTHONPATH=/app python scripts/backfill_missing_snapshot_slots.py --days 3"

例:
  python scripts/backfill_missing_snapshot_slots.py --days 3
  python scripts/backfill_missing_snapshot_slots.py --business-day 2026-06-20
  python scripts/backfill_missing_snapshot_slots.py --days 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()
os.environ["USE_DUMMY_DATA"] = "false"

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def _business_days(end: date, days: int) -> list[date]:
    return [end - timedelta(days=i) for i in range(days - 1, -1, -1)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing trend_daily_snapshots from cache")
    parser.add_argument("--days", type=int, default=3, help="end から遡る business_day 数")
    parser.add_argument("--business-day", help="単日 YYYY-MM-DD（--days より優先）")
    parser.add_argument("--end-date", help="--days 時の終端 business_day（default: 今日 JST）")
    parser.add_argument("--dry-run", action="store_true", help="欠損 slot_key の一覧のみ")
    parser.add_argument(
        "--mark-completed",
        action="store_true",
        help="backfill 成功時に mark_slot_completed",
    )
    args = parser.parse_args()

    from services.snapshot_slot_health import (
        iter_scheduled_slots_for_business_day,
        slot_has_snapshot,
        write_and_verify_snapshot,
    )

    if args.business_day:
        days_list = [date.fromisoformat(args.business_day)]
    else:
        if args.end_date:
            end = date.fromisoformat(args.end_date)
        else:
            import pytz
            from datetime import datetime

            jst = pytz.timezone("Asia/Tokyo")
            end = datetime.now(jst).date()
        days_list = _business_days(end, max(1, args.days))

    from app import create_app
    from database_config import TrendsCache

    app, _scheduler = create_app()
    db = TrendsCache()

    missing: list[dict] = []
    with app.app_context():
        managers = app.config.get("TREND_MANAGERS") or {}
        if not managers:
            print("error: TREND_MANAGERS not initialized", file=sys.stderr)
            return 1

        for bd in days_list:
            for slot_code, slot_key in iter_scheduled_slots_for_business_day(bd):
                if slot_has_snapshot(db, bd, slot_code):
                    continue
                missing.append(
                    {
                        "business_day": bd.isoformat(),
                        "slot": slot_code,
                        "slot_key": slot_key,
                    }
                )

        if args.dry_run:
            print(json.dumps({"missing": missing, "count": len(missing)}, ensure_ascii=False, indent=2))
            return 0

        results: list[dict] = []
        exit_code = 0
        for item in missing:
            slot_key = item["slot_key"]
            status = write_and_verify_snapshot(
                managers,
                db,
                slot_key,
                trigger_source="gap_retry",
            )
            status["slot_key"] = slot_key
            if args.mark_completed and status.get("verified_ok") and hasattr(db, "mark_slot_completed"):
                db.mark_slot_completed(slot_key)
            results.append(status)
            if not status.get("verified_ok"):
                exit_code = 1

        print(
            json.dumps(
                {"missing_before": missing, "results": results},
                ensure_ascii=False,
                indent=2,
            )
        )
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
