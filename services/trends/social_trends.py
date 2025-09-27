import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache

class SocialTrendsManager:
    """Instagram/Threadsのトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.db = TrendsCache()
        self.instagram_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        
        print(f"Social Trends Manager初期化:")
        print(f"  Instagram Token: {'設定済み' if self.instagram_token else '未設定'}")
    
    def get_instagram_trends(self, hashtag=None, limit=25):
        """Instagramのトレンドを取得（Basic Display API使用）"""
        if not self.instagram_token:
            return {'error': 'Instagramアクセストークンが設定されていません'}
        
        try:
            # Instagram Basic Display API
            url = f"https://graph.instagram.com/me/media"
            params = {
                'access_token': self.instagram_token,
                'fields': 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count',
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'data': data.get('data', []),
                    'status': 'success',
                    'source': 'Instagram Basic Display API'
                }
            else:
                return {'error': f'Instagram API エラー: {response.status_code}'}
                
        except Exception as e:
            return {'error': f'Instagramトレンド取得エラー: {str(e)}'}
    
    def get_threads_trends(self, limit=25):
        """Threadsのトレンドを取得（非公式）"""
        # 注意: これは利用規約に違反する可能性があります
        # 実装は省略
        return {'error': 'Threadsの公式APIは存在しません。非公式スクレイピングは利用規約に違反する可能性があります。'}
    
    def get_social_trends_summary(self):
        """ソーシャルメディアトレンドの概要を取得"""
        return {
            'instagram': {
                'available': bool(self.instagram_token),
                'note': 'Basic Display API: 個人の投稿データのみ取得可能'
            },
            'threads': {
                'available': False,
                'note': '公式APIなし、非公式スクレイピングは利用規約違反の可能性'
            },
            'recommendations': [
                'Instagram Basic Display APIを使用して個人データを取得',
                'サードパーティサービス（Social Blade, Brand24等）の利用を検討',
                'Webスクレイピングは利用規約に注意'
            ]
        }
