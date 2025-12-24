"""
トレンドマネージャーの初期化
各トレンドマネージャーのインスタンスを作成・管理
"""

from services.trends.google_trends import GoogleTrendsManager
from services.trends.youtube_trends import YouTubeTrendsManager
from services.trends.music_trends import MusicTrendsManager
from services.trends.news_trends import NewsTrendsManager
from services.trends.worldnews_trends import WorldNewsTrendsManager
from services.trends.podcast_trends import PodcastTrendsManager
from services.trends.rakuten_trends import RakutenTrendsManager
from services.trends.hatena_trends import HatenaTrendsManager
from services.trends.twitch_trends import TwitchTrendsManager
from services.trends.reddit_trends import RedditTrendsManager
from services.trends.hackernews_trends import HackerNewsTrendsManager
from services.trends.qiita_trends import QiitaTrendsManager
from services.trends.producthunt_trends import ProductHuntTrendsManager
from services.trends.nhk_trends import NHKTrendsManager
from services.trends.cnn_trends import CNNTrendsManager
from services.trends.stock_trends import StockTrendsManager
from services.trends.crypto_trends import CryptoTrendsManager
from services.trends.movie_trends import MovieTrendsManager
from services.trends.book_trends import BookTrendsManager
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

# マネージャー設定リスト
MANAGER_CONFIGS = [
    ('google', GoogleTrendsManager, 'Google Trends'),
    ('youtube', YouTubeTrendsManager, 'YouTube'),
    ('music', MusicTrendsManager, 'Music'),
    ('news', NewsTrendsManager, 'News'),
    ('worldnews', WorldNewsTrendsManager, 'World News'),
    ('podcast', PodcastTrendsManager, 'Podcast'),
    ('rakuten', RakutenTrendsManager, 'Rakuten'),
    ('hatena', HatenaTrendsManager, 'Hatena'),
    ('twitch', TwitchTrendsManager, 'Twitch'),
    ('reddit', RedditTrendsManager, 'Reddit'),
    ('hackernews', HackerNewsTrendsManager, 'Hacker News'),
    ('qiita', QiitaTrendsManager, 'Qiita'),
    ('producthunt', ProductHuntTrendsManager, 'Product Hunt'),
    ('nhk', NHKTrendsManager, 'NHK'),
    ('cnn', CNNTrendsManager, 'CNN'),
    ('stock', StockTrendsManager, 'Stock'),
    ('crypto', CryptoTrendsManager, 'Crypto'),
    ('movie', MovieTrendsManager, 'Movie'),
    ('book', BookTrendsManager, 'Book'),
]


def _initialize_single_manager(key, manager_class, display_name):
    """
    単一のマネージャーを初期化
    
    Args:
        key: マネージャーのキー
        manager_class: マネージャークラス
        display_name: 表示名
    
    Returns:
        初期化されたマネージャーインスタンス、またはNone
    """
    try:
        manager = manager_class()
        logger.info(f"✅ {display_name} Manager初期化完了")
        return manager
    except Exception as e:
        logger.error(f"❌ {display_name} Manager初期化エラー: {e}", exc_info=True)
        return None


def initialize_managers():
    """
    全トレンドマネージャーを初期化
    一部のマネージャーが失敗しても、成功したマネージャーは返す
    
    Returns:
        dict: 初期化されたマネージャーの辞書（失敗したものはNoneまたは含まれない）
    """
    managers = {}
    success_count = 0
    fail_count = 0
    
    for key, manager_class, display_name in MANAGER_CONFIGS:
        manager = _initialize_single_manager(key, manager_class, display_name)
        if manager is not None:
            managers[key] = manager
            success_count += 1
        else:
            fail_count += 1
            logger.warning(f"⚠️ {display_name} Managerの初期化に失敗しましたが、続行します")
    
    logger.info(f"✅ マネージャー初期化完了: 成功{success_count}個、失敗{fail_count}個")
    return managers


