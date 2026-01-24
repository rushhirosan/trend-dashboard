import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class MediumTrendsManager(BaseTrendsManager):
    """Mediumトレンド管理クラス（RSSフィード使用）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='medium', max_requests=10, window_seconds=60)
        
        # Medium RSSフィードURL（トップ記事と人気のタグ）
        self.rss_urls = [
            "https://medium.com/feed/tag/programming",
            "https://medium.com/feed/tag/technology",
            "https://medium.com/feed/tag/startup",
        ]

        logger.info("Medium Trends Manager初期化:")
        logger.info(f"  RSS URLs: {self.rss_urls}")

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_medium_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        # 例外を再発生させて、base_trends_managerで詳細なエラー情報を取得できるようにする
        return self.db.save_medium_trends_to_cache(data)

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_medium_trends_cache()
        except Exception as e:
            logger.error(f"❌ Medium キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'medium_trends'

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            self.db.update_cache_status(cache_key, data_count)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Medium: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """Mediumトレンドを取得（キャッシュ優先、公開日でソート）"""
        # ベースクラスのget_trendsを使用し、公開日でソートするように設定
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュがない場合は自動的にAPIを呼び出す
            sort_key='published_date',  # 公開日でソート
            sort_reverse=True  # 降順
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
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
