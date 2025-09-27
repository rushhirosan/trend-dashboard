import os
import requests
import json
from datetime import datetime, timedelta
from database_config import TrendsCache

class RedditTrendsManager:
    """Redditトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://www.reddit.com"
        self.api_url = "https://oauth.reddit.com"
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = "TrendsApp/1.0"
        self.db = TrendsCache()
        
        print(f"Reddit Trends Manager初期化:")
        print(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        print(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
    
    def get_popular_posts(self, subreddit='all', limit=25, time_filter='day'):
        """Redditの人気投稿を取得"""
        try:
            # Reddit API認証
            access_token = self._get_access_token()
            if not access_token:
                return {'error': 'Reddit API認証に失敗しました'}
            
            # 人気投稿を取得
            url = f"{self.api_url}/r/{subreddit}/hot.json"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': self.user_agent
            }
            params = {
                'limit': limit,
                't': time_filter  # hour, day, week, month, year, all
            }
            
            print(f"Reddit API呼び出し: {url}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                trends_data = []
                for i, post in enumerate(posts):
                    post_data = post.get('data', {})
                    
                    # 投稿情報を抽出
                    trends_data.append({
                        'rank': i + 1,
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
                
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': f'Reddit r/{subreddit}',
                    'total_count': len(trends_data),
                    'subreddit': subreddit,
                    'time_filter': time_filter
                }
            else:
                return {'error': f'Reddit API エラー: {response.status_code}'}
                
        except Exception as e:
            return {'error': f'Redditトレンド取得エラー: {str(e)}'}
    
    def get_trending_subreddits(self, limit=10):
        """トレンド中のサブレディットを取得"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return {'error': 'Reddit API認証に失敗しました'}
            
            url = f"{self.api_url}/subreddits/popular.json"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': self.user_agent
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
            print("Reddit API認証情報が設定されていません")
            return None
        
        try:
            url = "https://www.reddit.com/api/v1/access_token"
            auth = (self.client_id, self.client_secret)
            data = {
                'grant_type': 'client_credentials'
            }
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.post(url, auth=auth, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token')
            else:
                print(f"Reddit API認証エラー: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Reddit API認証エラー: {str(e)}")
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
