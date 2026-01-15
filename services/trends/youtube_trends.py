"""
YouTube Trends関連の処理を管理するモジュール
"""

import os
from datetime import datetime, timezone, timedelta
import pytz
from googleapiclient.discovery import build
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class YouTubeTrendsManager(BaseTrendsManager):
    """YouTube Trendsの管理クラス"""
    
    def __init__(self):
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='youtube', max_requests=10, window_seconds=60)
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'youtube_trends'
    
    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        region_code = kwargs.get('region_code', 'JP')
        trend_type = kwargs.get('trend_type', 'trending')
        return self.db.get_youtube_trends_from_cache(region_code, trend_type)
    
    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            region_code = kwargs.get('region_code', 'JP')
            trend_type = kwargs.get('trend_type', 'trending')
            return self.db.save_youtube_trends_to_cache(data, region_code, trend_type)
        except Exception as e:
            logger.error(f"❌ YouTube キャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            region_code = kwargs.get('region_code', 'JP')
            # clear_youtube_trends_cacheはregionを受け取るが、trend_typeは受け取らない
            # 実際にはclear_cache('youtube_trends', region)を呼び出す
            # ここではregion_codeのみを使用
            return self.db.clear_youtube_trends_cache(region_code)
        except Exception as e:
            logger.error(f"❌ YouTube キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ YouTube: cache_status更新エラー: {e}")
            return False
    
    def get_trends(self, region_code: str = 'JP', max_results: int = 25, force_refresh=False):
        """YouTubeのトレンド動画を取得（キャッシュデータが存在しない場合は外部APIを呼び出し）"""
        # ベースクラスのget_trendsを使用し、視聴回数でソートするように設定
        # auto_fetch_on_cache_miss=Trueで、キャッシュがない場合はAPIを呼び出す
        return super().get_trends(
            limit=max_results,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュがない場合はAPIを呼び出す
            sort_key='view_count',  # 視聴回数でソート
            sort_reverse=True,  # 降順
            region_code=region_code,
            trend_type='trending'
        )
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """YouTubeの人気動画を外部APIから取得"""
        region_code = kwargs.get('region_code', 'JP')
        
        if not self.youtube_api_key:
            return {'error': 'YouTube APIキーが設定されていません', 'success': False}
        
        # レート制限をチェック
        self.rate_limiter.wait_if_needed()
        
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # 人気動画を取得
            request = youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                maxResults=limit
            )
            
            response = request.execute()
            
            if not response.get('items'):
                return {'error': '動画データが取得できませんでした', 'success': False}
            
            # データを整形
            trends = []
            for item in response['items']:
                try:
                    trends.append({
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
                    logger.warning(f"動画データの処理でエラー: {e}", exc_info=True)
                    continue
            
            # 視聴回数でソート（降順）
            trends.sort(key=lambda x: x.get('view_count', 0), reverse=True)
            
            # ランキングを設定
            for i, trend in enumerate(trends, 1):
                trend['rank'] = i
            
            logger.info(f"✅ YouTube人気動画: 外部APIから{len(trends)}件のデータを取得し、視聴回数でソートしました")
            
            return {
                'success': True,
                'data': trends,
                'status': 'api_fetched',
                'region_code': region_code,
                'source': 'YouTube Data API'
            }
            
        except Exception as e:
            logger.error(f"YouTube Data APIでエラー: {e}", exc_info=True)
            return {'error': f'YouTube Data APIでエラーが発生しました: {str(e)}', 'success': False}

    def get_rising_trends(self, region_code: str = 'JP', max_results: int = 25, force_refresh: bool = False):
        """YouTubeの急上昇トレンド動画を取得（キャッシュ優先）"""
        try:
            cached_data = None
            if force_refresh:
                logger.info(f"🔄 YouTube急上昇: force_refresh指定のためキャッシュをスキップします (region: {region_code})")
            else:
                logger.debug(f"🔍 YouTube急上昇: キャッシュデータ取得開始 (region: {region_code})")
            
                # キャッシュから取得を試行
                cached_data = self.get_from_cache(region_code, 'rising')
                logger.debug(f"🔍 YouTube急上昇: キャッシュデータ取得結果: {type(cached_data)}, 長さ: {len(cached_data) if cached_data else 0}")
            
            if cached_data and len(cached_data) > 0:
                # 急上昇トレンドの場合は、トレンドスコアまたは視聴回数で再ソートしてランキングを設定
                if any(item.get('trend_score') is not None for item in cached_data):
                    # トレンドスコアでソート（降順）- None値を0として扱う
                    cached_data.sort(key=lambda x: x.get('trend_score') or 0, reverse=True)
                else:
                    # 視聴回数でソート（降順）- None値を0として扱う
                    cached_data.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
                # ランキングを設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                logger.info(f"✅ YouTube急上昇: キャッシュデータを使用 ({len(cached_data)}件, region: {region_code})")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'region_code': region_code
                }
            
            logger.warning(f"⚠️ YouTube急上昇: キャッシュにデータがないため外部APIを呼び出します (region: {region_code})")
            return self._fetch_rising_trends_from_api(region_code, max_results)
                
        except Exception as e:
            logger.error(f"YouTube急上昇 キャッシュ取得エラー: {e}", exc_info=True)
            return {'error': f'YouTube急上昇 キャッシュ取得でエラーが発生しました: {str(e)}'}

    def _fetch_rising_trends_from_api(self, region_code: str = 'JP', max_results: int = 25):
        """YouTubeの急上昇トレンド動画を外部APIから取得"""
        if not self.youtube_api_key:
            return {'error': 'YouTube APIキーが設定されていません'}
        
        # レート制限をチェック
        self.rate_limiter.wait_if_needed()
        
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # 最近アップロードされた動画を検索（急上昇の代わり）
            from datetime import datetime, timezone, timedelta
            seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            
            request = youtube.search().list(
                part='snippet',
                type='video',
                order='date',  # 最新順
                regionCode=region_code,
                maxResults=max_results,
                publishedAfter=seven_days_ago  # 過去7日以内
            )
            
            response = request.execute()
            
            if not response.get('items'):
                return {'error': '動画データが取得できませんでした'}
            
            # 動画IDを収集
            video_ids = [item['id']['videoId'] for item in response['items']]
            
            # 動画の詳細情報を取得
            video_request = youtube.videos().list(
                part='snippet,statistics',
                id=','.join(video_ids)
            )
            video_response = video_request.execute()
            
            # データを整形し、トレンドスコアを計算
            trends = []
            for item in video_response['items']:
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
                    logger.warning(f"動画データの処理でエラー: {e}", exc_info=True)
                    continue
            
            # トレンドスコアでソート
            if trends:
                trends.sort(key=lambda x: x['trend_score'], reverse=True)
                for i, trend in enumerate(trends, 1):
                    trend['rank'] = i
            
            if trends:
                logger.info(f"急上昇トレンド計算完了: 1位={trends[0]['trend_score']:,.0f}点, 25位={trends[-1]['trend_score']:,.0f}点")
            
            # キャッシュに保存
            self.save_to_cache(region_code, 'rising', trends)
            logger.info(f"✅ YouTube急上昇: 外部APIから{len(trends)}件のデータを取得し、キャッシュに保存しました")
            
            return {
                'success': True,
                'data': trends,
                'status': 'api_fetched',
                'region_code': region_code
            }
            
        except Exception as e:
            logger.error(f"YouTube Data APIでエラー: {e}", exc_info=True)
            return {'error': f'YouTube Data APIでエラーが発生しました: {str(e)}'}

    def save_to_cache(self, region_code: str, trend_type: str, trends_data: list):
        """YouTube Trendsデータをキャッシュに保存（get_rising_trends用）"""
        try:
            self.db.save_youtube_trends_to_cache(trends_data, region_code, trend_type)
            # cache_statusテーブルも更新
            self._update_cache_status('youtube_trends', len(trends_data))
        except Exception as e:
            logger.error(f"YouTubeキャッシュ保存エラー: {e}", exc_info=True)
            raise
    
    def get_from_cache(self, region_code: str, trend_type: str = 'trending'):
        """キャッシュからYouTube Trendsデータを取得（get_rising_trends用）"""
        try:
            cached_data = self.db.get_youtube_trends_from_cache(region_code, trend_type)
            
            # キャッシュデータがない場合（Noneまたは空のリスト）はNoneを返す
            if not cached_data or len(cached_data) == 0:
                logger.warning(f"⚠️ YouTube急上昇: キャッシュにデータがありません (region: {region_code}, trend_type: {trend_type}, cached_data: {cached_data})")
                return None
            
            # キャッシュデータにランキングを追加（rankフィールドがない場合）
            if cached_data:
                # 急上昇トレンドの場合は、トレンドスコアまたは視聴回数で再ソートしてランキングを設定
                if trend_type == 'rising':
                    # トレンドスコアがある場合はそれでソート、ない場合は視聴回数でソート
                    if any(item.get('trend_score') is not None for item in cached_data):
                        # トレンドスコアでソート（降順）- None値を0として扱う
                        cached_data.sort(key=lambda x: x.get('trend_score') or 0, reverse=True)
                    else:
                        # 視聴回数でソート（降順）- None値を0として扱う
                        cached_data.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
                    # ランキングを設定
                    for i, item in enumerate(cached_data, 1):
                        item['rank'] = i
                else:
                    # 通常のトレンドの場合は順番通りにランキングを設定
                    for i, item in enumerate(cached_data, 1):
                        if 'rank' not in item:
                            item['rank'] = i
            
            logger.info(f"✅ YouTube急上昇: キャッシュから{len(cached_data)}件のデータを取得 (region: {region_code}, trend_type: {trend_type})")
            return cached_data
        except Exception as e:
            logger.error(f"❌ YouTube急上昇: キャッシュ取得エラー: {e}", exc_info=True)
            return None

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
                logger.info(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
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
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
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
            logger.error(f"キャッシュ更新日時記録エラー: {e}", exc_info=True)
