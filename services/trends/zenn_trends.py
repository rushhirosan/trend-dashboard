import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class ZennTrendsManager(BaseTrendsManager):
    """Zennトレンド管理クラス（RSSフィード使用）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='zenn', max_requests=10, window_seconds=60)
        
        # Zenn RSSフィードURL
        self.rss_url = "https://zenn.dev/feed"

        logger.info("Zenn Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_url}")

    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'zenn_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_zenn_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_zenn_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ Zenn キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_zenn_trends_cache()
        except Exception as e:
            logger.error(f"❌ Zenn キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Zenn: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """Zennトレンドを取得（キャッシュ優先、published_dateでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='published_date'で公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='published_date',  # 公開日でソート
            sort_reverse=True  # 降順（新しい順）
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
        """Zenn RSSフィードからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            logger.info(f"Zenn RSSフィード取得開始: {self.rss_url}")
            feed = feedparser.parse(self.rss_url)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"⚠️ Zenn RSS: フィードパースエラー - {feed.bozo_exception}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'rss_parse_error',
                    'source': 'zenn_rss',
                    'error': f'RSSフィードのパースに失敗しました: {str(feed.bozo_exception)}'
                }

            entries = feed.entries
            if not entries:
                logger.warning("⚠️ Zenn RSS: 記事が取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_articles',
                    'source': 'zenn_rss'
                }

            # データを整形
            formatted_data = []
            for entry in entries[:limit * 2]:
                try:
                    # 公開日時をパース
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except Exception:
                            published_date = datetime.now()
                    elif hasattr(entry, 'published'):
                        try:
                            published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                        except Exception:
                            try:
                                published_date = datetime.fromisoformat(entry.published.replace('Z', '+00:00'))
                            except Exception:
                                published_date = datetime.now()
                    else:
                        published_date = datetime.now()

                    # 著者情報を取得
                    author = ''
                    if hasattr(entry, 'author'):
                        author = entry.author
                    elif hasattr(entry, 'author_detail') and hasattr(entry.author_detail, 'name'):
                        author = entry.author_detail.name

                    formatted_data.append({
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'description': entry.get('summary', '')[:300] if entry.get('summary') else '',  # 説明は300文字に制限
                        'published_date': published_date.isoformat() if published_date else None,
                        'author': author,
                        'source': 'Zenn'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Zenn 記事データの処理でエラー: {e}", exc_info=True)
                    continue

            # published_dateでソート（降順、新しい順）
            formatted_data.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            
            # ランキングを設定
            for i, item in enumerate(formatted_data[:limit], 1):
                item['rank'] = i
            
            final_data = formatted_data[:limit]

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
