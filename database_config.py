"""
データベース設定とキャッシュシステム
PostgreSQLデータベースの接続とキャッシュ機能を提供
"""

import os
import json
import threading
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from psycopg2 import extensions
from datetime import datetime, timedelta
from contextlib import contextmanager
from dotenv import load_dotenv
from utils.logger_config import get_logger

# 環境変数を読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

# シングルトンインスタンス（全マネージャーで共有）
_shared_cache_instance = None

# 接続プール（グローバルで共有）
_connection_pool = None
_pool_lock = threading.Lock()

def _get_connection_pool():
    """接続プールを取得または作成（シングルトン）"""
    global _connection_pool
    
    if _connection_pool is not None:
        return _connection_pool
    
    with _pool_lock:
        # ダブルチェック（他のスレッドが既に作成した可能性がある）
        if _connection_pool is not None:
            return _connection_pool
        
        try:
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                # 接続パラメータを構築
                min_conn = 2  # 最小接続数
                max_conn = 10  # 最大接続数（同時リクエストに対応）
                
                # 接続パラメータを抽出
                _connection_pool = pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    dsn=database_url,
                    connect_timeout=15,
                    keepalives=1,
                    keepalives_idle=10,
                    keepalives_interval=5,
                    keepalives_count=3,
                    options='-c statement_timeout=60000 -c tcp_keepalives_idle=10 -c tcp_keepalives_interval=5 -c tcp_keepalives_count=3'
                )
                logger.info(f"✅ 接続プールを作成しました (min={min_conn}, max={max_conn})")
            else:
                # 個別の環境変数を使用
                min_conn = 2
                max_conn = 10
                
                _connection_pool = pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    database=os.getenv('DB_NAME', 'trends_db'),
                    user=os.getenv('DB_USER', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'password'),
                    connect_timeout=15,
                    keepalives=1,
                    keepalives_idle=10,
                    keepalives_interval=5,
                    keepalives_count=3
                )
                logger.info(f"✅ 接続プールを作成しました (min={min_conn}, max={max_conn})")
            
            return _connection_pool
        except Exception as e:
            logger.error(f"❌ 接続プール作成エラー: {e}", exc_info=True)
            _connection_pool = None
            raise

