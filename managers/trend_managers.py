"""
トレンドマネージャーの初期化
各トレンドマネージャーのインスタンスを作成・管理
"""

from services.trends.google_trends import GoogleTrendsManager
from services.trends.youtube_trends import YouTubeTrendsManager
from services.trends.music_trends import MusicTrendsManager
from services.trends.worldnews_trends import WorldNewsTrendsManager
from services.trends.podcast_trends import PodcastTrendsManager
from services.trends.rakuten_trends import RakutenTrendsManager
from services.trends.hatena_trends import HatenaTrendsManager
from services.trends.twitch_trends import TwitchTrendsManager
# Redditは使用していないため無効化
# from services.trends.reddit_trends import RedditTrendsManager
from services.trends.hackernews_trends import HackerNewsTrendsManager
from services.trends.qiita_trends import QiitaTrendsManager
from services.trends.producthunt_trends import ProductHuntTrendsManager
from services.trends.nhk_trends import NHKTrendsManager
from services.trends.cnn_trends import CNNTrendsManager
from services.trends.stock_trends import StockTrendsManager
from services.trends.crypto_trends import CryptoTrendsManager
from services.trends.movie_trends import MovieTrendsManager
from services.trends.book_trends import BookTrendsManager
from services.trends.github_trends import GitHubTrendsManager
from services.trends.appstore_trends import AppStoreTrendsManager
from services.trends.cisa_kev_trends import CISAKEVTrendsManager
from services.trends.thehackernews_trends import TheHackerNewsTrendsManager
from services.trends.ipa_trends import IPATrendsManager
from services.trends.jpcert_trends import JPCERTTrendsManager
from services.trends.hackernoon_trends import HackerNoonTrendsManager
from services.trends.zenn_trends import ZennTrendsManager
from services.trends.note_trends import NoteTrendsManager
from services.trends.ebay_trends import eBayTrendsManager
from services.trends.medium_trends import MediumTrendsManager
from services.trends.devto_trends import DevToTrendsManager
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

