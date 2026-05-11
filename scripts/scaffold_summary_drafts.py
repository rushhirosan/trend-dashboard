#!/usr/bin/env python3
"""
Create empty summary draft Markdown under docs/summaries/ from repo templates.

Same idea as X post samples: commit drafts daily / weekly, review in-repo, ship later.

  python scripts/scaffold_summary_drafts.py --today
  python scripts/scaffold_summary_drafts.py --daily 2026-05-11
  python scripts/scaffold_summary_drafts.py --weekly-for-date 2026-05-11
  python scripts/scaffold_summary_drafts.py --today --weekly-for-date 2026-05-12 --force

Templates:
  docs/summaries/daily_template.md
  docs/summaries/weekly_hot_bundle_template.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIES = REPO_ROOT / "docs" / "summaries"
DAILY_TEMPLATE = SUMMARIES / "daily_template.md"
WEEKLY_TEMPLATE = SUMMARIES / "weekly_hot_bundle_template.md"
DAILY_DIR = SUMMARIES / "daily"
WEEKLY_DIR = SUMMARIES / "weekly"


def _jst_today() -> date:
    return datetime.now(JST).date()


def _iso_week_stem(d: date) -> str:
    iso_y, iso_w, _ = d.isocalendar()
    return f"{iso_y}-W{iso_w:02d}"


def _week_range_mon_sun(d: date) -> tuple[date, date]:
    mon = d - timedelta(days=d.isoweekday() - 1)
    sun = mon + timedelta(days=6)
    return mon, sun


def _render_daily(summary_date: date) -> str:
    text = DAILY_TEMPLATE.read_text(encoding="utf-8")
    s = summary_date.isoformat()
    return text.replace("{{SUMMARY_DATE}}", s)


def _render_weekly(any_day_in_week: date) -> str:
    text = WEEKLY_TEMPLATE.read_text(encoding="utf-8")
    stem = _iso_week_stem(any_day_in_week)
    mon, sun = _week_range_mon_sun(any_day_in_week)
    return (
        text.replace("{{ISO_WEEK_STEM}}", stem)
        .replace("{{WEEK_MON}}", mon.isoformat())
        .replace("{{WEEK_SUN}}", sun.isoformat())
    )


def _write(path: Path, content: str, force: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        print(f"skip (exists): {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return False
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    return True


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> int:
    p = argparse.ArgumentParser(description="Scaffold summary drafts under docs/summaries/")
    p.add_argument(
        "--today",
        action="store_true",
        help="Use today's date in JST for --daily (unless --daily is also passed)",
    )
    p.add_argument("--daily", metavar="YYYY-MM-DD", help="Create daily/YYYY-MM-DD.md")
    p.add_argument(
        "--weekly-for-date",
        metavar="YYYY-MM-DD",
        help="Create weekly/YYYY-Www.md for the ISO week containing this date",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    args = p.parse_args()

    if not args.today and not args.daily and not args.weekly_for_date:
        p.error("Specify at least one of --today, --daily, --weekly-for-date")

    if not DAILY_TEMPLATE.is_file():
        print(f"missing template: {DAILY_TEMPLATE}", file=sys.stderr)
        return 1
    if not WEEKLY_TEMPLATE.is_file():
        print(f"missing template: {WEEKLY_TEMPLATE}", file=sys.stderr)
        return 1

    wrote = 0

    if args.daily:
        d = _parse_date(args.daily)
        out = DAILY_DIR / f"{d.isoformat()}.md"
        if _write(out, _render_daily(d), args.force):
            wrote += 1
    elif args.today:
        d = _jst_today()
        out = DAILY_DIR / f"{d.isoformat()}.md"
        if _write(out, _render_daily(d), args.force):
            wrote += 1

    if args.weekly_for_date:
        d = _parse_date(args.weekly_for_date)
        stem = _iso_week_stem(d)
        out = WEEKLY_DIR / f"{stem}.md"
        if _write(out, _render_weekly(d), args.force):
            wrote += 1

    if wrote == 0 and not (args.weekly_for_date and args.daily):
        # e.g. only --today but file existed
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
