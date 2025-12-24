#!/usr/bin/env python3
"""
データベースのキャッシュデータを確認するスクリプト
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import pytz

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
    
    # 7時の更新確認
    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.now(jst)
    today = now_jst.date()
    today_7am = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
    today_8am = now_jst.replace(hour=8, minute=0, second=0, microsecond=0)
    
    print("\n" + "=" * 60)
    print(f"7時の更新確認（今日: {today.strftime('%Y-%m-%d')} JST）")
    print("=" * 60)
    
    # cache_statusテーブルを確認
    try:
        cursor.execute("""
            SELECT cache_key, last_updated, data_count 
            FROM cache_status 
            ORDER BY cache_key
        """)
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
                            print(f"{status_icon} {row['cache_key']:30s} : {row['data_count']:3d}件 (最終更新: {time_str})")
                        else:
                            print(f"❌ {row['cache_key']:30s} : {row['data_count']:3d}件 (最終更新: {last_updated} - 形式エラー)")
                            not_updated_count += 1
                    except Exception as e:
                        print(f"❌ {row['cache_key']:30s} : {row['data_count']:3d}件 (最終更新: {last_updated} - 処理エラー: {e})")
                        not_updated_count += 1
                else:
                    print(f"❌ {row['cache_key']:30s} : {row['data_count']:3d}件 (最終更新: なし)")
                    not_updated_count += 1
            
            print("-" * 60)
            print(f"✅ 7時に更新済み: {updated_count}件")
            print(f"❌ 7時に未更新: {not_updated_count}件")
        else:
            print("  cache_statusテーブルにデータがありません")
    except Exception as e:
        print(f"  ❌ cache_statusテーブルの確認エラー: {e}")
        import traceback
        traceback.print_exc()
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ データベース接続エラー: {e}")
    sys.exit(1)
