#!/usr/bin/env python3
"""
PR TIMES / GlobeNewswire バックエンドのデータ取得テスト（RSS取得のみ、DB不要）
entry.tags（RSS/Atom の category）の有無・内容も確認する。
"""
import sys
import os

# プロジェクトルートを path に追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _inspect_entry_tags(manager, source_name, limit=3):
    """RSS を直接パースして entry.tags を表示（feedparser の構造確認用）"""
    import requests
    import feedparser

    print(f"--- {source_name} entry.tags 確認 ---")
    if source_name == "GlobeNewswire":
        url = getattr(manager, "rss_url", None)
        if not url:
            print("  (rss_url なし)")
            return
        resp = requests.get(url, timeout=15, headers=manager.session.headers)
    else:
        # PR TIMES: カテゴリページから RSS URL を取得
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        page_url = (manager.category_page_urls or ["https://prtimes.jp/technology/"])[0]
        resp = requests.get(page_url, timeout=10, headers=manager.session.headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("link", rel="alternate", type="application/rss+xml")
        href = (link and link.get("href") or "").strip()
        url = urljoin(page_url, href) if href else None
        if not url:
            print("  (RSS URL 取得失敗)")
            return
        resp = requests.get(url, timeout=10, headers=manager.session.headers)

    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}")
        return
    parsed = feedparser.parse(resp.content)
    entries = getattr(parsed, "entries", [])[:limit]
    for i, e in enumerate(entries):
        tags = getattr(e, "tags", None)
        print(f"  entry[{i}] title: {(e.get('title') or '')[:50]}...")
        print(f"           tags: {tags}")
        if tags:
            for j, t in enumerate(tags):
                if isinstance(t, dict):
                    print(f"             [{j}] term={t.get('term')!r} scheme={t.get('scheme')!r} label={t.get('label')!r}")
                else:
                    print(f"             [{j}] {t!r}")
    print()


def main():
    from services.trends.prtimes_trends import PRTimesTrendsManager
    from services.trends.globenewswire_trends import GlobeNewswireTrendsManager

    print("=" * 60)
    print("PR TIMES (JP) 取得テスト")
    print("=" * 60)
    pr = PRTimesTrendsManager()
    result = pr._fetch_trends(limit=5)
    if result.get("success") and result.get("data"):
        print(f"OK: {len(result['data'])} 件取得")
        for i, item in enumerate(result["data"][:3], 1):
            print(f"  {i}. {item.get('title', '')[:60]}...")
            print(f"     {item.get('url', '')[:70]}...")
    else:
        print(f"NG: {result.get('error', 'unknown')}")
    _inspect_entry_tags(pr, "PR TIMES")

    print("=" * 60)
    print("GlobeNewswire (US) 取得テスト")
    print("=" * 60)
    gw = GlobeNewswireTrendsManager()
    result = gw._fetch_trends(limit=5)
    if result.get("success") and result.get("data"):
        print(f"OK: {len(result['data'])} 件取得")
        for i, item in enumerate(result["data"][:3], 1):
            print(f"  {i}. {item.get('title', '')[:60]}...")
            print(f"     {item.get('url', '')[:70]}...")
    else:
        print(f"NG: {result.get('error', 'unknown')}")
    _inspect_entry_tags(gw, "GlobeNewswire")

    print("テスト完了")


if __name__ == "__main__":
    main()
