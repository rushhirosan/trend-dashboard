import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class DevToTrendsManager(BaseTrendsManager):
    """DEV.toトレンド管理クラス（API使用）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='devto', max_requests=5, window_seconds=60)
        
        # DEV.to APIエンドポイント（無料、認証不要）
        self.api_url = "https://dev.to/api/articles"

        logger.info("DEV.to Trends Manager初期化:")
        logger.info(f"  API URL: {self.api_url}")

    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'devto_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_devto_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_devto_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ DEV.to キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_devto_trends_cache()
        except Exception as e:
            logger.error(f"❌ DEV.to キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ DEV.to: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """DEV.toトレンドを取得（キャッシュ優先、reactions_countでソート）"""
        # ベースクラスのget_trendsを使用し、reactions_countでソートするように設定
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='reactions_count',  # reactions_countでソート
            sort_reverse=True  # 降順
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
        """DEV.to APIからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            # トップ記事を取得（top=1でトップ記事を取得）
            # per_pageで取得件数を指定（最大1000件まで）
            params = {
                'top': '1',  # トップ記事を取得
                'per_page': min(limit * 2, 100),  # 余裕を持って取得（最大100件）
            }
            
            logger.info(f"DEV.to API呼び出し開始: {self.api_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.api_url, params=params, headers=headers, timeout=10)
            logger.info(f"📊 DEV.to API: HTTP status={response.status_code}")

            if response.status_code != 200:
                logger.warning(f"⚠️ DEV.to API: HTTP {response.status_code} - {response.text[:200]}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'api_fetch_failed',
                    'source': 'devto_api',
                    'error': f'API取得に失敗しました: HTTP {response.status_code}'
                }

            articles = response.json()
            if not isinstance(articles, list):
                logger.warning(f"⚠️ DEV.to API: 予期しないレスポンス形式 - {type(articles)}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'invalid_response',
                    'source': 'devto_api',
                    'error': 'APIレスポンスが不正な形式です'
                }

            if not articles:
                logger.warning("⚠️ DEV.to API: 記事が取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_articles',
                    'source': 'devto_api'
                }

            # データを整形
            formatted_data = []
            for article in articles[:limit * 2]:
                try:
                    # 公開日を取得
                    published_date = None
                    if article.get('published_at'):
                        try:
                            published_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
                        except Exception:
                            try:
                                published_date = datetime.strptime(article['published_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                            except Exception:
                                published_date = datetime.now()

                    # タグを取得
                    tags = []
                    if article.get('tag_list'):
                        tags = article['tag_list'] if isinstance(article['tag_list'], list) else [article['tag_list']]
                    elif article.get('tags'):
                        tags = article['tags']

                    formatted_data.append({
                        'id': article.get('id'),
                        'title': article.get('title', 'No Title'),
                        'url': article.get('url', ''),
                        'canonical_url': article.get('canonical_url', article.get('url', '')),
                        'article_id': article.get('id'),
                        'published_date': published_date.isoformat() if published_date else None,
                        'published_at': article.get('published_at'),
                        'description': article.get('description', '')[:300] if article.get('description') else '',
                        'author': article.get('user', {}).get('username', '') if article.get('user') else '',
                        'tags': tags,
                        'reactions_count': article.get('positive_reactions_count', article.get('reactions_count', 0)),
                        'positive_reactions_count': article.get('positive_reactions_count', article.get('reactions_count', 0)),
                        'comments_count': article.get('comments_count', 0),
                        'reading_time_minutes': article.get('reading_time_minutes', 0),
                        'source': 'DEV.to'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ DEV.to 記事パースエラー: {e}")
                    continue

            # reactions_countでソート（降順）
            formatted_data.sort(key=lambda x: x.get('reactions_count', 0), reverse=True)
            
            # ランキングを設定
            for i, item in enumerate(formatted_data[:limit], 1):
                item['rank'] = i
            
            final_data = formatted_data[:limit]

            logger.info(f"✅ DEV.to: {len(final_data)}件の記事を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'devto_api',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ DEV.to API タイムアウトエラー", exc_info=True)
            return {'error': 'DEV.to API タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ DEV.to API エラー: {e}", exc_info=True)
            return {'error': f'DEV.to API取得エラー: {str(e)}', 'success': False}
