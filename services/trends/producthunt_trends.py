import os
import requests
import json
import time
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

class ProductHuntTrendsManager:
    """Product Huntトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.api_url = "https://api.producthunt.com/v2/api/graphql"
        # Product Hunt APIの認証情報（オプション）
        self.client_id = os.getenv('PRODUCTHUNT_CLIENT_ID')
        self.client_secret = os.getenv('PRODUCTHUNT_CLIENT_SECRET')
        self.access_token = None
        
        # レート制限: 認証なしは制限あり、認証ありは緩和される
        self.rate_limit_requests = []
        self.rate_limit_max = 100  # 1時間あたりの最大リクエスト数（認証ありの場合）
        self.rate_limit_window = 3600  # 1時間
        
        self.db = TrendsCache()
        
        # アクセストークンを取得（認証情報が設定されている場合）
        if self.client_id and self.client_secret:
            self._get_access_token()
        
        logger.info(f"Product Hunt Trends Manager初期化:")
        logger.info(f"  API URL: {self.api_url}")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        logger.info(f"  Access Token: {'取得済み' if self.access_token else '未取得（認証なし）'}")
    
    def _get_access_token(self):
        """OAuthアクセストークンを取得"""
        try:
            url = "https://api.producthunt.com/v2/oauth/token"
            
            # Product Hunt APIは application/x-www-form-urlencoded 形式を要求
            # リダイレクトURIを環境変数から取得（設定されていない場合は本番URLを使用）
            redirect_uri = os.getenv('PRODUCTHUNT_REDIRECT_URI', 'https://trends-dashboard.fly.dev/us')
            
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
                'redirect_uri': redirect_uri
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            logger.info(f"Product Hunt OAuth リクエスト: url={url}, client_id={self.client_id}")
            logger.debug(f"Product Hunt OAuth リクエストデータ: {data}")
            logger.debug(f"Product Hunt OAuth リクエストヘッダー: {headers}")
            
            response = requests.post(url, data=data, headers=headers, timeout=10)
            
            logger.info(f"Product Hunt OAuth レスポンス: status={response.status_code}")
            if response.status_code != 200:
                logger.error(f"Product Hunt OAuth エラーレスポンス: {response.text}")
                logger.error(f"Product Hunt OAuth リクエストURL: {url}")
                logger.error(f"Product Hunt OAuth リクエストデータ: {data}")
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                if self.access_token:
                    logger.info("✅ Product Hunt アクセストークン取得成功")
                else:
                    logger.warning("⚠️ Product Hunt アクセストークンがレスポンスに含まれていません")
                    logger.debug(f"Product Hunt OAuth レスポンス: {result}")
                    self.access_token = None
            else:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.warning(f"⚠️ Product Hunt アクセストークン取得失敗: {response.status_code} - {error_text}")
                self.access_token = None
                
        except Exception as e:
            logger.error(f"⚠️ Product Hunt アクセストークン取得エラー: {e}", exc_info=True)
            self.access_token = None
    
    def get_trends(self, limit=25, sort='votes', force_refresh=False):
        """Product Huntトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 Product Hunt force_refresh: キャッシュをクリアします")
                self.db.clear_producthunt_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_producthunt_trends_from_cache()
            
            if cached_data:
                # キャッシュデータを使用する場合でも、cache_statusを更新（スケジューラー実行時の時刻を統一するため）
                if force_refresh:
                    try:
                        self.db.update_cache_status('producthunt_trends', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ Product Hunt: cache_status更新エラー（処理は継続）: {e}")
                
                logger.info(f"✅ Product Hunt: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'sort': sort
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ Product Hunt: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'success': True,  # エラーではなく、データがない状態として扱う
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ Product Hunt: キャッシュデータが見つかりません。外部APIを呼び出します")
                # APIを呼び出してデータを取得
                api_result = self.get_popular_products(limit, sort)
                
                # 認証エラーの場合でも、エラーレスポンスを返す（キャッシュがないため）
                if not api_result.get('success', False):
                    logger.warning("⚠️ Product Hunt: API呼び出し失敗。認証情報が設定されていない可能性があります。")
                    # エラーレスポンスにキャッシュがないことを明示
                    if 'suggestion' not in api_result:
                        api_result['suggestion'] = 'キャッシュにデータがない場合は表示できません。'
                
                return api_result
                
        except Exception as e:
            logger.error(f"❌ Product Hunt トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Product Huntトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _check_rate_limit(self):
        """レート制限をチェックし、必要に応じて待機"""
        now = time.time()
        
        # 1時間以上前のリクエストを削除
        self.rate_limit_requests = [req_time for req_time in self.rate_limit_requests 
                                   if now - req_time < self.rate_limit_window]
        
        # レート制限に達している場合は待機
        if len(self.rate_limit_requests) >= self.rate_limit_max:
            oldest_request = min(self.rate_limit_requests)
            sleep_time = self.rate_limit_window - (now - oldest_request) + 1
            if sleep_time > 0:
                logger.info(f"⏳ Product Hunt API レート制限: {sleep_time:.1f}秒待機します")
                time.sleep(sleep_time)
                # 待機後に再度古いリクエストを削除
                now = time.time()
                self.rate_limit_requests = [req_time for req_time in self.rate_limit_requests 
                                           if now - req_time < self.rate_limit_window]
        
        # 現在のリクエストを記録
        self.rate_limit_requests.append(time.time())
    
    def get_popular_products(self, limit=25, sort='votes'):
        """Product Huntの人気プロダクトを取得"""
        try:
            # アクセストークンが無い場合は取得を試みる
            if not self.access_token and self.client_id and self.client_secret:
                self._get_access_token()
            
            # アクセストークンがまだ無い場合はエラーを返す
            if not self.access_token:
                logger.warning("⚠️ Product Hunt: アクセストークンが取得できませんでした。認証情報を確認してください。")
                # キャッシュにデータがあるか確認
                cached_data = self.db.get_producthunt_trends_from_cache()
                if cached_data:
                    logger.info(f"✅ Product Hunt: 認証情報なしですが、キャッシュから{len(cached_data)}件のデータを取得しました")
                    return {
                        'success': True,
                        'data': cached_data,
                        'status': 'cached',
                        'source': 'database_cache',
                        'sort': sort,
                        'warning': '認証情報が設定されていないため、キャッシュデータを表示しています。最新データを取得するには認証情報を設定してください。'
                    }
                else:
                    # 認証情報が設定されているかどうかでメッセージを変える
                    if self.client_id and self.client_secret:
                        error_msg = 'Product Hunt API認証に失敗しました。認証情報（PRODUCTHUNT_CLIENT_ID、PRODUCTHUNT_CLIENT_SECRET）が正しいか確認してください。'
                    else:
                        error_msg = 'Product Hunt API認証情報が設定されていません。'
                    
                    return {
                        'error': error_msg,
                        'success': False,
                        'status_code': 401,
                        'suggestion': '環境変数 PRODUCTHUNT_CLIENT_ID と PRODUCTHUNT_CLIENT_SECRET を設定してください。キャッシュにデータがない場合は表示できません。'
                    }
            
            # レート制限をチェック
            self._check_rate_limit()
            
            # GraphQLクエリを構築
            # sort: VOTES, CREATED_AT, UPDATED_AT
            sort_map = {
                'votes': 'VOTES',
                'created': 'CREATED_AT',
                'updated': 'UPDATED_AT'
            }
            sort_value = sort_map.get(sort, 'VOTES')
            
            query = f"""
            {{
              posts(order: {sort_value}, first: {min(limit, 50)}) {{
                edges {{
                  node {{
                    id
                    name
                    tagline
                    description
                    url
                    votesCount
                    commentsCount
                    createdAt
                    website
                    topics {{
                      edges {{
                        node {{
                          name
                        }}
                      }}
                    }}
                    user {{
                      name
                      username
                    }}
                  }}
                }}
              }}
            }}
            """
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            logger.debug(f"Product Hunt API呼び出し: {self.api_url}")
            logger.debug(f"Product Hunt GraphQL クエリ: {query[:200]}...")
            
            response = requests.post(
                self.api_url,
                json={'query': query},
                headers=headers,
                timeout=10
            )
            
            logger.debug(f"Product Hunt APIレスポンス: status={response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"Product Hunt APIエラーレスポンス: {error_text}")
                return {
                    'error': f'Product Hunt API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            data = response.json()
            
            # エラーチェック
            if 'errors' in data:
                error_msg = data['errors'][0].get('error_description', 'Unknown error') if data['errors'] else 'Unknown error'
                logger.error(f"Product Hunt GraphQL エラー: {error_msg}")
                return {
                    'error': f'Product Hunt GraphQL エラー: {error_msg}',
                    'success': False,
                    'errors': data['errors']
                }
            
            if 'data' in data and data['data'] and 'posts' in data['data']:
                posts = data['data']['posts']['edges']
                
                # データを整形
                formatted_data = []
                for i, edge in enumerate(posts[:limit], 1):
                    node = edge['node']
                    
                    # トピックをリストに変換
                    topics = []
                    if 'topics' in node and 'edges' in node['topics']:
                        topics = [topic_edge['node']['name'] for topic_edge in node['topics']['edges']]
                    
                    formatted_item = {
                        'product_id': node.get('id', ''),
                        'name': node.get('name', ''),
                        'tagline': node.get('tagline', ''),
                        'description': node.get('description', ''),
                        'url': node.get('url', ''),
                        'website': node.get('website', ''),
                        'votes_count': node.get('votesCount', 0),
                        'comments_count': node.get('commentsCount', 0),
                        'created_at': node.get('createdAt', ''),
                        'topics': topics,
                        'user_name': node.get('user', {}).get('name', ''),
                        'user_username': node.get('user', {}).get('username', ''),
                        'rank': i
                    }
                    formatted_data.append(formatted_item)
                
                # データベースにキャッシュ
                if formatted_data:
                    self.db.save_producthunt_trends_to_cache(formatted_data)
                
                logger.info(f"✅ Product Hunt: {len(formatted_data)}件のプロダクトを取得しました")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'producthunt_api',
                    'sort': sort
                }
            else:
                return {
                    'error': 'Product Hunt API 予期しないレスポンス形式',
                    'success': False
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ Product Hunt API タイムアウトエラー")
            return {
                'error': 'Product Hunt API タイムアウト',
                'success': False
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Product Hunt API リクエストエラー: {e}", exc_info=True)
            return {
                'error': f'Product Hunt API リクエストエラー: {str(e)}',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ Product Hunt トレンド取得エラー: {e}", exc_info=True)
            return {
                'error': f'Product Huntトレンドの取得に失敗しました: {str(e)}',
                'success': False
            }

