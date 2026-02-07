#!/usr/bin/env python3
"""PR TIMES 各カテゴリのRSS取得状況をデバッグ"""
import sys
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

def parse_pub_date(pub_val):
    """published を datetime に変換"""
    if not pub_val:
        return None
    if hasattr(pub_val, 'timestamp'):
        return datetime.fromtimestamp(pub_val.timestamp(), tz=timezone.utc)
    if isinstance(pub_val, str):
        try:
            return parsedate_to_datetime(pub_val)
        except Exception:
            try:
                s = pub_val.replace('Z', '+00:00')[:19]
                dt = datetime.fromisoformat(s)
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            except Exception:
                return None
    return None

URLS = [
    "https://prtimes.jp/technology/",
    "https://prtimes.jp/business/",
    "https://prtimes.jp/entertainment/",
    "https://prtimes.jp/gourmet/",
    "https://prtimes.jp/app/",
    "https://prtimes.jp/lifestyle/",
]

session = requests.Session()
session.headers.update({
    'User-Agent': 'TrendDashboard/1.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
})

cutoff = datetime.now(timezone.utc) - timedelta(days=7)

for page_url in URLS:
    try:
        resp = session.get(page_url, timeout=10)
        print(f"\n{page_url}")
        print(f"  HTTP {resp.status_code}")
        if resp.status_code != 200:
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        link = soup.find('link', rel='alternate', type='application/rss+xml')
        if not link or not link.get('href'):
            print("  RSSリンク: なし")
            continue
        href = link['href'].strip()
        rss_url = urljoin(page_url, href) if href else None
        print(f"  RSS URL: {rss_url}")

        if rss_url:
            rresp = session.get(rss_url, timeout=10)
            if rresp.status_code != 200:
                print(f"  RSS取得: HTTP {rresp.status_code}")
                continue
            import feedparser
            parsed = feedparser.parse(rresp.content)
            entries = parsed.entries or []
            print(f"  RSSエントリ数: {len(entries)}")

            in_range = 0
            for e in entries[:5]:
                pub_val = e.get('published') or e.get('updated') or e.get('created')
                print(f"    - {(e.get('title') or '')[:40]}... | pub={pub_val}")
                dt = parse_pub_date(pub_val)
                if dt and dt >= cutoff:
                    in_range += 1
            if entries:
                for e in entries[5:]:
                    pub_val = e.get('published') or e.get('updated') or e.get('created')
                    dt = parse_pub_date(pub_val)
                    if dt and dt >= cutoff:
                        in_range += 1
                print(f"  7日以内の件数: {in_range}/{len(entries)}")
    except Exception as ex:
        print(f"  エラー: {ex}")
