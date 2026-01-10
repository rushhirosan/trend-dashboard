import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class DevToTrendsManager:
    """DEV.toトレンド管理クラス（API使用）"""

    def __init__(self):
        """初期化"""
        self.base_url = "https://dev.to/api"
        self.db = TrendsCache()
        # レート制限: DEV.to APIは認証なしで1時間60リクエスト、認証ありで1時間1000リクエスト
        # 認証なしで運用するため、50リクエスト/時間（約0.83リクエスト/分）に設定
        self.rate_limiter = get_rate_limiter('devto', max_requests=50, window_seconds=3600)

        logger.info("DEV.to Trends Manager初期化:")
        logger.info(f"  Base URL: {self.base_url}")

    def get_trends(self, limit=25, force_refresh=False):
        """DEV.toトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info("🔄 DEV.to force_refresh: キャッシュをクリアします")
                self.db.clear_devto_trends_cache()

            cached_data = self.db.get_devto_trends_from_cache()
            if cached_data:
                # 公開日でソート（降順）
                cached_data.sort(key=lambda x: x.get('published_at') or '', reverse=True)
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                logger.info(f"✅ DEV.to: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                if not force_refresh:
                    logger.warning("⚠️ DEV.to: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                logger.warning("⚠️ DEV.to: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_devto_trends(limit)

        except Exception as e:
            logger.error(f"❌ DEV.to トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'DEV.toトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def _fetch_devto_trends(self, limit=25):
        """DEV.to APIからトレンド記事を取得"""
        try:
            logger.info(f"DEV.to API呼び出し開始 (limit: {limit})")

            # DEV.to APIの記事取得エンドポイント
            # 認証なしで使用可能、パラメータで並び替えやページネーションが可能
            url = f"{self.base_url}/articles"
            params = {
                'per_page': min(limit, 100),  # APIの最大は1000だが、安全のため100に制限
                'page': 1
            }

            # レート制限をチェック
            self.rate_limiter.wait_if_needed()

            headers = {
                'User-Agent': 'TrendsDashboard/1.0',
                'Accept': 'application/vnd.forem.api-v1+json'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"DEV.to API エラーレスポンス: {error_text}")
                return {
                    'error': f'DEV.to API エラー: {response.status_code}',
                    'success': False
                }

            articles = response.json()

            if not articles or not isinstance(articles, list):
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_articles',
                    'source': 'devto_api'
                }

            formatted_data = []
            for i, article in enumerate(articles[:limit], 1):
                try:
                    # 公開日のパース
                    published_at = article.get('published_at')
                    if published_at:
                        try:
                            # ISO 8601形式の日付をパース
                            published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        except Exception:
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()

                    # タグ情報を取得
                    tags = []
                    if article.get('tag_list'):
                        if isinstance(article['tag_list'], list):
                            tags = article['tag_list']
                        elif isinstance(article['tag_list'], str):
                            tags = [tag.strip() for tag in article['tag_list'].split(',') if tag.strip()]

                    formatted_data.append({
                        'rank': i,
                        'id': article.get('id'),
                        'title': article.get('title', 'No Title'),
                        'url': article.get('url', ''),
                        'canonical_url': article.get('canonical_url', ''),
                        'description': article.get('description', ''),
                        'published_at': published_at,
                        'published_date': published_date.isoformat() if published_date else None,
                        'positive_reactions_count': article.get('positive_reactions_count', 0),
                        'comments_count': article.get('comments_count', 0),
                        'reading_time_minutes': article.get('reading_time_minutes', 0),
                        'tags': tags,
                        'author': article.get('user', {}).get('username', 'Unknown') if article.get('user') else 'Unknown',
                        'source': 'DEV.to'
                    })
                except Exception as e:
                    logger.warning(f"DEV.to 記事パースエラー: {e}")
                    continue

            # 公開日でソート（降順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_devto_trends_to_cache(final_data)
                self.db.update_cache_status('devto_trends', len(final_data))

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
            return {
                'error': f'DEV.to API取得エラー: {str(e)}',
                'success': False
            }

