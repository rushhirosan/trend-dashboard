import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class WorldNewsTrendsManager(BaseTrendsManager):
    """World News APIを使用して日本のニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='worldnews', max_requests=10, window_seconds=60)
        
        self.api_key = os.getenv('WORLDNEWS_API_KEY')
        self.base_url = "https://api.worldnewsapi.com"
        
        if not self.api_key:
            logger.warning("Warning: WORLDNEWS_API_KEYが設定されていません")
        
        logger.debug(f"World News API認証情報確認:")
        logger.debug(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
        
        # World News API接続テスト（キャッシュモードでは無効化）
        # if self.api_key:
        #     self._test_connection()
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        country = kwargs.get('country', 'jp')
        return f'worldnews_trends_{country}'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            country = kwargs.get('country', 'jp')
            # データベースに保存されている形式に合わせる（小文字）
            return self.db.get_worldnews_trends_from_cache('general', country.lower())
        except Exception as e:
            logger.error(f"❌ WorldNews: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            country = kwargs.get('country', 'jp')
            cache_key = kwargs.get('cache_key', 'worldnews_trends')
            return self.db.save_worldnews_trends_to_cache(data, cache_key, country)
        except Exception as e:
            logger.error(f"❌ WorldNews キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            country = kwargs.get('country', 'jp')
            return self.db.clear_worldnews_trends_cache('general', country)
        except Exception as e:
            logger.error(f"❌ WorldNews キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ WorldNews: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, country='jp', category=None, page_size=25, *args, **kwargs):
        """外部APIからWorld Newsデータを取得"""
        result = self._get_worldnews_trends(country, category, page_size)
        if result:
            return {
                'success': True,
                'data': result,
                'status': 'api_fetched',
                'country': country.upper(),
                'category': category,
                'source': 'World News API'
            }
        else:
            return {
                'success': False,
                'error': 'データが取得できませんでした',
                'data': []
            }

    def _test_connection(self):
        """World News API接続テスト"""
        try:
            # 簡単なテストリクエスト（日本のニュース）
            test_url = f"{self.base_url}/search-news"
            params = {
                'api-key': self.api_key,
                'source-country': 'jp',
                'number': 1
            }
            
            response = requests.get(test_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"World News API接続テスト成功: {data.get('available', 0)}件の記事")
                logger.debug(f"レスポンス詳細: {data}")
            else:
                logger.warning(f"World News API接続テスト失敗: {response.status_code}")
                logger.warning(f"エラーレスポンス: {response.text}")
                
        except Exception as e:
            logger.error(f"World News API接続テストエラー: {e}", exc_info=True)
    
    def get_trends(self, country='jp', category=None, page_size=25, force_refresh=False):
        """World Newsトレンドを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            cache_key = 'worldnews_trends'
            cached_data = None
            
            if force_refresh:
                logger.info(f"🔄 World News: force_refresh指定のためキャッシュをスキップします (country: {country})")
            else:
                logger.debug(f"🔍 World News: キャッシュデータ取得開始 (country: {country})")
                cached_data = self.get_from_cache(cache_key, country)
                logger.debug(f"🔍 World News: キャッシュデータ取得結果: {type(cached_data)}, 長さ: {len(cached_data) if cached_data else 0}")
            
            if cached_data:
                logger.info(f"✅ World News: キャッシュデータを使用 ({len(cached_data)}件)")
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'country': country.upper(),
                    'category': category,
                    'source': 'World News API (Cached)'
                }
            
            # force_refresh=falseの場合、キャッシュがない時は空のデータを返す（API呼び出しをスキップ）
            if not force_refresh:
                logger.warning(f"⚠️ World News: キャッシュにデータがありません (country: {country})。force_refresh=falseのため外部APIは呼び出しません")
                return {
                    'data': [],
                    'status': 'cache_not_found',
                    'country': country.upper(),
                    'category': category,
                    'source': 'World News API',
                    'message': 'キャッシュにデータがありません'
                }
            
            logger.warning(f"⚠️ World News: キャッシュ未使用のため外部APIを呼び出します")
            trends_data = self._get_worldnews_trends(country, category, page_size)
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, cache_key, country)
                logger.info(f"✅ World News: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                return {
                    'data': trends_data,
                    'status': 'api_fetched',
                    'country': country.upper(),
                    'category': category,
                    'source': 'World News API'
                }
            else:
                logger.error(f"❌ World News: 外部APIからデータを取得できませんでした")
                return {
                    'data': [],
                    'status': 'api_error',
                    'country': country.upper(),
                    'category': category
                }
                
        except Exception as e:
            logger.error(f"World News APIトレンド取得エラー: {e}", exc_info=True)
            return {'error': f'World News APIトレンドの取得に失敗しました: {str(e)}'}
    
    def _get_worldnews_trends(self, country='jp', category=None, page_size=25):
        """World News APIからトレンドデータを取得"""
        if not self.api_key:
            logger.warning("World News APIキーが設定されていません")
            return None
        
        try:
            logger.info(f"World News API呼び出し開始 (国: {country}, カテゴリ: {category})")
            
            url = f"{self.base_url}/search-news"
            
            # 最新の記事を取得するため、日付フィルタを追加
            # 今日から過去2日間の記事を取得（最新データを確実に取得）
            from datetime import datetime, timedelta
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            
            params = {
                'api-key': self.api_key,
                'source-country': country,
                'number': page_size,
                'language': 'ja' if country == 'jp' else 'en',
                'earliest-publish-date': yesterday.strftime('%Y-%m-%d'),
                'latest-publish-date': today.strftime('%Y-%m-%d'),
                'sort': 'publish-time',  # 公開日時でソート
                'sort-direction': 'DESC'  # 新しい順
            }
            
            # カテゴリが指定されている場合のみtextパラメータを追加
            # ただし、'general'の場合は除外（検索結果が0件になるため）
            if category and category != 'general':
                params['text'] = category
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            logger.debug(f"World News APIリクエスト: {params}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"World News API エラー: HTTP {response.status_code}")
                logger.error(f"エラーレスポンス: {response.text}")
                return None
            
            data = response.json()
            logger.debug(f"World News API レスポンス: {data}")
            
            articles = data.get('news', [])
            logger.info(f"World News APIで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                logger.warning("World News APIで記事が取得できませんでした")
                return []
            
            trends = []
            for i, article in enumerate(articles, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(articles) - 1)) if len(articles) > 1 else 100
                
                source_info = article.get('source')
                if isinstance(source_info, dict):
                    source_name = source_info.get('name') or source_info.get('title') or source_info.get('region')
                elif isinstance(source_info, str):
                    source_name = source_info
                else:
                    source_name = article.get('source_name') or article.get('source_title')
                if not source_name:
                    source_name = ''

                publish_raw = article.get('publish_date') or article.get('published_at') or article.get('date')
                if publish_raw:
                    try:
                        publish_dt = datetime.fromisoformat(publish_raw.replace('Z', '+00:00'))
                        publish_formatted = publish_dt.isoformat()
                    except Exception:
                        publish_formatted = publish_raw
                else:
                    publish_formatted = ''

                description = article.get('summary') or article.get('text') or article.get('excerpt') or ''

                trends.append({
                    'rank': i,
                    'article_id': f"worldnews_{country}_{i}_{hash(article.get('url', ''))}", # article_idを生成
                    'title': article.get('title', 'No Title'),
                    'description': description,
                    'source': source_name,
                    'url': article.get('url') or article.get('link') or '',
                    'image_url': article.get('image') or article.get('image_url') or '',
                    'published_at': publish_formatted,
                    'score': round(score, 1),
                    'category': category or 'general',
                    'country': country # countryフィールドを追加
                })
            
            logger.info(f"World News API処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            logger.error(f"World News API エラー: {e}", exc_info=True)
            return []
    
    def get_from_cache(self, cache_key, country):
        """キャッシュからデータを取得"""
        try:
            # データベースに保存されている形式に合わせる（小文字）
            return self.db.get_worldnews_trends_from_cache('general', country.lower())
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def save_to_cache(self, data, cache_key, country):
        """データをキャッシュに保存"""
        try:
            self.db.save_worldnews_trends_to_cache(data, cache_key, country)
            # cache_statusテーブルも更新
            self._update_cache_status('worldnews_trends', len(data))
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.error(f"cache_status更新エラー: {e}", exc_info=True)
            return False
    
    def is_cache_valid(self, cache_key, country):
        """キャッシュが有効かチェック（6時間以内）"""
        try:
            return self.db.is_news_cache_valid(country, cache_key)
        except Exception as e:
            logger.error(f"キャッシュ有効性チェックエラー: {e}", exc_info=True)
            return False
    
    def _should_refresh_cache(self, category, country):
        """今日既にキャッシュを更新したかチェック（朝5時から夜12時まで）"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            today = now.date()
            current_hour = now.hour
            
            # 時間制限：5時から24時まで
            if not (5 <= current_hour < 24):
                logger.info(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('worldnews_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
            return True 