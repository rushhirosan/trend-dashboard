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
                        'success': True,  # エラーではなく、データがない状態として扱う
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'country': country,
                        'category': category
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ App Store: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self.get_top_apps(country, category, limit)
                
        except Exception as e:
            logger.error(f"❌ App Store トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'App Storeトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def get_top_apps(self, country='JP', category='all', limit=25):
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
                
                # データを整形
                formatted_data = []
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
                        
                        # 評価情報
                        rating_info = entry.get('im:rating', {}) if isinstance(entry.get('im:rating'), dict) else {}
                        average_user_rating = float(rating_info.get('label', 0)) if rating_info.get('label') else 0
                        
                        rating_count_info = entry.get('im:ratingCount', {}) if isinstance(entry.get('im:ratingCount'), dict) else {}
                        user_rating_count = int(rating_count_info.get('label', 0)) if rating_count_info.get('label') else 0
                        
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
                            'average_user_rating': average_user_rating,
                            'user_rating_count': user_rating_count,
                            'release_date': release_date,
                            'current_version_release_date': release_date,
                            'artwork_url_60': artwork_url_100,  # RSS Feedには60pxがないので100pxを使用
                            'artwork_url_100': artwork_url_100,
                            'artwork_url_512': artwork_url_512,
                            'screenshot_urls': [],  # RSS Feedにはスクリーンショットがない
                            'rank': i
                        }
                        formatted_data.append(formatted_item)
                    except Exception as e:
                        logger.warning(f"App Store エントリ処理エラー (rank {i}): {e}")
                        continue
                
                # データベースにキャッシュ
                if formatted_data:
                    self.db.save_appstore_trends_to_cache(formatted_data, country)
                    # cache_statusを更新
                    cache_key = f'appstore_trends_{country}'
                    self.db.update_cache_status(cache_key, len(formatted_data))
                
                logger.info(f"✅ App Store: {len(formatted_data)}件のトレンドアプリを取得しました (RSS Feed API使用)")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'appstore_rss_feed',
                    'country': country,
                    'category': category
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

