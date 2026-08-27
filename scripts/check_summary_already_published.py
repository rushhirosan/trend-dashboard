#!/usr/bin/env python3
"""本番 summary_documents に対象日次/週次が既にあるか確認する。

手動 Run のあとに遅延した schedule が二重生成・二重メールしないためのガード。
jp と us の両方が存在するときだけ skip=true。API 失敗時は skip=false（生成を続行）。

使い方:
  SUMMARY_UPSERT_TOKEN=... python scripts/check_summary_already_published.py --kind daily
  python scripts/check_summary_already_published.py --kind weekly --id 2026-W34 --github-output
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import requests

JST = ZoneInfo("Asia/Tokyo")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_BASE_URL = "https://trends-dashboard.com"
REGIONS = ("jp", "us")


def default_daily_id(now: Optional[datetime] = None) -> str:
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    return (now.date() - timedelta(days=1)).isoformat()


def default_weekly_id(now: Optional[datetime] = None) -> str:
    """直前に終了した ISO 週（generate_ai_weekly_summary と同じ）。"""
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    today = now.date()
    this_mon = today - timedelta(days=today.isoweekday() - 1)
    prior_mon = this_mon - timedelta(days=7)
    y, w, _ = prior_mon.isocalendar()
    return f"{y}-W{w:02d}"


def document_exists(
    *,
    base_url: str,
    token: str,
    kind: str,
    region: str,
    doc_id: str,
    timeout: float = 30.0,
) -> bool:
    """exists=True のときだけ True。失敗・exists=false は False（呼び出し側で欠落扱い）。"""
    url = f"{base_url.rstrip('/')}/api/summaries/documents"
    resp = requests.get(
        url,
        params={"kind": kind, "region": region, "id": doc_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"unexpected response: {payload!r}")
    return bool(payload.get("exists"))


def check_both_regions(
    *,
    base_url: str,
    token: str,
    kind: str,
    doc_id: str,
) -> tuple[bool, dict[str, Optional[bool]]]:
    """両 region があるとき True。戻り値 2 つ目は region → exists（問い合わせ失敗は None）。"""
    statuses: dict[str, Optional[bool]] = {}
    for region in REGIONS:
        try:
            statuses[region] = document_exists(
                base_url=base_url,
                token=token,
                kind=kind,
                region=region,
                doc_id=doc_id,
            )
        except Exception as e:
            print(f"WARN: lookup failed {kind}/{region}/{doc_id}: {e}", file=sys.stderr)
            statuses[region] = None
    both = all(statuses.get(r) is True for r in REGIONS)
    return both, statuses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("daily", "weekly"), required=True)
    parser.add_argument(
        "--id",
        default="",
        help="daily=YYYY-MM-DD / weekly=YYYY-Www（省略時は JST 既定）",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("TREND_DASHBOARD_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="GITHUB_OUTPUT に skip= / doc_id= を書く",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="常に skip=false（再生成したいとき）",
    )
    args = parser.parse_args()

    doc_id = (args.id or "").strip()
    if not doc_id:
        doc_id = default_daily_id() if args.kind == "daily" else default_weekly_id()

    if args.force:
        skip = False
        print(f"force: skip=false kind={args.kind} id={doc_id}")
    else:
        token = (os.getenv("SUMMARY_UPSERT_TOKEN") or "").strip()
        if not token:
            print(
                "WARN: SUMMARY_UPSERT_TOKEN unset; treating as not published (skip=false)",
                file=sys.stderr,
            )
            skip = False
        else:
            both, statuses = check_both_regions(
                base_url=args.base_url,
                token=token,
                kind=args.kind,
                doc_id=doc_id,
            )
            skip = both
            print(
                f"kind={args.kind} id={doc_id} jp={statuses.get('jp')} "
                f"us={statuses.get('us')} skip={str(skip).lower()}"
            )

    if args.github_output:
        out_path = os.getenv("GITHUB_OUTPUT")
        if not out_path:
            print("ERROR: GITHUB_OUTPUT not set", file=sys.stderr)
            return 1
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(f"skip={'true' if skip else 'false'}\n")
            fh.write(f"doc_id={doc_id}\n")
            fh.write(f"kind={args.kind}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
