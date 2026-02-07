"""
GlobeNewswire トレンドマネージャー（US向け）
公式RSSを利用。件数制限・リンクアウトのみ（再配信しない）。
"""

import requests
from datetime import datetime

import feedparser
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# GlobeNewswire 公式ATOM（Public Companies - 上場企業ニュース）
# RssFeed は404のため AtomFeed を使用（feedparser は両方対応）
# https://www.globenewswire.com/Rss/List で公開されている公式フィード
DEFAULT_RSS_URL = (
    "https://www.globenewswire.com/AtomFeed/orgclass/1/"
    "feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies"
)


class GlobeNewswireTrendsManager(BaseTrendsManager):
    """GlobeNewswire 公式RSSからプレスリリーストレンドを取得・管理するクラス"""

    def __init__(self):
        super().__init__(service_name='globenewswire', max_requests=6, window_seconds=60)
        self.rss_url = DEFAULT_RSS_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrendDashboard/1.0 (trend detection; link-out only)',
            'Accept': 'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        logger.info("GlobeNewswire Trends Manager初期化（公式RSS利用）")

    def _get_cache_key(self, *args, **kwargs):
        return 'globenewswire_trends'

    def _get_from_cache(self, *args, **kwargs):
        try:
            return self.db.get_globenewswire_trends_from_cache() or []
        except Exception as e:
            logger.error(f"❌ GlobeNewswire: キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data, *args, **kwargs):
        try:
            return self.db.save_globenewswire_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ GlobeNewswire キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        try:
            return self.db.clear_globenewswire_trends_cache()
        except Exception as e:
            logger.error(f"❌ GlobeNewswire キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ GlobeNewswire: cache_status更新エラー: {e}")
            return False

    def _parse_feed(self):
        """公式RSSを取得してエントリ一覧を返す"""
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(self.rss_url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"GlobeNewswire RSS status: {resp.status_code}")
                return []
            parsed = feedparser.parse(resp.content)
            items = []
            for e in parsed.entries:
                link = e.get('link') or (e.get('links') or [{}])[0].get('href') or ''
                title = (e.get('title') or '').strip()
                if not link or not title:
                    continue
                published = None
                for key in ('published', 'updated', 'created'):
                    val = e.get(key)
                    if val:
                        try:
                            if hasattr(val, 'timestamp'):
                                published = datetime.utcfromtimestamp(val.timestamp()).isoformat() + 'Z'
                            else:
                                published = val
                            break
                        except Exception:
                            published = val
                            break
                description = (e.get('summary') or e.get('description') or '')
                if hasattr(description, 'strip'):
                    description = description.strip()[:500] if description else ''
                # RSSのそのままの形: entry.tags（category）を付与
                tags = []
                for t in (getattr(e, 'tags', None) or []):
                    if isinstance(t, dict):
                        tags.append({'term': t.get('term'), 'scheme': t.get('scheme'), 'label': t.get('label')})
                    else:
                        tags.append({
                            'term': getattr(t, 'term', None),
                            'scheme': getattr(t, 'scheme', None),
                            'label': getattr(t, 'label', None),
                        })
                items.append({
                    'title': title,
                    'url': link,
                    'published_date': published,
                    'description': description or '',
                    'tags': tags,
                })
            return items
        except Exception as e:
            logger.warning(f"GlobeNewswire RSS取得エラー: {e}")
            return []

    def get_trends(self, limit=25, force_refresh=False):
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,
            sort_key='published_date',
            sort_reverse=True,
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
        """公式RSSからトレンドデータを取得"""
        try:
            logger.info("GlobeNewswire: 公式RSS取得開始")
            items = self._parse_feed()
            if not items:
                logger.warning("GlobeNewswire: 取得件数0")
                return {
                    'success': False,
                    'error': 'GlobeNewswire RSSで記事を取得できませんでした',
                    'data': [],
                }
            items.sort(key=lambda x: (x.get('published_date') or ''), reverse=True)
            formatted = items[:limit]
            for i, item in enumerate(formatted, 1):
                item['rank'] = i
            logger.info(f"✅ GlobeNewswire: {len(formatted)}件取得")
            return {
                'success': True,
                'data': formatted,
                'status': 'api_fetched',
                'source': 'globenewswire_rss',
                'total_count': len(formatted),
            }
        except requests.exceptions.Timeout:
            logger.error("❌ GlobeNewswire タイムアウト", exc_info=True)
            return {'success': False, 'error': 'GlobeNewswire からの応答がタイムアウトしました', 'data': []}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ GlobeNewswire リクエストエラー: {e}", exc_info=True)
            return {'success': False, 'error': f'GlobeNewswire リクエストエラー: {str(e)}', 'data': []}
        except Exception as e:
            logger.error(f"❌ GlobeNewswire 取得エラー: {e}", exc_info=True)
            return {'success': False, 'error': f'GlobeNewswire 取得に失敗しました: {str(e)}', 'data': []}
