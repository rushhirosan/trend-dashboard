"""
PR TIMES トレンドマネージャー（日本向け）
カテゴリページに紐づく公式RSSを取得。件数制限・リンクアウトのみ（再配信しない）。
"""

import requests
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

import feedparser
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# トレンド用に利用するPR TIMESカテゴリページ（ここからRSS URLを取得）
# 公式RSSは一覧化されていないが、カテゴリ／特集ページの <link rel="alternate" type="application/rss+xml"> で配信されている
DEFAULT_CATEGORY_PAGE_URLS = [
    "https://prtimes.jp/technology/",   # テクノロジー
    "https://prtimes.jp/business/",     # ビジネス
]


class PRTimesTrendsManager(BaseTrendsManager):
    """PR TIMES カテゴリRSSからプレスリリーストレンドを取得・管理するクラス"""

    def __init__(self):
        super().__init__(service_name='prtimes', max_requests=6, window_seconds=60)
        self.category_page_urls = DEFAULT_CATEGORY_PAGE_URLS
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrendDashboard/1.0 (trend detection; link-out only)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en;q=0.9',
        })
        logger.info("PR TIMES Trends Manager初期化（カテゴリRSS利用）")

    def _get_cache_key(self, *args, **kwargs):
        return 'prtimes_trends'

    def _get_from_cache(self, *args, **kwargs):
        try:
            return self.db.get_prtimes_trends_from_cache() or []
        except Exception as e:
            logger.error(f"❌ PR TIMES: キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data, *args, **kwargs):
        try:
            return self.db.save_prtimes_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ PR TIMES キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        try:
            return self.db.clear_prtimes_trends_cache()
        except Exception as e:
            logger.error(f"❌ PR TIMES キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ PR TIMES: cache_status更新エラー: {e}")
            return False

    def _discover_rss_url(self, category_page_url):
        """カテゴリページのHTMLから rel=\"alternate\" type=\"application/rss+xml\" のhrefを取得"""
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(category_page_url, timeout=10)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, 'html.parser')
            link = soup.find('link', rel='alternate', type='application/rss+xml')
            if not link or not link.get('href'):
                return None
            href = link['href'].strip()
            if not href:
                return None
            return urljoin(category_page_url, href)
        except Exception as e:
            logger.warning(f"⚠️ PR TIMES RSS URL取得エラー ({category_page_url}): {e}")
            return None

    def _parse_rss_feed(self, rss_url):
        """RSS/Atom URLを取得してエントリ一覧を返す"""
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(rss_url, timeout=10)
            if resp.status_code != 200:
                return []
            parsed = feedparser.parse(resp.content)
            if getattr(parsed, 'bozo', False) and not parsed.entries:
                logger.debug(f"PR TIMES feed parse warning: {rss_url}")
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
            logger.warning(f"⚠️ PR TIMES RSS取得エラー ({rss_url}): {e}")
            return []

    def _remove_duplicates(self, items):
        seen_urls = set()
        unique = []
        for item in items:
            url = (item.get('url') or '').strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if (item.get('title') or '').strip():
                unique.append(item)
        return unique

    def get_trends(self, limit=25, force_refresh=False):
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,
            sort_key='published_date',
            sort_reverse=True,
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
        """カテゴリページからRSS URLを取得し、RSSを取得してトレンドデータを返す"""
        try:
            logger.info("PR TIMES: カテゴリRSS取得開始")
            all_items = []
            seen_rss_urls = set()

            for page_url in self.category_page_urls:
                rss_url = self._discover_rss_url(page_url)
                if not rss_url or rss_url in seen_rss_urls:
                    continue
                seen_rss_urls.add(rss_url)
                items = self._parse_rss_feed(rss_url)
                all_items.extend(items)
                logger.info(f"  {page_url} -> {len(items)}件")

            if not all_items:
                logger.warning("PR TIMES: 取得件数0")
                return {
                    'success': False,
                    'error': 'PR TIMES RSSで記事を取得できませんでした',
                    'data': [],
                }

            unique = self._remove_duplicates(all_items)
            unique.sort(key=lambda x: (x.get('published_date') or ''), reverse=True)
            formatted = unique[:limit]
            for i, item in enumerate(formatted, 1):
                item['rank'] = i

            logger.info(f"✅ PR TIMES: {len(formatted)}件取得")
            return {
                'success': True,
                'data': formatted,
                'status': 'api_fetched',
                'source': 'prtimes_rss',
                'total_count': len(formatted),
            }
        except requests.exceptions.Timeout:
            logger.error("❌ PR TIMES タイムアウト", exc_info=True)
            return {'success': False, 'error': 'PR TIMES からの応答がタイムアウトしました', 'data': []}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ PR TIMES リクエストエラー: {e}", exc_info=True)
            return {'success': False, 'error': f'PR TIMES リクエストエラー: {str(e)}', 'data': []}
        except Exception as e:
            logger.error(f"❌ PR TIMES 取得エラー: {e}", exc_info=True)
            return {'success': False, 'error': f'PR TIMES 取得に失敗しました: {str(e)}', 'data': []}
