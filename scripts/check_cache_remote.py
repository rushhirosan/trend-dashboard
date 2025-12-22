#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

database_url = os.getenv('DATABASE_URL')
conn = psycopg2.connect(database_url, connect_timeout=10)
conn.autocommit = True
cursor = conn.cursor(cursor_factory=RealDictCursor)

# テーブル一覧を取得
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%_cache'
    ORDER BY table_name
""")
tables = [row['table_name'] for row in cursor.fetchall()]

print('=' * 60)
print('キャッシュテーブルのデータ件数')
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

print('=' * 60)
print('\nキャッシュステータス（cache_statusテーブル）:')
print('-' * 60)
try:
    cursor.execute('SELECT cache_key, last_updated, data_count FROM cache_status ORDER BY cache_key')
    results = cursor.fetchall()
    if results:
        for row in results:
            print(f'  {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: {row["last_updated"]})')
    else:
        print('  cache_statusテーブルにデータがありません')
except Exception as e:
    print(f'  ❌ エラー: {e}')

cursor.close()
conn.close()
