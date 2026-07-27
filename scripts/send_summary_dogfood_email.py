#!/usr/bin/env python3
"""AI サマリー dogfood メールを送る（自分宛・draft 可）。

例:
  # 昨日分 JP+US 日次（dry-run）
  python scripts/send_summary_dogfood_email.py --kind daily --dry-run

  # 指定日を実送信
  python scripts/send_summary_dogfood_email.py --kind daily --id 2026-07-22

  # 直前 ISO 週の週次
  python scripts/send_summary_dogfood_email.py --kind weekly

環境変数:
  EMAIL_PROVIDER=resend（推奨・検証と本番で共通）
  RESEND_API_KEY / RESEND_FROM_EMAIL
  SUMMARY_DOGFOOD_TO（宛先。未設定なら From）
  SUMMARY_DOGFOOD_ENABLED=false で無効化
  （任意フォールバック）EMAIL_PROVIDER=smtp + Gmail SMTP
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from services.summary.summary_dogfood_email import (  # noqa: E402
    default_daily_doc_id,
    default_weekly_doc_id,
    send_summary_dogfood,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send AI summary dogfood emails")
    parser.add_argument("--kind", choices=("daily", "weekly"), required=True)
    parser.add_argument(
        "--id",
        default="",
        help="daily: YYYY-MM-DD / weekly: YYYY-Www（省略時は既定の昨日 or 前週）",
    )
    parser.add_argument(
        "--regions",
        default="jp,us",
        help="カンマ区切り（既定: jp,us）",
    )
    parser.add_argument("--to", default="", help="上書き宛先（未指定時は SUMMARY_DOGFOOD_TO）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    doc_id = (args.id or "").strip()
    if not doc_id:
        doc_id = (
            default_daily_doc_id()
            if args.kind == "daily"
            else default_weekly_doc_id()
        )

    regions = [r.strip().lower() for r in args.regions.split(",") if r.strip()]
    if not regions:
        print("no regions", file=sys.stderr)
        return 2

    results = send_summary_dogfood(
        kind=args.kind,
        doc_id=doc_id,
        regions=regions,
        to_email=args.to or None,
        dry_run=args.dry_run,
    )

    sent = 0
    failed = 0
    skipped = 0
    for r in results:
        status = "ok" if r.ok else ("skip" if r.skipped else "fail")
        print(
            f"{status}\tkind={r.kind}\tregion={r.region}\tid={r.doc_id}"
            f"\tpath={r.path}\terror={r.error or '-'}"
        )
        if r.ok and not r.skipped:
            sent += 1
        elif r.skipped:
            skipped += 1
        else:
            failed += 1

    print(f"summary: sent={sent} skipped={skipped} failed={failed} dry_run={args.dry_run}")
    # 全スキップのみは成功扱い（原稿なし・無効化）。実送信失敗があれば非ゼロ。
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