class TrendsCache:
    """トレンドデータのキャッシュシステム"""
    
    def __init__(self):
        """初期化"""
        global _shared_cache_instance
        
        # シングルトンパターン：既存のインスタンスがあれば再利用
        if _shared_cache_instance is not None:
            # 既存インスタンスの属性をコピー（接続プールを共有）
            self.pool = _shared_cache_instance.pool
            return
        
        # 初回インスタンス作成
        self.pool = None
        # 接続プールを初期化（エラーが発生してもアプリは起動を続行）
        try:
            self.pool = _get_connection_pool()
        except Exception as e:
            logger.warning(f"⚠️ 接続プールの初期化に失敗しました（後で再試行可能）: {e}", exc_info=True)
            self.pool = None
        
        # グローバルインスタンスに保存
        _shared_cache_instance = self
    
    def connect(self):
        """接続プールを初期化（後方互換性のため）"""
        try:
            if not self.pool:
                self.pool = _get_connection_pool()
                logger.info("✅ 接続プールを初期化しました")
        except Exception as e:
            logger.error(f"❌ 接続プール初期化エラー: {e}", exc_info=True)
            self.pool = None
    
    def init_database(self):
        """データベースを初期化"""
        try:
            with self.get_connection() as conn:
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
                
                CREATE TABLE IF NOT EXISTS github_trends_cache (
                    id SERIAL PRIMARY KEY,
                    repo_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    full_name VARCHAR(500) NOT NULL,
                    description TEXT,
                    url TEXT,
                    language VARCHAR(100),
                    stars_count INTEGER DEFAULT 0,
                    forks_count INTEGER DEFAULT 0,
                    watchers_count INTEGER DEFAULT 0,
                    open_issues_count INTEGER DEFAULT 0,
                    created_at VARCHAR(100),
                    updated_at VARCHAR(100),
                    pushed_at VARCHAR(100),
                    owner_login VARCHAR(255),
                    owner_avatar_url TEXT,
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS appstore_trends_cache (
                    id SERIAL PRIMARY KEY,
                    app_id VARCHAR(255) NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    bundle_id VARCHAR(255),
                    description TEXT,
                    url TEXT,
                    artist_name VARCHAR(255),
                    artist_id VARCHAR(255),
                    price DECIMAL(10, 2) DEFAULT 0,
                    currency VARCHAR(10),
                    category VARCHAR(100),
                    genre_ids TEXT,
                    average_user_rating DECIMAL(3, 2) DEFAULT 0,
                    user_rating_count INTEGER DEFAULT 0,
                    release_date VARCHAR(100),
                    current_version_release_date VARCHAR(100),
                    artwork_url_60 TEXT,
                    artwork_url_100 TEXT,
                    artwork_url_512 TEXT,
                    screenshot_urls TEXT,
                    country VARCHAR(10) NOT NULL DEFAULT 'JP',
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
                    item_url TEXT,
                    amazon_link TEXT,
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
                
                CREATE TABLE IF NOT EXISTS cisa_kev_trends_cache (
                    id SERIAL PRIMARY KEY,
                    cve_id VARCHAR(100) NOT NULL,
                    vendor_project VARCHAR(255),
                    product VARCHAR(255),
                    vulnerability_name TEXT,
                    date_added VARCHAR(50),
                    date_required VARCHAR(50),
                    due_date VARCHAR(50),
                    short_description TEXT,
                    required_action TEXT,
                    notes TEXT,
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS thehackernews_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS ipa_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    last_updated_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS jpcert_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS hackernoon_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS zenn_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS note_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    category VARCHAR(50) DEFAULT 'all',
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- note_trends_cacheテーブルにcategoryカラムを追加（既存テーブル用）
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'note_trends_cache' AND column_name = 'category') THEN
                        ALTER TABLE note_trends_cache ADD COLUMN category VARCHAR(50) DEFAULT 'all';
                    END IF;
                END $$;
                
                CREATE TABLE IF NOT EXISTS amazon_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    asin VARCHAR(50),
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    rank INTEGER DEFAULT 0,
                    category TEXT DEFAULT 'books',
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS ebay_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    item_id VARCHAR(50),
                    price VARCHAR(50),
                    currency VARCHAR(10) DEFAULT 'USD',
                    image_url TEXT,
                    condition VARCHAR(100),
                    seller VARCHAR(255),
                    shipping VARCHAR(50),
                    rank INTEGER DEFAULT 0,
                    category VARCHAR(50) NOT NULL DEFAULT 'electronics',
                    published_date TIMESTAMP WITH TIME ZONE,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 既存のテーブルにcategoryカラムを追加（既存テーブルがある場合）
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'ebay_trends_cache' AND column_name = 'category'
                    ) THEN
                        ALTER TABLE ebay_trends_cache ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT 'electronics';
                    END IF;
                END $$;
                
                CREATE TABLE IF NOT EXISTS medium_trends_cache (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    slug VARCHAR(255),
                    published_date TIMESTAMP WITH TIME ZONE,
                    description TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS devto_trends_cache (
                    id SERIAL PRIMARY KEY,
                    article_id INTEGER,
                    title TEXT NOT NULL,
                    url TEXT,
                    canonical_url TEXT,
                    description TEXT,
                    published_at VARCHAR(50),
                    published_date TIMESTAMP WITH TIME ZONE,
                    positive_reactions_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    reading_time_minutes INTEGER DEFAULT 0,
                    tags TEXT,
                    author VARCHAR(255),
                    rank INTEGER DEFAULT 0,
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
                    frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
                    categories TEXT[],
                    is_active BOOLEAN DEFAULT TRUE,
                    unsubscribe_token VARCHAR(255) UNIQUE,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- subscriptionsテーブルのマイグレーション（既存テーブルにカラムがない場合は追加）
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'frequency') THEN
                        ALTER TABLE subscriptions ADD COLUMN frequency VARCHAR(20) NOT NULL DEFAULT 'daily';
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'categories') THEN
                        ALTER TABLE subscriptions ADD COLUMN categories TEXT[];
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'unsubscribe_token') THEN
                        ALTER TABLE subscriptions ADD COLUMN unsubscribe_token VARCHAR(255);
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'created_at') THEN
                        ALTER TABLE subscriptions ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'updated_at') THEN
                        ALTER TABLE subscriptions ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'subscriptions' AND column_name = 'subscribed_at') THEN
                        ALTER TABLE subscriptions ADD COLUMN subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                END $$;

                CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(email);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(is_active);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_token ON subscriptions(unsubscribe_token);
                
                -- すべてのキャッシュテーブルのrankカラムにインデックスを追加（パフォーマンス向上）
                CREATE INDEX IF NOT EXISTS idx_google_trends_cache_rank ON google_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_youtube_trends_cache_rank ON youtube_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_music_trends_cache_rank ON music_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_podcast_trends_cache_rank ON podcast_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_worldnews_trends_cache_rank ON worldnews_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_rakuten_trends_cache_rank ON rakuten_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_hatena_trends_cache_rank ON hatena_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_twitch_trends_cache_rank ON twitch_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_reddit_trends_cache_rank ON reddit_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_hackernews_trends_cache_rank ON hackernews_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_qiita_trends_cache_rank ON qiita_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_github_trends_cache_rank ON github_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_appstore_trends_cache_rank ON appstore_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_nhk_trends_cache_rank ON nhk_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_cnn_trends_cache_rank ON cnn_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_producthunt_trends_cache_rank ON producthunt_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_stock_trends_cache_rank ON stock_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_crypto_trends_cache_rank ON crypto_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_movie_trends_cache_rank ON movie_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_book_trends_cache_rank ON book_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_cisa_kev_trends_cache_rank ON cisa_kev_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_thehackernews_trends_cache_rank ON thehackernews_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_ipa_trends_cache_rank ON ipa_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_jpcert_trends_cache_rank ON jpcert_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_hackernoon_trends_cache_rank ON hackernoon_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_zenn_trends_cache_rank ON zenn_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_ebay_trends_cache_rank ON ebay_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_medium_trends_cache_rank ON medium_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_devto_trends_cache_rank ON devto_trends_cache(rank);
                CREATE INDEX IF NOT EXISTS idx_note_trends_cache_rank ON note_trends_cache(rank);
                """
                
                cursor.execute(create_tables_sql)
                conn.commit()
                
                # ipa_trends_cacheテーブルのスキーマ更新（既存テーブルにカラムを追加）
                try:
                    cursor.execute("ALTER TABLE ipa_trends_cache ADD COLUMN IF NOT EXISTS last_updated_date TIMESTAMP WITH TIME ZONE")
                    conn.commit()
                    logger.info("✅ ipa_trends_cacheテーブルのスキーマ更新完了")
                except Exception as e:
                    logger.warning(f"⚠️ ipa_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
                
                # movie_trends_cacheテーブルのスキーマ更新（既存テーブルにカラムを追加）
                try:
                    cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS item_url TEXT")
                    cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS amazon_link TEXT")
                    conn.commit()
                    logger.info("✅ movie_trends_cacheテーブルのスキーマ更新完了")
                except Exception as e:
                    logger.warning(f"⚠️ movie_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
                
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
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 既存のデータを削除
                    table_name = f"{cache_key}_cache"
                    delete_column_map = {
                        'google_trends': 'region',
                        'podcast_trends': 'region',
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
                    elif cache_key == 'note_trends':
                        # note_trendsの場合はcategoryで削除
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
                        elif cache_key == 'note_trends':
                            cursor.execute(
                                "INSERT INTO note_trends_cache (title, url, published_date, description, author, rank, category) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (item.get('title', ''), item.get('url', ''), item.get('published_date') or None, item.get('description', ''), item.get('author', ''), item.get('rank', 0), item.get('category', region) or region or 'all')
                            )
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    
                    # Noteの場合はカテゴリ別のキャッシュキーで更新
                    if cache_key == 'note_trends':
                        # regionパラメータがカテゴリ（all, tech, business, lifestyle, entertainment）を表す
                        cache_status_key = f'{cache_key}_{region}' if region else f'{cache_key}_all'
                    else:
                        cache_status_key = cache_key
                    
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        (cache_status_key, now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ {cache_status_key}のキャッシュを更新しました ({len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            # 接続エラーの場合
            error_str = str(e)
            if "cursor already closed" in error_str.lower() or "server closed the connection" in error_str or "connection" in error_str.lower() or "closed" in error_str.lower():
                logger.warning(f"⚠️ キャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
                # 接続エラーの場合は接続をリセット（次回のget_connection()で再接続される）
                self.connection = None
            else:
                # 接続エラー以外のデータベースエラー
                logger.error(f"❌ キャッシュ保存エラー: {e}", exc_info=True)
            return False
        except RuntimeError as e:
            # コンテキストマネージャーのエラー（generator didn't stop after throw()など）
            if "generator didn't stop" in str(e):
                logger.warning(f"⚠️ キャッシュ保存中にコンテキストマネージャーエラーが発生: {e}", exc_info=True)
            else:
                logger.error(f"❌ キャッシュ保存エラー: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"❌ キャッシュ保存エラー: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return False
    
    def get_from_cache(self, cache_key, region='JP'):
        """キャッシュからデータを取得
        
        Returns:
            list: キャッシュデータのリスト（データが存在する場合）
            []: 空のリスト（データが存在しない場合）
            None: エラーが発生した場合（データベースエラーなど）
        """
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                table_name = f"{cache_key}_cache"
                
                # hatena_trends、twitch_trends、note_trendsの場合はcategoryでフィルタリング
                if cache_key == 'hatena_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE category = %s ORDER BY rank ASC, created_at DESC LIMIT 50", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC LIMIT 50")
                elif cache_key == 'twitch_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE category = %s ORDER BY rank ASC, created_at DESC LIMIT 50", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC LIMIT 50")
                elif cache_key == 'note_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE category = %s ORDER BY rank ASC, cached_at DESC LIMIT 50", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, cached_at DESC LIMIT 50")
                # rakuten_trendsの場合はgenre_idでフィルタリング（regionパラメータがgenre_idとして渡される）
                elif cache_key == 'rakuten_trends':
                    if region and region != '':
                        cursor.execute(f"SELECT * FROM {table_name} WHERE genre_id = %s ORDER BY rank ASC, created_at DESC LIMIT 50", (region,))
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rank ASC, created_at DESC LIMIT 50")
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
        
        try:
            result = self._execute_with_retry(query_func)
            # _execute_with_retryがNoneを返した場合はエラー
            if result is None:
                logger.error(f"❌ キャッシュ取得エラー: _execute_with_retryがNoneを返しました (cache_key={cache_key}, region={region})")
                return None
            # 空のリストの場合はデータが存在しない（正常）
            return result
        except Exception as e:
            logger.error(f"❌ キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def is_cache_valid(self, cache_key, region='JP', hours=24):
        """キャッシュが有効かどうかを確認"""
        try:
            with self.get_connection() as conn:
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
            logger.warning(f"⚠️ キャッシュ有効性チェック中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ キャッシュ有効性確認エラー: {e}", exc_info=True)
            return False
    
    def clear_cache(self, cache_key, region='JP'):
        """キャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
    
    def _safe_set_autocommit(self, conn, value):
        """トランザクション状態を確認してからautocommitを安全に設定する
        
        Args:
            conn: データベース接続オブジェクト
            value: 設定するautocommitの値（True/False）
        
        Returns:
            tuple: (成功したかどうか, 元のautocommit値)
        """
        try:
            original_autocommit = conn.autocommit
            # トランザクション状態を確認
            transaction_status = conn.get_transaction_status()
            # トランザクションが開始されている場合は、先にコミットまたはロールバック
            if transaction_status == extensions.TRANSACTION_STATUS_INTRANS:
                # トランザクション内の場合は、ロールバックしてからautocommitを設定
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.warning(f"⚠️ トランザクションロールバック中にエラーが発生しました: {rollback_error}")
                    return (False, original_autocommit)
            elif transaction_status == extensions.TRANSACTION_STATUS_INERROR:
                # エラー状態のトランザクションの場合は、ロールバックが必要
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.warning(f"⚠️ エラー状態のトランザクションロールバック中にエラーが発生しました: {rollback_error}")
                    return (False, original_autocommit)
            
            # トランザクションが終了した後、autocommitを設定
            try:
                conn.autocommit = value
                return (True, original_autocommit)
            except psycopg2.ProgrammingError as e:
                if "set_session cannot be used inside a transaction" in str(e):
                    logger.warning(f"⚠️ トランザクション内でautocommitを設定できません: {e}")
                    return (False, original_autocommit)
                else:
                    raise
        except Exception as e:
            logger.warning(f"⚠️ autocommit設定中にエラーが発生しました: {e}")
            return (False, original_autocommit if 'original_autocommit' in locals() else None)
    
    @contextmanager
    def get_connection(self):
        """データベース接続を取得（コンテキストマネージャー）
        
        接続プールから接続を取得し、使用後に自動的に返却します。
        各リクエストで独立した接続を取得するため、同時リクエストに対応できます。
        
        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
        """
        import time
        
        if not self.pool:
            # 接続プールが初期化されていない場合は初期化を試みる
            try:
                self.pool = _get_connection_pool()
            except Exception as e:
                logger.error(f"❌ 接続プールの取得に失敗しました: {e}", exc_info=True)
                raise psycopg2.OperationalError(f"接続プールが利用できません: {e}")
        
        conn = None
        max_retries = 3
        base_retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # 接続プールから接続を取得
                conn = self.pool.getconn()
                if not conn:
                    raise psycopg2.OperationalError("接続プールから接続を取得できませんでした")
                
                # 接続が有効か検証
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SET statement_timeout = 5000")
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                        cursor.execute("RESET statement_timeout")
                except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as verify_error:
                    # 接続が無効な場合は返却して再試行
                    if conn:
                        try:
                            self.pool.putconn(conn, close=True)
                        except Exception:
                            pass
                        conn = None
                    
                    if attempt < max_retries - 1:
                        wait_time = base_retry_delay * (2 ** attempt)
                        logger.warning(f"⚠️ 接続検証失敗（再接続します）: {verify_error}")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise verify_error
                
                # 接続を返す（コンテキストマネージャーとして）
                try:
                    yield conn
                finally:
                    # 使用後に接続を返却
                    if conn:
                        try:
                            # 接続が有効か確認
                            try:
                                # トランザクション状態を確認してクリーンアップ
                                transaction_status = conn.get_transaction_status()
                                if transaction_status == extensions.TRANSACTION_STATUS_INTRANS:
                                    # トランザクションが開いている場合はロールバック
                                    try:
                                        conn.rollback()
                                    except Exception:
                                        pass
                                elif transaction_status == extensions.TRANSACTION_STATUS_INERROR:
                                    # エラー状態の場合はロールバック
                                    try:
                                        conn.rollback()
                                    except Exception:
                                        pass
                            except (psycopg2.InterfaceError, psycopg2.OperationalError, AttributeError):
                                # 接続が無効な場合は、そのまま接続を閉じて返却
                                pass
                            
                            # 接続を返却
                            try:
                                self.pool.putconn(conn)
                            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                                # 接続が無効な場合は閉じて返却
                                try:
                                    self.pool.putconn(conn, close=True)
                                except Exception:
                                    pass
                        except Exception as put_error:
                            logger.warning(f"⚠️ 接続の返却中にエラーが発生しました: {put_error}")
                            # エラーが発生した場合は接続を閉じて返却
                            try:
                                self.pool.putconn(conn, close=True)
                            except Exception:
                                pass
                return
                
            except pool.PoolError as pool_error:
                # 接続プールのエラー
                if attempt < max_retries - 1:
                    wait_time = base_retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️ 接続プールエラー（再試行します）: {pool_error}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ 接続プールエラー（最大試行回数）: {pool_error}")
                    raise psycopg2.OperationalError(f"接続プールから接続を取得できませんでした: {pool_error}")
            
            except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                # 接続エラー
                if conn:
                    try:
                        self.pool.putconn(conn, close=True)
                    except Exception:
                        pass
                    conn = None
                
                if attempt < max_retries - 1:
                    wait_time = base_retry_delay * (2 ** attempt)
                    error_str = str(e).lower()
                    if "server closed" in error_str or "connection" in error_str:
                        logger.warning(f"⚠️ データベース接続エラー（再試行します）: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ データベース接続エラー（最大試行回数）: {e}")
                    raise
        
        # 全ての再試行が失敗した場合
        raise psycopg2.OperationalError("データベース接続を取得できませんでした（最大試行回数に達しました）")
    
    def _execute_with_retry(self, query_func, max_retries=3, is_read_only=True):
        """接続エラーが発生した場合に自動的に再接続を試みるヘルパーメソッド
        
        Args:
            query_func: データベースクエリを実行する関数（接続オブジェクトを引数として受け取る）
            max_retries: 最大再試行回数（デフォルト: 3）
            is_read_only: Trueの場合はSELECT文（読み取り専用）、Falseの場合はINSERT/UPDATE/DELETE（書き込み）
        
        Returns:
            クエリ関数の戻り値、またはNone（全ての再試行が失敗した場合）
        """
        import time
        
        base_wait_time = 0.5  # ベース待機時間（秒）
        
        for attempt in range(max_retries):
            try:
                # 接続プールから接続を取得（コンテキストマネージャーとして）
                with self.get_connection() as conn:
                    # 接続が有効か再確認（get_connection()で検証済みだが、念のため）
                    try:
                        if conn.closed:
                            raise psycopg2.InterfaceError("接続が閉じられています")
                        # 軽量な検証クエリを実行して接続が有効か確認（タイムアウト5秒）
                        with conn.cursor() as test_cursor:
                            test_cursor.execute("SET statement_timeout = 5000")
                            test_cursor.execute("SELECT 1")
                            test_cursor.fetchone()
                            test_cursor.execute("RESET statement_timeout")
                    except psycopg2.OperationalError as timeout_error:
                        # タイムアウトエラーの場合は接続が無効と判断
                        error_str = str(timeout_error).lower()
                        if "timeout" in error_str:
                            logger.warning(f"⚠️ 接続検証タイムアウト（再接続します）: {timeout_error}")
                        else:
                            logger.warning(f"⚠️ 接続検証失敗（再接続します）: {timeout_error}")
                        if attempt < max_retries - 1:
                            wait_time = base_wait_time * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                        else:
                            raise timeout_error
                    except (psycopg2.InterfaceError, psycopg2.DatabaseError) as verify_error:
                        # 接続が無効な場合は再接続を試みる
                        logger.warning(f"⚠️ 接続検証失敗（再接続します）: {verify_error}")
                        if attempt < max_retries - 1:
                            wait_time = base_wait_time * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                        else:
                            raise verify_error
                    
                    # SELECT文（読み取り専用）の場合はautocommitを有効化してトランザクションを開かない
                    # INSERT/UPDATE/DELETE（書き込み）の場合はトランザクション管理が必要
                    original_autocommit = None
                    if is_read_only:
                        success, original_autocommit = self._safe_set_autocommit(conn, True)
                        if not success:
                            # autocommit設定に失敗した場合は、接続をリセットして再接続を試みる
                            logger.warning("⚠️ autocommit設定に失敗しました。再接続を試みます")
                            if attempt < max_retries - 1:
                                wait_time = base_wait_time * (2 ** attempt)
                                time.sleep(wait_time)
                                continue
                            else:
                                raise psycopg2.ProgrammingError("autocommit設定に失敗しました")
                    
                    # クエリを実行
                    result = query_func(conn)
                    
                    # SELECT文の場合は明示的なコミットは不要（autocommit=Trueのため）
                    # 書き込み操作の場合は呼び出し側でコミットを実行
                    
                    # autocommitを元に戻す（読み取り専用の場合のみ）
                    if is_read_only and original_autocommit is not None:
                        try:
                            conn.autocommit = original_autocommit
                        except Exception:
                            pass  # 元に戻すのに失敗しても無視
                    
                    return result
                    
            except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                error_str = str(e)
                
                # 接続が閉じられたエラーを特定
                if ("server closed the connection" in error_str.lower() or 
                    "connection" in error_str.lower() or 
                    "closed" in error_str.lower() or
                    "server terminated abnormally" in error_str.lower()):
                    logger.warning(f"⚠️ データベース接続エラーが発生しました: {e} (試行 {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        # 指数バックオフで待機時間を増やす
                        # "server terminated abnormally"の場合は、より長い待機時間を設定
                        if "server terminated abnormally" in error_str.lower():
                            wait_time = base_wait_time * (2 ** attempt) * 3  # 通常の3倍
                            logger.info(f"⏳ データベースサーバーが異常終了した可能性があります。{wait_time}秒待機してから再試行します...")
                        else:
                            wait_time = base_wait_time * (2 ** attempt)
                            logger.info(f"⏳ {wait_time}秒待機してから再試行します...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ データベース接続エラー（最大試行回数）: {e}")
                        return None
                else:
                    # 接続エラー以外のデータベースエラーはそのまま再スロー
                    logger.error(f"❌ データベースエラー（再接続不可）: {e}", exc_info=True)
                    raise
                    
            except Exception as e:
                # 接続エラー以外のエラーはそのまま再スロー
                logger.error(f"❌ 予期しないエラーが発生しました: {e}", exc_info=True)
                raise
        
        # 全ての再試行が失敗した場合
        logger.error("❌ データベース接続エラー（最大試行回数に達しました）")
        return None
    
    
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            return None
        except Exception as e:
            logger.error(f"❌ YouTubeキャッシュ取得エラー: データベース接続取得に失敗しました: {e}", exc_info=True)
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            return False
    
    def get_music_trends_from_cache(self, service='spotify', region='JP'):
        """Music Trendsデータをキャッシュから取得"""
        # 既存環境ではmusic_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            with self.get_connection() as conn:
                try:
                    with conn.cursor() as cursor:
                        # INSERT文で使用しているカラムを確認して追加
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS album TEXT")
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS play_count INTEGER DEFAULT 0")
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS spotify_url TEXT")
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 0")
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS region_code VARCHAR(10)")
                        cursor.execute("ALTER TABLE music_trends_cache ADD COLUMN IF NOT EXISTS track_id VARCHAR(255)")
                    conn.commit()
                except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                    error_str = str(e)
                    if "server closed the connection" in error_str or "connection" in error_str.lower() or "closed" in error_str.lower():
                        logger.warning(f"⚠️ music_trends_cacheスキーマ更新中に接続エラーが発生: {e}")
        except Exception as e:
            logger.warning(f"⚠️ music_trends_cacheのスキーマ更新に失敗しました: {e}", exc_info=True)
        
        # 接続を取得（有効性チェックと再接続を自動で行う）
        max_retries = 2
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    # 実際のクエリを実行（接続エラーが発生した場合は再接続を試みる）
                    try:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            cursor.execute("""
                                SELECT title, artist, album, play_count, popularity, spotify_url, rank, 
                                       service, region_code, created_at, track_id
                                FROM music_trends_cache 
                                WHERE service = %s AND region_code = %s
                                ORDER BY rank
                                LIMIT 50
                            """, (service, region))
                            data = cursor.fetchall()
                            
                            # RealDictCursorの結果を辞書のリストに変換
                            result = []
                            for row in data:
                                result.append(dict(row))
                            
                            return result
                    except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                        error_str = str(e)
                        if "server closed the connection" in error_str or "connection" in error_str.lower() or "closed" in error_str.lower():
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ Music Trendsキャッシュ取得中に接続エラーが発生、再接続を試みます (試行 {attempt + 1}/{max_retries}): {e}")
                                self.connection = None
                                import time
                                time.sleep(0.5)
                                continue
                            else:
                                logger.error(f"❌ Music Trendsキャッシュ取得エラー: 接続エラーが継続しています（最大試行回数）: {e}")
                                return None
                        else:
                            # 接続エラー以外のデータベースエラー
                            logger.error(f"❌ Music Trendsキャッシュ取得エラー: {e}", exc_info=True)
                            return None
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Music Trendsキャッシュ取得エラー: {e} - 再試行します (試行 {attempt + 1}/{max_retries})")
                    self.connection = None
                    import time
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"❌ Music Trendsキャッシュ取得エラー（最大試行回数）: {e}", exc_info=True)
                    return None
        
        return None
    
    def clear_music_trends_cache(self, service='spotify', region='JP'):
        """Music Trendsキャッシュをクリア"""
        # 既存環境ではmusic_trends_cacheに不足カラムがあるケースがあるため、ここで補完しておく
        try:
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
    
    # World News Trends キャッシュメソッド
    def save_worldnews_trends_to_cache(self, data, cache_key='worldnews_trends', country='JP'):
        """World News Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
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
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # World News専用のクエリ（countryカラムで検索）
                cursor.execute("SELECT * FROM worldnews_trends_cache WHERE country = %s ORDER BY created_at DESC", (country.lower(),))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
        
        return self._execute_with_retry(query_func)
    
    def clear_worldnews_trends_cache(self, category='general', country='JP'):
        """World News Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # worldnews_trends_cacheテーブルはcountryカラムを使用（regionカラムは存在しない）
                    cursor.execute("DELETE FROM worldnews_trends_cache WHERE country = %s", (country.lower(),))
                    conn.commit()
                    logger.info(f"✅ worldnews_trendsのキャッシュをクリアしました (country: {country})")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ worldnews_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ worldnews_trendsキャッシュクリアエラー: {e}", exc_info=True)
            return False
    
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
            with self.get_connection() as schema_conn:
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
    
    def update_all_trends_timestamp(self, timestamp):
        """全トレンドの更新時刻を一括で設定（スケジューラー実行時の時刻を統一するため）"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # データベースからすべてのcache_keyを動的に取得
                    # これにより、新しいトレンドが追加されても自動的に対応できる
                    # JPとUSの両方のデータを含むすべてのcache_keyを取得
                    cursor.execute("""
                        SELECT DISTINCT cache_key 
                        FROM cache_status
                        WHERE cache_key IS NOT NULL
                        ORDER BY cache_key
                    """)
                    cache_keys = [row[0] for row in cursor.fetchall()]
                    
                    if not cache_keys:
                        logger.warning("⚠️ 更新対象のcache_keyが見つかりませんでした")
                        return False
                    
                    # JPとUSのcache_keyを分類してログ出力
                    jp_keys = [k for k in cache_keys if k.endswith('_JP') or (not k.endswith('_US') and not k.endswith('_us'))]
                    us_keys = [k for k in cache_keys if k.endswith('_US') or k.endswith('_us')]
                    logger.info(f"📊 更新対象: JP={len(jp_keys)}件, US={len(us_keys)}件, 合計={len(cache_keys)}件")
                    
                    # すべてのcache_keyに対して、更新時刻を統一
                    # データ件数は変更せず、更新時刻のみを更新
                    updated_count = 0
                    for cache_key in cache_keys:
                        cursor.execute("""
                            UPDATE cache_status 
                            SET last_updated = %s
                            WHERE cache_key = %s
                        """, (timestamp, cache_key))
                        updated_count += cursor.rowcount
                        
                    conn.commit()
                    logger.info(f"✅ 全トレンドの更新時刻を一括設定しました: {updated_count}件のcache_keyを更新 ({timestamp.strftime('%Y-%m-%d %H:%M:%S JST')})")
                    logger.info(f"📋 更新されたcache_keyの例（最初の10件）: {', '.join(cache_keys[:10])}")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 更新時刻一括設定中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ 全トレンド更新時刻一括設定エラー: {e}", exc_info=True)
            return False
    
    def update_successful_trends_timestamp(self, cache_keys, timestamp):
        """成功したトレンドのみタイムスタンプを更新"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if not cache_keys:
                        logger.warning("⚠️ 更新対象のcache_keyが空です")
                        return False
                    
                    # 重複を除去
                    unique_cache_keys = list(set(cache_keys))
                    
                    # 成功したcache_keyのみタイムスタンプを更新
                    updated_count = 0
                    for cache_key in unique_cache_keys:
                        cursor.execute("""
                            UPDATE cache_status 
                            SET last_updated = %s
                            WHERE cache_key = %s
                        """, (timestamp, cache_key))
                        updated_count += cursor.rowcount
                    
                    conn.commit()
                    logger.info(f"✅ 成功したトレンドの更新時刻を更新しました: {updated_count}件のcache_keyを更新 ({timestamp.strftime('%Y-%m-%d %H:%M:%S JST')})")
                    if unique_cache_keys:
                        logger.info(f"📋 更新されたcache_keyの例（最初の10件）: {', '.join(unique_cache_keys[:10])}")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ 更新時刻設定中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ 成功したトレンド更新時刻設定エラー: {e}", exc_info=True)
            return False
    
    def update_cache_status(self, cache_key, data_count, timestamp=None):
        """特定のトレンドのcache_statusを更新"""
        import pytz
        if timestamp is None:
            jst = pytz.timezone('Asia/Tokyo')
            timestamp = datetime.now(jst)
        
        def query_func(conn):
            """cache_statusを更新するクエリ関数"""
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, (cache_key, timestamp, data_count))
                conn.commit()
                return True
        
        try:
            result = self._execute_with_retry(query_func, max_retries=5, is_read_only=False)
            if result is None:
                logger.warning(f"⚠️ データベース接続が取得できませんでした。cache_status更新をスキップします (cache_key: {cache_key})")
                return False
            return result
        except Exception as e:
            logger.error(f"❌ cache_status更新エラー: {e}", exc_info=True)
            return False
    
    def clear_all_cache(self):
        """全キャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            return False
    
    def get_reddit_trends_from_cache(self, subreddit='all'):
        """Reddit Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT post_id, title, url, subreddit, author, score, upvote_ratio,
                           num_comments, permalink, is_video, domain, rank, created_at
                    FROM reddit_trends_cache 
                    WHERE subreddit = %s 
                    ORDER BY rank
                    LIMIT 50
                """, (subreddit,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ Reddit Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_reddit_trends_cache(self, subreddit='all'):
        """Reddit Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            return False
    
    # Hacker News Trends キャッシュメソッド
    def save_hackernews_trends_to_cache(self, data, story_type='top'):
        """Hacker News Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('hackernews_trends', now_jst, len(data)))
                    
                    conn.commit()
                    logger.info(f"✅ hackernews_trendsキャッシュを保存しました (type: {story_type}, {len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ hackernews_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ hackernews_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_hackernews_trends_from_cache(self, story_type='top'):
        """Hacker News Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT story_id, title, url, score, author, story_time, 
                           comments, story_type, rank, created_at
                    FROM hackernews_trends_cache 
                    WHERE story_type = %s 
                    ORDER BY rank
                    LIMIT 50
                """, (story_type,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ Hacker News Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_hackernews_trends_cache(self, story_type='top'):
        """Hacker News Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            return False
    
    # Qiita Trends キャッシュメソッド
    def save_qiita_trends_to_cache(self, data):
        """Qiita Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
            return False
    
    def get_qiita_trends_from_cache(self):
        """Qiita Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT item_id, title, url, user_id, user_name, likes_count, stocks_count,
                           comments_count, created_at, updated_at, tags, rank, cached_at
                    FROM qiita_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ Qiita Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_qiita_trends_cache(self):
        """Qiita Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            return False
    
    # GitHub Trends キャッシュメソッド
    def save_github_trends_to_cache(self, data):
        """GitHub Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 既存のデータを削除
                    cursor.execute("""
                        DELETE FROM github_trends_cache
                    """)
                    
                    # 新しいデータを挿入
                    for item in data:
                        # stars_countを取得（starsキーからも取得を試みる）
                        stars_count = item.get('stars_count', 0) or 0
                        if stars_count == 0:
                            stars_count = item.get('stars', 0) or 0
                        
                        cursor.execute("""
                            INSERT INTO github_trends_cache 
                            (repo_id, name, full_name, description, url, language, stars_count, forks_count,
                             watchers_count, open_issues_count, created_at, updated_at, pushed_at,
                             owner_login, owner_avatar_url, rank)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('repo_id', ''),
                            item.get('name', ''),
                            item.get('full_name', ''),
                            item.get('description', ''),
                            item.get('url', ''),
                            item.get('language', ''),
                            stars_count,
                            item.get('forks_count', 0) or 0,
                            item.get('watchers_count', 0) or 0,
                            item.get('open_issues_count', 0) or 0,
                            item.get('created_at', ''),
                            item.get('updated_at', ''),
                            item.get('pushed_at', ''),
                            item.get('owner_login', ''),
                            item.get('owner_avatar_url', ''),
                            item.get('rank', 0)
                        ))
                    
                    # キャッシュステータスを更新
                    from datetime import datetime
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('github_trends', datetime.now(jst), len(data), datetime.now(jst), len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ github_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ github_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ github_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_github_trends_from_cache(self):
        """GitHub Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT repo_id, name, full_name, description, url, language, stars_count, forks_count,
                           watchers_count, open_issues_count, created_at, updated_at, pushed_at,
                           owner_login, owner_avatar_url, rank, cached_at
                    FROM github_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    result.append(dict(row))
                
                return result
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ GitHub Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_github_trends_cache(self):
        """GitHub Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM github_trends_cache
                    """)
                    conn.commit()
                    logger.info(f"✅ github_trendsのキャッシュをクリアしました")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ github_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ github_trendsキャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    # App Store Trends キャッシュメソッド
    def save_appstore_trends_to_cache(self, data, country='JP'):
        """App Store Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 既存のデータを削除（国別）
                    cursor.execute("""
                        DELETE FROM appstore_trends_cache WHERE country = %s
                    """, (country,))
                    
                    # 新しいデータを挿入
                    for item in data:
                        # 配列をJSON文字列に変換
                        genre_ids_json = json.dumps(item.get('genre_ids', []), ensure_ascii=False)
                        screenshot_urls_json = json.dumps(item.get('screenshot_urls', []), ensure_ascii=False)
                        
                        cursor.execute("""
                            INSERT INTO appstore_trends_cache 
                            (app_id, name, bundle_id, description, url, artist_name, artist_id, price, currency,
                             category, genre_ids, average_user_rating, user_rating_count, release_date,
                             current_version_release_date, artwork_url_60, artwork_url_100, artwork_url_512,
                             screenshot_urls, country, rank)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('app_id', ''),
                            item.get('name', ''),
                            item.get('bundle_id', ''),
                            item.get('description', ''),
                            item.get('url', ''),
                            item.get('artist_name', ''),
                            item.get('artist_id', ''),
                            item.get('price', 0),
                            item.get('currency', ''),
                            item.get('category', ''),
                            genre_ids_json,
                            item.get('average_user_rating', 0),
                            item.get('user_rating_count', 0),
                            item.get('release_date', ''),
                            item.get('current_version_release_date', ''),
                            item.get('artwork_url_60', ''),
                            item.get('artwork_url_100', ''),
                            item.get('artwork_url_512', ''),
                            screenshot_urls_json,
                            country,
                            item.get('rank', 0)
                        ))
                    
                    # キャッシュステータスを更新
                    from datetime import datetime
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    cache_key = f'appstore_trends_{country}'
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        (cache_key, datetime.now(jst), len(data), datetime.now(jst), len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ appstore_trendsキャッシュを保存しました ({len(data)}件, country={country})")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ appstore_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ appstore_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_appstore_trends_from_cache(self, country='JP'):
        """App Store Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT app_id, name, bundle_id, description, url, artist_name, artist_id, price, currency,
                           category, genre_ids, average_user_rating, user_rating_count, release_date,
                           current_version_release_date, artwork_url_60, artwork_url_100, artwork_url_512,
                           screenshot_urls, country, rank, cached_at
                    FROM appstore_trends_cache 
                    WHERE country = %s
                    ORDER BY rank
                    LIMIT 50
                """, (country,))
                data = cursor.fetchall()
                
                # RealDictCursorの結果を辞書のリストに変換
                result = []
                for row in data:
                    item = dict(row)
                    # JSON文字列を配列に変換
                    if item.get('genre_ids'):
                        try:
                            item['genre_ids'] = json.loads(item['genre_ids'])
                        except:
                            item['genre_ids'] = []
                    if item.get('screenshot_urls'):
                        try:
                            item['screenshot_urls'] = json.loads(item['screenshot_urls'])
                        except:
                            item['screenshot_urls'] = []
                    result.append(item)
                
                return result
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ App Store Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def clear_appstore_trends_cache(self, country='JP'):
        """App Store Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM appstore_trends_cache WHERE country = %s
                    """, (country,))
                    conn.commit()
                    logger.info(f"✅ appstore_trendsのキャッシュをクリアしました (country={country})")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ appstore_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ appstore_trendsキャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    # NHK Trends キャッシュメソッド
    def save_nhk_trends_to_cache(self, data):
        """NHK Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
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
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('nhk_trends', now_jst, len(data), now_jst, len(data))
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
            return False

    def get_nhk_trends_from_cache(self):
        """NHK Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, rank, cached_at
                    FROM nhk_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        try:
            return self._execute_with_retry(query_func)
        except Exception as e:
            logger.error(f"❌ NHK Trendsキャッシュ取得エラー: {e}", exc_info=True)
            return None

    def clear_nhk_trends_cache(self):
        """NHK Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            return False
    
    # CNN Trends キャッシュメソッド
    def save_cnn_trends_to_cache(self, data):
        """CNN Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
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
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('cnn_trends', now_jst, len(data), now_jst, len(data))
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
            return False

    def get_cnn_trends_from_cache(self):
        """CNN Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, rank, cached_at
                    FROM cnn_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        return self._execute_with_retry(query_func)

    def clear_cnn_trends_cache(self):
        """CNN Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
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
            return False
    
    # Product Hunt Trends キャッシュメソッド
    def save_producthunt_trends_to_cache(self, data):
        """Product Hunt Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('producthunt_trends', now_jst, len(data)))
                    
                    conn.commit()
                    logger.info(f"✅ producthunt_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ producthunt_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ producthunt_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_producthunt_trends_from_cache(self):
        """Product Hunt Trendsデータをキャッシュから取得"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT product_id, name, tagline, description, url, website, votes_count, comments_count,
                               created_at, topics, user_name, user_username, rank, cached_at
                        FROM producthunt_trends_cache 
                        ORDER BY rank
                        LIMIT 50
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
            with self.get_connection() as conn:
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
            return False
    
    # Stock Trends キャッシュメソッド
    def save_stock_trends_to_cache(self, data, market='US'):
        """Stock Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
            return False
    
    def get_stock_trends_from_cache(self, market='US'):
        """Stock Trendsデータをキャッシュから取得"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT symbol, name, current_price, previous_price, change, change_percent,
                               volume, market_cap, market, rank, updated_at, cached_at
                        FROM stock_trends_cache 
                        WHERE market = %s 
                        ORDER BY rank
                        LIMIT 50
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
            with self.get_connection() as conn:
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
            return False
    
    # Crypto Trends キャッシュメソッド
    def save_crypto_trends_to_cache(self, data):
        """Crypto Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
            return False
    
    def get_crypto_trends_from_cache(self):
        """Crypto Trendsデータをキャッシュから取得"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT coin_id, symbol, name, market_cap_rank, search_score,
                               current_price, price_change_24h, price_change_percentage_24h,
                               market_cap, volume_24h, image_url, rank, updated_at, cached_at
                        FROM crypto_trends_cache 
                        ORDER BY rank
                        LIMIT 50
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
            with self.get_connection() as conn:
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
            return False
    
    def save_movie_trends_to_cache(self, data, country='JP'):
        """Movie Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # テーブルスキーマを確認し、必要に応じてカラムを追加
                    try:
                        cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS item_url TEXT")
                        cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS amazon_link TEXT")
                        conn.commit()
                        logger.info("✅ movie_trends_cacheテーブルのスキーマ更新完了（item_url, amazon_link）")
                    except Exception as schema_error:
                        # カラムが既に存在する場合やその他のエラーは無視
                        conn.rollback()
                        if "already exists" not in str(schema_error).lower() and "duplicate" not in str(schema_error).lower():
                            logger.debug(f"⚠️ movie_trends_cacheスキーマ更新: {schema_error}")
                    
                    # 既存のデータを削除（国別）
                    cursor.execute("DELETE FROM movie_trends_cache WHERE country = %s", (country,))
                    
                    # 新しいデータを挿入
                    for idx, item in enumerate(data):
                        try:
                            cursor.execute("""
                                INSERT INTO movie_trends_cache
                                (country, movie_id, title, original_title, overview, popularity,
                                 vote_average, vote_count, release_date, poster_path,
                                 backdrop_path, poster_url, backdrop_url, item_url, amazon_link, rank, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                                item.get('item_url', ''),
                                item.get('amazon_link', ''),
                                item.get('rank', 0),
                                item.get('updated_at')
                            ))
                        except Exception as item_error:
                            logger.error(f"❌ movie_trendsキャッシュ保存エラー (item {idx}): {item_error}", exc_info=True)
                            logger.error(f"Item data: {item}")
                            raise
                    # cache_statusテーブルを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cache_key = f'movie_trends_{country}'
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, (cache_key, now_jst, len(data)))
                    
                    conn.commit()
                    logger.info(f"✅ movie_trendsのキャッシュを保存しました (country: {country}, {len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ movie_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ movie_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_movie_trends_from_cache(self, country='JP'):
        """Movie Trendsデータをキャッシュから取得"""
        try:
            with self.get_connection() as conn:
                # テーブルスキーマを確認し、必要に応じてカラムを追加
                with conn.cursor() as schema_cursor:
                    try:
                        schema_cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS item_url TEXT")
                        schema_cursor.execute("ALTER TABLE movie_trends_cache ADD COLUMN IF NOT EXISTS amazon_link TEXT")
                        conn.commit()
                    except Exception as schema_error:
                        # カラムが既に存在する場合やその他のエラーは無視
                        conn.rollback()
                
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT country, movie_id, title, original_title, overview, popularity,
                               vote_average, vote_count, release_date, poster_path,
                               backdrop_path, poster_url, backdrop_url, item_url, amazon_link, rank, updated_at, cached_at
                        FROM movie_trends_cache 
                        WHERE country = %s
                        ORDER BY rank
                        LIMIT 50
                    """, (country,))
                    data = cursor.fetchall()
                    
                    # RealDictCursorの結果を辞書のリストに変換
                    result = []
                    for row in data:
                        result.append(dict(row))
                    
                    logger.debug(f"✅ movie_trendsキャッシュから{len(result)}件のデータを取得しました (country: {country})")
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
            with self.get_connection() as conn:
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
            return False
    
    def save_book_trends_to_cache(self, data, country='JP'):
        """Book Trendsデータをキャッシュに保存"""
        if not data:
            return False
        
        try:
            with self.get_connection() as conn:
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
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, (f'book_trends_{country}', now_jst, len(data)))
                    
                    conn.commit()
                    logger.info(f"✅ book_trendsのキャッシュを保存しました ({country}, {len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            # 接続エラーの場合
            error_str = str(e)
            if "cursor already closed" in error_str.lower() or "server closed the connection" in error_str or "connection" in error_str.lower() or "closed" in error_str.lower():
                logger.warning(f"⚠️ book_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
                # 接続エラーの場合は接続をリセット（次回のget_connection()で再接続される）
                self.connection = None
            else:
                # 接続エラー以外のデータベースエラー
                logger.error(f"❌ book_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
        except RuntimeError as e:
            # コンテキストマネージャーのエラー（generator didn't stop after throw()など）
            if "generator didn't stop" in str(e):
                logger.warning(f"⚠️ book_trendsキャッシュ保存中にコンテキストマネージャーエラーが発生: {e}", exc_info=True)
            else:
                logger.error(f"❌ book_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"❌ book_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def get_book_trends_from_cache(self, country='JP'):
        """Book Trendsデータをキャッシュから取得"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT country, book_id, isbn, title, subtitle, author, authors, publisher,
                               price, sales, published_date, release_date, description, page_count,
                               categories, average_rating, ratings_count, language, item_url,
                               affiliate_url, preview_link, info_link, buy_link, image_url,
                               thumbnail, small_thumbnail, medium, large, rank, updated_at, cached_at
                        FROM book_trends_cache 
                        WHERE country = %s
                        ORDER BY rank ASC, cached_at DESC
                        LIMIT 50
                    """, (country,))
                    data = cursor.fetchall()
                    
                    logger.info(f"🔍 Book Trends キャッシュ取得: country={country}, 取得件数={len(data)}")
                    
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
            with self.get_connection() as conn:
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
            return False
    
    # CISA KEV Trends キャッシュメソッド
    def save_cisa_kev_trends_to_cache(self, data):
        """CISA KEV Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM cisa_kev_trends_cache")
                    for item in data:
                        cursor.execute("""
                            INSERT INTO cisa_kev_trends_cache 
                            (cve_id, vendor_project, product, vulnerability_name, date_added, date_required, 
                             due_date, short_description, required_action, notes, rank)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('cve_id', ''),
                            item.get('vendor_project', ''),
                            item.get('product', ''),
                            item.get('vulnerability_name', ''),
                            item.get('date_added', ''),
                            item.get('date_required', ''),
                            item.get('due_date', ''),
                            item.get('short_description', ''),
                            item.get('required_action', ''),
                            item.get('notes', ''),
                            item.get('rank', 0)
                        ))
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('cisa_kev_trends', now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ cisa_kev_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
                
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ cisa_kev_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ cisa_kev_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False

    def get_cisa_kev_trends_from_cache(self):
        """CISA KEV Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT cve_id, vendor_project, product, vulnerability_name, date_added, date_required,
                           due_date, short_description, required_action, notes, rank, cached_at
                    FROM cisa_kev_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                return [dict(row) for row in cursor.fetchall()]
        
        return self._execute_with_retry(query_func)

    def clear_cisa_kev_trends_cache(self):
        """CISA KEV Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM cisa_kev_trends_cache")
                    conn.commit()
                    logger.info(f"✅ cisa_kev_trendsのキャッシュをクリアしました")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ cisa_kev_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ cisa_kev_trendsキャッシュクリアエラー: {e}", exc_info=True)
            return False

    # The Hacker News Trends キャッシュメソッド
    def save_thehackernews_trends_to_cache(self, data):
        """The Hacker News Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM thehackernews_trends_cache")
                    for item in data:
                        cursor.execute("""
                            INSERT INTO thehackernews_trends_cache 
                            (title, url, published_date, description, author, rank)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('title', ''),
                            item.get('url', ''),
                            item.get('published_date'),
                            item.get('description', ''),
                            item.get('author', ''),
                            item.get('rank', 0)
                        ))
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('thehackernews_trends', now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ thehackernews_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ thehackernews_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ thehackernews_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False

    def get_thehackernews_trends_from_cache(self):
        """The Hacker News Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, author, rank, cached_at
                    FROM thehackernews_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        return self._execute_with_retry(query_func)

    def clear_thehackernews_trends_cache(self):
        """The Hacker News Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM thehackernews_trends_cache")
                    conn.commit()
                    logger.info(f"✅ thehackernews_trendsのキャッシュをクリアしました")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ thehackernews_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ thehackernews_trendsキャッシュクリアエラー: {e}", exc_info=True)
            return False

    # IPA Trends キャッシュメソッド
    def save_ipa_trends_to_cache(self, data):
        """IPA Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM ipa_trends_cache")
                    for item in data:
                        cursor.execute("""
                            INSERT INTO ipa_trends_cache 
                            (title, url, published_date, last_updated_date, description, author, rank)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('title', ''),
                            item.get('url', ''),
                            item.get('published_date'),
                            item.get('last_updated_date'),
                            item.get('description', ''),
                            item.get('author', ''),
                            item.get('rank', 0)
                        ))
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('ipa_trends', now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ ipa_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ ipa_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ ipa_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False

    def get_ipa_trends_from_cache(self):
        """IPA Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, last_updated_date, description, author, rank, cached_at
                    FROM ipa_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    # published_dateをISO形式の文字列に変換
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    # last_updated_dateをISO形式の文字列に変換
                    if row_dict.get('last_updated_date'):
                        if isinstance(row_dict['last_updated_date'], datetime):
                            row_dict['last_updated_date'] = row_dict['last_updated_date'].isoformat()
                    result.append(row_dict)
                return result
        
        return self._execute_with_retry(query_func)

    def clear_ipa_trends_cache(self):
        """IPA Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM ipa_trends_cache")
                    conn.commit()
                    logger.info(f"✅ ipa_trendsのキャッシュをクリアしました")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ ipa_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ ipa_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # JPCERT/CC Trends キャッシュメソッド
    def save_jpcert_trends_to_cache(self, data):
        """JPCERT/CC Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM jpcert_trends_cache")
                    for item in data:
                        cursor.execute("""
                        INSERT INTO jpcert_trends_cache 
                        (title, url, published_date, description, author, rank)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('author', ''),
                        item.get('rank', 0)
                    ))
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('jpcert_trends', now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ jpcert_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ jpcert_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ jpcert_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_jpcert_trends_from_cache(self):
        """JPCERT/CC Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, author, rank, cached_at
                    FROM jpcert_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        return self._execute_with_retry(query_func)

    def clear_jpcert_trends_cache(self):
        """JPCERT/CC Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM jpcert_trends_cache")
                    conn.commit()
                logger.info(f"✅ jpcert_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ jpcert_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ jpcert_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # Hacker Noon Trends キャッシュメソッド
    def save_hackernoon_trends_to_cache(self, data):
        """Hacker Noon Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM hackernoon_trends_cache")
                    for item in data:
                        cursor.execute("""
                        INSERT INTO hackernoon_trends_cache 
                        (title, url, published_date, description, author, rank)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('author', ''),
                        item.get('rank', 0)
                    ))
                    
                    # キャッシュステータスを更新
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('hackernoon_trends', now_jst, len(data), now_jst, len(data))
                    )
                    
                    conn.commit()
                    logger.info(f"✅ hackernoon_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ hackernoon_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ hackernoon_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_hackernoon_trends_from_cache(self):
        """Hacker Noon Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, author, rank, cached_at
                    FROM hackernoon_trends_cache 
                    ORDER BY rank
                    LIMIT 50
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
        
        return self._execute_with_retry(query_func)

    def clear_hackernoon_trends_cache(self):
        """Hacker Noon Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM hackernoon_trends_cache")
                    conn.commit()
                logger.info(f"✅ hackernoon_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ hackernoon_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ hackernoon_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # Zenn Trends キャッシュメソッド
    def save_zenn_trends_to_cache(self, data):
        """Zenn Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM zenn_trends_cache")
                    for item in data:
                        cursor.execute("""
                        INSERT INTO zenn_trends_cache 
                        (title, url, published_date, description, author, rank)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('author', ''),
                        item.get('rank', 0)
                    ))
                    
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('zenn_trends', now_jst, len(data), now_jst, len(data))
                    )
                    conn.commit()
                    logger.info(f"✅ zenn_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ zenn_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ zenn_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_zenn_trends_from_cache(self):
        """Zenn Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, published_date, description, author, rank, cached_at
                    FROM zenn_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    result.append(row_dict)
                return result
        return self._execute_with_retry(query_func)

    def clear_zenn_trends_cache(self):
        """Zenn Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM zenn_trends_cache")
                    conn.commit()
                logger.info(f"✅ zenn_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ zenn_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ zenn_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # Amazon Best Sellers Trends キャッシュメソッド
    def save_amazon_trends_to_cache(self, data):
        """Amazon Best Sellers Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM amazon_trends_cache")
                    conn.commit()
                logger.info(f"✅ amazon_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ amazon_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ amazon_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # eBay Trends キャッシュメソッド
    def save_ebay_trends_to_cache(self, data, category='electronics'):
        """eBay Popular/Trending Trendsデータをキャッシュに保存（カテゴリ対応）"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # カテゴリ別に削除
                    cursor.execute("DELETE FROM ebay_trends_cache WHERE category = %s", (category,))
                    for item in data:
                        cursor.execute("""
                            INSERT INTO ebay_trends_cache 
                            (title, url, item_id, price, currency, image_url, condition, seller, shipping, rank, category, published_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item.get('title', ''),
                            item.get('url', ''),
                            item.get('item_id'),
                            item.get('price'),
                            item.get('currency', 'USD'),
                            item.get('image_url'),
                            item.get('condition'),
                            item.get('seller'),
                            item.get('shipping'),
                            item.get('rank', 0),
                            item.get('category', category),
                            item.get('published_date')
                        ))
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('ebay_trends', now_jst, len(data), now_jst, len(data))
                    )
                    conn.commit()
                    logger.info(f"✅ ebay_trendsキャッシュを保存しました (category: {category}, {len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ ebay_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ ebay_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False

    def get_ebay_trends_from_cache(self, category='electronics'):
        """eBay Popular/Trending Trendsデータをキャッシュから取得（カテゴリ対応）"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, item_id, price, currency, image_url, condition, seller, shipping, rank, category, published_date, cached_at
                    FROM ebay_trends_cache 
                    WHERE category = %s
                    ORDER BY rank
                    LIMIT 50
                """, (category,))
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    result.append(row_dict)
                return result
        return self._execute_with_retry(query_func)

    def clear_ebay_trends_cache(self, category=None):
        """eBay Popular/Trending Trendsキャッシュをクリア（カテゴリ対応）"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if category:
                        cursor.execute("DELETE FROM ebay_trends_cache WHERE category = %s", (category,))
                        logger.info(f"✅ ebay_trendsのキャッシュをクリアしました (category: {category})")
                    else:
                        cursor.execute("DELETE FROM ebay_trends_cache")
                        logger.info(f"✅ ebay_trendsのキャッシュをクリアしました（全カテゴリ）")
                    conn.commit()
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ ebay_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ ebay_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # Medium Trends キャッシュメソッド
    def save_medium_trends_to_cache(self, data):
        """Medium Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM medium_trends_cache")
                    for item in data:
                        cursor.execute("""
                        INSERT INTO medium_trends_cache 
                        (title, url, slug, published_date, description, author, rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('slug'),
                        item.get('published_date'),
                        item.get('description', ''),
                        item.get('author', ''),
                        item.get('rank', 0)
                    ))
                    
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('medium_trends', now_jst, len(data), now_jst, len(data))
                    )
                    conn.commit()
                    logger.info(f"✅ medium_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            # 接続エラーの場合
            error_str = str(e)
            if "cursor already closed" in error_str.lower() or "server closed the connection" in error_str or "connection" in error_str.lower() or "closed" in error_str.lower():
                logger.warning(f"⚠️ medium_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
                # 接続エラーの場合は接続をリセット（次回のget_connection()で再接続される）
                self.connection = None
            else:
                # 接続エラー以外のデータベースエラー
                logger.error(f"❌ medium_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
        except RuntimeError as e:
            # コンテキストマネージャーのエラー（generator didn't stop after throw()など）
            if "generator didn't stop" in str(e):
                logger.warning(f"⚠️ medium_trendsキャッシュ保存中にコンテキストマネージャーエラーが発生: {e}", exc_info=True)
            else:
                logger.error(f"❌ medium_trendsキャッシュ保存エラー: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"❌ medium_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_medium_trends_from_cache(self):
        """Medium Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT title, url, slug, published_date, description, author, rank, cached_at
                    FROM medium_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    result.append(row_dict)
                return result
        return self._execute_with_retry(query_func)

    def clear_medium_trends_cache(self):
        """Medium Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM medium_trends_cache")
                    conn.commit()
                logger.info(f"✅ medium_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ medium_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ medium_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # DEV.to Trends キャッシュメソッド
    def save_devto_trends_to_cache(self, data):
        """DEV.to Trendsデータをキャッシュに保存"""
        if not data:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM devto_trends_cache")
                    for item in data:
                        # tagsを文字列として保存（JSON形式）
                        tags_str = ', '.join(item.get('tags', [])) if isinstance(item.get('tags'), list) else str(item.get('tags', ''))
                        cursor.execute("""
                        INSERT INTO devto_trends_cache 
                        (article_id, title, url, canonical_url, description, published_at, published_date, 
                         positive_reactions_count, comments_count, reading_time_minutes, tags, author, rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('id'),
                        item.get('title', ''),
                        item.get('url', ''),
                        item.get('canonical_url', ''),
                        item.get('description', ''),
                        item.get('published_at'),
                        item.get('published_date'),
                        item.get('positive_reactions_count', 0),
                        item.get('comments_count', 0),
                        item.get('reading_time_minutes', 0),
                        tags_str,
                        item.get('author', ''),
                        item.get('rank', 0)
                    ))
                    
                    import pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    now_jst = datetime.now(jst)
                    cursor.execute(
                        "INSERT INTO cache_status (cache_key, last_updated, data_count) VALUES (%s, %s, %s) ON CONFLICT (cache_key) DO UPDATE SET last_updated = %s, data_count = %s",
                        ('devto_trends', now_jst, len(data), now_jst, len(data))
                    )
                    conn.commit()
                    logger.info(f"✅ devto_trendsキャッシュを保存しました ({len(data)}件)")
                    return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ devto_trendsキャッシュ保存中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ devto_trendsキャッシュ保存エラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    def get_devto_trends_from_cache(self):
        """DEV.to Trendsデータをキャッシュから取得"""
        def query_func(conn):
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT article_id, title, url, canonical_url, description, published_at, published_date,
                           positive_reactions_count, comments_count, reading_time_minutes, tags, author, rank, cached_at
                    FROM devto_trends_cache 
                    ORDER BY rank
                    LIMIT 50
                """)
                data = cursor.fetchall()
                result = []
                for row in data:
                    row_dict = dict(row)
                    if row_dict.get('published_date'):
                        if isinstance(row_dict['published_date'], datetime):
                            row_dict['published_date'] = row_dict['published_date'].isoformat()
                    # tagsをリストに変換
                    if row_dict.get('tags'):
                        if isinstance(row_dict['tags'], str):
                            row_dict['tags'] = [tag.strip() for tag in row_dict['tags'].split(',') if tag.strip()]
                        else:
                            row_dict['tags'] = []
                    else:
                        row_dict['tags'] = []
                    result.append(row_dict)
                return result
        return self._execute_with_retry(query_func)

    def clear_devto_trends_cache(self):
        """DEV.to Trendsキャッシュをクリア"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM devto_trends_cache")
                    conn.commit()
                logger.info(f"✅ devto_trendsのキャッシュをクリアしました")
                return True
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"⚠️ devto_trendsキャッシュクリア中に接続エラーが発生: {e}", exc_info=True)
            self.connection = None
            return False
        except Exception as e:
            logger.error(f"❌ devto_trendsキャッシュクリアエラー: {e}", exc_info=True)
            try:
                conn.rollback()
            except:
                pass
            return False

    # Note Trends キャッシュメソッド（カテゴリ対応）
    def save_note_trends_to_cache(self, data, category='all'):
        """Note Trendsデータをキャッシュに保存（カテゴリ別）"""
        return self.save_to_cache(data, 'note_trends', category)
    
    def get_note_trends_from_cache(self, category='all'):
        """Note Trendsデータをキャッシュから取得（カテゴリ別）"""
        return self.get_from_cache('note_trends', category)
    
    def clear_note_trends_cache(self, category='all'):
        """Note Trendsキャッシュをクリア（カテゴリ別）"""
        return self.clear_cache('note_trends', category)
    
    def is_note_cache_valid(self, category='all'):
        """Note Trendsキャッシュが有効かどうかを確認"""
        return self.is_cache_valid('note_trends', category, 24)

    def close(self):
        """データベース接続を閉じる"""
        if self.connection:
            self.connection.close()
            logger.info("✅ データベース接続を閉じました")
