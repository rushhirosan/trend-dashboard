#!/usr/bin/env python3
"""
指定スロットの trend_daily_snapshots をキャッシュから保存する（全量 refresh なし）。

19 時定時 / gap_retry 失敗後の手動補完用。AI 日次サマリー・X 投稿案が slot 19 を要求する。

例:
  python scripts/backfill_snapshot_slot.py --slot-key 7pm_2026-06-20
  python scripts/backfill_snapshot_slot.py --business-day 2026-06-20 --slot 19
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# 手動補完は本番キャッシュを読む（ローカル .env の USE_DUMMY_DATA=true を上書き）
os.environ["USE_DUMMY_DATA"] = "false"

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def _slot_key(business_day: date, slot: str) -> str:
    from datetime import timedelta

    slot = slot.zfill(2)
    if slot == "01":
        cal = business_day + timedelta(days=1)
        return f"1am_{cal.isoformat()}"
    if slot == "07":
        return f"7am_{business_day.isoformat()}"
    if slot == "13":
        return f"1pm_{business_day.isoformat()}"
    if slot == "19":
        return f"7pm_{business_day.isoformat()}"
    raise ValueError(f"unsupported slot: {slot}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill trend_daily_snapshots from cache")
    parser.add_argument("--slot-key", help="e.g. 7pm_2026-06-20")
    parser.add_argument("--business-day", help="YYYY-MM-DD (with --slot)")
    parser.add_argument(
        "--slot",
        choices=("01", "07", "13", "19", "7", "13", "19"),
        help="slot code (with --business-day)",
    )
    parser.add_argument(
        "--mark-completed",
        action="store_true",
        help="Record scheduler_slot_run for the slot_key on success",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse slot_key and exit without writing",
    )
    args = parser.parse_args()

    slot_key = (args.slot_key or "").strip()
    if not slot_key:
        if not args.business_day or not args.slot:
            parser.error("Provide --slot-key or both --business-day and --slot")
        bd = date.fromisoformat(args.business_day)
        slot_norm = str(args.slot).zfill(2)
        slot_key = _slot_key(bd, slot_norm)

    if args.dry_run:
        print(json.dumps({"slot_key": slot_key, "dry_run": True}, ensure_ascii=False))
        return 0

    from app import create_app
    from database_config import TrendsCache
    from services.snapshot_slot_health import write_and_verify_snapshot

    app, _scheduler = create_app()
    db = TrendsCache()

    with app.app_context():
        managers = app.config.get("TREND_MANAGERS") or {}
        if not managers:
            print("error: TREND_MANAGERS not initialized", file=sys.stderr)
            return 1
        status = write_and_verify_snapshot(
            managers,
            db,
            slot_key,
            trigger_source="gap_retry",
        )

    if args.mark_completed and status.get("verified_ok") and hasattr(db, "mark_slot_completed"):
        db.mark_slot_completed(slot_key)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status.get("verified_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
