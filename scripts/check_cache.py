#!/usr/bin/env python3
"""
データベースのキャッシュデータを確認するスクリプト
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# 環境変数を読み込み
load_dotenv()

# DATABASE_URLを取得
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URLが設定されていません")
    sys.exit(1)

# 接続
try:
    conn = psycopg2.connect(database_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("✅ データベース接続成功\n")
    
    # 各カテゴリのキャッシュテーブルを確認
    categories = [
        ('google_trends_cache', 'JP'),
        ('youtube_trends_cache', 'JP'),
        ('music_trends_cache', 'JP'),
        ('news_trends_cache', 'JP'),
        ('worldnews_trends_cache', 'JP'),
        ('podcast_trends_cache', 'JP'),
        ('rakuten_trends_cache', 'all'),
        ('hatena_trends_cache', 'all'),
        ('twitch_trends_cache', 'games'),
        ('qiita_trends_cache', None),
        ('nhk_trends_cache', None),
        ('stock_trends_cache', 'JP'),
        ('crypto_trends_cache', None),
    ]
    
    print("=" * 60)
    print("キャッシュデータの確認結果")
    print("=" * 60)
    
    for table_name, filter_value in categories:
        try:
            if filter_value:
                if table_name == 'stock_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE market = %s", (filter_value,))
                elif table_name == 'hatena_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE category = %s", (filter_value,))
                elif table_name == 'twitch_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE category = %s", (filter_value,))
                elif table_name == 'rakuten_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE genre_id = %s", (filter_value,))
                elif table_name == 'worldnews_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE country = %s", (filter_value.lower(),))
                elif table_name == 'youtube_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE region_code = %s", (filter_value,))
                elif table_name == 'google_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE country = %s", (filter_value,))
                elif table_name == 'music_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE region_code = %s", (filter_value,))
                elif table_name == 'podcast_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE region_code = %s", (filter_value.upper(),))
                elif table_name == 'news_trends_cache':
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name} WHERE country = %s", (filter_value.lower(),))
                else:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            else:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            status = "✅" if count > 0 else "❌"
            print(f"{status} {table_name:30s} : {count:3d}件")
            
        except psycopg2.errors.UndefinedTable:
            print(f"❌ {table_name:30s} : テーブルが存在しません")
        except Exception as e:
            print(f"❌ {table_name:30s} : エラー - {str(e)[:50]}")
    
    print("=" * 60)
    
    # cache_statusテーブルも確認
    print("\nキャッシュステータス（cache_statusテーブル）:")
    print("-" * 60)
    try:
        cursor.execute("""
            SELECT cache_key, last_updated, data_count 
            FROM cache_status 
            ORDER BY cache_key
        """)
        results = cursor.fetchall()
        if results:
            for row in results:
                print(f"  {row['cache_key']:30s} : {row['data_count']:3d}件 (最終更新: {row['last_updated']})")
        else:
            print("  cache_statusテーブルにデータがありません")
    except Exception as e:
        print(f"  ❌ cache_statusテーブルの確認エラー: {e}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ データベース接続エラー: {e}")
    sys.exit(1)
