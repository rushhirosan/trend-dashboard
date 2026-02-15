#!/usr/bin/env python3
"""
官公需APIの疎通確認スクリプト。
実行: python scripts/check_kkj_api.py
0件になる原因（タイムアウト・日付形式・XML構造）の切り分けに使えます。
"""
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    print("requests がありません: pip install requests")
    sys.exit(1)

KKJ_API_BASE = "http://www.kkj.go.jp/api/"
date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
params = {"Query": "デジタル", "CFT_Issue_Date": date_from, "Count": "5"}
url = KKJ_API_BASE + "?" + urlencode(params)

print("官公需API 疎通確認")
print("URL:", url)
print("タイムアウト: 45秒")
print()

try:
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    raw = r.content
    print("Status:", r.status_code, "Length:", len(raw))
    text = raw.decode("utf-8", errors="replace")
    if "SearchHits" in text or "searchhits" in text.lower():
        print("SearchHits を検出: 件数取得は成功している可能性あり")
    else:
        print("SearchHits が見つかりません。APIのレスポンス形式を確認してください。")
    print("--- 先頭1500文字 ---")
    print(text[:1500])
except requests.exceptions.Timeout:
    print("エラー: タイムアウトしました。ネットワークまたは官公需API側の遅延の可能性があります。")
    sys.exit(2)
except requests.RequestException as e:
    print("エラー:", e)
    sys.exit(1)
