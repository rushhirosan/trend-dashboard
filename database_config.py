"""
データベース設定とキャッシュシステム
PostgreSQLデータベースの接続とキャッシュ機能を提供
"""

import os
import json
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.logger_config import get_logger

# 環境変数を読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

# シングルトンインスタンス（全マネージャーで共有）
_shared_cache_instance = None

# データベース接続取得用のロック（複数マネージャーからの同時アクセスを防ぐ）
_connection_lock = threading.Lock()

class TrendsCache:
    """トレンドデータのキャッシュシステム"""
    
    def __init__(self):
        """初期化"""
        global _shared_cache_instance
        
        # シングルトンパターン：既存のインスタンスがあれば再利用
        if _shared_cache_instance is not None:
            # 既存インスタンスの属性をコピー（接続を共有）
            self.connection = _shared_cache_instance.connection
            return
        
        # 初回インスタンス作成
        self.connection = None
        # 接続を遅延初期化（エラーが発生してもアプリを起動できるように）
        try:
            self.connect()
        except Exception as e:
            logger.warning(f"⚠️ データベース接続の初期化に失敗しました（後で再試行可能）: {e}", exc_info=True)
            self.connection = None
        
        # グローバルインスタンスに保存
        _shared_cache_instance = self
    
    def connect(self):
        """データベースに接続"""
        # 既存の接続を閉じる（存在する場合）
        if self.connection:
            try:
                if not self.connection.closed:
                    self.connection.close()
            except Exception:
                pass  # 既に閉じられている場合は無視
            self.connection = None
        
        try:
            # DATABASE_URLが設定されている場合は優先的に使用（fly.ioなど）
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                # DATABASE_URLの形式: postgresql://user:password@host:port/database
                # 接続タイムアウトとキープアライブ設定を追加
                # Fly.ioのPostgreSQLは接続を閉じる可能性があるため、より積極的なキープアライブ設定を使用
                self.connection = psycopg2.connect(
                    database_url,
                    connect_timeout=10,  # 10秒に延長（並列リクエスト時の接続確立時間を考慮）
                    keepalives=1,
                    keepalives_idle=10,  # 10秒でキープアライブを開始
                    keepalives_interval=5,  # 5秒間隔でキープアライブを送信
                    keepalives_count=5  # 5回失敗まで許容
                )
                # 自動コミットを無効化（トランザクション制御のため）
                self.connection.autocommit = False
                logger.info("✅ データベース接続成功 (DATABASE_URL使用)")
            else:
                # 個別の環境変数を使用（ローカル開発環境など）
                self.connection = psycopg2.connect(
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    database=os.getenv('DB_NAME', 'trends_db'),
                    user=os.getenv('DB_USER', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'password'),
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3
                )
                # 自動コミットを無効化（トランザクション制御のため）
                self.connection.autocommit = False
                logger.info("✅ データベース接続成功 (個別環境変数使用)")
        except Exception as e:
            logger.error(f"❌ データベース接続エラー: {e}", exc_info=True)
            self.connection = None
    
    def init_database(self):
        """データベースを初期化"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ データベース初期化エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
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
                    region_code VARCHAR(10),
                    trend_type VARCHAR(50) DEFAULT 'trending',
                    video_id VARCHAR(255),
                    title TEXT NOT NULL,
                    channel_title VARCHAR(255),
                    view_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    published_at TIMESTAMP,
                    thumbnail_url TEXT,
                    rank INTEGER DEFAULT 0,
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
                    cache_key VARCHAR(255),
                    region_code VARCHAR(10),
                    podcast_id VARCHAR(255),
                    title TEXT NOT NULL,
                    description TEXT,
                    publisher VARCHAR(255),
                    url TEXT,
                    image_url TEXT,
                    language VARCHAR(10),
                    country VARCHAR(100),
                    score INTEGER DEFAULT 0,
                    rank INTEGER DEFAULT 0,
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
                    published_at TIMESTAMP,
                    category VARCHAR(50) NOT NULL,
                    country VARCHAR(10) NOT NULL,
                    url TEXT,
                    description TEXT,
                    image_url TEXT,
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
                    description TEXT,
                    bookmark_count INTEGER NOT NULL,
                    published VARCHAR(100),
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    category VARCHAR(50) NOT NULL,
                    region VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS twitch_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500),
                    game_name VARCHAR(255),
                    viewer_count INTEGER DEFAULT 0,
                    rank INTEGER DEFAULT 0,
                    category VARCHAR(50) NOT NULL,
                    thumbnail_url VARCHAR(500),
                    user_name VARCHAR(255),
                    language VARCHAR(10),
                    started_at VARCHAR(50),
                    view_count INTEGER DEFAULT 0,
                    creator_name VARCHAR(255),
                    duration INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    url VARCHAR(500),
                    box_art_url VARCHAR(500),
                    game_id VARCHAR(255)
                );
                
                CREATE TABLE IF NOT EXISTS reddit_trends_cache (
                    id SERIAL PRIMARY KEY,
                    post_id VARCHAR(255),
                    title TEXT NOT NULL,
                    url TEXT,
                    subreddit VARCHAR(100) NOT NULL,
                    author VARCHAR(100),
                    score INTEGER DEFAULT 0,
                    upvote_ratio FLOAT DEFAULT 0,
                    num_comments INTEGER DEFAULT 0,
                    permalink TEXT,
                    is_video BOOLEAN DEFAULT FALSE,
                    domain VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    region VARCHAR(10) DEFAULT 'all'
                );
                
                CREATE TABLE IF NOT EXISTS hackernews_trends_cache (
                    id SERIAL PRIMARY KEY,
                    story_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    score INTEGER DEFAULT 0,
                    author VARCHAR(100),
                    story_time INTEGER,
                    comments INTEGER DEFAULT 0,
                    story_type VARCHAR(50) DEFAULT 'top',
                    rank INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS qiita_trends_cache (
                    id SERIAL PRIMARY KEY,
                    item_id VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    user_id VARCHAR(100),
                    user_name VARCHAR(100),
                    likes_count INTEGER DEFAULT 0,
                    stocks_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    created_at VARCHAR(100),
                    updated_at VARCHAR(100),
                    tags TEXT,
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS nhk_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS cnn_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS producthunt_trends_cache (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(255) NOT NULL,
                    name TEXT NOT NULL,
                    tagline TEXT,
                    description TEXT,
                    url TEXT,
                    website TEXT,
                    votes_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    created_at VARCHAR(100),
                    topics TEXT,
                    user_name VARCHAR(100),
                    user_username VARCHAR(100),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS stock_trends_cache (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL,
                    name TEXT NOT NULL,
                    current_price DECIMAL(15, 2),
                    previous_price DECIMAL(15, 2),
                    change DECIMAL(15, 2),
                    change_percent DECIMAL(10, 2),
                    volume BIGINT DEFAULT 0,
                    market_cap BIGINT DEFAULT 0,
                    market VARCHAR(10) NOT NULL,
                    rank INTEGER DEFAULT 0,
                    updated_at TIMESTAMP,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS crypto_trends_cache (
                    id SERIAL PRIMARY KEY,
                    coin_id VARCHAR(100) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    name TEXT NOT NULL,
                    market_cap_rank INTEGER DEFAULT 0,
                    search_score INTEGER DEFAULT 0,
                    current_price DECIMAL(20, 8),
                    price_change_24h DECIMAL(20, 8),
                    price_change_percentage_24h DECIMAL(10, 2),
                    market_cap BIGINT DEFAULT 0,
                    volume_24h BIGINT DEFAULT 0,
                    image_url TEXT,
                    rank INTEGER DEFAULT 0,
                    updated_at TIMESTAMP,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS movie_trends_cache (
                    id SERIAL PRIMARY KEY,
                    country VARCHAR(10) NOT NULL DEFAULT 'JP',
                    movie_id INTEGER NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    original_title VARCHAR(500),
                    overview TEXT,
                    popularity DECIMAL(10, 4),
                    vote_average DECIMAL(4, 2),
                    vote_count INTEGER,
                    release_date VARCHAR(20),
                    poster_path VARCHAR(500),
                    backdrop_path VARCHAR(500),
                    poster_url TEXT,
                    backdrop_url TEXT,
                    rank INTEGER,
                    updated_at TIMESTAMP,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS book_trends_cache (
                    id SERIAL PRIMARY KEY,
                    country VARCHAR(10) NOT NULL,
                    book_id VARCHAR(100),
                    isbn VARCHAR(20),
                    title VARCHAR(500) NOT NULL,
                    subtitle VARCHAR(500),
                    author TEXT,
                    authors TEXT,
                    publisher VARCHAR(200),
                    price DECIMAL(10, 2),
                    sales INTEGER,
                    published_date VARCHAR(20),
                    release_date VARCHAR(20),
                    description TEXT,
                    page_count INTEGER,
                    categories TEXT,
                    average_rating DECIMAL(3, 2),
                    ratings_count INTEGER,
                    language VARCHAR(10),
                    item_url TEXT,
                    affiliate_url TEXT,
                    preview_link TEXT,
                    info_link TEXT,
                    buy_link TEXT,
                    image_url TEXT,
                    thumbnail TEXT,
                    small_thumbnail TEXT,
                    medium TEXT,
                    large TEXT,
                    rank INTEGER,
                    updated_at TIMESTAMP,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                conn.commit()
                logger.info("✅ データベーステーブル作成完了")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ データベース初期化中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ データベース初期化エラー: {e}", exc_info=True)
            return False
    
    def save_to_cache(self, data, cache_key, region='JP'):
        """データをキャッシュに保存"""
        if not data:
            return False
        
        # Fly.ioでは接続を保持するよりも、毎回新規接続を作成する方が安全
        # 接続を取得（毎回新規接続を作成、リトライロジック付き）
        import time
        conn = None
        max_retries = 3
        retry_delay = 1.0  # 1秒待機してから再試行
        
        for attempt in range(max_retries):
            try:
                # 接続をリセットしてから新規接続を作成
                if self.connection:
                    try:
                        if not self.connection.closed:
                            self.connection.close()
                    except:
                        pass
                    self.connection = None
                
                # 新規接続を作成
                database_url = os.getenv('DATABASE_URL')
                if database_url:
                    conn = psycopg2.connect(
                        database_url,
                        connect_timeout=5,  # 5秒に短縮（キャッシュ取得は高速であるべき）
                        keepalives=1,
                        keepalives_idle=10,
                        keepalives_interval=5,
                        keepalives_count=5
                    )
                    conn.autocommit = False
                    logger.info(f"✅ データベース接続成功 (試行 {attempt + 1}/{max_retries})")
                    break  # 接続成功したらループを抜ける
                else:
                    conn = psycopg2.connect(
                        host=os.getenv('DB_HOST', 'localhost'),
                        port=os.getenv('DB_PORT', '5432'),
                        database=os.getenv('DB_NAME', 'trends_db'),
                        user=os.getenv('DB_USER', 'postgres'),
                        password=os.getenv('DB_PASSWORD', 'password'),
                        connect_timeout=10,
                        keepalives=1,
                        keepalives_idle=30,
                        keepalives_interval=10,
                        keepalives_count=3
                    )
                    conn.autocommit = False
                    logger.info(f"✅ データベース接続成功 (試行 {attempt + 1}/{max_retries})")
                    break  # 接続成功したらループを抜ける
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ データベース接続失敗 (試行 {attempt + 1}/{max_retries}): {e} - {retry_delay}秒後に再試行します", exc_info=True)
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # 指数バックオフ
                    continue
                else:
                    logger.error(f"❌ キャッシュ保存エラー: データベース接続取得に失敗しました（最大試行回数に達しました）: {e}", exc_info=True)
                    return False
            except Exception as e:
                logger.error(f"❌ キャッシュ保存エラー: 予期しないエラー: {e}", exc_info=True)
                import traceback
                traceback.print_exc()
                return False
        
        if not conn:
            logger.error("❌ キャッシュ保存エラー: データベース接続を取得できませんでした")
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                table_name = f"{cache_key}_cache"
                delete_column_map = {
                    'google_trends': 'region',
                    'podcast_trends': 'region',
                    'news_trends': 'country',
                    'worldnews_trends': 'country',
                    'rakuten_trends': 'genre_id',
                    'hatena_trends': 'category',
                    'twitch_trends': 'category'
                }
                
                if cache_key == 'music_trends':
                    cursor.execute(f"DELETE FROM {table_name} WHERE service = %s", (region,))
                elif cache_key == 'podcast_trends':
                    cursor.execute(f"DELETE FROM podcast_trends_cache WHERE region = %s", (region,))
                elif cache_key == 'youtube_trends':
                    # YouTubeはregionとtrend_typeで削除
                    # dataの最初のitemからtrend_typeを取得
                    trend_type = data[0].get('trend_type', 'trending') if data else 'trending'
                    cursor.execute(f"DELETE FROM {table_name} WHERE region = %s AND trend_type = %s", (region, trend_type))
                elif cache_key == 'reddit_trends':
                    cursor.execute(f"DELETE FROM {table_name} WHERE subreddit = %s", (region,))
                elif cache_key == 'hackernews_trends':
                    cursor.execute(f"DELETE FROM {table_name} WHERE story_type = %s", (region,))
                elif cache_key == 'qiita_trends':
                    cursor.execute(f"DELETE FROM {table_name}")
                elif cache_key == 'nhk_trends':
                    cursor.execute(f"DELETE FROM {table_name}")
                elif cache_key == 'producthunt_trends':
                    cursor.execute(f"DELETE FROM {table_name}")
                elif cache_key == 'hatena_trends':
                    # hatena_trendsの場合はcategoryで削除
                    if region and region != '':
                        cursor.execute(f"DELETE FROM {table_name} WHERE category = %s", (region,))
                    else:
                        # regionが空の場合は全データを削除
                        cursor.execute(f"DELETE FROM {table_name}")
                else:
                    delete_column = delete_column_map.get(cache_key, 'region')
                    if delete_column and region is not None:
                        cursor.execute(f"DELETE FROM {table_name} WHERE {delete_column} = %s", (region,))
                    else:
                        cursor.execute(f"DELETE FROM {table_name}")
                
                # 新しいデータを挿入
                for item in data:
                    if cache_key == 'google_trends':
                        cursor.execute(
                            "INSERT INTO google_trends_cache (keyword, score, region) VALUES (%s, %s, %s)",
                            (item.get('keyword', ''), item.get('score', 0), region)
                        )
                    elif cache_key == 'youtube_trends':
                        cursor.execute(
                            "INSERT INTO youtube_trends_cache (region_code, trend_type, video_id, title, channel_title, view_count, like_count, comment_count, published_at, thumbnail_url, rank, region) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (region, item.get('trend_type', 'trending'), item.get('video_id', ''), item.get('title', ''), item.get('channel_title', ''), item.get('view_count', 0), item.get('like_count', 0), item.get('comment_count', 0), item.get('published_at') or None, item.get('thumbnail_url', ''), item.get('rank', 0), region)
                        )
                    elif cache_key == 'music_trends':
                        cursor.execute(
                            "INSERT INTO music_trends_cache (service, region_code, title, artist, album, play_count, popularity, spotify_url, rank, track_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (item.get('service', 'spotify'), region, item.get('title', ''), item.get('artist', ''), item.get('album', ''), item.get('play_count', 0), item.get('popularity', 0), item.get('spotify_url', ''), item.get('rank', 0), item.get('track_id', ''))
                        )
                    elif cache_key == 'podcast_trends':
                        # podcast_idはitemのidまたはpodcast_idまたはlistennotes_urlから抽出
                        podcast_id = item.get('id', '') or item.get('podcast_id', '')
                        if not podcast_id and item.get('listennotes_url'):
                            # listennotes_urlからIDを抽出: https://www.listennotes.com/c/{id}/
                            url_parts = item.get('listennotes_url', '').rstrip('/').split('/')
                            podcast_id = url_parts[-1] if url_parts else ''
                        # podcast_idが空の場合は、タイトルとpublisherから生成（フォールバック）
                        if not podcast_id:
                            podcast_id = f"{item.get('title', '')[:50]}_{item.get('publisher', '')[:30]}".replace(' ', '_')[:100]
                        cursor.execute(
                            "INSERT INTO podcast_trends_cache (podcast_id, cache_key, region_code, title, description, publisher, url, image_url, language, country, score, rank, trend_type, region) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (podcast_id, cache_key, region, item.get('title', ''), item.get('description', ''), item.get('publisher', ''), item.get('url', ''), item.get('image_url', ''), item.get('language', ''), item.get('country', ''), item.get('score', 0), item.get('rank', 0), item.get('trend_type', ''), region)
                        )
                    elif cache_key == 'news_trends':
                        cursor.execute(
                            "INSERT INTO news_trends_cache (article_id, title, source, published_at, category, country) VALUES (%s, %s, %s, %s, %s, %s)",
                            (item.get('article_id', ''), item.get('title', ''), item.get('source', ''), item.get('published_at', ''), item.get('category', ''), item.get('country', ''))
                        )
                    elif cache_key == 'worldnews_trends':
                        cursor.execute(
                            "INSERT INTO worldnews_trends_cache (article_id, title, source, published_at, category, country, url, description, image_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                item.get('article_id', ''),
                                item.get('title', ''),
                                item.get('source', ''),
                                item.get('published_at') or None,
                                item.get('category', ''),
                                item.get('country', ''),
                                item.get('url', ''),
                                item.get('description', ''),
                                item.get('image_url', '')
                            )
                        )
                    elif cache_key == 'rakuten_trends':
                        # rakuten_trendsの場合、genre_idカラムにはリクエスト時のgenre_id（regionパラメータ）を保存
                        # 各アイテムのgenreIdではなく、リクエスト時のgenre_idを使用
                        # item_idはitemCodeから取得（例: 'alpen:10499596'）
                        item_id = item.get('item_id', '') or item.get('itemCode', '')
                        if not item_id:
                            # item_idが取得できない場合は、URLから生成するか、スキップする
                            logger.warning(f"⚠️ Rakuten: item_idが取得できませんでした。item keys: {list(item.keys())}")
                            continue
                        # デバッグ: 最初のアイテムのみログ出力
                        if data.index(item) == 0:
                            logger.debug(f"🔍 Rakuten: item_id={item_id}, genre_id={region}, title={item.get('title', '')[:30]}")
                        cursor.execute(
                            "INSERT INTO rakuten_trends_cache (item_id, genre_id, title, price, category, review_count, review_average, image_url, url, shop_name, sales_rank, sales_count, rank, region) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (item_id, region, item.get('title', ''), item.get('price', 0), region or 'all', item.get('review_count', 0), item.get('review_average', 0.0), item.get('image_url', ''), item.get('url', ''), item.get('shop_name', ''), item.get('sales_rank', ''), item.get('sales_count', ''), item.get('rank', 0), region)
                        )
                    elif cache_key == 'hatena_trends':
                        cursor.execute(
                            "INSERT INTO hatena_trends_cache (category, title, url, description, bookmark_count, published, author, rank, region, entry_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (item.get('category', ''), item.get('title', ''), item.get('url', ''), item.get('description', ''), item.get('bookmark_count', 0), item.get('published', ''), item.get('author', ''), item.get('rank', 0), region, item.get('entry_id', ''))
                        )
                    elif cache_key == 'twitch_trends':
                        cursor.execute(
                            "INSERT INTO twitch_trends_cache (category, title, game_name, viewer_count, view_count, user_name, creator_name, thumbnail_url, url, rank, box_art_url, game_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (region, item.get('title', ''), item.get('game_name', '') or item.get('name', ''), item.get('viewer_count', 0), item.get('view_count', 0), item.get('user_name', ''), item.get('creator_name', ''), item.get('thumbnail_url', ''), item.get('url', ''), item.get('rank', 0), item.get('box_art_url', ''), item.get('id', '') or item.get('game_id', ''))
                        )
                
                # キャッシュステータスを更新
                cursor.execute(
                    "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                    (cache_key, datetime.now(), len(data), datetime.now(), len(data))
                )
                
                conn.commit()
                logger.info(f"✅ {cache_key}のキャッシュを更新しました ({len(data)}件)")
                # 接続を閉じる（毎回新規接続を作成するため）
                try:
                    if conn and not conn.closed:
                        conn.close()
                except:
                    pass
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            # 接続エラーの場合
            logger.warning(f"⚠️ キャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            # ロールバックを試みる（接続が有効な場合のみ）
            try:
                if conn and not conn.closed:
                    conn.rollback()
                    conn.close()
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"❌ キャッシュ保存エラー: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            # ロールバックを試みる（接続が有効な場合のみ）
            try:
                if conn and not conn.closed:
                    conn.rollback()
                    conn.close()
            except:
                pass
            return False
    
    def get_from_cache(self, cache_key, region='JP'):
        """キャッシュからデータを取得"""
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                logger.error("❌ キャッシュ取得エラー: データベース接続を取得できませんでした")
                return None
        except Exception as e:
            logger.error(f"❌ キャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                table_name = f"{cache_key}_cache"
                
                # hatena_trendsとtwitch_trendsの場合はcategoryでフィルタリング
                if cache_key == 'hatena_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE category = %s ORDER BY rank ASC, created_at DESC", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC")
                elif cache_key == 'twitch_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE category = %s ORDER BY rank ASC, created_at DESC", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC")
                # rakuten_trendsの場合はgenre_idでフィルタリング（regionパラメータがgenre_idとして渡される）
                elif cache_key == 'rakuten_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE genre_id = %s ORDER BY rank ASC, created_at DESC", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC")
                # regionが空の場合はregion条件を除外
                elif region and region != '':
                    cursor.execute(f"SELECT * FROM {table_name} WHERE region = %s ORDER BY created_at DESC", (region,))
                else:
                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY created_at DESC")
                
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            # 接続エラーの場合は再接続を試みる
            logger.warning(f"⚠️ キャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            try:
                # 接続をリセットして次回の操作で再接続されるようにする
                self.connection = None
                return None
            except Exception as retry_error:
                logger.error(f"❌ 再接続試行エラー: {retry_error}", exc_info=True)
                return None
        except Exception as e:
            logger.error(f"❌ キャッシュ取得エラー: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return None
    
    def is_cache_valid(self, cache_key, region='JP', hours=24):
        """キャッシュが有効かどうかを確認"""
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.warning(f"⚠️ キャッシュ有効性チェック: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
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
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            # 接続エラーの場合は再接続を試みる
            logger.warning(f"⚠️ キャッシュ有効性チェック中に接続エラーが発生: {e}", exc_info=True)
            try:
                # 接続をリセットして次回の操作で再接続されるようにする
                self.connection = None
                return False
            except Exception as retry_error:
                logger.error(f"❌ 再接続試行エラー: {retry_error}", exc_info=True)
                return False
        except Exception as e:
            logger.error(f"❌ キャッシュ有効性確認エラー: {e}", exc_info=True)
            return False
    
    def clear_cache(self, cache_key, region='JP'):
        """キャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ キャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                table_name = f"{cache_key}_cache"
                cursor.execute(f"DELETE FROM {table_name} WHERE region = %s", (region,))
                conn.commit()
                logger.info(f"✅ {cache_key}のキャッシュをクリアしました")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ キャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    def get_connection(self):
        """データベース接続を取得（接続されていない場合は再接続を試みる）

        ロックを使用して、複数のマネージャーからの同時アクセスを防ぐ
        ロックの範囲を最小限にして、クエリ実行時のブロッキングを防ぐ
        """
        import time
        global _connection_lock

        max_retries = 3  # リトライ回数を3に増加（並列リクエスト時の接続確立を考慮）
        retry_delay = 0.5  # 待機時間を0.5秒に設定（接続確立の余裕を持たせる）

        # 接続が既に存在し、閉じられていない場合は即座に返す（ロック不要、SELECT 1チェックも省略）
        # 接続が無効な場合は、クエリ実行時にエラーが発生するので、その時点で再接続する
        if self.connection and not self.connection.closed:
            return self.connection

        # ロックを取得して、同時アクセスを防ぐ（再接続時のみ）
        with _connection_lock:
            # ロック取得後、再度チェック（他のスレッドが既に接続を確立した可能性がある）
            if self.connection and not self.connection.closed:
                return self.connection

            for attempt in range(max_retries):
                try:
                    # 接続が存在しない、または閉じられている場合は再接続
                    if not self.connection:
                        self.connect()
                    else:
                        try:
                            # 接続が閉じられているか確認
                            if self.connection.closed:
                                self.connect()
                            # 接続が有効かどうかは、実際のクエリ実行時にエラーが発生したら再接続する
                            # SELECT 1による事前確認は削除（ブロッキングの原因となるため）
                        except (psycopg2.InterfaceError, psycopg2.OperationalError, AttributeError) as e:
                            # 接続エラーの場合は再接続
                            logger.warning(f"⚠️ データベース接続エラー検出、再接続します: {e}")
                            self.connect()
                    
                    # 接続が確立されたか確認（SELECT 1による確認は削除）
                    if self.connection and not self.connection.closed:
                        # 接続が有効かどうかは、実際のクエリ実行時にエラーが発生したら再接続する
                        # 事前確認を削除することで、ブロッキングを防ぐ
                        return self.connection
                except Exception as e:
                    # 予期しないエラーの場合も再試行
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ データベース接続取得エラー: {e} - {retry_delay}秒後に再試行します")
                        time.sleep(retry_delay)
                        self.connection = None
                        continue
                    else:
                        logger.error(f"❌ データベース接続取得エラー（最大試行回数）: {e}")
            
            # 全ての再試行が失敗した場合
            error_msg = "データベース接続を確立できませんでした（最大試行回数に達しました）"
            logger.error(f"❌ {error_msg}")
            raise psycopg2.OperationalError(error_msg)
    
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
    def save_youtube_trends_to_cache(self, data, region='JP', trend_type='trending'):
        """YouTube Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        # trend_typeを各itemに追加（辞書の場合のみ）
        if isinstance(data, list) and isinstance(data[0], dict):
            for item in data:
                if not item.get('trend_type'):
                    item['trend_type'] = trend_type
        
        # 既存環境ではyoutube_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    # INSERT文で使用しているカラムを確認して追加
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS trend_type VARCHAR(50) DEFAULT 'trending'")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS video_id VARCHAR(255)")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS like_count INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS comment_count INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS published_at TIMESTAMP")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS thumbnail_url TEXT")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS region VARCHAR(10)")
                    cursor.execute("ALTER TABLE youtube_trends_cache ADD COLUMN IF NOT EXISTS description TEXT")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ youtube_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
        return self.save_to_cache(data, 'youtube_trends', region)
    
    def get_youtube_trends_from_cache(self, region='JP', trend_type='trending'):
        """YouTube Trendsデータをキャッシュから取得"""
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ YouTubeキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM youtube_trends_cache WHERE region = %s AND trend_type = %s ORDER BY created_at DESC",
                    (region, trend_type)
                )
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ YouTubeキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ YouTubeキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_youtube_trends_cache(self, region='JP'):
        """YouTube Trendsキャッシュをクリア"""
        return self.clear_cache('youtube_trends', region)
    
    def is_youtube_cache_valid(self, region='JP'):
        """YouTube Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('youtube_trends', region, 6)
    
    # Music Trends キャッシュメソッド
    def save_music_trends_to_cache(self, data, service='spotify', region='JP'):
        """Music Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        # 既存環境ではmusic_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    # INSERT文で使用しているカラムを確認して追加
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS album TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS spotify_url TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS track_id VARCHAR(255)")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ music_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ music_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM music_trends_cache 
                    WHERE service = %s AND region_code = %s
                """, (service, region))
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO music_trends_cache 
                        (title, artist, album, play_count, popularity, spotify_url, rank, 
                         service, region_code, created_at, track_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('artist', ''),
                        item.get('album', ''),
                        item.get('play_count', 0),
                        item.get('popularity', 0),
                        item.get('spotify_url', ''),
                        item.get('rank', 0),
                        service,
                        region,
                        item.get('created_at'),
                        item.get('track_id', '')
                    ))
                
                conn.commit()
                logger.info(f"✅ music_trendsキャッシュを保存しました (service: {service}, region: {region}, {len(data)}件)")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ music_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ music_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_music_trends_from_cache(self, service='spotify', region='JP'):
        """Music Trendsデータをキャッシュから取得"""
        # 既存環境ではmusic_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    # INSERT文で使用しているカラムを確認して追加
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS album TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS spotify_url TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS track_id VARCHAR(255)")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ music_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Music Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, artist, album, play_count, popularity, spotify_url, rank, 
                           service, region_code, created_at, track_id
                    FROM music_trends_cache 
                    WHERE service = %s AND region_code = %s
                    ORDER BY rank
                """, (service, region))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Music Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Music Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_music_trends_cache(self, service='spotify', region='JP'):
        """Music Trendsキャッシュをクリア"""
        # 既存環境ではmusic_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    # INSERT文で使用しているカラムを確認して追加
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS album TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS spotify_url TEXT")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                    cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS track_id VARCHAR(255)")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ music_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ music_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM music_trends_cache 
                    WHERE service = %s AND region_code = %s
                """, (service, region))
                conn.commit()
                logger.info(f"✅ music_trendsのキャッシュをクリアしました (service: {service}, region: {region})")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ music_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ music_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def is_music_cache_valid(self, service='spotify'):
        """Music Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('music_trends', service, 12)
    
    # Podcast Trends キャッシュメソッド
    def save_podcast_trends_to_cache(self, data, cache_key='podcast_trends', region='JP'):
        """Podcast Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        # 既存環境ではpodcast_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    # INSERT文で使用しているカラムを確認して追加
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS cache_key VARCHAR(255)")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS description TEXT")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS url TEXT")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS image_url TEXT")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS language VARCHAR(10)")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS country VARCHAR(100)")
                    # countryカラムが既に存在する場合は長さを拡張
                    try:
                        cursor.execute("ALTER TABLE podcast_trends_cache ALTER COLUMN country TYPE VARCHAR(100)")
                    except Exception:
                        pass  # 既にVARCHAR(100)の場合はエラーを無視
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS score INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS trend_type VARCHAR(50)")
                    cursor.execute("ALTER TABLE podcast_trends_cache ADD COLUMN IF NOT EXISTS region VARCHAR(10)")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ podcast_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
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
        if not data:
            return False
        
        # 既存環境ではnews_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS article_id VARCHAR(255)")
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS title TEXT")
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS source VARCHAR(255)")
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS published_at TIMESTAMP")
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS category VARCHAR(50)")
                    cursor.execute("ALTER TABLE news_trends_cache ADD COLUMN IF NOT EXISTS country VARCHAR(10)")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ news_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
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
        if not data:
            return False
        try:
            conn = self.get_connection()
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("ALTER TABLE worldnews_trends_cache ADD COLUMN IF NOT EXISTS url TEXT")
                    cursor.execute("ALTER TABLE worldnews_trends_cache ADD COLUMN IF NOT EXISTS description TEXT")
                    cursor.execute("ALTER TABLE worldnews_trends_cache ADD COLUMN IF NOT EXISTS image_url TEXT")
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ worldnews_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        return self.save_to_cache(data, cache_key, country)
    
    def get_worldnews_trends_from_cache(self, category='general', country='JP'):
        """World News Trendsデータをキャッシュから取得"""
        # 接続を取得（有効性チェックと再接続を自動で行う）
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"World News キャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # World News専用のクエリ（countryカラムで検索）
                cursor.execute("SELECT * FROM worldnews_trends_cache WHERE country = %s ORDER BY created_at DESC", (country.lower(),))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ World News キャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"World News キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_worldnews_trends_cache(self, category='general', country='JP'):
        """World News Trendsキャッシュをクリア"""
        return self.clear_cache('worldnews_trends', country)
    
    def is_worldnews_cache_valid(self, category='general', country='JP'):
        """World News Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('worldnews_trends', country, 24)
    
    # Rakuten Trends キャッシュメソッド
    def save_rakuten_trends_to_cache(self, data, category='all'):
        """Rakuten Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        # 既存環境ではrakuten_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        # スキーマ更新は別トランザクションで実行（エラーが発生してもメイン処理に影響しないように）
        try:
            schema_conn = self.get_connection()
            if schema_conn:
                try:
                    with schema_conn.cursor() as cursor:
                        # INSERT文で使用しているカラムを確認して追加
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS genre_id VARCHAR(255)")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS review_average FLOAT DEFAULT 0.0")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS image_url TEXT")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS url TEXT")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS shop_name VARCHAR(255)")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS sales_rank VARCHAR(255)")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS sales_count VARCHAR(255)")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                        cursor.execute("ALTER TABLE rakuten_trends_cache ADD COLUMN IF NOT EXISTS region VARCHAR(10) DEFAULT 'JP'")
                    schema_conn.commit()
                except Exception as schema_error:
                    logger.warning(f"⚠️ rakuten_trends_cacheのスキーマ更新に失敗しました: {schema_error}", exc_info=True)
                    schema_conn.rollback()
                finally:
                    if schema_conn and not schema_conn.closed:
                        schema_conn.close()
        except Exception as e:
            logger.warning(f"⚠️ rakuten_trends_cacheのスキーマ更新用接続取得に失敗しました: {e}", exc_info=True)
        
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
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ キャッシュ情報取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor() as cursor:
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
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ キャッシュ情報取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ キャッシュ情報取得エラー: {e}", exc_info=True)
            return None
    
    def get_all_cache_status(self):
        """全キャッシュの状態を取得"""
        try:
            conn = self.get_connection()
            if not conn:
                # データベース接続が取得できない場合は空の状態を返す
                logger.warning("⚠️ データベース接続が取得できないため、空のキャッシュ状態を返します")
                return {}
            if not conn:
                return {}
        except Exception as e:
            logger.error(f"❌ 全キャッシュ状態取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return {}
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT cache_key, last_updated, data_count FROM cache_status")
                results = cursor.fetchall()
                
                status = {}
                for row in results:
                    status[row[0]] = {
                        'last_updated': row[1],
                        'data_count': row[2]
                    }
                return status
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 全キャッシュ状態取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return {}
        except Exception as e:
            logger.error(f"❌ 全キャッシュ状態取得エラー: {e}", exc_info=True)
            return {}
    
    def get_last_update_time(self):
        """最後の更新時刻を取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ 最終更新時刻取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(last_updated) FROM cache_status")
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 最終更新時刻取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ 最終更新時刻取得エラー: {e}", exc_info=True)
            return None
    
    def clear_all_cache(self):
        """全キャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ 全キャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
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
                
                conn.commit()
                logger.info("✅ 全キャッシュをクリアしました")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 全キャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ 全キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    def delete_old_cache_data(self, days=2):
        """古いキャッシュデータを削除（指定日数以上経過したデータ）
        
        Args:
            days: 削除対象となる日数（デフォルト: 2日）
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ 古いキャッシュデータ削除エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with conn.cursor() as cursor:
                deleted_counts = {}
                
                # 各キャッシュテーブルから古いデータを削除
                cache_tables = [
                    'google_trends_cache',
                    'youtube_trends_cache',
                    'music_trends_cache',
                    'podcast_trends_cache',
                    'news_trends_cache',
                    'worldnews_trends_cache',
                    'rakuten_trends_cache',
                    'hatena_trends_cache',
                    'twitch_trends_cache',
                    'reddit_trends_cache',
                    'hackernews_trends_cache',
                    'qiita_trends_cache',
                    'nhk_trends_cache',
                    'cnn_trends_cache',
                    'producthunt_trends_cache'
                ]
                
                for table in cache_tables:
                    try:
                        # テーブルに存在する日時カラムを確認して削除
                        # まずcreated_atを試し、なければcached_atを使用
                        cursor.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = %s 
                            AND column_name IN ('created_at', 'cached_at')
                        """, (table,))
                        date_columns = [row[0] for row in cursor.fetchall()]
                        
                        if date_columns:
                            # 存在するカラムで削除
                            where_clause = ' OR '.join([f"{col} < %s" for col in date_columns])
                            params = [cutoff_date] * len(date_columns)
                            cursor.execute(f"DELETE FROM {table} WHERE {where_clause}", params)
                            count = cursor.rowcount
                            if count > 0:
                                deleted_counts[table] = count
                        else:
                            logger.debug(f"⚠️ {table}: 日時カラムが見つかりませんでした")
                    except Exception as e:
                        # エラーが発生した場合はスキップ（テーブルが存在しない場合など）
                        logger.debug(f"⚠️ {table}の古いデータ削除をスキップ: {e}")
                
                conn.commit()
                
                total_deleted = sum(deleted_counts.values())
                if total_deleted > 0:
                    logger.info(f"✅ 古いキャッシュデータを削除しました: 合計{total_deleted}件")
                    for table, count in deleted_counts.items():
                        logger.info(f"   - {table}: {count}件")
                else:
                    logger.debug(f"📊 削除対象の古いキャッシュデータはありませんでした")
                
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 古いキャッシュデータ削除中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ 古いキャッシュデータ削除エラー: {e}", exc_info=True)
            return False
    
    def clear_cache_by_type(self, cache_type):
        """特定のキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ {cache_type}キャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                table_name = f"{cache_type}_cache"
                cursor.execute(f"DELETE FROM {table_name}")
                cursor.execute("DELETE FROM cache_status WHERE cache_key = %s", (cache_type,))
                conn.commit()
                logger.info(f"✅ {cache_type}キャッシュをクリアしました")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ {cache_type}キャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ {cache_type}キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    # Reddit Trends キャッシュメソッド
    def save_reddit_trends_to_cache(self, data, subreddit='all'):
        """Reddit Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ reddit_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM reddit_trends_cache 
                    WHERE subreddit = %s
                """, (subreddit,))
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO reddit_trends_cache 
                        (post_id, title, url, subreddit, author, score, upvote_ratio, 
                         num_comments, permalink, is_video, domain, rank, region)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('post_id', ''),
                        item.get('title', ''),
                        item.get('url', ''),
                        subreddit,
                        item.get('author', ''),
                        item.get('score', 0),
                        item.get('upvote_ratio', 0.0),
                        item.get('num_comments', 0),
                        item.get('permalink', ''),
                        item.get('is_video', False),
                        item.get('domain', ''),
                        item.get('rank', 0),
                        subreddit
                    ))
                
                conn.commit()
                logger.info(f"✅ reddit_trendsキャッシュを保存しました (subreddit: {subreddit}, {len(data)}件)")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ reddit_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ reddit_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_reddit_trends_from_cache(self, subreddit='all'):
        """Reddit Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Reddit Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT post_id, title, url, subreddit, author, score, upvote_ratio,
                           num_comments, permalink, is_video, domain, rank, created_at
                    FROM reddit_trends_cache 
                    WHERE subreddit = %s 
                    ORDER BY rank
                """, (subreddit,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Reddit Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Reddit Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_reddit_trends_cache(self, subreddit='all'):
        """Reddit Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ reddit_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM reddit_trends_cache 
                    WHERE subreddit = %s
                """, (subreddit,))
                conn.commit()
                logger.info(f"✅ reddit_trendsのキャッシュをクリアしました (subreddit: {subreddit})")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ reddit_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ reddit_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # Hacker News Trends キャッシュメソッド
    def save_hackernews_trends_to_cache(self, data, story_type='top'):
        """Hacker News Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ hackernews_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM hackernews_trends_cache 
                    WHERE story_type = %s
                """, (story_type,))
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO hackernews_trends_cache 
                        (story_id, title, url, score, author, story_time, comments, story_type, rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('story_id', 0),
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('score', 0),
                        item.get('by', ''),
                        item.get('time', 0),
                        item.get('comments', 0),
                        story_type,
                        item.get('rank', 0)
                    ))
                
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, ('hackernews_trends', now, len(data)))
                
                conn.commit()
                logger.info(f"✅ hackernews_trendsキャッシュを保存しました (type: {story_type}, {len(data)}件)")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ hackernews_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ hackernews_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_hackernews_trends_from_cache(self, story_type='top'):
        """Hacker News Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Hacker News Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT story_id, title, url, score, author, story_time, 
                           comments, story_type, rank, created_at
                    FROM hackernews_trends_cache 
                    WHERE story_type = %s 
                    ORDER BY rank
                """, (story_type,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Hacker News Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Hacker News Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_hackernews_trends_cache(self, story_type='top'):
        """Hacker News Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ hackernews_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM hackernews_trends_cache 
                    WHERE story_type = %s
                """, (story_type,))
                conn.commit()
                logger.info(f"✅ hackernews_trendsのキャッシュをクリアしました (type: {story_type})")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ hackernews_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ hackernews_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # Qiita Trends キャッシュメソッド
    def save_qiita_trends_to_cache(self, data):
        """Qiita Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ qiita_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM qiita_trends_cache
                """)
                
                # 新しいデータを挿入
                for item in data:
                    # タグをJSON文字列に変換
                    tags_json = json.dumps(item.get('tags', []), ensure_ascii=False)
                    
                    cursor.execute("""
                        INSERT INTO qiita_trends_cache 
                        (item_id, title, url, user_id, user_name, likes_count, stocks_count,
                         comments_count, created_at, updated_at, tags, rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('item_id', ''),
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('user_id', ''),
                        item.get('user_name', ''),
                        item.get('likes_count', 0),
                        item.get('stocks_count', 0),
                        item.get('comments_count', 0),
                        item.get('created_at', ''),
                        item.get('updated_at', ''),
                        tags_json,
                        item.get('rank', 0)
                    ))
                
                # キャッシュステータスを更新
                cursor.execute(
                    "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                    ('qiita_trends', datetime.now(), len(data), datetime.now(), len(data))
                )
                
                conn.commit()
                logger.info(f"✅ qiita_trendsキャッシュを保存しました ({len(data)}件)")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ qiita_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ qiita_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_qiita_trends_from_cache(self):
        """Qiita Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Qiita Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT item_id, title, url, user_id, user_name, likes_count, stocks_count,
                           comments_count, created_at, updated_at, tags, rank, cached_at
                    FROM qiita_trends_cache 
                    ORDER BY rank
                """)
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    item = dict(row)
                    # タグをJSONからリストに変換
                    if item.get('tags'):
                        try:
                            item['tags'] = json.loads(item['tags'])
                        except:
                            item['tags'] = []
                    result.append(item)
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Qiita Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Qiita Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_qiita_trends_cache(self):
        """Qiita Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ qiita_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM qiita_trends_cache
                """)
                conn.commit()
                logger.info(f"✅ qiita_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ qiita_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ qiita_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # NHK Trends キャッシュメソッド
    def save_nhk_trends_to_cache(self, data):
        """NHK Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ nhk_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM nhk_trends_cache")
                for item in data:
                    cursor.execute("""
                        INSERT INTO nhk_trends_cache 
                        (title, url, published_date, description, rank)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('rank', 0)
                    ))
                
                # キャッシュステータスを更新
                cursor.execute(
                    "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                    ('nhk_trends', datetime.now(), len(data), datetime.now(), len(data))
                )
                
                conn.commit()
                logger.info(f"✅ nhk_trendsキャッシュを保存しました ({len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ nhk_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ nhk_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_nhk_trends_from_cache(self):
        """NHK Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ NHK Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, rank, cached_at
                    FROM nhk_trends_cache 
                    ORDER BY rank
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    # published_dateをISO形式の文字列に変換
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    result.append(row_dict)
                return result
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ NHK Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ NHK Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None

    def clear_nhk_trends_cache(self):
        """NHK Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ nhk_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM nhk_trends_cache")
                conn.commit()
                logger.info(f"✅ nhk_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ nhk_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ nhk_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # CNN Trends キャッシュメソッド
    def save_cnn_trends_to_cache(self, data):
        """CNN Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ cnn_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cnn_trends_cache")
                for item in data:
                    cursor.execute("""
                        INSERT INTO cnn_trends_cache 
                        (title, url, published_date, description, rank)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('rank', 0)
                    ))
                
                # キャッシュステータスを更新
                cursor.execute(
                    "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                    ('cnn_trends', datetime.now(), len(data), datetime.now(), len(data))
                )
                
                conn.commit()
                logger.info(f"✅ cnn_trendsキャッシュを保存しました ({len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ cnn_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ cnn_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_cnn_trends_from_cache(self):
        """CNN Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ CNN Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, rank, cached_at
                    FROM cnn_trends_cache 
                    ORDER BY rank
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    # published_dateをISO形式の文字列に変換
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    result.append(row_dict)
                return result
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ CNN Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ CNN Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None

    def clear_cnn_trends_cache(self):
        """CNN Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ cnn_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cnn_trends_cache")
                conn.commit()
                logger.info(f"✅ cnn_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ cnn_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ cnn_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # Product Hunt Trends キャッシュメソッド
    def save_producthunt_trends_to_cache(self, data):
        """Product Hunt Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ producthunt_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM producthunt_trends_cache
                """)
                
                # 新しいデータを挿入
                for item in data:
                    # トピックをJSON文字列に変換
                    topics_json = json.dumps(item.get('topics', []), ensure_ascii=False)
                    
                    cursor.execute("""
                        INSERT INTO producthunt_trends_cache 
                        (product_id, name, tagline, description, url, website, votes_count, comments_count,
                         created_at, topics, user_name, user_username, rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('product_id', ''),
                        item.get('name', ''),
                        item.get('tagline', ''),
                        item.get('description', ''),
                        item.get('url', ''),
                        item.get('website', ''),
                        item.get('votes_count', 0),
                        item.get('comments_count', 0),
                        item.get('created_at', ''),
                        topics_json,
                        item.get('user_name', ''),
                        item.get('user_username', ''),
                        item.get('rank', 0)
                    ))
                
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, ('producthunt_trends', now, len(data)))
                
                conn.commit()
                logger.info(f"✅ producthunt_trendsキャッシュを保存しました ({len(data)}件)")
                return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ producthunt_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ producthunt_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_producthunt_trends_from_cache(self):
        """Product Hunt Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Product Hunt Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT product_id, name, tagline, description, url, website, votes_count, comments_count,
                           created_at, topics, user_name, user_username, rank, cached_at
                    FROM producthunt_trends_cache 
                    ORDER BY rank
                """)
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    item = dict(row)
                    # トピックをJSONからリストに変換
                    if item.get('topics'):
                        try:
                            item['topics'] = json.loads(item['topics'])
                        except:
                            item['topics'] = []
                    result.append(item)
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Product Hunt Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Product Hunt Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_producthunt_trends_cache(self):
        """Product Hunt Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ producthunt_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM producthunt_trends_cache
                """)
                conn.commit()
                logger.info(f"✅ producthunt_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ producthunt_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ producthunt_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # Stock Trends キャッシュメソッド
    def save_stock_trends_to_cache(self, data, market='US'):
        """Stock Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ stock_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("""
                    DELETE FROM stock_trends_cache 
                    WHERE market = %s
                """, (market,))
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO stock_trends_cache
                        (symbol, name, current_price, previous_price, change, change_percent,
                         volume, market_cap, market, rank, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('symbol', ''),
                        item.get('name', ''),
                        item.get('current_price', 0),
                        item.get('previous_price', 0),
                        item.get('change', 0),
                        item.get('change_percent', 0),
                        item.get('volume', 0),
                        item.get('market_cap', 0),
                        market,
                        item.get('rank', 0),
                        item.get('updated_at')
                    ))
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, ('stock_trends', now, len(data)))
                
                conn.commit()
                logger.info(f"✅ stock_trendsのキャッシュを保存しました (market: {market}, {len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ stock_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ stock_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_stock_trends_from_cache(self, market='US'):
        """Stock Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Stock Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT symbol, name, current_price, previous_price, change, change_percent,
                           volume, market_cap, market, rank, updated_at, cached_at
                    FROM stock_trends_cache 
                    WHERE market = %s 
                    ORDER BY rank
                """, (market,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Stock Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Stock Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_stock_trends_cache(self, market='US'):
        """Stock Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ stock_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM stock_trends_cache 
                    WHERE market = %s
                """, (market,))
                conn.commit()
                logger.info(f"✅ stock_trendsのキャッシュをクリアしました (market: {market})")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ stock_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ stock_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    # Crypto Trends キャッシュメソッド
    def save_crypto_trends_to_cache(self, data):
        """Crypto Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ crypto_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("DELETE FROM crypto_trends_cache")
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO crypto_trends_cache
                        (coin_id, symbol, name, market_cap_rank, search_score,
                         current_price, price_change_24h, price_change_percentage_24h,
                         market_cap, volume_24h, image_url, rank, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('coin_id', ''),
                        item.get('symbol', ''),
                        item.get('name', ''),
                        item.get('market_cap_rank', 0),
                        item.get('search_score', 0),
                        item.get('current_price', 0),
                        item.get('price_change_24h', 0),
                        item.get('price_change_percentage_24h', 0),
                        item.get('market_cap', 0),
                        item.get('volume_24h', 0),
                        item.get('image_url', ''),
                        item.get('rank', 0),
                        item.get('updated_at')
                    ))
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, ('crypto_trends', now, len(data)))
                
                conn.commit()
                logger.info(f"✅ crypto_trendsのキャッシュを保存しました ({len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ crypto_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ crypto_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_crypto_trends_from_cache(self):
        """Crypto Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Crypto Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT coin_id, symbol, name, market_cap_rank, search_score,
                           current_price, price_change_24h, price_change_percentage_24h,
                           market_cap, volume_24h, image_url, rank, updated_at, cached_at
                    FROM crypto_trends_cache 
                    ORDER BY rank
                """)
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Crypto Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Crypto Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_crypto_trends_cache(self):
        """Crypto Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ crypto_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM crypto_trends_cache")
                conn.commit()
                logger.info(f"✅ crypto_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ crypto_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ crypto_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def save_movie_trends_to_cache(self, data, country='JP'):
        """Movie Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ movie_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除（国別）
                cursor.execute("DELETE FROM movie_trends_cache WHERE country = %s", (country,))
                
                # 新しいデータを挿入
                for item in data:
                    cursor.execute("""
                        INSERT INTO movie_trends_cache
                        (country, movie_id, title, original_title, overview, popularity,
                         vote_average, vote_count, release_date, poster_path,
                         backdrop_path, poster_url, backdrop_url, rank, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        country,
                        item.get('id', 0),
                        item.get('title', ''),
                        item.get('original_title', ''),
                        item.get('overview', ''),
                        item.get('popularity', 0),
                        item.get('vote_average', 0),
                        item.get('vote_count', 0),
                        item.get('release_date', ''),
                        item.get('poster_path', ''),
                        item.get('backdrop_path', ''),
                        item.get('poster_url', ''),
                        item.get('backdrop_url', ''),
                        item.get('rank', 0),
                        item.get('updated_at')
                    ))
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cache_key = f'movie_trends_{country}'
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, (cache_key, now, len(data)))
                
                conn.commit()
                logger.info(f"✅ movie_trendsのキャッシュを保存しました (country: {country}, {len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ movie_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ movie_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_movie_trends_from_cache(self, country='JP'):
        """Movie Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Movie Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT country, movie_id, title, original_title, overview, popularity,
                           vote_average, vote_count, release_date, poster_path,
                           backdrop_path, poster_url, backdrop_url, rank, updated_at, cached_at
                    FROM movie_trends_cache 
                    WHERE country = %s
                    ORDER BY rank
                """, (country,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Movie Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Movie Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_movie_trends_cache(self, country='JP'):
        """Movie Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ movie_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM movie_trends_cache WHERE country = %s", (country,))
                conn.commit()
                logger.info(f"✅ movie_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ movie_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ movie_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def save_book_trends_to_cache(self, data, country='JP'):
        """Book Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ book_trendsキャッシュ保存エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                # 既存のデータを削除（国別）
                cursor.execute("DELETE FROM book_trends_cache WHERE country = %s", (country,))
                
                # 新しいデータを挿入
                for item in data:
                    # 配列や辞書をJSON文字列に変換
                    authors = item.get('authors', [])
                    authors_str = json.dumps(authors, ensure_ascii=False) if isinstance(authors, list) else str(authors)
                    categories = item.get('categories', [])
                    categories_str = json.dumps(categories, ensure_ascii=False) if isinstance(categories, list) else str(categories)
                    
                    # updated_atの処理
                    updated_at = item.get('updated_at')
                    if not updated_at:
                        from datetime import timezone
                        updated_at = datetime.now(timezone.utc)
                    
                    # パラメータの準備
                    params = (
                        country,
                        item.get('id', ''),
                        item.get('isbn', ''),
                        item.get('title', ''),
                        item.get('subtitle', ''),
                        item.get('author', ''),
                        authors_str,
                        item.get('publisher', ''),
                        item.get('price', 0),
                        item.get('sales', 0),
                        item.get('published_date', ''),
                        item.get('release_date', ''),
                        item.get('description', ''),
                        item.get('page_count', 0),
                        categories_str,
                        item.get('average_rating', 0),
                        item.get('ratings_count', 0),
                        item.get('language', ''),
                        item.get('item_url', ''),
                        item.get('affiliate_url', ''),
                        item.get('preview_link', ''),
                        item.get('info_link', ''),
                        item.get('buy_link', ''),
                        item.get('image_url', ''),
                        item.get('thumbnail', ''),
                        item.get('small_thumbnail', ''),
                        item.get('medium', ''),
                        item.get('large', ''),
                        item.get('rank', 0),
                        updated_at
                    )
                    
                    cursor.execute("""
                        INSERT INTO book_trends_cache
                        (country, book_id, isbn, title, subtitle, author, authors, publisher,
                         price, sales, published_date, release_date, description, page_count,
                         categories, average_rating, ratings_count, language, item_url,
                         affiliate_url, preview_link, info_link, buy_link, image_url,
                         thumbnail, small_thumbnail, medium, large, rank, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, params)
                # cache_statusテーブルを更新
                from datetime import datetime
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, (f'book_trends_{country}', now, len(data)))
                
                conn.commit()
                logger.info(f"✅ book_trendsのキャッシュを保存しました ({country}, {len(data)}件)")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ book_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ book_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def get_book_trends_from_cache(self, country='JP'):
        """Book Trendsデータをキャッシュから取得"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
        except Exception as e:
            logger.error(f"❌ Book Trendsキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT country, book_id, isbn, title, subtitle, author, authors, publisher,
                           price, sales, published_date, release_date, description, page_count,
                           categories, average_rating, ratings_count, language, item_url,
                           affiliate_url, preview_link, info_link, buy_link, image_url,
                           thumbnail, small_thumbnail, medium, large, rank, updated_at, cached_at
                    FROM book_trends_cache 
                    WHERE country = %s
                    ORDER BY rank
                """, (country,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    row_dict = dict(row)
                    # JSON文字列を配列に変換
                    if row_dict.get('authors'):
                        try:
                            row_dict['authors'] = json.loads(row_dict['authors']) if isinstance(row_dict['authors'], str) else row_dict['authors']
                        except:
                            row_dict['authors'] = []
                    if row_dict.get('categories'):
                        try:
                            row_dict['categories'] = json.loads(row_dict['categories']) if isinstance(row_dict['categories'], str) else row_dict['categories']
                        except:
                            row_dict['categories'] = []
                    result.append(row_dict)
                
                return result
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ Book Trendsキャッシュ取得中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return None
        except Exception as e:
            logger.error(f"❌ Book Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_book_trends_cache(self, country='JP'):
        """Book Trendsキャッシュをクリア"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
        except Exception as e:
            logger.error(f"❌ book_trendsキャッシュクリアエラー: データベース接続取得に失敗しました: {e}", exc_info=True)
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM book_trends_cache WHERE country = %s", (country,))
                conn.commit()
                logger.info(f"✅ book_trendsのキャッシュをクリアしました ({country})")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ book_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ book_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False
    
    def close(self):
        """データベース接続を閉じる"""
        if self.connection:
            self.connection.close()
            logger.info("✅ データベース接続を閉じました")
