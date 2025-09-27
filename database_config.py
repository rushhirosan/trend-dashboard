"""
データベース設定とキャッシュシステム
PostgreSQLデータベースの接続とキャッシュ機能を提供
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class TrendsCache:
    """トレンドデータのキャッシュシステム"""
    
    def __init__(self):
        """初期化"""
        self.connection = None
        self.connect()
    
    def connect(self):
        """データベースに接続"""
        try:
            self.connection = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'trends_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'password')
            )
            print("✅ データベース接続成功")
        except Exception as e:
            print(f"❌ データベース接続エラー: {e}")
            self.connection = None
    
    def init_database(self):
        """データベースを初期化"""
        if not self.connection:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                # テーブル作成のSQL
                create_tables_sql = """
                CREATE TABLE IF NOT EXISTS google_trends_cache (
                    id SERIAL PRIMARY KEY,
                    keyword VARCHAR(255) NOT NULL,
                    score INTEGER NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS youtube_trends_cache (
                    id SERIAL PRIMARY KEY,
                    video_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    channel_title VARCHAR(255) NOT NULL,
                    view_count INTEGER NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS music_trends_cache (
                    id SERIAL PRIMARY KEY,
                    track_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    artist VARCHAR(255) NOT NULL,
                    popularity INTEGER NOT NULL,
                    service VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS podcast_trends_cache (
                    id SERIAL PRIMARY KEY,
                    podcast_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    publisher VARCHAR(255) NOT NULL,
                    score INTEGER NOT NULL,
                    trend_type VARCHAR(50) NOT NULL,
                    region VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS news_trends_cache (
                    id SERIAL PRIMARY KEY,
                    article_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    source VARCHAR(255) NOT NULL,
                    published_at TIMESTAMP NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    country VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS worldnews_trends_cache (
                    id SERIAL PRIMARY KEY,
                    article_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    source VARCHAR(255) NOT NULL,
                    published_at TIMESTAMP NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    country VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS rakuten_trends_cache (
                    id SERIAL PRIMARY KEY,
                    item_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS hatena_trends_cache (
                    id SERIAL PRIMARY KEY,
                    entry_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    bookmark_count INTEGER NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS twitch_trends_cache (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(255) NOT NULL,
                    game_name VARCHAR(255) NOT NULL,
                    viewer_count INTEGER NOT NULL,
                    trend_type VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS cache_status (
                    id SERIAL PRIMARY KEY,
                    cache_key VARCHAR(255) NOT NULL UNIQUE,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_count INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'active'
                );
                
                -- 既存のcountry_codeカラムをcache_keyに変更（存在する場合）
                DO $$ 
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cache_status' AND column_name = 'country_code') THEN
                        ALTER TABLE cache_status RENAME COLUMN country_code TO cache_key;
                    END IF;
                END $$;
                
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                );
                """
                
                cursor.execute(create_tables_sql)
                self.connection.commit()
                print("✅ データベーステーブル作成完了")
                return True
                
        except Exception as e:
            print(f"❌ データベース初期化エラー: {e}")
            return False
    
    def save_to_cache(self, data, cache_key, region='JP'):
        """データをキャッシュに保存"""
        if not self.connection or not data:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                # 既存のデータを削除
                table_name = f"{cache_key}_cache"
                cursor.execute(f"DELETE FROM {table_name} WHERE region = %s", (region,))
                
                # 新しいデータを挿入
                for item in data:
                    if cache_key == 'google_trends':
                        cursor.execute(
                            "INSERT INTO google_trends_cache (keyword, score, region) VALUES (%s, %s, %s)",
                            (item.get('keyword', ''), item.get('score', 0), region)
                        )
                    elif cache_key == 'youtube_trends':
                        cursor.execute(
                            "INSERT INTO youtube_trends_cache (region_code, trend_type, video_id, title, channel_title, view_count, like_count, comment_count, published_at, thumbnail_url, rank) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (region, 'trending', item.get('video_id', ''), item.get('title', ''), item.get('channel_title', ''), item.get('view_count', 0), item.get('like_count', 0), item.get('comment_count', 0), item.get('published_at', 'NOW()'), item.get('thumbnail_url', ''), item.get('rank', 0))
                        )
                    elif cache_key == 'music_trends':
                        cursor.execute(
                            "INSERT INTO music_trends_cache (service, region_code, title, artist, album, play_count, popularity, spotify_url, rank, track_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (item.get('service', 'spotify'), region, item.get('title', ''), item.get('artist', ''), item.get('album', ''), item.get('play_count', 0), item.get('popularity', 0), item.get('spotify_url', ''), item.get('rank', 0), item.get('track_id', ''))
                        )
                    elif cache_key == 'podcast_trends':
                        cursor.execute(
                            "INSERT INTO podcast_trends_cache (podcast_id, title, publisher, score, trend_type, region) VALUES (%s, %s, %s, %s, %s, %s)",
                            (item.get('podcast_id', ''), item.get('title', ''), item.get('publisher', ''), item.get('score', 0), item.get('trend_type', ''), region)
                        )
                    elif cache_key == 'news_trends':
                        cursor.execute(
                            "INSERT INTO news_trends_cache (article_id, title, source, published_at, category, country) VALUES (%s, %s, %s, %s, %s, %s)",
                            (item.get('article_id', ''), item.get('title', ''), item.get('source', ''), item.get('published_at', ''), item.get('category', ''), item.get('country', ''))
                        )
                    elif cache_key == 'worldnews_trends':
                        cursor.execute(
                            "INSERT INTO worldnews_trends_cache (article_id, title, source, published_at, category, country) VALUES (%s, %s, %s, %s, %s, %s)",
                            (item.get('article_id', ''), item.get('title', ''), item.get('source', ''), item.get('published_at', ''), item.get('category', ''), item.get('country', ''))
                        )
                    elif cache_key == 'rakuten_trends':
                        cursor.execute(
                            "INSERT INTO rakuten_trends_cache (item_id, title, price, category) VALUES (%s, %s, %s, %s)",
                            (item.get('item_id', ''), item.get('title', ''), item.get('price', 0), item.get('category', ''))
                        )
                    elif cache_key == 'hatena_trends':
                        cursor.execute(
                            "INSERT INTO hatena_trends_cache (entry_id, title, url, bookmark_count, category) VALUES (%s, %s, %s, %s, %s)",
                            (item.get('entry_id', ''), item.get('title', ''), item.get('url', ''), item.get('bookmark_count', 0), item.get('category', ''))
                        )
                    elif cache_key == 'twitch_trends':
                        cursor.execute(
                            "INSERT INTO twitch_trends_cache (game_id, game_name, viewer_count, trend_type) VALUES (%s, %s, %s, %s)",
                            (item.get('game_id', ''), item.get('game_name', ''), item.get('viewer_count', 0), item.get('trend_type', ''))
                        )
                
                # キャッシュステータスを更新
                cursor.execute(
                    "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                    (cache_key, datetime.now(), len(data), datetime.now(), len(data))
                )
                
                self.connection.commit()
                print(f"✅ {cache_key}のキャッシュを更新しました ({len(data)}件)")
                return True
                
        except Exception as e:
            print(f"❌ キャッシュ保存エラー: {e}")
            return False
    
    def get_from_cache(self, cache_key, region='JP'):
        """キャッシュからデータを取得"""
        if not self.connection:
            return None
        
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                table_name = f"{cache_key}_cache"
                # regionが空の場合はregion条件を除外
                if region and region != '':
                    cursor.execute(f"SELECT * FROM {table_name} WHERE region = %s ORDER BY created_at DESC", (region,))
                else:
                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY created_at DESC")
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except Exception as e:
            print(f"❌ キャッシュ取得エラー: {e}")
            return None
    
    def is_cache_valid(self, cache_key, region='JP', hours=24):
        """キャッシュが有効かどうかを確認"""
        if not self.connection:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT last_updated FROM cache_status WHERE cache_key = %s",
                    (cache_key,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                last_updated = result[0]
                now = datetime.now()
                time_diff = now - last_updated
                
                return time_diff.total_seconds() < (hours * 3600)
                
        except Exception as e:
            print(f"❌ キャッシュ有効性確認エラー: {e}")
            return False
    
    def clear_cache(self, cache_key, region='JP'):
        """キャッシュをクリア"""
        if not self.connection:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                table_name = f"{cache_key}_cache"
                cursor.execute(f"DELETE FROM {table_name} WHERE region = %s", (region,))
                self.connection.commit()
                print(f"✅ {cache_key}のキャッシュをクリアしました")
                return True
                
        except Exception as e:
            print(f"❌ キャッシュクリアエラー: {e}")
            return False
    
    def get_connection(self):
        """データベース接続を取得"""
        return self.connection
    
    # Google Trends キャッシュメソッド
    def save_google_trends_to_cache(self, data, region='JP'):
        """Google Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'google_trends', region)
    
    def get_google_trends_from_cache(self, region='JP'):
        """Google Trendsデータをキャッシュから取得"""
        return self.get_from_cache('google_trends', region)
    
    def clear_google_trends_cache(self, region='JP'):
        """Google Trendsキャッシュをクリア"""
        return self.clear_cache('google_trends', region)
    
    def is_google_cache_valid(self, region='JP'):
        """Google Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('google_trends', region, 6)
    
    # YouTube Trends キャッシュメソッド
    def save_youtube_trends_to_cache(self, data, region='JP'):
        """YouTube Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'youtube_trends', region)
    
    def get_youtube_trends_from_cache(self, region='JP'):
        """YouTube Trendsデータをキャッシュから取得"""
        return self.get_from_cache('youtube_trends', region)
    
    def clear_youtube_trends_cache(self, region='JP'):
        """YouTube Trendsキャッシュをクリア"""
        return self.clear_cache('youtube_trends', region)
    
    def is_youtube_cache_valid(self, region='JP'):
        """YouTube Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('youtube_trends', region, 6)
    
    # Music Trends キャッシュメソッド
    def save_music_trends_to_cache(self, data, service='spotify'):
        """Music Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'music_trends', service)
    
    def get_music_trends_from_cache(self, service='spotify'):
        """Music Trendsデータをキャッシュから取得"""
        return self.get_from_cache('music_trends', service)
    
    def clear_music_trends_cache(self, service='spotify'):
        """Music Trendsキャッシュをクリア"""
        return self.clear_cache('music_trends', service)
    
    def is_music_cache_valid(self, service='spotify'):
        """Music Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('music_trends', service, 12)
    
    # Podcast Trends キャッシュメソッド
    def save_podcast_trends_to_cache(self, data, cache_key='podcast_trends', region='JP'):
        """Podcast Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, cache_key, region)
    
    def get_podcast_trends_from_cache(self, trend_type='best_podcasts', region='JP'):
        """Podcast Trendsデータをキャッシュから取得"""
        return self.get_from_cache('podcast_trends', region)
    
    def clear_podcast_trends_cache(self, trend_type='best_podcasts'):
        """Podcast Trendsキャッシュをクリア"""
        return self.clear_cache('podcast_trends', 'JP')
    
    def is_podcast_cache_valid(self, trend_type='best_podcasts', region='JP'):
        """Podcast Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('podcast_trends', region, 24)
    
    # News Trends キャッシュメソッド
    def save_news_trends_to_cache(self, data, category='general', country='JP'):
        """News Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'news_trends', country)
    
    def get_news_trends_from_cache(self, category='general', country='JP'):
        """News Trendsデータをキャッシュから取得"""
        return self.get_from_cache('news_trends', country)
    
    def clear_news_trends_cache(self, category='general', country='JP'):
        """News Trendsキャッシュをクリア"""
        return self.clear_cache('news_trends', country)
    
    def is_news_cache_valid(self, category='general', country='JP'):
        """News Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('news_trends', country, 24)
    
    # World News Trends キャッシュメソッド
    def save_worldnews_trends_to_cache(self, data, cache_key='worldnews_trends', country='JP'):
        """World News Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, cache_key, country)
    
    def get_worldnews_trends_from_cache(self, category='general', country='JP'):
        """World News Trendsデータをキャッシュから取得"""
        return self.get_from_cache('worldnews_trends', country)
    
    def clear_worldnews_trends_cache(self, category='general', country='JP'):
        """World News Trendsキャッシュをクリア"""
        return self.clear_cache('worldnews_trends', country)
    
    def is_worldnews_cache_valid(self, category='general', country='JP'):
        """World News Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('worldnews_trends', country, 24)
    
    # Rakuten Trends キャッシュメソッド
    def save_rakuten_trends_to_cache(self, data, category='all'):
        """Rakuten Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'rakuten_trends', category)
    
    def get_rakuten_trends_from_cache(self, category='all'):
        """Rakuten Trendsデータをキャッシュから取得"""
        return self.get_from_cache('rakuten_trends', category)
    
    def clear_rakuten_trends_cache(self, category='all'):
        """Rakuten Trendsキャッシュをクリア"""
        return self.clear_cache('rakuten_trends', category)
    
    def is_rakuten_cache_valid(self, category='all'):
        """Rakuten Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('rakuten_trends', category, 24)
    
    # Hatena Trends キャッシュメソッド
    def save_hatena_trends_to_cache(self, data, category='all'):
        """Hatena Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'hatena_trends', category)
    
    def get_hatena_trends_from_cache(self, category='all'):
        """Hatena Trendsデータをキャッシュから取得"""
        return self.get_from_cache('hatena_trends', category)
    
    def clear_hatena_trends_cache(self, category='all'):
        """Hatena Trendsキャッシュをクリア"""
        return self.clear_cache('hatena_trends', category)
    
    def is_hatena_cache_valid(self, category='all'):
        """Hatena Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('hatena_trends', category, 24)
    
    # Twitch Trends キャッシュメソッド
    def save_twitch_trends_to_cache(self, data, trend_type='games'):
        """Twitch Trendsデータをキャッシュに保存"""
        return self.save_to_cache(data, 'twitch_trends', trend_type)
    
    def get_twitch_trends_from_cache(self, trend_type='games'):
        """Twitch Trendsデータをキャッシュから取得"""
        return self.get_from_cache('twitch_trends', trend_type)
    
    def clear_twitch_trends_cache(self, trend_type='games'):
        """Twitch Trendsキャッシュをクリア"""
        return self.clear_cache('twitch_trends', trend_type)
    
    def is_twitch_cache_valid(self, trend_type='games'):
        """Twitch Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('twitch_trends', trend_type, 24)
    
    def get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        if not self.connection:
            return None
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT last_updated, data_count FROM cache_status WHERE cache_key = %s",
                    (cache_key,)
                )
                result = cursor.fetchone()
                
                if result:
                    return {
                        'last_updated': result[0].isoformat() if result[0] else None,
                        'data_count': result[1]
                    }
                return None
                
        except Exception as e:
            print(f"❌ キャッシュ情報取得エラー: {e}")
            return None
    
    def get_all_cache_status(self):
        """全キャッシュの状態を取得"""
        if not self.connection:
            return {}
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT cache_key, last_updated, data_count FROM cache_status")
                results = cursor.fetchall()
                
                status = {}
                for row in results:
                    status[row[0]] = {
                        'last_updated': row[1],
                        'data_count': row[2]
                    }
                return status
                
        except Exception as e:
            print(f"❌ 全キャッシュ状態取得エラー: {e}")
            return {}
    
    def get_last_update_time(self):
        """最後の更新時刻を取得"""
        if not self.connection:
            return None
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT MAX(last_updated) FROM cache_status")
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except Exception as e:
            print(f"❌ 最終更新時刻取得エラー: {e}")
            return None
    
    def clear_all_cache(self):
        """全キャッシュをクリア"""
        if not self.connection:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                # 全キャッシュテーブルをクリア
                tables = [
                    'google_trends_cache',
                    'youtube_trends_cache',
                    'music_trends_cache',
                    'podcast_trends_cache',
                    'news_trends_cache',
                    'worldnews_trends_cache',
                    'rakuten_trends_cache',
                    'hatena_trends_cache',
                    'twitch_trends_cache'
                ]
                
                for table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                
                # cache_statusもクリア
                cursor.execute("DELETE FROM cache_status")
                
                self.connection.commit()
                print("✅ 全キャッシュをクリアしました")
                return True
                
        except Exception as e:
            print(f"❌ 全キャッシュクリアエラー: {e}")
            return False
    
    def clear_cache_by_type(self, cache_type):
        """特定のキャッシュをクリア"""
        if not self.connection:
            return False
        
        try:
            with self.connection.cursor() as cursor:
                table_name = f"{cache_type}_cache"
                cursor.execute(f"DELETE FROM {table_name}")
                cursor.execute("DELETE FROM cache_status WHERE cache_key = %s", (cache_type,))
                self.connection.commit()
                print(f"✅ {cache_type}キャッシュをクリアしました")
                return True
                
        except Exception as e:
            print(f"❌ {cache_type}キャッシュクリアエラー: {e}")
            return False
    
    def close(self):
        """データベース接続を閉じる"""
        if self.connection:
            self.connection.close()
            print("✅ データベース接続を閉じました")
