import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class AppStoreTrendsManager:
    """App Storeトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://itunes.apple.com"
        self.db = TrendsCache()
        # レート制限: iTunes APIは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('appstore', max_requests=10, window_seconds=60)
        
        logger.info(f"App Store Trends Manager初期化:")
        logger.info(f"  API URL: {self.base_url}")
    
    def get_trends(self, country='JP', category='all', limit=25, force_refresh=False):
        """App Storeトレンドを取得（キャッシュ優先）"""
        try:
            cache_key = f'appstore_trends_{country}'
            
            if force_refresh:
                logger.info(f"🔄 App Store force_refresh: キャッシュをクリアします")
                self.db.clear_appstore_trends_cache(country)
            
            # キャッシュからデータを取得
            cached_data = self.db.get_appstore_trends_from_cache(country)
            
            if cached_data:
                logger.info(f"✅ App Store: キャッシュから{len(cached_data)}件のデータを取得しました")
                # cache_statusを更新
                self.db.update_cache_status(cache_key, len(cached_data))
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'country': country,
                    'category': category
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ App Store: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': False,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ App Store: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self.get_top_apps(country, category, limit)
                
        except Exception as e:
            logger.error(f"❌ App Store トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'App Storeトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def get_top_apps(self, country='JP', category='all', limit=25):
        """App Storeの人気アプリを取得"""
        try:
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # iTunes Search APIを使用
            url = f"{self.base_url}/search"
            
            # カテゴリマッピング
            category_map = {
                'all': '6000',  # すべて
                'games': '6014',  # ゲーム
                'business': '6000',  # ビジネス
                'education': '6017',  # 教育
                'entertainment': '6016',  # エンターテインメント
                'finance': '6015',  # ファイナンス
                'health': '6013',  # ヘルスケア
                'lifestyle': '6012',  # ライフスタイル
                'news': '6009',  # ニュース
                'productivity': '6007',  # 仕事効率化
                'social': '6005',  # ソーシャルネットワーキング
                'sports': '6004',  # スポーツ
                'travel': '6003',  # 旅行
                'utilities': '6002',  # ユーティリティ
            }
            
            genre_id = category_map.get(category.lower(), '6000')
            
            params = {
                'country': country.lower(),
                'media': 'software',
                'entity': 'software',
                'limit': min(limit, 200),  # iTunes APIの最大制限は200
                'genreId': genre_id
            }
            
            logger.debug(f"App Store API呼び出し: {url}")
            logger.debug(f"App Store API パラメータ: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            
            logger.debug(f"App Store APIレスポンス: status={response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"App Store APIエラーレスポンス: {error_text}")
                return {
                    'error': f'App Store API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('results', [])
                
                # データを整形
                formatted_data = []
                for i, item in enumerate(items[:limit], 1):
                    formatted_item = {
                        'app_id': str(item.get('trackId', '')),
                        'name': item.get('trackName', ''),
                        'bundle_id': item.get('bundleId', ''),
                        'description': item.get('description', ''),
                        'url': item.get('trackViewUrl', ''),
                        'artist_name': item.get('artistName', ''),
                        'artist_id': str(item.get('artistId', '')),
                        'price': item.get('price', 0),
                        'currency': item.get('currency', ''),
                        'category': item.get('primaryGenreName', ''),
                        'genre_ids': item.get('genreIds', []),
                        'average_user_rating': item.get('averageUserRating', 0),
                        'user_rating_count': item.get('userRatingCount', 0),
                        'release_date': item.get('releaseDate', ''),
                        'current_version_release_date': item.get('currentVersionReleaseDate', ''),
                        'artwork_url_60': item.get('artworkUrl60', ''),
                        'artwork_url_100': item.get('artworkUrl100', ''),
                        'artwork_url_512': item.get('artworkUrl512', ''),
                        'screenshot_urls': item.get('screenshotUrls', []),
                        'rank': i
                    }
                    formatted_data.append(formatted_item)
                
                # データベースにキャッシュ
                if formatted_data:
                    self.db.save_appstore_trends_to_cache(formatted_data, country)
                    # cache_statusを更新
                    cache_key = f'appstore_trends_{country}'
                    self.db.update_cache_status(cache_key, len(formatted_data))
                
                logger.info(f"✅ App Store: {len(formatted_data)}件のトレンドアプリを取得しました")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'appstore_api',
                    'country': country,
                    'category': category
                }
            else:
                return {
                    'error': f'App Store API 予期しないレスポンス: {response.status_code}',
                    'success': False
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ App Store API タイムアウトエラー")
            return {
                'error': 'App Store API タイムアウト',
                'success': False
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ App Store API リクエストエラー: {e}", exc_info=True)
            return {
                'error': f'App Store API リクエストエラー: {str(e)}',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ App Store トレンド取得エラー: {e}", exc_info=True)
            return {
                'error': f'App Storeトレンドの取得に失敗しました: {str(e)}',
                'success': False
            }

