#!/usr/bin/env python3
"""
trend_daily_snapshots / scheduler_slot_run の古い行を削除する。

本番（dry-run）:
  fly ssh console -a trends-dashboard -C \\
    "sh -c 'cd /app && PYTHONPATH=/app python scripts/purge_snapshot_retention.py --dry-run'"

実行:
  python scripts/purge_snapshot_retention.py
  python scripts/purge_snapshot_retention.py --days 10 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.snapshot_retention import purge_expired_snapshots  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge trend_daily_snapshots and scheduler_slot_run older than retention"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="保持日数（default: TREND_SNAPSHOT_RETENTION_DAYS or 10）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除せず対象件数のみ表示",
    )
    parser.add_argument("--json", action="store_true", help="結果を JSON で出力")
    args = parser.parse_args()

    result = purge_expired_snapshots(days=args.days, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"retention={result['retention_days']}d "
            f"snapshot_cutoff={result['snapshot_cutoff']} "
            f"snapshots={'would_delete' if args.dry_run else 'deleted'}="
            f"{result['snapshots_deleted']} "
            f"scheduler_slot_run={'would_delete' if args.dry_run else 'deleted'}="
            f"{result['scheduler_rows_deleted']}"
        )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
