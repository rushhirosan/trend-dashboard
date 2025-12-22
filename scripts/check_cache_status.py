#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

database_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(database_url, connect_timeout=10)
conn.autocommit = True
cursor = conn.cursor(cursor_factory=RealDictCursor)

# タイムアウトしているカテゴリのキャッシュテーブルを確認
tables = ['stock_trends_cache', 'crypto_trends_cache', 'podcast_trends_cache', 'rakuten_trends_cache', 'hatena_trends_cache', 'twitch_trends_cache', 'nhk_trends_cache', 'qiita_trends_cache']

print('=' * 60)
print('タイムアウトしているカテゴリのキャッシュデータ件数')
print('=' * 60)

for table_name in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) as count FROM {table_name}')
        result = cursor.fetchone()
        count = result['count'] if result else 0
        status = '✅' if count > 0 else '❌'
        print(f'{status} {table_name:30s} : {count:3d}件')
    except Exception as e:
        print(f'❌ {table_name:30s} : エラー - {str(e)[:50]}')

print('\n' + '=' * 60)
print('cache_statusテーブルの状態')
print('=' * 60)
try:
    cache_keys = ['stock_trends', 'crypto_trends', 'podcast_trends', 'rakuten_trends', 'hatena_trends', 'twitch_trends', 'nhk_trends', 'qiita_trends']
    placeholders = ','.join(['%s'] * len(cache_keys))
    cursor.execute(f'SELECT cache_key, last_updated, data_count FROM cache_status WHERE cache_key IN ({placeholders}) ORDER BY cache_key', cache_keys)
    results = cursor.fetchall()
    if results:
        for row in results:
            print(f'  {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: {row["last_updated"]})')
    else:
        print('  該当するデータがありません')
except Exception as e:
    print(f'  ❌ エラー: {e}')

cursor.close()
conn.close()
