import os
import requests
import json
import time
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

class QiitaTrendsManager:
    """Qiitaトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://qiita.com"
        self.api_url = f"{self.base_url}/api/v2"
        # Qiita APIの認証トークン（オプション、レート制限緩和のため）
        self.access_token = os.getenv('QIITA_ACCESS_TOKEN')
        
        # レート制限: 認証なしは1時間60回、認証ありは1時間1000回
        # リクエストのタイムスタンプを記録
        self.rate_limit_requests = []
        self.rate_limit_max = 60 if not self.access_token else 1000  # 認証ありの場合は1000回
        self.rate_limit_window = 3600  # 1時間
        
        self.db = TrendsCache()
        
        logger.info(f"Qiita Trends Manager初期化:")
        logger.info(f"  API URL: {self.api_url}")
        logger.info(f"  Access Token: {'設定済み' if self.access_token else '未設定（認証なし、1時間60回制限）'}")
        logger.info(f"  レート制限: 1時間{self.rate_limit_max}回")
    
    def get_trends(self, limit=25, sort='likes_count', force_refresh=False):
        """Qiitaトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 Qiita force_refresh: キャッシュをクリアします")
                self.db.clear_qiita_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_qiita_trends_from_cache()
            
            if cached_data:
                logger.info(f"✅ Qiita: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'sort': sort
                }
            else:
                logger.warning("⚠️ Qiita: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self.get_popular_items(limit, sort)
                
        except Exception as e:
            logger.error(f"❌ Qiita トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Qiitaトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
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
                logger.info(f"⏳ Qiita API レート制限: {sleep_time:.1f}秒待機します")
                time.sleep(sleep_time)
                # 待機後に再度古いリクエストを削除
                now = time.time()
                self.rate_limit_requests = [req_time for req_time in self.rate_limit_requests 
                                           if now - req_time < self.rate_limit_window]
        
        # 現在のリクエストを記録
        self.rate_limit_requests.append(time.time())
    
    def get_popular_items(self, limit=25, sort='likes_count'):
        """Qiitaの人気記事を取得"""
        try:
            # レート制限をチェック
            self._check_rate_limit()
            
            # Qiita API v2を使用
            url = f"{self.api_url}/items"
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # 認証トークンが設定されている場合は追加
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
            
            params = {
                'per_page': min(limit, 100),  # Qiitaの最大制限は100
                'page': 1,
                'query': 'stocks:>10'  # ストック数10以上の記事を取得（トレンド記事の目安）
            }
            
            logger.debug(f"Qiita API呼び出し: {url}")
            logger.debug(f"Qiita API パラメータ: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            logger.debug(f"Qiita APIレスポンス: status={response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"Qiita APIエラーレスポンス: {error_text}")
                return {
                    'error': f'Qiita API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            if response.status_code == 200:
                items = response.json()
                
                # いいね数やストック数でソート
                if sort == 'likes_count':
                    items.sort(key=lambda x: x.get('likes_count', 0), reverse=True)
                elif sort == 'stocks_count':
                    items.sort(key=lambda x: x.get('stocks_count', 0), reverse=True)
                elif sort == 'created_at':
                    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
                # データを整形
                formatted_data = []
                for i, item in enumerate(items[:limit], 1):
                    formatted_item = {
                        'item_id': item.get('id', ''),
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'user_id': item.get('user', {}).get('id', ''),
                        'user_name': item.get('user', {}).get('name', ''),
                        'likes_count': item.get('likes_count', 0),
                        'stocks_count': item.get('stocks_count', 0),
                        'comments_count': item.get('comments_count', 0),
                        'created_at': item.get('created_at', ''),
                        'updated_at': item.get('updated_at', ''),
                        'tags': [tag.get('name', '') for tag in item.get('tags', [])],
                        'rank': i
                    }
                    formatted_data.append(formatted_item)
                
                # データベースにキャッシュ
                if formatted_data:
                    self.db.save_qiita_trends_to_cache(formatted_data)
                
                logger.info(f"✅ Qiita: {len(formatted_data)}件のトレンド記事を取得しました")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'qiita_api',
                    'sort': sort
                }
            else:
                return {
                    'error': f'Qiita API 予期しないレスポンス: {response.status_code}',
                    'success': False
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ Qiita API タイムアウトエラー")
            return {
                'error': 'Qiita API タイムアウト',
                'success': False
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Qiita API リクエストエラー: {e}", exc_info=True)
            return {
                'error': f'Qiita API リクエストエラー: {str(e)}',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ Qiita トレンド取得エラー: {e}", exc_info=True)
            return {
                'error': f'Qiitaトレンドの取得に失敗しました: {str(e)}',
                'success': False
            }

