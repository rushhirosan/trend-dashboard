import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class ZennTrendsManager:
    """Zennトレンド管理クラス（RSSフィード使用: 最新/人気のフォールバック含む）"""

    def __init__(self):
        """初期化"""
        # 既知のRSS候補（公開状況によりエントリが得られない場合があるため複数用意）
        self.rss_urls = [
            "https://zenn.dev/feed",
        ]
        self.db = TrendsCache()
        self.rate_limiter = get_rate_limiter('zenn', max_requests=10, window_seconds=60)

        logger.info("Zenn Trends Manager初期化:")
        logger.info(f"  RSS URLs: {self.rss_urls}")

    def get_trends(self, limit=25, force_refresh=False):
        """Zennトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info("🔄 Zenn force_refresh: キャッシュをクリアします")
                self.db.clear_zenn_trends_cache()

            cached_data = self.db.get_zenn_trends_from_cache()
            if cached_data:
                cached_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                logger.info(f"✅ Zenn: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                if not force_refresh:
                    logger.warning("⚠️ Zenn: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                logger.warning("⚠️ Zenn: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_zenn_trends(limit)

        except Exception as e:
            logger.error(f"❌ Zenn トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Zennトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def _fetch_zenn_trends(self, limit=25):
        """Zenn RSSフィードからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            entries = []
            for rss_url in self.rss_urls:
                try:
                    logger.info(f"Zenn RSS呼び出し開始: {rss_url}")
                    feed = feedparser.parse(rss_url)
                    if feed.entries:
                        entries = feed.entries
                        logger.info(f"✅ Zenn RSS: {len(entries)}件のエントリーを取得")
                        break
                    else:
                        logger.warning(f"⚠️ Zenn RSS({rss_url}): エントリーが見つかりませんでした")
                except requests.exceptions.Timeout:
                    logger.warning(f"❌ Zenn RSS({rss_url}) タイムアウト")
                except Exception as e:
                    logger.warning(f"❌ Zenn RSS({rss_url}) エラー: {e}")

            if not entries:
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'zenn_rss'
                }

            formatted_data = []
            for i, entry in enumerate(entries[:limit], 1):
                try:
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except Exception:
                            published_date = datetime.now()
                    elif hasattr(entry, 'published'):
                        try:
                            from email.utils import parsedate_to_datetime
                            published_date = parsedate_to_datetime(entry.published)
                        except Exception:
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()

                    description = ''
                    if hasattr(entry, 'description'):
                        description = entry.description
                    elif hasattr(entry, 'summary'):
                        description = entry.summary

                    formatted_data.append({
                        'rank': i,
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description,
                        'author': entry.get('author', ''),
                        'source': 'Zenn'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Zenn エントリーパースエラー: {e}")
                    continue

            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_zenn_trends_to_cache(final_data)
                self.db.update_cache_status('zenn_trends', len(final_data))

            logger.info(f"✅ Zenn: {len(final_data)}件の記事を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'zenn_rss',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Zenn RSS タイムアウトエラー", exc_info=True)
            return {'error': 'Zenn RSS タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Zenn RSS エラー: {e}", exc_info=True)
            return {'error': f'Zenn RSS取得エラー: {str(e)}', 'success': False}


