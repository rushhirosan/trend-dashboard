#!/usr/bin/env python3
"""指定した日次サムネだけ本番 API に upsert する。

使い方:
  SUMMARY_UPSERT_TOKEN=... python scripts/publish_thumb_files.py \\
    --date 2026-10-27 --region both
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
THUMB_ROOT = REPO_ROOT / "static" / "images" / "summaries" / "daily"
DEFAULT_BASE_URL = "https://trends-dashboard.com"
_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def find_file(region: str, day: str) -> Path | None:
    directory = THUMB_ROOT / region
    for suffix in (".jpg", ".jpeg", ".png"):
        path = directory / f"{day}{suffix}"
        if path.is_file():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--region", choices=("jp", "us", "both"), default="both")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TREND_DASHBOARD_BASE_URL", DEFAULT_BASE_URL),
    )
    args = parser.parse_args()
    token = (os.getenv("SUMMARY_UPSERT_TOKEN") or "").strip()
    if not token:
        print("ERROR: SUMMARY_UPSERT_TOKEN が未設定です", file=sys.stderr)
        return 1

    regions = ("jp", "us") if args.region == "both" else (args.region,)
    endpoint = f"{args.base_url.rstrip('/')}/api/summaries/thumbs"
    failures = 0
    for region in regions:
        path = find_file(region, args.date)
        if path is None:
            print(f"FAIL {region}/{args.date}: local thumb missing", file=sys.stderr)
            failures += 1
            continue
        content_type = _TYPES[path.suffix.lower()]
        resp = requests.post(
            endpoint,
            json={
                "kind": "daily",
                "region": region,
                "id": args.date,
                "content_type": content_type,
                "image_b64": base64.b64encode(path.read_bytes()).decode("ascii"),
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        label = f"daily/{region}/{args.date}"
        if resp.status_code == 200:
            print(f"OK   {label} ({path.name})")
        else:
            failures += 1
            print(f"FAIL {label}: HTTP {resp.status_code} {resp.text[:200]}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
