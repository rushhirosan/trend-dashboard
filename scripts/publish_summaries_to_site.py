#!/usr/bin/env python3
"""docs/summaries の日次・週次 Markdown を本番の summary_documents に upsert する。

GitHub Actions（ai-daily-summary / ai-weekly-summary）が生成・コミット後に
呼ぶ想定。閲覧ページは DB を優先して読むため、deploy なしで新しい原稿が
公開される。upsert は冪等（同じ ID の再送は上書き）なので、リポジトリに
残っている原稿を毎回まとめて送ってよい。保持期間超過の行は本番の
03:00 JST クリーンアップ（purge_expired_snapshots）が削除する。

使い方:
  SUMMARY_UPSERT_TOKEN=... python scripts/publish_summaries_to_site.py
  python scripts/publish_summaries_to_site.py --base-url http://localhost:8080 --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIES_DIR = REPO_ROOT / "docs" / "summaries"
DEFAULT_BASE_URL = "https://trends-dashboard.fly.dev"

_DOC_ID_RES = {
    "daily": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "weekly": re.compile(r"^\d{4}-W\d{2}$"),
}


def collect_documents() -> list[dict]:
    """docs/summaries/{daily,weekly}{,/us} の公開対象 Markdown を集める。"""
    docs: list[dict] = []
    for kind in ("daily", "weekly"):
        kind_dir = SUMMARIES_DIR / kind
        for region, directory in (("jp", kind_dir), ("us", kind_dir / "us")):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                if not _DOC_ID_RES[kind].match(path.stem):
                    continue  # README・テンプレ等はスキップ
                docs.append(
                    {
                        "kind": kind,
                        "region": region,
                        "id": path.stem,
                        "path": path,
                    }
                )
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("TREND_DASHBOARD_BASE_URL", DEFAULT_BASE_URL),
        help=f"アプリのベース URL（既定: TREND_DASHBOARD_BASE_URL または {DEFAULT_BASE_URL}）",
    )
    parser.add_argument("--dry-run", action="store_true", help="送信せず対象一覧のみ表示")
    args = parser.parse_args()

    token = (os.getenv("SUMMARY_UPSERT_TOKEN") or "").strip()
    if not args.dry_run and not token:
        print(
            "ERROR: SUMMARY_UPSERT_TOKEN が未設定です。"
            "GHA Secrets と fly secrets の両方に同じ値を設定してください。",
            file=sys.stderr,
        )
        return 1

    docs = collect_documents()
    if not docs:
        print("No summary documents found; nothing to publish.")
        return 0

    endpoint = f"{args.base_url.rstrip('/')}/api/summaries/documents"
    print(f"Publishing {len(docs)} document(s) to {endpoint}")

    failures = 0
    for doc in docs:
        label = f"{doc['kind']}/{doc['region']}/{doc['id']}"
        if args.dry_run:
            print(f"  [dry-run] {label} ({doc['path']})")
            continue
        try:
            body_md = doc["path"].read_text(encoding="utf-8")
            resp = requests.post(
                endpoint,
                json={
                    "kind": doc["kind"],
                    "region": doc["region"],
                    "id": doc["id"],
                    "body_md": body_md,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            if resp.status_code == 200:
                print(f"  OK   {label}")
            else:
                failures += 1
                print(f"  FAIL {label}: HTTP {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        except Exception as e:  # ネットワーク断等でも残りは送る
            failures += 1
            print(f"  FAIL {label}: {e}", file=sys.stderr)

    if failures:
        print(f"ERROR: {failures} document(s) failed to publish.", file=sys.stderr)
        return 1
    print("All documents published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