# マネージャー設定リスト
MANAGER_CONFIGS = [
    ('google', GoogleTrendsManager, 'Google Trends'),
    ('youtube', YouTubeTrendsManager, 'YouTube'),
    ('music', MusicTrendsManager, 'Music'),
    ('worldnews', WorldNewsTrendsManager, 'World News'),
    ('podcast', PodcastTrendsManager, 'Podcast'),
    ('rakuten', RakutenTrendsManager, 'Rakuten'),
    ('hatena', HatenaTrendsManager, 'Hatena'),
    ('twitch', TwitchTrendsManager, 'Twitch'),
    # Redditは使用していないため無効化
    # ('reddit', RedditTrendsManager, 'Reddit'),
    ('hackernews', HackerNewsTrendsManager, 'Hacker News'),
    ('qiita', QiitaTrendsManager, 'Qiita'),
    ('producthunt', ProductHuntTrendsManager, 'Product Hunt'),
    ('nhk', NHKTrendsManager, 'NHK'),
    ('cnn', CNNTrendsManager, 'CNN'),
    ('stock', StockTrendsManager, 'Stock'),
    ('crypto', CryptoTrendsManager, 'Crypto'),
    ('movie', MovieTrendsManager, 'Movie'),
    ('book', BookTrendsManager, 'Book'),
    ('github', GitHubTrendsManager, 'GitHub'),
    ('appstore', AppStoreTrendsManager, 'App Store'),
    ('cisa_kev', CISAKEVTrendsManager, 'CISA KEV'),
    ('thehackernews', TheHackerNewsTrendsManager, 'The Hacker News'),
    ('ipa', IPATrendsManager, 'IPA'),
    ('jpcert', JPCERTTrendsManager, 'JPCERT/CC'),
    ('hackernoon', HackerNoonTrendsManager, 'Hacker Noon'),
    ('zenn', ZennTrendsManager, 'Zenn'),
    ('note', NoteTrendsManager, 'Note'),
    ('ebay', eBayTrendsManager, 'eBay Popular/Trending'),
    ('medium', MediumTrendsManager, 'Medium'),
    ('devto', DevToTrendsManager, 'DEV.to'),
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
        logger.info(f"🔄 {display_name} Manager初期化開始 (key: {key})")
        manager = manager_class()
        logger.info(f"✅ {display_name} Manager初期化完了")
        return manager
    except Exception as e:
        logger.error(f"❌ {display_name} Manager初期化エラー: {type(e).__name__}: {e}", exc_info=True)
        logger.warning(f"⚠️ {display_name} Manager ({key}) の初期化に失敗しました: {str(e)}")
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
    call_manager('worldnews', lambda m: m.get_trends(country='jp', category=None, force_refresh=force_refresh), 'JP')
    call_manager('podcast', lambda m: m.get_trends('best_podcasts', region='jp', force_refresh=force_refresh), 'JP')
    call_manager('rakuten', lambda m: m.get_trends(force_refresh=force_refresh), 'JP')
    call_manager('hatena', lambda m: m.get_trends(category='all', limit=25, force_refresh=force_refresh, fetch_all_categories=True), 'JP')
    # Twitch: 全カテゴリーを取得してキャッシュに保存
    call_manager('twitch', lambda m: m._fetch_and_cache_all_categories(), 'JP')
    call_manager('qiita', lambda m: m.get_trends(limit=25, sort='likes_count', force_refresh=force_refresh), 'JP')
    call_manager('nhk', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('stock', lambda m: m.get_trends(market='JP', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('movie', lambda m: m.get_trends(country='JP', time_window='day', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('book', lambda m: m.get_trends(country='JP', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('github', lambda m: m.get_trends(language='all', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('appstore', lambda m: m.get_trends(country='JP', category='all', limit=25, force_refresh=force_refresh), 'JP')
    call_manager('ipa', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('jpcert', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('zenn', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP')
    call_manager('note', lambda m: m.get_trends(category='all', limit=25, force_refresh=force_refresh, fetch_all_categories=True), 'JP')
    
    # USのデータを更新
    logger.info("🇺🇸 USのデータを更新中...")
    call_manager('google', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US')
    call_manager('youtube', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US')
    call_manager('music', lambda m: m.get_trends('spotify', 'US', force_refresh=force_refresh), 'US')
    call_manager('worldnews', lambda m: m.get_trends(country='us', category=None, force_refresh=force_refresh), 'US')
    call_manager('podcast', lambda m: m.get_trends('best_podcasts', region='us', force_refresh=force_refresh), 'US')
    # Twitch: 全カテゴリーを取得してキャッシュに保存
    call_manager('twitch', lambda m: m._fetch_and_cache_all_categories(), 'US')
    # eBay: 全カテゴリーを取得してキャッシュに保存
    ebay_manager = managers.get('ebay')
    if ebay_manager:
        categories = ebay_manager.get_available_categories()
        for category in categories:
            def ebay_handler(m, cat=category):
                return m.get_trends(category=cat, limit=25, force_refresh=force_refresh)
            call_manager('ebay', ebay_handler, 'US')
    # Redditは使用していないため無効化
    # call_manager('reddit', lambda m: m.get_trends('all', limit=25, time_filter='day', force_refresh=force_refresh), 'US')
    call_manager('hackernews', lambda m: m.get_trends('top', limit=25, force_refresh=force_refresh), 'US')
    call_manager('producthunt', lambda m: m.get_trends(limit=25, sort='votes', force_refresh=force_refresh), 'US')
    call_manager('cnn', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('stock', lambda m: m.get_trends(market='US', limit=25, force_refresh=force_refresh), 'US')
    call_manager('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('movie', lambda m: m.get_trends(country='US', time_window='day', limit=25, force_refresh=force_refresh), 'US')
    call_manager('book', lambda m: m.get_trends(country='US', limit=25, force_refresh=force_refresh), 'US')
    call_manager('github', lambda m: m.get_trends(language='all', limit=25, force_refresh=force_refresh), 'US')
    call_manager('appstore', lambda m: m.get_trends(country='US', category='all', limit=25, force_refresh=force_refresh), 'US')
    call_manager('cisa_kev', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('thehackernews', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('medium', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    call_manager('devto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US')
    
    overall_success = all(result.get('success') for result in results.values())
    
    return {
        'success': overall_success,
        'results': results
    }



