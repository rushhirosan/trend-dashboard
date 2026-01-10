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
        # DEV.to APIエンドポイント（無料、認証不要）
        self.api_url = "https://dev.to/api/articles"
        self.db = TrendsCache()
        # レート制限: DEV.to APIは1分あたり10リクエスト（保守的に5リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('devto', max_requests=5, window_seconds=60)

        logger.info("DEV.to Trends Manager初期化:")
        logger.info(f"  API URL: {self.api_url}")

    def get_trends(self, limit=25, force_refresh=False):
        """DEV.toトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info("🔄 DEV.to force_refresh: キャッシュをクリアします")
                self.db.clear_devto_trends_cache()

            cached_data = self.db.get_devto_trends_from_cache()
            if cached_data:
                # reactions_countでソート（降順）
                cached_data.sort(key=lambda x: x.get('reactions_count', 0), reverse=True)
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
                    'success': True,
                    'data': [],
                    'status': 'api_fetch_failed',
                    'source': 'devto_api',
                    'error': f'API取得に失敗しました: HTTP {response.status_code}'
                }

            articles = response.json()
            if not isinstance(articles, list):
                logger.warning(f"⚠️ DEV.to API: 予期しないレスポンス形式 - {type(articles)}")
                return {
                    'success': True,
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

            logger.info(f"✅ DEV.to API: {len(articles)}件の記事を取得")

            formatted_data = []
            for i, article in enumerate(articles[:limit * 2], 1):
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
                        'rank': i,
                        'title': article.get('title', 'No Title'),
                        'url': article.get('url', ''),
                        'canonical_url': article.get('canonical_url', article.get('url', '')),
                        'article_id': article.get('id'),
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': article.get('description', '')[:300] if article.get('description') else '',
                        'author': article.get('user', {}).get('username', '') if article.get('user') else '',
                        'tags': tags,
                        'reactions_count': article.get('positive_reactions_count', article.get('reactions_count', 0)),
                        'comments_count': article.get('comments_count', 0),
                        'source': 'DEV.to'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ DEV.to 記事パースエラー: {e}")
                    continue

            # reactions_countでソート（降順）
            formatted_data.sort(key=lambda x: x.get('reactions_count', 0), reverse=True)
            for i, item in enumerate(formatted_data[:limit], 1):
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
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ DEV.to API リクエストエラー: {e}", exc_info=True)
            return {'error': f'DEV.to APIリクエストエラー: {str(e)}', 'success': False}
        except Exception as e:
            logger.error(f"❌ DEV.to API エラー: {e}", exc_info=True)
            return {'error': f'DEV.to API取得エラー: {str(e)}', 'success': False}

