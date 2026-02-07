"""
PR TIMES × はてなブックマーク トレンドマネージャー（ミニマル案）
PR TIMES RSS の直近7日分を取得し、はてなブックマーク一括Count APIで件数を取得。
ブクマ数 > 0 のみ残し、ブクマ数でソートして Top5 を返す。
"""

import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# はてなブックマーク 一括件数取得API（最大50URL/1リクエスト）
HATENA_COUNT_BATCH_URL = "http://api.b.st-hatena.com/entry.counts"
HATENA_BATCH_SIZE = 50

# PR TIMES カテゴリページ（RSS URL取得用）
# 全カテゴリ同一の index.rdf を指すが、将来的なカテゴリ別RSSに対応
DEFAULT_CATEGORY_PAGE_URLS = [
    "https://prtimes.jp/technology/",
    "https://prtimes.jp/business/",
    "https://prtimes.jp/entertainment/",
    "https://prtimes.jp/gourmet/",
    "https://prtimes.jp/app/",
    "https://prtimes.jp/lifestyle/",
]
DAYS_AGO = 7
TOP_N = 5


class PRTimesHatenaTrendsManager(BaseTrendsManager):
    """PR TIMES RSS × はてなブックマーク（7日以内・ブクマ数>0・Top5）"""

    def __init__(self):
        super().__init__(service_name='prtimes_hatena', max_requests=15, window_seconds=60)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrendDashboard/1.0 (trend detection; link-out only)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en;q=0.9',
        })
        logger.info("PR TIMES × はてブ Trends Manager初期化（一括Count API利用）")

    def _get_cache_key(self, *args, **kwargs):
        return 'prtimes_hatena_trends'

    def _get_from_cache(self, *args, **kwargs):
        try:
            return self.db.get_prtimes_hatena_trends_from_cache() or []
        except Exception as e:
            logger.error(f"❌ PR TIMES×はてブ: キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data, *args, **kwargs):
        try:
            return self.db.save_prtimes_hatena_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ PR TIMES×はてブ キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        try:
            return self.db.clear_prtimes_hatena_trends_cache()
        except Exception as e:
            logger.error(f"❌ PR TIMES×はてブ キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ PR TIMES×はてブ: cache_status更新エラー: {e}")
            return False

    def _discover_rss_url(self, category_page_url):
        """カテゴリページのHTMLから RSS URL を取得"""
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
            return urljoin(category_page_url, href) if href else None
        except Exception as e:
            logger.warning(f"⚠️ PR TIMES RSS URL取得エラー ({category_page_url}): {e}")
            return None

    def _parse_rss_feed(self, rss_url):
        """RSS を取得してエントリ一覧を返す"""
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(rss_url, timeout=10)
            if resp.status_code != 200:
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
                                published = datetime.utcfromtimestamp(val.timestamp())
                            else:
                                published = val
                            break
                        except Exception:
                            published = val
                            break
                if published is None:
                    continue
                if isinstance(published, str):
                    try:
                        from email.utils import parsedate_to_datetime
                        published = parsedate_to_datetime(published)
                    except Exception:
                        try:
                            s = published.replace('Z', '+00:00')[:19]
                            parsed = datetime.fromisoformat(s)
                            if getattr(parsed, 'tzinfo', None) is None:
                                parsed = parsed.replace(tzinfo=timezone.utc) if hasattr(parsed, 'replace') else datetime.combine(parsed, datetime.min.time()).replace(tzinfo=timezone.utc)
                            published = parsed
                        except Exception:
                            continue
                description = (e.get('summary') or e.get('description') or '')
                if hasattr(description, 'strip'):
                    description = description.strip()[:500] if description else ''
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
                    'published_date_iso': published.isoformat() if hasattr(published, 'isoformat') else str(published),
                    'description': description or '',
                    'tags': tags,
                })
            return items
        except Exception as e:
            logger.warning(f"⚠️ PR TIMES RSS取得エラー ({rss_url}): {e}")
            return []

    def _get_pr_items_last_7_days(self):
        """PR TIMES RSS から直近7日分のエントリを取得（重複除く）"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_AGO)
        all_items = []
        seen_rss = set()
        seen_urls = set()

        for page_url in DEFAULT_CATEGORY_PAGE_URLS:
            rss_url = self._discover_rss_url(page_url)
            if not rss_url:
                logger.debug(f"PR TIMES × はてブ: RSS URL取得失敗 ({page_url})")
                continue
            if rss_url in seen_rss:
                continue
            seen_rss.add(rss_url)
            items_raw = self._parse_rss_feed(rss_url)
            logger.info(f"  {page_url} -> RSS {len(items_raw)}件")
            for item in items_raw:
                url = (item.get('url') or '').strip()
                if not url or url in seen_urls:
                    continue
                pub = item.get('published_date')
                if pub is None:
                    continue
                try:
                    if hasattr(pub, 'tzinfo') and pub.tzinfo:
                        ts = pub.timestamp()
                    else:
                        ts = (pub.replace(tzinfo=timezone.utc)).timestamp()
                except Exception:
                    continue
                if ts < cutoff.timestamp():
                    continue
                seen_urls.add(url)
                all_items.append(item)

        if not all_items and seen_rss:
            logger.warning(f"PR TIMES × はてブ: RSS {len(seen_rss)}件取得したが7日以内のエントリが0件")
        elif not seen_rss:
            logger.warning("PR TIMES × はてブ: 全カテゴリでRSS URL取得失敗")
        return all_items

    def _get_bookmark_counts_batch(self, url_list):
        """
        はてなブックマーク一括Count API で複数URLのブクマ数を取得。
        最大50URL/リクエスト。返り値: dict[url -> count]
        """
        result = {}
        for i in range(0, len(url_list), HATENA_BATCH_SIZE):
            chunk = url_list[i:i + HATENA_BATCH_SIZE]
            self.rate_limiter.wait_if_needed()
            try:
                resp = self.session.get(
                    HATENA_COUNT_BATCH_URL,
                    params={'url': chunk},
                    timeout=15,
                )
                if resp.status_code != 200:
                    logger.warning(f"はてな一括Count API status: {resp.status_code}")
                    for u in chunk:
                        result[u] = 0
                    continue
                data = resp.json()
                # レスポンスは URL をキーにした dict の想定
                if isinstance(data, dict):
                    for u in chunk:
                        result[u] = int(data.get(u, 0) or 0)
                else:
                    for u in chunk:
                        result[u] = 0
            except Exception as e:
                logger.warning(f"はてな一括Count API エラー: {e}")
                for u in chunk:
                    result[u] = 0
        return result

    def get_trends(self, limit=TOP_N, force_refresh=False):
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key='bookmark_count',
            sort_reverse=True,
        )

    def _fetch_trends(self, limit=TOP_N, *args, **kwargs):
        """
        PR TIMES 7日分 → はてな一括Count → ブクマ>0 のみ → ブクマ数降順 Top5
        """
        try:
            logger.info("PR TIMES × はてブ: 取得開始")
            items = self._get_pr_items_last_7_days()
            if not items:
                logger.warning("PR TIMES × はてブ: 7日以内のPRが0件")
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'prtimes_hatena',
                    'total_count': 0,
                }

            url_list = [(i.get('url') or '').strip() for i in items if (i.get('url') or '').strip()]
            counts = self._get_bookmark_counts_batch(url_list)

            for item in items:
                item['bookmark_count'] = counts.get((item.get('url') or '').strip(), 0)
                # レスポンス用に published_date を ISO 文字列に
                if 'published_date_iso' in item:
                    item['published_date'] = item['published_date_iso']

            filtered = [i for i in items if (i.get('bookmark_count') or 0) > 0]
            filtered.sort(key=lambda x: x.get('bookmark_count', 0), reverse=True)
            top = filtered[:limit]

            for i, item in enumerate(top, 1):
                item['rank'] = i

            logger.info(f"✅ PR TIMES × はてブ: {len(top)}件（ブクマ>0）")
            return {
                'success': True,
                'data': top,
                'status': 'api_fetched',
                'source': 'prtimes_hatena',
                'total_count': len(top),
            }
        except requests.exceptions.Timeout:
            logger.error("❌ PR TIMES × はてブ タイムアウト", exc_info=True)
            return {'success': False, 'error': 'タイムアウトしました', 'data': []}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ PR TIMES × はてブ リクエストエラー: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}
        except Exception as e:
            logger.error(f"❌ PR TIMES × はてブ 取得エラー: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'data': []}
