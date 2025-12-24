#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import pytz

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

# 7時の更新確認
jst = pytz.timezone('Asia/Tokyo')
now_jst = datetime.now(jst)
today = now_jst.date()
today_7am = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
today_8am = now_jst.replace(hour=8, minute=0, second=0, microsecond=0)

print('\n' + '=' * 60)
print(f'7時の更新確認（今日: {today.strftime("%Y-%m-%d")} JST）')
print('=' * 60)

try:
    cursor.execute('SELECT cache_key, last_updated, data_count FROM cache_status ORDER BY cache_key')
    results = cursor.fetchall()
    if results:
        updated_count = 0
        not_updated_count = 0
        for row in results:
            last_updated = row['last_updated']
            if last_updated:
                try:
                    # PostgreSQLから取得した時刻をJSTに変換
                    if isinstance(last_updated, datetime):
                        # タイムゾーン情報がない場合はJSTとして扱う
                        if last_updated.tzinfo is None:
                            last_updated_jst = jst.localize(last_updated)
                        else:
                            # タイムゾーン情報がある場合はJSTに変換
                            last_updated_jst = last_updated.astimezone(jst)
                        
                        # 今日の7時から8時の間に更新されたかチェック
                        is_updated_at_7am = (today_7am <= last_updated_jst < today_8am) and (last_updated_jst.date() == today)
                        
                        if is_updated_at_7am:
                            status_icon = "✅"
                            updated_count += 1
                        else:
                            status_icon = "❌"
                            not_updated_count += 1
                        
                        time_str = last_updated_jst.strftime('%Y-%m-%d %H:%M:%S JST')
                        print(f'{status_icon} {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: {time_str})')
                    else:
                        print(f'❌ {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: {last_updated} - 形式エラー)')
                        not_updated_count += 1
                except Exception as e:
                    print(f'❌ {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: {last_updated} - 処理エラー: {e})')
                    not_updated_count += 1
            else:
                print(f'❌ {row["cache_key"]:30s} : {row["data_count"]:3d}件 (最終更新: なし)')
                not_updated_count += 1
        
        print('-' * 60)
        print(f'✅ 7時に更新済み: {updated_count}件')
        print(f'❌ 7時に未更新: {not_updated_count}件')
    else:
        print('  cache_statusテーブルにデータがありません')
except Exception as e:
    print(f'  ❌ エラー: {e}')

cursor.close()
conn.close()
