"""
YouTube Trends関連の処理を管理するモジュール
"""

import os
from datetime import datetime, timezone
from googleapiclient.discovery import build
from database_config import TrendsCache

class YouTubeTrendsManager:
    """YouTube Trendsの管理クラス"""
    
    def __init__(self):
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.db = TrendsCache()
    
    def get_trends(self, region_code: str = 'JP', max_results: int = 25, force_refresh=False):
        """YouTubeのトレンド動画を取得"""
        if not self.youtube_api_key:
            return {'error': 'YouTube APIキーが設定されていません'}
        
        try:
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache(region_code):
                print(f"⚠️ YouTubeのキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                cached_data = self.db.get_youtube_trends_from_cache(region_code)
                if cached_data:
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'region_code': region_code
                    }
            
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # 人気動画を取得
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                maxResults=max_results
            )
            
            response = request.execute()
            
            if not response.get('items'):
                return {'error': '動画データが取得できませんでした'}
            
            # データを整形
            trends = []
            for i, item in enumerate(response['items'], 1):
                try:
                    trends.append({
                        'rank': i,
                        'title': item['snippet']['title'],
                        'channel_title': item['snippet']['channelTitle'],
                        'view_count': int(item['statistics'].get('viewCount', 0)),
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'comment_count': int(item['statistics'].get('commentCount', 0)),
                        'published_at': item['snippet']['publishedAt'],
                        'video_id': item['id'],
                        'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                        'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                    })
                except Exception as e:
                    print(f"動画データの処理でエラー: {e}")
                    continue
            
            # 視聴回数で再ソートして正しい順位を設定
            if trends:
                trends.sort(key=lambda x: x['view_count'], reverse=True)
                for i, trend in enumerate(trends, 1):
                    trend['rank'] = i
            
            print(f"視聴回数順でソート完了: 1位={trends[0]['view_count']:,}回, 25位={trends[-1]['view_count']:,}回")
            
            # キャッシュに保存
            self.save_to_cache(region_code, 'trending', trends)
            
            return trends
            
        except Exception as e:
            print(f"YouTube Data APIでエラー: {e}")
            return {'error': f'YouTube Data APIでエラーが発生しました: {str(e)}'}

    def get_rising_trends(self, region_code: str = 'JP', max_results: int = 25):
        """YouTubeの急上昇トレンド動画を取得（投稿日時と視聴回数から推定）"""
        if not self.youtube_api_key:
            return {'error': 'YouTube APIキーが設定されていません'}
        
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # 人気動画を取得
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                maxResults=max_results
            )
            
            response = request.execute()
            
            if not response.get('items'):
                return {'error': '動画データが取得できませんでした'}
            
            # データを整形し、トレンドスコアを計算
            trends = []
            for item in response['items']:
                try:
                    # 投稿日時から経過日数を計算
                    published_date = datetime.fromisoformat(
                        item['snippet']['publishedAt'].replace('Z', '+00:00')
                    )
                    days_since_published = max(1, (datetime.now(timezone.utc) - published_date).days)
                    
                    # 視聴回数密度（1日あたりの視聴回数）を計算
                    view_count = int(item['statistics'].get('viewCount', 0))
                    view_density = view_count / days_since_published
                    
                    # トレンドスコア（新しい動画ほど高スコア）
                    trend_score = view_density
                    if days_since_published <= 1:
                        trend_score *= 2.0  # 1日以内は2倍
                    elif days_since_published <= 3:
                        trend_score *= 1.5  # 3日以内は1.5倍
                    
                    trends.append({
                        'title': item['snippet']['title'],
                        'channel_title': item['snippet']['channelTitle'],
                        'view_count': view_count,
                        'like_count': int(item['statistics'].get('likeCount', 0)),
                        'comment_count': int(item['statistics'].get('commentCount', 0)),
                        'published_at': item['snippet']['publishedAt'],
                        'video_id': item['id'],
                        'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                        'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description'],
                        'days_since_published': days_since_published,
                        'view_density': view_density,
                        'trend_score': trend_score
                    })
                except Exception as e:
                    print(f"動画データの処理でエラー: {e}")
                    continue
            
            # トレンドスコアでソート
            if trends:
                trends.sort(key=lambda x: x['trend_score'], reverse=True)
                for i, trend in enumerate(trends, 1):
                    trend['rank'] = i
            
            print(f"急上昇トレンド計算完了: 1位={trends[0]['trend_score']:,.0f}点, 25位={trends[-1]['trend_score']:,.0f}点")
            
            return trends
            
        except Exception as e:
            print(f"YouTube Data APIでエラー: {e}")
            return {'error': f'YouTube Data APIでエラーが発生しました: {str(e)}'}

    def save_to_cache(self, region_code: str, trend_type: str, trends_data: list):
        """YouTube Trendsデータをキャッシュに保存"""
        try:
            self.db.save_youtube_trends_to_cache(trends_data, region_code)
            # cache_statusテーブルも更新
            self._update_cache_status('youtube_trends', len(trends_data))
        except Exception as e:
            print(f"YouTubeキャッシュ保存エラー: {e}")
            raise
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            from datetime import datetime
            now = datetime.now()
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, (cache_key, now, data_count))
                    conn.commit()
        except Exception as e:
            print(f"cache_status更新エラー: {e}")

    def get_from_cache(self, region_code: str, trend_type: str):
        """キャッシュからYouTube Trendsデータを取得"""
        return self.db.get_cached_youtube_trends(region_code, trend_type)

    def is_cache_valid(self, region_code: str, trend_type: str):
        """YouTubeキャッシュが有効かチェック"""
        return self.db.is_youtube_cache_valid(region_code, trend_type)
    
    def _should_refresh_cache(self, region_code):
        """今日既にキャッシュを更新したかチェック（朝5時から夜12時まで）"""
        try:
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            today = now.date()
            current_hour = now.hour
            
            # 時間制限：5時から24時まで
            if not (5 <= current_hour < 24):
                print(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('youtube_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            print(f"キャッシュ更新日時チェックエラー: {e}")
            return True
    
    def _update_refresh_time(self, region_code):
        """キャッシュ更新日時を記録"""
        try:
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (platform, region, last_refresh_date, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (platform, region) 
                        DO UPDATE SET last_refresh_date = %s, updated_at = %s
                    """, ('youtube', region_code, now, now, 
                          now, now))
                    conn.commit()
        except Exception as e:
            print(f"キャッシュ更新日時記録エラー: {e}") 