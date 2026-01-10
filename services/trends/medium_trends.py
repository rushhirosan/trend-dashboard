import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class MediumTrendsManager:
    """Mediumトレンド管理クラス（RSSフィード使用）"""

    def __init__(self):
        """初期化"""
        # Medium RSSフィードURL（トップ記事と人気のタグ）
        self.rss_urls = [
            "https://medium.com/feed/tag/programming",
            "https://medium.com/feed/tag/technology",
            "https://medium.com/feed/tag/startup",
        ]
        self.db = TrendsCache()
        # レート制限: RSSフィードは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('medium', max_requests=10, window_seconds=60)

        logger.info("Medium Trends Manager初期化:")
        logger.info(f"  RSS URLs: {self.rss_urls}")

    def get_trends(self, limit=25, force_refresh=False):
        """Mediumトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info("🔄 Medium force_refresh: キャッシュをクリアします")
                self.db.clear_medium_trends_cache()

            cached_data = self.db.get_medium_trends_from_cache()
            if cached_data:
                # 公開日でソート（降順）
                cached_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                logger.info(f"✅ Medium: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                if not force_refresh:
                    logger.warning("⚠️ Medium: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                logger.warning("⚠️ Medium: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_medium_trends(limit)

        except Exception as e:
            logger.error(f"❌ Medium トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Mediumトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def _fetch_medium_trends(self, limit=25):
        """Medium RSSフィードからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            all_entries = []
            for rss_url in self.rss_urls:
                try:
                    logger.info(f"Medium RSS呼び出し開始: {rss_url}")
                    feed = feedparser.parse(rss_url)
                    if feed.entries:
                        all_entries.extend(feed.entries)
                        logger.info(f"✅ Medium RSS({rss_url}): {len(feed.entries)}件のエントリーを取得")
                except requests.exceptions.Timeout:
                    logger.warning(f"❌ Medium RSS({rss_url}) タイムアウト")
                except Exception as e:
                    logger.warning(f"❌ Medium RSS({rss_url}) エラー: {e}")

            if not all_entries:
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'medium_rss'
                }

            # 重複を除去（タイトルベース）
            seen_titles = set()
            unique_entries = []
            for entry in all_entries:
                title = entry.get('title', '').strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_entries.append(entry)

            formatted_data = []
            for i, entry in enumerate(unique_entries[:limit * 2], 1):  # 余裕を持って取得
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

                    # Medium URLからスラッグを抽出（可能な場合）
                    slug = None
                    link = entry.get('link', '')
                    if '/@' in link and '/' in link.split('/@')[1]:
                        try:
                            slug = link.split('/')[-1]
                        except Exception:
                            pass

                    # 著者情報を抽出
                    author = entry.get('author', '')
                    if not author and hasattr(entry, 'tags'):
                        # タグから著者情報を推測（MediumのRSS構造による）
                        pass

                    formatted_data.append({
                        'rank': i,
                        'title': entry.get('title', 'No Title'),
                        'url': link,
                        'slug': slug,
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description[:300] if description else '',  # 説明は300文字に制限
                        'author': author,
                        'source': 'Medium'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Medium エントリーパースエラー: {e}")
                    continue

            # 公開日でソート（降順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            for i, item in enumerate(formatted_data[:limit], 1):
                item['rank'] = i
            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_medium_trends_to_cache(final_data)
                self.db.update_cache_status('medium_trends', len(final_data))

            logger.info(f"✅ Medium: {len(final_data)}件の記事を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'medium_rss',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Medium RSS タイムアウトエラー", exc_info=True)
            return {'error': 'Medium RSS タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Medium RSS エラー: {e}", exc_info=True)
            return {'error': f'Medium RSS取得エラー: {str(e)}', 'success': False}

