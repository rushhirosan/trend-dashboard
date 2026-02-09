#!/usr/bin/env python3
"""
楽天ブックス「ビジネス」で取得できるデータを確認するスクリプト。
- BooksGenre/Search: 001006 の子ジャンル一覧（ID・名前）
- BooksBook/Search: 各子ジャンルで取得できる書籍サンプル

実行: python scripts/check_rakuten_book_business_data.py
"""
import os
import sys
import json
import time

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

import requests

RAKUTEN_APP_ID = os.getenv('RAKUTEN_APP_ID')
GENRE_URL = "https://app.rakuten.co.jp/services/api/BooksGenre/Search/20121128"
BOOK_URL = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"


def fetch_child_genres(parent_id: str):
    """001006 の子ジャンルを取得し、ID と名前の一覧を返す。"""
    if not RAKUTEN_APP_ID:
        print("❌ RAKUTEN_APP_ID が未設定です。.env を確認してください。")
        return []
    r = requests.get(
        GENRE_URL,
        params={
            'applicationId': RAKUTEN_APP_ID,
            'format': 'json',
            'booksGenreId': parent_id,
        },
        headers={'Accept': 'application/json', 'User-Agent': 'trends-dashboard/1.0.0'},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"❌ BooksGenre API HTTP {r.status_code}: {r.text[:500]}")
        return []
    data = r.json()
    # 生レスポンスの構造を確認用に表示（子ジャンル部分）
    if 'children' in data or 'Children' in data:
        raw = data.get('children', data.get('Children', []))
        print("\n--- BooksGenre/Search レスポンス (children 部分) ---")
        print(json.dumps(raw, ensure_ascii=False, indent=2)[:3000])
        if len(json.dumps(raw)) > 3000:
            print("... (省略)")
        print("---\n")
    # パース: 子ジャンルを [{"id": "001006001", "name": "経営"}, ...] に
    raw = data.get('children', data.get('Children', []))
    if isinstance(raw, dict):
        raw = raw.get('child', raw.get('Child', []))
    if not isinstance(raw, list):
        raw = [raw] if raw else []
    result = []
    for c in raw:
        child = c.get('child', c.get('Child', c)) if isinstance(c, dict) else c
        if isinstance(child, dict):
            gid = child.get('booksGenreId', child.get('BooksGenreId', ''))
            gname = child.get('booksGenreName', child.get('BooksGenreName', ''))
            if gid and str(gid).strip():
                result.append({'id': str(gid).strip(), 'name': gname or '(名前なし)'})
    return result


def fetch_books_sample(genre_id: str, hits: int = 5):
    """指定ジャンルで書籍を取得し、サンプルを返す。"""
    if not RAKUTEN_APP_ID:
        return None
    time.sleep(1.1)  # 楽天APIレート制限
    r = requests.get(
        BOOK_URL,
        params={
            'applicationId': RAKUTEN_APP_ID,
            'format': 'json',
            'booksGenreId': genre_id,
            'sort': 'sales',
            'hits': hits,
            'page': 1,
        },
        headers={'Accept': 'application/json', 'User-Agent': 'trends-dashboard/1.0.0'},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"  ❌ BooksBook API HTTP {r.status_code}")
        return None
    data = r.json()
    items = data.get('Items', data.get('items', []))
    return items


def main():
    print("=" * 60)
    print("楽天ブックス「ビジネス(001006)」で取得できるデータの確認")
    print("=" * 60)

    # 1) 子ジャンル一覧
    print("\n[1] 子ジャンル一覧 (BooksGenre/Search booksGenreId=001006)")
    children = fetch_child_genres('001006')
    if not children:
        print("   → 子ジャンルが0件、またはAPIエラーです。")
        print("   → 親ID 001006 のまま BooksBook/Search の結果を試します。")
        time.sleep(1.1)
        items = fetch_books_sample('001006', hits=5)
        if items:
            print(f"   親ID 001006 で取得件数: {len(items)}")
            for i, it in enumerate(items[:3], 1):
                inner = it.get('Item', it.get('item', it))
                title = inner.get('title', inner.get('itemName', ''))
                author = inner.get('author', '')
                price = inner.get('itemPrice', '')
                print(f"     {i}. {title[:50]} | {author} | ¥{price}")
        else:
            print("   親ID 001006 では0件でした。")
        return

    print(f"   → {len(children)} 件の子ジャンル:")
    for g in children:
        print(f"      - {g['id']} : {g['name']}")

    # 2) 先頭2子ジャンルで書籍サンプル取得
    print("\n[2] 書籍サンプル (BooksBook/Search, sort=sales)")
    for g in children[:2]:
        genre_id, genre_name = g['id'], g['name']
        print(f"\n   ジャンル: {genre_id} ({genre_name})")
        items = fetch_books_sample(genre_id, hits=5)
        if not items:
            print("      → 0件")
            continue
        print(f"      → {len(items)} 件取得 (先頭3件)")
        for i, it in enumerate(items[:3], 1):
            inner = it.get('Item', it.get('item', it))
            title = inner.get('title', inner.get('itemName', ''))
            author = inner.get('author', '')
            price = inner.get('itemPrice', '')
            sales = inner.get('sales', '')
            print(f"        {i}. {title[:45]}... | {author} | ¥{price} (sales: {sales})")

    print("\n" + "=" * 60)
    print("以上がビジネスカテゴリで取得できるデータのサンプルです。")
    print("=" * 60)


if __name__ == '__main__':
    main()
