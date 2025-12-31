import os
import requests
import json
import time
from datetime import datetime, timedelta
from collections import deque
from database_config import TrendsCache
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

class RedditTrendsManager:
    """Redditトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://www.reddit.com"
        self.api_url = "https://oauth.reddit.com"
        # 認証なしで使用するため、環境変数は読み込むが必須ではない
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        
        # Redditが要求するUser-Agent形式: platform:appid:version (by /u/username)
        # 環境変数REDDIT_USERNAMEが設定されていれば使用、なければデフォルト値
        reddit_username = os.getenv('REDDIT_USERNAME', 'trends_dashboard')
        self.user_agent = f"web:trends_dashboard:1.0.0 (by /u/{reddit_username})"
        
        # レート制限: 1分間に最大100リクエスト
        # リクエストのタイムスタンプを記録
        self.rate_limit_requests = deque()
        self.rate_limit_max = 100  # 1分間の最大リクエスト数
        self.rate_limit_window = 60  # 時間窓（秒）
        
        self.db = TrendsCache()
        
        logger.info(f"Reddit Trends Manager初期化（認証なしモード）:")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定（認証なしで試行）'}")
        logger.info(f"  Client Secret: {'設定済み' if self.client_secret else '未設定（認証なしで試行）'}")
        logger.info(f"  User-Agent: {self.user_agent}")
    
    def get_trends(self, subreddit='all', limit=25, time_filter='day', force_refresh=False):
        """Redditトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 Reddit force_refresh: キャッシュをクリアします")
                self.db.clear_reddit_trends_cache(subreddit)
            
            # キャッシュからデータを取得
            cached_data = self.db.get_reddit_trends_from_cache(subreddit)
            
            if cached_data:
                logger.info(f"✅ Reddit: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'subreddit': subreddit
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ Reddit: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': False,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'subreddit': subreddit,
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ Reddit: キャッシュデータが見つかりません。外部APIを呼び出します")
                api_result = self.get_popular_posts(subreddit, limit, time_filter)
                
                # 403エラーまたはその他のエラーが発生した場合、キャッシュを再確認
                if not api_result.get('success', False) and api_result.get('status_code') == 403:
                    logger.warning("⚠️ Reddit API 403エラー発生。キャッシュを再確認します...")
                    cached_data = self.db.get_reddit_trends_from_cache(subreddit)
                    if cached_data:
                        logger.info(f"✅ Reddit: 403エラー後、キャッシュから{len(cached_data)}件のデータを取得しました")
                        return {
                            'success': True,
                            'data': cached_data,
                            'status': 'cached_fallback',
                            'source': 'database_cache',
                            'subreddit': subreddit,
                            'warning': 'APIアクセスが拒否されましたが、キャッシュデータを表示しています。'
                        }
                
                return api_result
                
        except Exception as e:
            logger.error(f"❌ Reddit トレンド取得エラー: {e}", exc_info=True)
            # エラー時にもキャッシュを確認
            try:
                cached_data = self.db.get_reddit_trends_from_cache(subreddit)
                if cached_data:
                    logger.info(f"✅ Reddit: エラー後、キャッシュから{len(cached_data)}件のデータを取得しました")
                    return {
                        'success': True,
                        'data': cached_data,
                        'status': 'cached_fallback',
                        'source': 'database_cache',
                        'subreddit': subreddit
                    }
            except:
                pass
            
            return {'error': f'Redditトレンドの取得に失敗しました: {str(e)}'}
    
    def _check_rate_limit(self):
        """レート制限をチェックし、必要に応じて待機"""
        now = time.time()
        
        # 1分以上前のリクエストを削除
        while self.rate_limit_requests and now - self.rate_limit_requests[0] > self.rate_limit_window:
            self.rate_limit_requests.popleft()
        
        # レート制限に達している場合は待機
        if len(self.rate_limit_requests) >= self.rate_limit_max:
            sleep_time = self.rate_limit_window - (now - self.rate_limit_requests[0]) + 1
            if sleep_time > 0:
                logger.info(f"⏳ Reddit API レート制限: {sleep_time:.1f}秒待機します")
                time.sleep(sleep_time)
                # 待機後に再度古いリクエストを削除
                now = time.time()
                while self.rate_limit_requests and now - self.rate_limit_requests[0] > self.rate_limit_window:
                    self.rate_limit_requests.popleft()
        
        # 現在のリクエストを記録
        self.rate_limit_requests.append(time.time())
    
    def _is_deleted_or_removed(self, post_data):
        """投稿が削除または削除済みかどうかを判定"""
        author = post_data.get('author', '')
        selftext = post_data.get('selftext', '')
        
        # 作者が削除された、または投稿が削除/削除済み
        if author == '[deleted]' or author == '':
            return True
        if selftext == '[deleted]' or selftext == '[removed]':
            return True
        
        return False
    
    def get_popular_posts(self, subreddit='all', limit=25, time_filter='day'):
        """Redditの人気投稿を取得（認証情報があれば認証を使用、なければ公開API）"""
        try:
            # レート制限をチェック
            self._check_rate_limit()
            
            # 認証情報が設定されている場合は認証を使用
            access_token = None
            if self.client_id and self.client_secret:
                access_token = self._get_access_token()
                if access_token:
                    logger.info("✅ Reddit API認証を使用します")
                else:
                    logger.warning("⚠️ Reddit API認証に失敗しました。認証なしで試行します")
            
            # 認証情報がある場合はOAuth APIを使用、ない場合は公開APIを使用
            if access_token:
                url = f"{self.api_url}/r/{subreddit}/hot.json"
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'User-Agent': self.user_agent,
                    'Accept': 'application/json'
                }
                logger.debug(f"Reddit API呼び出し（認証あり）: {url}")
            else:
                url = f"{self.base_url}/r/{subreddit}/hot.json"
                headers = {
                    'User-Agent': self.user_agent,
                    'Accept': 'application/json'
                }
                logger.debug(f"Reddit API呼び出し（認証なし）: {url}")
            
            params = {
                'limit': min(limit, 100)  # Redditの最大制限は100
            }
            
            logger.debug(f"Reddit API User-Agent: {self.user_agent}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            logger.debug(f"Reddit APIレスポンス: status={response.status_code}")
            
            # 403エラーの場合、認証が必要な可能性があることを伝える
            if response.status_code == 403:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"❌ Reddit API 403エラー: {error_text[:200]}")
                
                # 認証なしで試行していた場合、認証を試す
                if not access_token and self.client_id and self.client_secret:
                    logger.info("🔄 認証なしで403エラーが発生しました。認証を試行します...")
                    access_token = self._get_access_token()
                    if access_token:
                        headers['Authorization'] = f'Bearer {access_token}'
                        url = f"{self.api_url}/r/{subreddit}/hot.json"
                        response = requests.get(url, headers=headers, params=params, timeout=10)
                        logger.debug(f"Reddit API再試行レスポンス: status={response.status_code}")
                        if response.status_code == 200:
                            logger.info("✅ 認証を使用してReddit APIアクセス成功")
                            # 成功した場合は処理を継続（下の200チェックへ）
                        else:
                            # 再試行後も403の場合はエラーを返す
                            logger.warning(f"⚠️ 認証後も403エラー: {response.status_code}")
                            return {
                                'error': 'Reddit API アクセスが拒否されました（403）。',
                                'success': False,
                                'status_code': 403,
                                'suggestion': 'Reddit APIキー（Client ID/Secret）を確認するか、キャッシュデータを確認してください。'
                            }
                    else:
                        # 認証トークン取得失敗
                        return {
                            'error': 'Reddit API アクセスが拒否されました（403）。認証情報の取得に失敗しました。',
                            'success': False,
                            'status_code': 403,
                            'suggestion': 'Reddit APIキー（Client ID/Secret）を確認するか、キャッシュデータを確認してください。'
                        }
                else:
                    # 認証情報がない場合
                    return {
                        'error': 'Reddit API アクセスが拒否されました（403）。',
                        'success': False,
                        'status_code': 403,
                        'suggestion': 'Reddit APIキー（Client ID/Secret）の設定を検討するか、キャッシュデータを確認してください。',
                        'note': '本番環境ではIPアドレスがブロックされている可能性があります。'
                    }
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"Reddit APIエラーレスポンス: {error_text}")
                return {
                    'error': f'Reddit API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            if response.status_code == 200:
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                if not posts:
                    logger.warning(f"⚠️ Reddit: 投稿データが見つかりませんでした (subreddit: {subreddit})")
                    return {'error': 'Reddit投稿データが見つかりませんでした', 'success': False}
                
                trends_data = []
                valid_rank = 1
                for post in posts:
                    post_data = post.get('data', {})
                    
                    # 削除された投稿をスキップ
                    if self._is_deleted_or_removed(post_data):
                        continue
                    
                    # 投稿情報を抽出
                    trends_data.append({
                        'rank': valid_rank,
                        'post_id': post_data.get('id', ''),
                        'title': post_data.get('title', ''),
                        'url': post_data.get('url', ''),
                        'subreddit': post_data.get('subreddit', ''),
                        'author': post_data.get('author', ''),
                        'score': post_data.get('score', 0),
                        'upvote_ratio': post_data.get('upvote_ratio', 0),
                        'num_comments': post_data.get('num_comments', 0),
                        'created_utc': post_data.get('created_utc', 0),
                        'permalink': f"https://reddit.com{post_data.get('permalink', '')}",
                        'is_video': post_data.get('is_video', False),
                        'domain': post_data.get('domain', ''),
                        'category': 'reddit'
                    })
                    valid_rank += 1
                
                # キャッシュに保存
                self.db.save_reddit_trends_to_cache(trends_data, subreddit)
                
                logger.info(f"✅ Reddit: {len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                
                return {
                    'success': True,
                    'data': trends_data,
                    'status': 'api_fetched',
                    'source': f'Reddit r/{subreddit}',
                    'total_count': len(trends_data),
                    'subreddit': subreddit,
                    'time_filter': time_filter
                }
                
        except Exception as e:
            logger.error(f"❌ Redditトレンド取得エラー: {str(e)}", exc_info=True)
            return {'error': f'Redditトレンド取得エラー: {str(e)}', 'success': False}
    
    def get_trending_subreddits(self, limit=10):
        """トレンド中のサブレディットを取得"""
        try:
            # レート制限をチェック
            self._check_rate_limit()
            
            access_token = self._get_access_token()
            if not access_token:
                return {'error': 'Reddit API認証に失敗しました'}
            
            # レート制限をチェック（APIリクエスト前）
            self._check_rate_limit()
            
            url = f"{self.api_url}/subreddits/popular.json"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': self.user_agent,
                'Accept': 'application/json'
            }
            params = {'limit': limit}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subreddits = data.get('data', {}).get('children', [])
                
                trends_data = []
                for i, subreddit in enumerate(subreddits):
                    subreddit_data = subreddit.get('data', {})
                    
                    trends_data.append({
                        'rank': i + 1,
                        'name': subreddit_data.get('display_name', ''),
                        'title': subreddit_data.get('title', ''),
                        'description': subreddit_data.get('public_description', ''),
                        'subscribers': subreddit_data.get('subscribers', 0),
                        'active_user_count': subreddit_data.get('active_user_count', 0),
                        'url': f"https://reddit.com/r/{subreddit_data.get('display_name', '')}",
                        'category': 'subreddit'
                    })
                
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': 'Reddit人気サブレディット',
                    'total_count': len(trends_data)
                }
            else:
                return {'error': f'Reddit API エラー: {response.status_code}'}
                
        except Exception as e:
            return {'error': f'Redditサブレディット取得エラー: {str(e)}'}
    
    def _get_access_token(self):
        """Reddit APIアクセストークンを取得"""
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit API認証情報が設定されていません")
            return None
        
        try:
            # レート制限をチェック（認証リクエストもカウント）
            self._check_rate_limit()
            
            url = "https://www.reddit.com/api/v1/access_token"
            auth = (self.client_id, self.client_secret)
            data = {
                'grant_type': 'client_credentials'
            }
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'application/json'
            }
            
            response = requests.post(url, auth=auth, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token')
            else:
                logger.error(f"Reddit API認証エラー: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Reddit API認証エラー: {str(e)}", exc_info=True)
            return None
    
    def get_reddit_trends_summary(self):
        """Redditトレンドの概要を取得"""
        return {
            'reddit_api': {
                'available': bool(self.client_id and self.client_secret),
                'note': 'Reddit公式API: 人気投稿、サブレディット',
                'features': [
                    '人気投稿取得',
                    'サブレディット別分類',
                    '投票数・コメント数',
                    '時間フィルター',
                    '公式API使用'
                ]
            },
            'limitations': [
                'API認証が必要',
                'レート制限あり',
                '英語中心'
            ],
            'setup_required': [
                'Redditアプリケーション登録',
                'Client ID/Secret取得'
            ]
        }
