import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class QiitaTrendsManager(BaseTrendsManager):
    """Qiitaトレンド管理クラス（API使用）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='qiita', max_requests=10, window_seconds=60)
        
        # Qiita APIエンドポイント
        self.api_url = "https://qiita.com/api/v2/items"

        logger.info("Qiita Trends Manager初期化:")
        logger.info(f"  API URL: {self.api_url}")

    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'qiita_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_qiita_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_qiita_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ Qiita キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_qiita_trends_cache()
        except Exception as e:
            logger.error(f"❌ Qiita キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Qiita: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, sort='likes_count', force_refresh=False):
        """Qiitaトレンドを取得（キャッシュ優先、likes_countでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='likes_count'でいいね数でソート
        # sortパラメータは互換性のために受け取るが、実際のソートはlikes_countで固定
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='likes_count',  # いいね数でソート
            sort_reverse=True  # 降順
        )

    def _fetch_trends(self, limit=25, *args, **kwargs):
        """Qiita APIからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            # トレンド記事を取得（ストック数順）
            params = {
                'query': 'stocks:>10',  # ストック数が10以上の記事
                'per_page': min(limit * 2, 100),  # 余裕を持って取得（最大100件）
                'sort': 'stocks',  # ストック数でソート
            }
            
            logger.info(f"Qiita API呼び出し開始: {self.api_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.api_url, params=params, headers=headers, timeout=10)
            logger.info(f"📊 Qiita API: HTTP status={response.status_code}")

            if response.status_code != 200:
                logger.warning(f"⚠️ Qiita API: HTTP {response.status_code} - {response.text[:200]}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'api_fetch_failed',
                    'source': 'qiita_api',
                    'error': f'API取得に失敗しました: HTTP {response.status_code}'
                }

            articles = response.json()
            if not isinstance(articles, list):
                logger.warning(f"⚠️ Qiita API: 予期しないレスポンス形式 - {type(articles)}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'invalid_response',
                    'source': 'qiita_api',
                    'error': 'APIレスポンスが不正な形式です'
                }

            if not articles:
                logger.warning("⚠️ Qiita API: 記事が取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_articles',
                    'source': 'qiita_api'
                }

            # データを整形
            formatted_data = []
            for article in articles:
                try:
                    # 公開日時をパース
                    created_at = article.get('created_at')
                    created_date = None
                    if created_at:
                        try:
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        except Exception:
                            created_date = datetime.now()

                    # タグを取得
                    tags = []
                    if article.get('tags'):
                        tags = [tag.get('name', '') for tag in article.get('tags', [])]

                    formatted_data.append({
                        'id': article.get('id', ''),
                        'title': article.get('title', 'No Title'),
                        'url': article.get('url', ''),
                        'body': article.get('body', '')[:300] if article.get('body') else '',  # 本文は300文字に制限
                        'created_at': created_date.isoformat() if created_date else None,
                        'updated_at': article.get('updated_at'),
                        'likes_count': article.get('likes_count', 0),
                        'comments_count': article.get('comments_count', 0),
                        'stocks_count': article.get('stocks_count', 0),
                        'page_views_count': article.get('page_views_count', 0),
                        'tags': tags,
                        'user': article.get('user', {}).get('id', '') if article.get('user') else '',
                        'user_name': article.get('user', {}).get('name', '') if article.get('user') else '',
                        'source': 'Qiita'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Qiita 記事データの処理でエラー: {e}", exc_info=True)
                    continue

            # likes_countでソート（降順）
            formatted_data.sort(key=lambda x: x.get('likes_count', 0), reverse=True)
            
            # ランキングを設定
            for i, item in enumerate(formatted_data[:limit], 1):
                item['rank'] = i
            
            final_data = formatted_data[:limit]

            logger.info(f"✅ Qiita: {len(final_data)}件の記事を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'qiita_api',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Qiita API タイムアウトエラー", exc_info=True)
            return {'error': 'Qiita API タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Qiita API エラー: {e}", exc_info=True)
            return {'error': f'Qiita API取得エラー: {str(e)}', 'success': False}
