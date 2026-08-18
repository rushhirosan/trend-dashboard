#!/usr/bin/env python3
"""有料購読者へ AI サマリーメールを送る。

例:
  python scripts/send_summary_paid_email.py --kind daily --dry-run
  python scripts/send_summary_paid_email.py --kind weekly --id 2026-W33
  python scripts/send_summary_paid_email.py --kind daily --from-api
"""

from __future__ import annotations

import argparse
import os
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
)
from services.summary.summary_paid_email import (  # noqa: E402
    SubscribersApiUnauthorized,
    SubscribersApiUnavailable,
    fetch_active_subscribers_from_site,
    send_summary_paid,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send AI summary paid subscriber emails")
    parser.add_argument("--kind", choices=("daily", "weekly"), required=True)
    parser.add_argument("--id", default="", help="daily: YYYY-MM-DD / weekly: YYYY-Www")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--from-api",
        action="store_true",
        help="購読者を本番 GET /api/billing/ai-summary/subscribers から取る"
        "（GHA では自動。Fly Postgres には直接繋がらない）",
    )
    args = parser.parse_args(argv)

    doc_id = (args.id or "").strip()
    if not doc_id:
        doc_id = (
            default_daily_doc_id()
            if args.kind == "daily"
            else default_weekly_doc_id()
        )

    use_api = args.from_api or os.getenv("GITHUB_ACTIONS") == "true"
    subscribers = None
    if use_api:
        try:
            subscribers = fetch_active_subscribers_from_site()
        except SubscribersApiUnavailable as e:
            print(f"skip: paid subscribers API unavailable ({e})")
            return 0
        except SubscribersApiUnauthorized:
            print("ERROR: SUMMARY_UPSERT_TOKEN unauthorized", file=sys.stderr)
            return 1
        print(f"subscribers_from_api={len(subscribers)}")

    results = send_summary_paid(
        kind=args.kind,
        doc_id=doc_id,
        dry_run=args.dry_run,
        subscribers=subscribers,
    )

    sent = failed = skipped = 0
    for r in results:
        status = "ok" if r.ok else ("skip" if r.skipped else "fail")
        print(
            f"{status}\tkind={r.kind}\tregion={r.region}\tid={r.doc_id}"
            f"\temail={r.email}\terror={r.error or '-'}"
        )
        if r.ok and not r.skipped:
            sent += 1
        elif r.skipped:
            skipped += 1
        else:
            failed += 1

    print(f"summary: sent={sent} skipped={skipped} failed={failed} dry_run={args.dry_run}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
