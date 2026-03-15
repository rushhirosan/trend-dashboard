import os
import requests
import base64
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager
from utils.dummy_data_generator import generate_dummy_ebay_data

logger = get_logger(__name__)


class eBayTrendsManager(BaseTrendsManager):
    """eBay Popular/Trendingトレンド管理クラス（eBay Browse API使用）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='ebay', max_requests=10, window_seconds=60)
        
        # eBay Client ID (App ID) を環境変数から取得
        self.client_id = os.getenv('EBAY_CLIENT_ID', '').strip()
        # eBay Client Secret (Cert ID) を環境変数から取得
        self.client_secret = os.getenv('EBAY_CLIENT_SECRET', '').strip()
        
        if not self.client_id:
            logger.warning("⚠️ eBay Client ID環境変数が設定されていません。eBay開発者プログラムでApp IDを取得して設定してください。")
        if not self.client_secret:
            logger.warning("⚠️ eBay Client Secret環境変数が設定されていません。eBay開発者プログラムでCert IDを取得して設定してください。")
        
        # サンドボックス環境かどうかを判定（Client IDまたはClient SecretがSBXで始まる場合はサンドボックス）
        is_sandbox = False
        if self.client_id and self.client_id.startswith('SBX-'):
            is_sandbox = True
        elif self.client_secret and self.client_secret.startswith('SBX-'):
            is_sandbox = True
        # サンドボックス環境のApp IDは "AppName-SBX-xxxxx-xxxxx" の形式の場合もある
        elif self.client_id and 'SBX-' in self.client_id:
            is_sandbox = True
        
        if is_sandbox:
            # サンドボックス環境
            self.api_base = 'https://api.sandbox.ebay.com/buy/browse/v1'
            self.oauth_url = 'https://api.sandbox.ebay.com/identity/v1/oauth2/token'
            logger.info("📦 eBayサンドボックス環境を使用します")
        else:
            # 本番環境
            self.api_base = 'https://api.ebay.com/buy/browse/v1'
            self.oauth_url = 'https://api.ebay.com/identity/v1/oauth2/token'
            logger.info("🌐 eBay本番環境を使用します")
        
        # OAuthトークンのキャッシュ
        self.access_token = None
        self.token_expires_at = None
        
        # eBayアフィリエイト設定（.env で管理、ハードコード禁止）
        # campid: パートナー固有のキャンペーンID（10桁、EPN必須）
        # mkrid: マーケットプレイス別ローテーションID（US: 711-53200-19255-0）
        self.ebay_campaign_id = (os.getenv('EBAY_CAMPAIGN_ID') or '').strip()
        affiliate_val = (os.getenv('EBAY_AFFILIATE_ID') or '').strip()
        rotation_val = (os.getenv('EBAY_ROTATION_ID') or '').strip()
        if not self.ebay_campaign_id and affiliate_val and '-' not in affiliate_val:
            # 後方互換: EBAY_AFFILIATE_ID を campid として使用（10桁キャンペーンID想定。ハイフンありは mkrid）
            self.ebay_campaign_id = affiliate_val
        self.ebay_rotation_id = rotation_val or (affiliate_val if (affiliate_val and '-' in affiliate_val) else '711-53200-19255-0')
        if self.ebay_campaign_id:
            logger.info(f"  eBay Campaign ID: 設定済み")
        else:
            logger.warning(f"  eBay Campaign ID: 未設定（.env の EBAY_CAMPAIGN_ID または EBAY_AFFILIATE_ID を設定）")
        
        # カテゴリ定義（カテゴリID、表示名、キーワード）
        self.categories = {
            'cell_phones': {
                'id': '9355',
                'name': 'Cell Phones & Accessories',
                'keyword': 'iphone'
            },
            'fashion': {
                'id': '11450',
                'name': 'Fashion',
                'keyword': 'clothing'
            },
            'home_garden': {
                'id': '11700',
                'name': 'Home & Garden',
                'keyword': 'home'
            },
            'computers': {
                'id': '58058',
                'name': 'Computers/Tablets',
                'keyword': 'laptop'
            },
            'video_games': {
                'id': '1249',
                'name': 'Video Games & Consoles',
                'keyword': 'playstation'
            },
            'beauty': {
                'id': '26395',
                'name': 'Beauty & Health',
                'keyword': 'makeup'
            },
            'toys': {
                'id': '220',
                'name': 'Toys & Hobbies',
                'keyword': 'lego'
            },
            'sports': {
                'id': '888',
                'name': 'Sports & Outdoors',
                'keyword': 'fitness'
            },
            'automotive': {
                'id': '6000',
                'name': 'Automotive Parts & Accessories',
                'keyword': 'car parts'
            }
        }
        
        logger.info("eBay Popular/Trending Trends Manager初期化:")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        logger.info(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
        logger.info(f"  カテゴリ数: {len(self.categories)}")
    
    def get_available_categories(self):
        """利用可能なカテゴリ一覧を取得"""
        return list(self.categories.keys())

    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'ebay_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            category = kwargs.get('category', 'fashion')
            if category not in self.categories:
                category = 'fashion'
            return self.db.get_ebay_trends_from_cache(category)
        except Exception as e:
            logger.error(f"❌ eBay: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            category = kwargs.get('category', 'fashion')
            if category not in self.categories:
                category = 'fashion'
            return self.db.save_ebay_trends_to_cache(data, category)
        except Exception as e:
            logger.error(f"❌ eBay: キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            category = kwargs.get('category')
            return self.db.clear_ebay_trends_cache(category)
        except Exception as e:
            logger.error(f"❌ eBay: キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ eBay: cache_status更新エラー: {e}")
            return False

    def _generate_dummy_data(self, limit=25, *args, **kwargs):
        """eBay用ダミーデータを生成（USE_DUMMY_DATA 時）"""
        category = kwargs.get('category', 'fashion')
        if category not in self.categories:
            category = 'fashion'
        return generate_dummy_ebay_data(category=category, limit=limit)
        
    def get_trends(self, category='fashion', limit=25, force_refresh=False):
        """eBay Popular/Trendingトレンドを取得（ベースクラスの共通処理を使用）"""
        # カテゴリの検証
        if category not in self.categories:
            logger.warning(f"⚠️ eBay: 無効なカテゴリ '{category}'、デフォルト 'fashion' を使用します")
            category = 'fashion'
        
        # 認証未設定時はダミーモード以外で早期リターン（ベースの_fetch_trends前にエラー返却）
        if not self._is_dummy_mode() and (not self.client_id or not self.client_secret):
            logger.warning("⚠️ eBay: 認証情報が設定されていません")
            missing = []
            if not self.client_id:
                missing.append('EBAY_CLIENT_ID')
            if not self.client_secret:
                missing.append('EBAY_CLIENT_SECRET')
            return {
                'success': False,
                'data': [],
                'status': 'api_key_not_configured',
                'error': f'eBay認証情報が設定されていません。環境変数{", ".join(missing)}を設定してください。',
                'source': 'ebay_api',
                'category': category
            }
        
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key='rank',
            sort_reverse=False,
            category=category
        )
        if result and isinstance(result, dict):
            result['category'] = category
        return result
    
    def _add_affiliate_params(self, url):
        """eBay URLにアフィリエイトパラメータを追加（EPN形式）
        
        EPN必須パラメータ: mkevt(1=Click), mkcid(1=EPN), mkrid(ローテーションID), campid(キャンペーンID), toolid(10001)
        参考: https://developer.ebay.com/api-docs/buy/static/ref-epn-link.html
        
        Args:
            url: eBay商品URL
        
        Returns:
            str: アフィリエイトパラメータが追加されたURL、または元のURL（campid未設定時）
        """
        if not self.ebay_campaign_id or not url:
            return url
        
        separator = '&' if '?' in url else '?'
        params = f"mkevt=1&mkcid=1&mkrid={self.ebay_rotation_id}&campid={self.ebay_campaign_id}&toolid=10001"
        return f"{url}{separator}{params}"
    
    def _fetch_trends(self, category='fashion', limit=25, *args, **kwargs):
        """eBay Browse APIから人気商品を取得
        
        Args:
            category (str): カテゴリ名
            limit (int): 取得件数
        """
        try:
            self.rate_limiter.wait_if_needed()
            
            # OAuthトークンを取得
            oauth_token = self._get_oauth_token()
            if not oauth_token:
                return {
                    'success': False,
                    'data': [],
                    'status': 'oauth_token_error',
                    'error': 'OAuthトークンの取得に失敗しました。認証情報を確認してください。',
                    'source': 'ebay_api'
                }
            
            # eBay Browse API - item_summary_searchを使用
            # 実際のAPI仕様: https://developer.ebay.com/api-docs/buy/browse/overview.html
            endpoint = f"{self.api_base}/item_summary/search"
            
            headers = {
                'Authorization': f'Bearer {oauth_token}',
                'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
                'Content-Type': 'application/json'
            }
            
            # カテゴリ情報を取得
            if category not in self.categories:
                category = 'fashion'
            category_info = self.categories[category]
            
            # パラメータ: 人気商品を取得
            # サンドボックス環境でも動作するように、具体的なキーワード + カテゴリID + フィルターで絞り込み
            params = {
                'q': category_info['keyword'],  # カテゴリに応じたキーワード
                'category_ids': category_info['id'],  # カテゴリID
                'filter': 'conditions:{NEW};price:[50..1500]',  # 新品のみ、価格フィルター
                'sort': 'bestMatch',  # ベストマッチ順
                'limit': min(limit, 25),  # 25件に固定
                'offset': 0
            }
            
            logger.info(f"eBay Browse API呼び出し開始: {endpoint}")
            logger.info(f"📋 eBay API パラメータ: {params}")
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=15)
            
            logger.info(f"📊 eBay API: HTTP status={response.status_code}")
            
            if response.status_code == 401:
                logger.error("❌ eBay API: 認証エラー（OAuthトークンが無効）")
                # トークンをクリアして再取得を試みる
                self.access_token = None
                self.token_expires_at = None
                return {
                    'success': False,
                    'data': [],
                    'status': 'authentication_error',
                    'error': 'eBay API認証エラー。OAuthトークンを確認してください。',
                    'source': 'ebay_api'
                }
            
            if response.status_code != 200:
                error_text = response.text[:200] if response.text else ''
                logger.warning(f"⚠️ eBay API: HTTP {response.status_code} - {error_text}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'api_error',
                    'source': 'ebay_api',
                    'error': f'eBay APIエラー: HTTP {response.status_code}'
                }
            
            data = response.json()
            items = data.get('itemSummaries', [])
            
            if not items:
                logger.warning(f"⚠️ eBay API: 商品が見つかりませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_items',
                    'source': 'ebay_api'
                }
            
            logger.info(f"✅ eBay API: {len(items)}件の商品を取得")
            
            # データを整形
            formatted_data = []
            for i, item in enumerate(items[:limit], 1):
                try:
                    formatted_item = {
                        'rank': i,
                        'title': item.get('title', 'No Title'),
                        'url': self._add_affiliate_params(item.get('itemWebUrl', '')),
                        'item_id': item.get('itemId', ''),
                        'price': item.get('price', {}).get('value', '') if item.get('price') else '',
                        'currency': item.get('price', {}).get('currency', 'USD') if item.get('price') else 'USD',
                        'image_url': item.get('image', {}).get('imageUrl', '') if item.get('image') else '',
                        'condition': item.get('condition', ''),
                        'seller': item.get('seller', {}).get('username', '') if item.get('seller') else '',
                        'shipping': item.get('shippingOptions', [{}])[0].get('shippingCost', {}).get('value', '') if item.get('shippingOptions') else '',
                        'category': category,  # カテゴリ情報を追加
                        'source': 'eBay Popular/Trending',
                        'published_date': datetime.now().isoformat()
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ eBay アイテムパースエラー: {e}")
                    continue
            
            final_data = formatted_data[:limit]
            # キャッシュ保存はベースクラスのget_trendsが_save_to_cacheを呼ぶ

            logger.info(f"✅ eBay: カテゴリ '{category}' から{len(final_data)}件の人気商品を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'category': category,
                'source': 'ebay_api',
                'total_count': len(final_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ eBay API タイムアウトエラー", exc_info=True)
            return {'error': 'eBay API タイムアウト', 'success': False}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ eBay API リクエストエラー: {e}", exc_info=True)
            return {'error': f'eBay APIリクエストエラー: {str(e)}', 'success': False}
        except Exception as e:
            logger.error(f"❌ eBay API エラー: {e}", exc_info=True)
            return {'error': f'eBay API取得エラー: {str(e)}', 'success': False}
    
    def _get_oauth_token(self):
        """OAuth 2.0トークンを取得（Client Credentials Grant）
        
        Returns:
            str: アクセストークン、またはNone（取得失敗時）
        """
        try:
            # トークンが有効期限切れでない場合は既存のものを使用
            if self.access_token and self.token_expires_at:
                if datetime.now() < self.token_expires_at - timedelta(minutes=5):  # 5分前に更新
                    return self.access_token
            
            if not self.client_id or not self.client_secret:
                logger.error("❌ eBay OAuth: 認証情報が設定されていません")
                return None
            
            # Basic認証用の認証情報をBase64エンコード
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            # OAuth 2.0 Client Credentials Grant
            data = {
                'grant_type': 'client_credentials'
            }
            # サンドボックス・本番環境ともに最小スコープを使用
            data['scope'] = 'https://api.ebay.com/oauth/api_scope'
            
            logger.info(f"eBay OAuth トークン取得開始: {self.oauth_url}")
            
            response = requests.post(self.oauth_url, headers=headers, data=data, timeout=10)
            
            logger.info(f"📊 eBay OAuth: HTTP status={response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 7200)  # デフォルト2時間
                
                if self.access_token:
                    # 有効期限を設定（expires_in秒後）
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 5分前に更新
                    logger.info(f"✅ eBay OAuth トークン取得成功（有効期限: {self.token_expires_at}）")
                    return self.access_token
                else:
                    logger.error("❌ eBay OAuth: トークンがレスポンスに含まれていません")
                    logger.debug(f"eBay OAuth レスポンス: {token_data}")
                    return None
            else:
                error_text = response.text[:500] if response.text else ''
                logger.error(f"❌ eBay OAuth トークン取得失敗: {response.status_code} - {error_text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ eBay OAuth トークン取得エラー: {e}", exc_info=True)
            return None