def refresh_all_trends(managers, force_refresh=True):
    """
    すべてのトレンドカテゴリを強制更新するユーティリティ関数
    日本（JP）と米国（US）の両方のデータを更新します
    
    Args:
        managers (dict): initialize_managers で生成されたマネージャー辞書
        force_refresh (bool): キャッシュを無視して取得するかどうか
    
    Returns:
        dict: 各カテゴリの更新結果
    """
    results = {}
    
    def call_manager(key, handler, region='JP'):
        """マネージャーを呼び出して結果を記録"""
        manager = managers.get(key)
        if not manager:
            results[f"{key}_{region}"] = {
                'success': False,
                'error': 'manager_not_initialized'
            }
            return
        try:
            response = handler(manager)
            success = False
            if isinstance(response, dict):
                if 'success' in response:
                    success = bool(response.get('success'))
                elif 'data' in response:
                    data = response.get('data')
                    success = bool(data)
                else:
                    success = True
            else:
                success = response is not None
            results[f"{key}_{region}"] = {
                'success': success,
                'response': response
            }
        except Exception as exc:
            results[f"{key}_{region}"] = {
                'success': False,
                'error': str(exc)
            }
    
    # 日本のデータを更新
    logger.info("🇯🇵 日本のデータを更新中...")
    call_manager('google', lambda m: m.get_trends('JP', force_refresh=force_refresh), 'JP')
    call_manager('youtube', lambda m: m.get_trends('JP', force_refresh=force_refresh), 'JP')
    call_manager('music', lambda m: m.get_trends('spotify', 'JP', force_refresh=force_refresh), 'JP')
    call_manager('news', lambda m: m.get_trends(country='jp', category='general', force_refresh=force_refresh), 'JP')
    call_manager('worldnews', lambda m: m.get_trends(country='jp', category=None, force_refresh=force_refresh), 'JP')
    call_manager('podcast', lambda m: m.get_trends('best_podcasts', region='jp', force_refresh=force_refresh), 'JP')
    call_manager('rakuten', lambda m: m.get_trends(force_refresh=force_refresh), 'JP')
    call_manager('hatena', lambda m: m.get_trends(category='all', limit=25, force_refresh=force_refresh, fetch_all_categories=True), 'JP')
    call_manager('twitch', lambda m: m.get_trends(category='games', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('qiita', lambda m: m.get_trends(limit=25, sort='likes_count', force_refresh=force_refresh), 'JP')
    call_manager('nhk', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('stock', lambda m: m.get_trends(market='JP', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('movie', lambda m: m.get_trends(country='JP', time_window='day', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('book', lambda m: m.get_trends(country='JP', limit=25, force_refresh=force_refresh), 'JP')
    
    # USのデータを更新
    logger.info("🇺🇸 USのデータを更新中...")
    call_manager('google', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US')
    call_manager('youtube', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US')
    call_manager('music', lambda m: m.get_trends('spotify', 'US', force_refresh=force_refresh), 'US')
    call_manager('worldnews', lambda m: m.get_trends(country='us', category=None, force_refresh=force_refresh), 'US')
    call_manager('podcast', lambda m: m.get_trends('best_podcasts', region='us', force_refresh=force_refresh), 'US')
    call_manager('twitch', lambda m: m.get_trends(category='games', limit=25, force_refresh=force_refresh), 'US')
    call_manager('reddit', lambda m: m.get_trends('all', limit=25, time_filter='day', force_refresh=force_refresh), 'US')
    call_manager('hackernews', lambda m: m.get_trends('top', limit=25, force_refresh=force_refresh), 'US')
    call_manager('producthunt', lambda m: m.get_trends(limit=25, sort='votes', force_refresh=force_refresh), 'US')
    call_manager('cnn', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('stock', lambda m: m.get_trends(market='US', limit=25, force_refresh=force_refresh), 'US')
    call_manager('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('movie', lambda m: m.get_trends(country='US', time_window='day', limit=25, force_refresh=force_refresh), 'US')
    call_manager('book', lambda m: m.get_trends(country='US', limit=25, force_refresh=force_refresh), 'US')
    
    overall_success = all(result.get('success') for result in results.values())
    
    return {
        'success': overall_success,
        'results': results
    }

