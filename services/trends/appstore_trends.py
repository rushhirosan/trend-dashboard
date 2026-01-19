import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class AppStoreTrendsManager(BaseTrendsManager):
    """App Storeトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='appstore', max_requests=10, window_seconds=60)
        
        self.base_url = "https://itunes.apple.com"
        
        logger.info(f"App Store Trends Manager初期化:")
        logger.info(f"  API URL: {self.base_url}")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す（国別に分ける）"""
        country = kwargs.get('country', 'JP')
        return f'appstore_trends_{country}'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        country = kwargs.get('country', 'JP')
        return self.db.get_appstore_trends_from_cache(country)

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            country = kwargs.get('country', 'JP')
            return self.db.save_appstore_trends_to_cache(data, country)
        except Exception as e:
            logger.error(f"❌ App Store キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            country = kwargs.get('country', 'JP')
            return self.db.clear_appstore_trends_cache(country)
        except Exception as e:
            logger.error(f"❌ App Store キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新（cache_keyは既に国別になっている）"""
        try:
            # cache_keyは既に_get_cache_key()で国別になっているので、そのまま使用
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ App Store: cache_status更新エラー: {e}")
            return False

    def get_trends(self, country='JP', category='all', limit=25, force_refresh=False):
        """App Storeトレンドを取得（キャッシュ優先、average_user_ratingでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='average_user_rating'で評価でソート（降順、評価0のものは下に来る）
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='average_user_rating',  # 評価でソート
            sort_reverse=True,  # 降順
            country=country,
            category=category
        )
        # countryとcategoryパラメータを結果に追加
        if result and isinstance(result, dict):
            result['country'] = country
            result['category'] = category
        return result
    
    def get_top_apps(self, country='JP', category='all', limit=25):
        """App Storeの人気アプリを取得（既存APIとの互換性のため）"""
        # force_refresh=Trueで強制更新
        return self.get_trends(country=country, category=category, limit=limit, force_refresh=True)
    
    def _fetch_trends(self, country='JP', category='all', limit=25, *args, **kwargs):
        """App Storeの人気アプリを取得（iTunes RSS Feed APIを使用）"""
        try:
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # 国コードのマッピング（RSS Feed用）
            country_code_map = {
                'JP': 'jp',
                'US': 'us',
                'GB': 'gb',
                'CA': 'ca',
                'AU': 'au',
                'DE': 'de',
                'FR': 'fr',
                'CN': 'cn',
                'KR': 'kr',
            }
            
            # デフォルトはjp
            rss_country = country_code_map.get(country.upper(), country.lower())
            
            # カテゴリマッピング
            category_map = {
                'all': None,  # すべての場合はカテゴリ指定なし
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
            
            genre_id = category_map.get(category.lower())
            
            # iTunes RSS Feed APIを使用（無料アプリランキング）
            # URL形式: https://itunes.apple.com/{country}/rss/topfreeapplications/genre={genre_id}/limit={limit}/json
            if genre_id:
                url = f"{self.base_url}/{rss_country}/rss/topfreeapplications/genre={genre_id}/limit={min(limit, 200)}/json"
            else:
                url = f"{self.base_url}/{rss_country}/rss/topfreeapplications/limit={min(limit, 200)}/json"
            
            logger.debug(f"App Store RSS Feed API呼び出し: {url}")
            
            response = requests.get(url, timeout=10)
            
            logger.debug(f"App Store RSS Feed APIレスポンス: status={response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"App Store RSS Feed APIエラーレスポンス: {error_text}")
                return {
                    'error': f'App Store RSS Feed API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            if response.status_code == 200:
                data = response.json()
                
                # RSS Feedの構造: feed.entry[] にアプリ情報が入っている
                feed = data.get('feed', {})
                entries = feed.get('entry', [])
                
                # エントリがリストでない場合（1件のみの場合）はリストに変換
                if not isinstance(entries, list):
                    entries = [entries] if entries else []
                
                # データを整形（まずRSS Feedから基本情報を取得）
                formatted_data = []
                app_ids = []
                for i, entry in enumerate(entries[:limit], 1):
                    # RSS Feedの構造から必要な情報を抽出
                    # entryは辞書で、'im:name', 'im:artist', 'im:image'などのキーを持つ
                    try:
                        app_name = entry.get('im:name', {}).get('label', '') if isinstance(entry.get('im:name'), dict) else ''
                        artist_name = entry.get('im:artist', {}).get('label', '') if isinstance(entry.get('im:artist'), dict) else ''
                        app_id = entry.get('id', {}).get('attributes', {}).get('im:id', '') if isinstance(entry.get('id'), dict) else ''
                        bundle_id = entry.get('id', {}).get('attributes', {}).get('im:bundleId', '') if isinstance(entry.get('id'), dict) else ''
                        app_url = entry.get('id', {}).get('label', '') if isinstance(entry.get('id'), dict) else ''
                        
                        # 画像URL（最大サイズを取得）
                        images = entry.get('im:image', [])
                        artwork_url_100 = ''
                        artwork_url_512 = ''
                        if isinstance(images, list) and len(images) > 0:
                            # 最後の要素が最大サイズ
                            largest_image = images[-1] if images else {}
                            artwork_url_100 = largest_image.get('label', '') if isinstance(largest_image, dict) else ''
                            artwork_url_512 = artwork_url_100
                        elif isinstance(images, dict):
                            artwork_url_100 = images.get('label', '')
                            artwork_url_512 = artwork_url_100
                        
                        # カテゴリ情報
                        category_info = entry.get('category', {}).get('attributes', {}) if isinstance(entry.get('category'), dict) else {}
                        category_name = category_info.get('label', '')
                        genre_id_list = [category_info.get('im:id', '')] if category_info.get('im:id') else []
                        
                        # 価格情報
                        price_info = entry.get('im:price', {}).get('attributes', {}) if isinstance(entry.get('im:price'), dict) else {}
                        price = float(price_info.get('amount', 0)) if price_info.get('amount') else 0
                        currency = price_info.get('currency', '')
                        
                        # リリース日
                        release_date = entry.get('im:releaseDate', {}).get('label', '') if isinstance(entry.get('im:releaseDate'), dict) else ''
                        
                        # 説明
                        summary = entry.get('summary', {}).get('label', '') if isinstance(entry.get('summary'), dict) else ''
                        
                        formatted_item = {
                            'app_id': str(app_id),
                            'name': app_name,
                            'bundle_id': bundle_id,
                            'description': summary,
                            'url': app_url,
                            'artist_name': artist_name,
                            'artist_id': '',  # RSS Feedにはartist_idがない
                            'price': price,
                            'currency': currency,
                            'category': category_name,
                            'genre_ids': genre_id_list,
                            'average_user_rating': 0,  # 後でLookup APIで取得
                            'user_rating_count': 0,  # 後でLookup APIで取得
                            'release_date': release_date,
                            'current_version_release_date': release_date,
                            'artwork_url_60': artwork_url_100,  # RSS Feedには60pxがないので100pxを使用
                            'artwork_url_100': artwork_url_100,
                            'artwork_url_512': artwork_url_512,
                            'screenshot_urls': [],  # RSS Feedにはスクリーンショットがない
                            'rank': i
                        }
                        formatted_data.append(formatted_item)
                        if app_id:
                            app_ids.append(app_id)
                    except Exception as e:
                        logger.warning(f"App Store エントリ処理エラー (rank {i}): {e}")
                        continue
                
                # iTunes Lookup APIで評価情報を取得（バッチ処理：最大200件まで一度に取得可能）
                if app_ids:
                    try:
                        logger.info(f"📊 App Store: {len(app_ids)}件のアプリの評価情報を取得中...")
                        # レート制限をチェック
                        self.rate_limiter.wait_if_needed()
                        
                        # 複数のapp_idをカンマ区切りで指定
                        lookup_url = f"{self.base_url}/lookup"
                        lookup_params = {
                            'id': ','.join(app_ids[:200]),  # iTunes APIの最大制限は200
                            'country': country.lower()  # 国コードを指定（JP, USなど）
                        }
                        
                        logger.debug(f"📊 App Store Lookup API呼び出し: {lookup_url}, params: {lookup_params}")
                        lookup_response = requests.get(lookup_url, params=lookup_params, timeout=15)
                        
                        if lookup_response.status_code == 200:
                            lookup_data = lookup_response.json()
                            lookup_results = lookup_data.get('results', [])
                            
                            logger.debug(f"📊 App Store Lookup API: {len(lookup_results)}件の結果を取得")
                            
                            # app_idをキーとした辞書を作成
                            rating_dict = {}
                            for result in lookup_results:
                                app_id_key = str(result.get('trackId', ''))
                                average_rating = result.get('averageUserRating')
                                user_rating_count = result.get('userRatingCount')
                                
                                # 評価情報がNoneの場合は、実際に評価がない可能性がある
                                # ただし、countryパラメータを指定することで、正しい評価情報が取得できる可能性がある
                                if average_rating is None:
                                    logger.debug(f"  ⚠️ app_id {app_id_key}: averageUserRatingがNone (評価情報なしまたは取得失敗)")
                                    # 実際のレスポンスのキーを確認（デバッグ用）
                                    available_keys = [k for k in result.keys() if 'rating' in k.lower() or 'review' in k.lower()]
                                    if available_keys:
                                        logger.debug(f"    評価関連キー: {available_keys}")
                                
                                rating_dict[app_id_key] = {
                                    'average_user_rating': average_rating if average_rating is not None else 0,
                                    'user_rating_count': user_rating_count if user_rating_count is not None else 0,
                                    'average_user_rating_for_current_version': result.get('averageUserRatingForCurrentVersion'),
                                    'user_rating_count_for_current_version': result.get('userRatingCountForCurrentVersion')
                                }
                            
                            # 評価情報をformatted_dataに反映
                            rating_updated_count = 0
                            rating_not_found_apps = []
                            for item in formatted_data:
                                app_id_key = item.get('app_id', '')
                                if app_id_key in rating_dict:
                                    rating_info = rating_dict[app_id_key]
                                    average_rating = rating_info.get('average_user_rating', 0)
                                    user_rating_count = rating_info.get('user_rating_count', 0)
                                    
                                    # Noneや空の場合は0として扱う
                                    if average_rating is None:
                                        average_rating = 0
                                    if user_rating_count is None:
                                        user_rating_count = 0
                                    
                                    item['average_user_rating'] = float(average_rating) or 0
                                    item['user_rating_count'] = int(user_rating_count) or 0
                                    rating_updated_count += 1
                                else:
                                    # 評価情報が取得できなかったアプリを記録
                                    rating_not_found_apps.append({
                                        'app_id': app_id_key,
                                        'name': item.get('name', 'N/A')
                                    })
                            
                            logger.info(f"✅ App Store: {rating_updated_count}件のアプリの評価情報を取得しました")
                            if rating_not_found_apps:
                                logger.warning(f"⚠️ App Store: {len(rating_not_found_apps)}件のアプリの評価情報が取得できませんでした")
                                for app in rating_not_found_apps[:5]:  # 最初の5件のみログ出力
                                    logger.debug(f"  - 評価情報なし: {app['name']} (app_id: {app['app_id']})")
                        else:
                            logger.warning(f"⚠️ App Store: 評価情報の取得に失敗しました (status: {lookup_response.status_code})")
                    except Exception as e:
                        logger.warning(f"⚠️ App Store: 評価情報取得エラー: {e}")
                        # 評価情報が取得できなくても続行
                
                logger.info(f"✅ App Store: {len(formatted_data)}件のトレンドアプリを取得しました (RSS Feed API使用)")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'appstore_rss_feed',
                    'country': country,
                    'category': category,
                    'total_count': len(formatted_data)
                }
            else:
                return {
                    'error': f'App Store RSS Feed API 予期しないレスポンス: {response.status_code}',
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
