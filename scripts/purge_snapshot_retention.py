#!/usr/bin/env python3
"""
trend_daily_snapshots / scheduler_slot_run / docs/summaries 原稿の古い行・ファイルを削除する。

本番 DB（dry-run）:
  fly ssh console -a trends-dashboard -C \\
    "sh -c 'cd /app && PYTHONPATH=/app python scripts/purge_snapshot_retention.py --dry-run'"

リポジトリ原稿（手元・保持確認）:
  python scripts/purge_snapshot_retention.py --dry-run
  python scripts/purge_snapshot_retention.py --summaries-only --dry-run

docs/summaries の git 反映: 毎日 GHA ``summary-retention-purge.yml``（JST 08:00 前後）。
手元で削除する場合は ``--summaries-only`` 実行後に commit する。
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
        description="Purge old snapshots, scheduler_slot_run rows, and docs/summaries files"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="DB スナップショット保持日数（default: TREND_SNAPSHOT_RETENTION_DAYS or 10）",
    )
    parser.add_argument(
        "--daily-summary-days",
        type=int,
        default=None,
        help="日次サマリー Markdown 保持日数（default: SUMMARY_DAILY_RETENTION_DAYS or 10）",
    )
    parser.add_argument(
        "--weekly-summary-days",
        type=int,
        default=None,
        help="週次サマリー Markdown 保持日数（default: SUMMARY_WEEKLY_RETENTION_DAYS or 30）",
    )
    parser.add_argument(
        "--summaries-only",
        action="store_true",
        help="docs/summaries のみ（DB は触らない）",
    )
    parser.add_argument(
        "--no-summaries",
        action="store_true",
        help="DB のみ（docs/summaries は触らない）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除せず対象件数のみ表示",
    )
    parser.add_argument("--json", action="store_true", help="結果を JSON で出力")
    args = parser.parse_args()

    if args.summaries_only:
        from services.snapshot_retention import purge_expired_summary_files

        summary_result = purge_expired_summary_files(
            daily_days=args.daily_summary_days,
            weekly_days=args.weekly_summary_days,
            dry_run=args.dry_run,
        )
        result = {
            "enabled": True,
            "dry_run": args.dry_run,
            "summaries_only": True,
            "ok": True,
            **summary_result,
            "snapshots_deleted": 0,
            "scheduler_rows_deleted": 0,
        }
    else:
        result = purge_expired_snapshots(
            days=args.days,
            daily_summary_days=args.daily_summary_days,
            weekly_summary_days=args.weekly_summary_days,
            purge_summary_files=not args.no_summaries,
            dry_run=args.dry_run,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "would_delete" if args.dry_run else "deleted"
        print(
            f"retention={result.get('retention_days')}d "
            f"snapshot_cutoff={result.get('snapshot_cutoff')} "
            f"snapshots={mode}={result.get('snapshots_deleted', 0)} "
            f"scheduler_slot_run={mode}={result.get('scheduler_rows_deleted', 0)} "
            f"daily_summary={mode}={result.get('daily_summary_files_deleted', 0)} "
            f"weekly_summary={mode}={result.get('weekly_summary_files_deleted', 0)}"
        )
        if result.get("daily_summary_cutoff"):
            print(
                f"daily_cutoff={result['daily_summary_cutoff']} "
                f"weekly_cutoff={result.get('weekly_summary_cutoff')}"
            )
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
