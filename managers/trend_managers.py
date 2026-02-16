"""
トレンドマネージャーの初期化
各トレンドマネージャーのインスタンスを作成・管理
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import threading
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
from services.trends.wikipedia_trends import WikipediaTrendsManager
from services.trends.prtimes_trends import PRTimesTrendsManager
from services.trends.prtimes_hatena_trends import PRTimesHatenaTrendsManager
from services.trends.globenewswire_trends import GlobeNewswireTrendsManager
from services.trends.globenewswire_market_reaction_trends import GlobeNewswireMarketReactionTrendsManager
from services.trends.estat_trends import EstatTrendsManager
from services.trends.kkj_trends import KKJTrendsManager
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
    ('wikipedia', WikipediaTrendsManager, 'Wikipedia'),
    ('prtimes', PRTimesTrendsManager, 'PR TIMES'),
    ('prtimes_hatena', PRTimesHatenaTrendsManager, 'PR TIMES × はてブ'),
    ('globenewswire', GlobeNewswireTrendsManager, 'GlobeNewswire'),
    ('globenewswire_market_reaction', GlobeNewswireMarketReactionTrendsManager, 'GlobeNewswire × Market'),
    ('estat', EstatTrendsManager, 'e-Stat'),
    ('kkj', KKJTrendsManager, '官公需'),
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
    並列実行により実行時間を短縮します。

    Args:
        managers (dict): initialize_managers で生成されたマネージャー辞書
        force_refresh (bool): キャッシュを無視して取得するかどうか

    Returns:
        dict: 各カテゴリの更新結果
    """
    results = {}
    results_lock = threading.Lock()

    def call_manager(key, handler, region='JP'):
        """マネージャーを呼び出して結果を返す（並列実行用）"""
        manager = managers.get(key)
        if not manager:
            return f"{key}_{region}", {
                'success': False,
                'error': 'manager_not_initialized'
            }
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
            return f"{key}_{region}", {
                'success': success,
                'response': response
            }
        except Exception as exc:
            logger.error(f"❌ トレンド取得エラー ({key}_{region}): {exc}", exc_info=True)
            return f"{key}_{region}", {
                'success': False,
                'error': str(exc)
            }

    # タスクリストを作成
    tasks = []

    # 日本のデータを更新するタスク
    logger.info("🇯🇵 日本のデータを更新中（並列実行）...")
    tasks.append(('google', lambda m: m.get_trends('JP', force_refresh=force_refresh), 'JP'))
    tasks.append(('youtube', lambda m: m.get_trends('JP', force_refresh=force_refresh), 'JP'))
    tasks.append(('music', lambda m: m.get_trends('spotify', 'JP', force_refresh=force_refresh), 'JP'))
    tasks.append(('worldnews', lambda m: m.get_trends(country='jp', category=None, force_refresh=force_refresh), 'JP'))
    tasks.append(('podcast', lambda m: m.get_trends('best_podcasts', region='jp', force_refresh=force_refresh), 'JP'))
    tasks.append(('rakuten', lambda m: m.get_trends(force_refresh=force_refresh, fetch_all_categories=True), 'JP'))
    tasks.append(('hatena', lambda m: m.get_trends(category='all', limit=25, force_refresh=force_refresh, fetch_all_categories=True), 'JP'))
    if os.getenv('TWITCH_CLIENT_ID') and os.getenv('TWITCH_CLIENT_SECRET'):
        tasks.append(('twitch', lambda m: m._fetch_and_cache_all_categories(), 'JP'))
    else:
        logger.info("⚠️ Twitch: 認証情報未設定のためスキップ (TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)")
    tasks.append(('qiita', lambda m: m.get_trends(limit=25, sort='likes_count', force_refresh=force_refresh), 'JP'))
    tasks.append(('nhk', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('prtimes', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('prtimes_hatena', lambda m: m.get_trends(limit=5, force_refresh=force_refresh), 'JP'))
    tasks.append(('stock', lambda m: m.get_trends(market='JP', limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('movie', lambda m: m.get_trends(country='JP', time_window='day', limit=25, force_refresh=force_refresh), 'JP'))
    # Book: 全カテゴリをキャッシュ（総合・文芸・ビジネス・人文・社会・実用・IT）
    for cat in ('all', 'fiction', 'business', 'humanities', 'practical'):
        def book_jp_handler(m, category=cat):
            return m.get_trends(country='JP', limit=25, force_refresh=force_refresh, category=category)
        tasks.append(('book', book_jp_handler, 'JP'))
    tasks.append(('github', lambda m: m.get_trends(language='all', limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('appstore', lambda m: m.get_trends(country='JP', category='all', limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('ipa', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('jpcert', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('zenn', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'JP'))
    tasks.append(('note', lambda m: m.get_trends(category='all', limit=25, force_refresh=force_refresh, fetch_all_categories=True), 'JP'))
    tasks.append(('wikipedia', lambda m: m.get_trends(lang='ja', limit=25, force_refresh=force_refresh), 'JP'))

    # USのデータを更新するタスク
    logger.info("🇺🇸 USのデータを更新中（並列実行）...")
    tasks.append(('google', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US'))
    tasks.append(('youtube', lambda m: m.get_trends('US', force_refresh=force_refresh), 'US'))
    tasks.append(('music', lambda m: m.get_trends('spotify', 'US', force_refresh=force_refresh), 'US'))
    tasks.append(('worldnews', lambda m: m.get_trends(country='us', category=None, force_refresh=force_refresh), 'US'))
    tasks.append(('podcast', lambda m: m.get_trends('best_podcasts', region='us', force_refresh=force_refresh), 'US'))
    if os.getenv('TWITCH_CLIENT_ID') and os.getenv('TWITCH_CLIENT_SECRET'):
        tasks.append(('twitch', lambda m: m._fetch_and_cache_all_categories(), 'US'))
    # eBay: 全カテゴリーを取得してキャッシュに保存
    ebay_manager = managers.get('ebay')
    if ebay_manager:
        categories = ebay_manager.get_available_categories()
        for category in categories:
            def ebay_handler(m, cat=category):
                return m.get_trends(category=cat, limit=25, force_refresh=force_refresh)
            tasks.append(('ebay', ebay_handler, 'US'))
    # Redditは使用していないため無効化
    # tasks.append(('reddit', lambda m: m.get_trends('all', limit=25, time_filter='day', force_refresh=force_refresh), 'US'))
    tasks.append(('hackernews', lambda m: m.get_trends('top', limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('producthunt', lambda m: m.get_trends(limit=25, sort='votes', force_refresh=force_refresh), 'US'))
    tasks.append(('cnn', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('globenewswire', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('globenewswire_market_reaction', lambda m: m.get_trends(limit=15, force_refresh=force_refresh), 'US'))
    tasks.append(('stock', lambda m: m.get_trends(market='US', limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('crypto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('movie', lambda m: m.get_trends(country='US', time_window='day', limit=25, force_refresh=force_refresh), 'US'))
    # Book: 全カテゴリをキャッシュ（all, fiction, business, biography, science）
    for cat in ('all', 'fiction', 'business', 'biography', 'science'):
        def book_us_handler(m, category=cat):
            return m.get_trends(country='US', limit=25, force_refresh=force_refresh, category=category)
        tasks.append(('book', book_us_handler, 'US'))
    tasks.append(('github', lambda m: m.get_trends(language='all', limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('appstore', lambda m: m.get_trends(country='US', category='all', limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('cisa_kev', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('thehackernews', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('medium', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('devto', lambda m: m.get_trends(limit=25, force_refresh=force_refresh), 'US'))
    tasks.append(('wikipedia', lambda m: m.get_trends(lang='en', limit=25, force_refresh=force_refresh), 'US'))

    # 並列実行（最大20スレッド）
    max_workers = min(20, len(tasks))
    logger.info(f"🚀 {len(tasks)}件のタスクを{max_workers}スレッドで並列実行します")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # すべてのタスクを実行
        future_to_task = {
            executor.submit(call_manager, key, handler, region): (key, region)
            for key, handler, region in tasks
        }

        # 完了したタスクから結果を収集
        completed_count = 0
        for future in as_completed(future_to_task):
            key, region = future_to_task[future]
            completed_count += 1
            try:
                result_key, result_data = future.result()
                with results_lock:
                    results[result_key] = result_data
                logger.debug(f"✅ [{completed_count}/{len(tasks)}] {result_key} 完了")
            except Exception as exc:
                logger.error(f"❌ タスク実行エラー ({key}_{region}): {exc}", exc_info=True)
                with results_lock:
                    results[f"{key}_{region}"] = {
                        'success': False,
                        'error': str(exc)
                    }

    logger.info(f"✅ 並列実行完了: {len(results)}件の結果を取得しました")

    overall_success = all(result.get('success') for result in results.values())

    return {
        'success': overall_success,
        'results': results
    }



