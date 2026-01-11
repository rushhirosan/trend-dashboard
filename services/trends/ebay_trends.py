import os
import requests
import base64
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class eBayTrendsManager:
    """eBay Popular/Trendingトレンド管理クラス（eBay Browse API使用）"""

    def __init__(self):
        """初期化"""
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
        
        self.db = TrendsCache()
        # レート制限: eBay APIの推奨に従い、1時間に5000リクエスト（保守的に1分に10リクエストに設定）
        self.rate_limiter = get_rate_limiter('ebay', max_requests=10, window_seconds=60)
        
        logger.info("eBay Popular/Trending Trends Manager初期化:")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        logger.info(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
        
    def get_trends(self, limit=25, force_refresh=False):
        """eBay Popular/Trendingトレンドを取得（キャッシュ優先）
        
        Args:
            limit (int): 取得件数
            force_refresh (bool): キャッシュを無視して取得するかどうか
        """
        try:
            if not self.client_id or not self.client_secret:
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
                    'source': 'ebay_api'
                }
            
            if force_refresh:
                logger.info(f"🔄 eBay force_refresh: キャッシュをクリアします")
                self.db.clear_ebay_trends_cache()

            cached_data = self.db.get_ebay_trends_from_cache()
            if cached_data:
                # ランキングでソート（昇順）
                cached_data.sort(key=lambda x: x.get('rank', 999), reverse=False)
                logger.info(f"✅ eBay: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                if not force_refresh:
                    logger.warning(f"⚠️ eBay: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'message': 'キャッシュにデータがありません。force_refresh=trueで更新してください。'
                    }
                logger.warning(f"⚠️ eBay: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_ebay_trends(limit)

        except Exception as e:
            logger.error(f"❌ eBay トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'eBayトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_ebay_trends(self, limit=25):
        """eBay Browse APIから人気商品を取得
        
        Args:
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
            
            # パラメータ: 人気商品を取得
            # サンドボックス環境でも動作するように、具体的なキーワード + カテゴリID + フィルターで絞り込み
            params = {
                'q': 'iphone',  # 具体的なキーワード
                'category_ids': '9355',  # ElectronicsカテゴリID（エラー回避のため絞り込み）
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
                        'url': item.get('itemWebUrl', ''),
                        'item_id': item.get('itemId', ''),
                        'price': item.get('price', {}).get('value', '') if item.get('price') else '',
                        'currency': item.get('price', {}).get('currency', 'USD') if item.get('price') else 'USD',
                        'image_url': item.get('image', {}).get('imageUrl', '') if item.get('image') else '',
                        'condition': item.get('condition', ''),
                        'seller': item.get('seller', {}).get('username', '') if item.get('seller') else '',
                        'shipping': item.get('shippingOptions', [{}])[0].get('shippingCost', {}).get('value', '') if item.get('shippingOptions') else '',
                        'source': 'eBay Popular/Trending',
                        'published_date': datetime.now().isoformat()
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ eBay アイテムパースエラー: {e}")
                    continue
            
            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_ebay_trends_to_cache(final_data)
                self.db.update_cache_status('ebay_trends', len(final_data))

            logger.info(f"✅ eBay: {len(final_data)}件の人気商品を取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
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
