import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class PodcastTrendsManager(BaseTrendsManager):
    """Listen Notes APIを使用してポッドキャストトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='podcast', max_requests=10, window_seconds=60)
        
        self.api_key = os.getenv('LISTEN_API_KEY')
        self.base_url = "https://listen-api.listennotes.com/api/v2"
        
        if not self.api_key:
            logger.warning("Warning: LISTEN_API_KEYが設定されていません")
        
        logger.debug(f"Listen Notes API認証情報確認:")
        logger.debug(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
    
    def _test_connection(self):
        """Listen Notes API接続テスト"""
        try:
            # 簡単なテストリクエスト（genresエンドポイント）
            test_url = f"{self.base_url}/genres"
            headers = {'X-ListenAPI-Key': self.api_key}
            
            response = requests.get(test_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info("Listen Notes API接続テスト成功")
            else:
                logger.warning(f"Listen Notes API接続テスト失敗: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Listen Notes API接続テストエラー: {e}", exc_info=True)
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す（ベースクラスが *args, **kwargs で呼ぶため受け取る）"""
        return 'podcast_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.get_podcast_trends_from_cache('podcast_trends', region)
        except Exception as e:
            logger.error(f"❌ Podcast: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.save_podcast_trends_to_cache(data, 'podcast_trends', region)
        except Exception as e:
            logger.error(f"❌ Podcast キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_podcast_trends_cache('podcast_trends')
        except Exception as e:
            logger.error(f"❌ Podcast キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Podcast: cache_status更新エラー: {e}")
            return False

    def get_trends(self, trend_type='best_podcasts', genre_id=None, region='jp', page_size=25, force_refresh=False):
        """ポッドキャストトレンドを取得（キャッシュ優先、total_episodesでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='total_episodes'でエピソード数でソート
        result = super().get_trends(
            limit=page_size,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='total_episodes',  # エピソード数でソート
            sort_reverse=True,  # 降順
            trend_type=trend_type,
            genre_id=genre_id,
            region=region
        )
        # trend_type、genre_id、regionパラメータを結果に追加
        if result and isinstance(result, dict):
            result['trend_type'] = trend_type
            result['genre_id'] = genre_id
            result['region'] = region.upper()
        return result
    
    def _fetch_trends(self, trend_type='best_podcasts', genre_id=None, region='jp', page_size=25, *args, **kwargs):
        """Listen Notes APIからポッドキャストトレンドデータを取得"""
        if not self.api_key:
            logger.warning("Listen Notes APIキーが設定されていません")
            return {
                'success': False,
                'error': 'Listen Notes APIキーが設定されていません',
                'data': []
            }
        
        try:
            logger.warning(f"⚠️ Podcast: キャッシュ未使用のため外部APIを呼び出します")
            if trend_type == 'best_podcasts':
                trends_data = self._get_best_podcasts(genre_id, page_size, region)
            elif trend_type == 'trending_searches':
                trends_data = self._get_trending_searches(region, page_size)
            else:
                logger.error(f"❌ 未対応のトレンドタイプ: {trend_type}")
                return {
                    'success': False,
                    'error': f'未対応のトレンドタイプ: {trend_type}',
                    'data': []
                }
            
            if not trends_data:
                return {
                    'success': False,
                    'error': 'データが取得できませんでした',
                    'data': []
                }
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'Listen Notes API',
                'trend_type': trend_type,
                'genre_id': genre_id,
                'region': region.upper()
            }
            
        except Exception as e:
            logger.error(f"ポッドキャストトレンド取得エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'ポッドキャストトレンドの取得に失敗しました: {str(e)}',
                'data': []
            }
    
    def _get_best_podcasts(self, genre_id=None, page_size=25, region='jp'):
        """ベストポッドキャストを取得"""
        try:
            url = f"{self.base_url}/best_podcasts"
            headers = {'X-ListenAPI-Key': self.api_key}
            
            params = {
                'page_size': page_size,
                'region': region
            }
            
            if genre_id:
                params['genre_id'] = genre_id
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Listen Notes API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            podcasts = data.get('podcasts', [])
            
            if len(podcasts) == 0:
                return []
            
            trends = []
            for podcast in podcasts:
                # podcast_idを取得（idフィールドまたはlistennotes_urlから抽出）
                podcast_id = podcast.get('id', '')
                if not podcast_id and podcast.get('listennotes_url'):
                    # listennotes_urlからIDを抽出: https://www.listennotes.com/c/{id}/
                    url_parts = podcast.get('listennotes_url', '').split('/')
                    podcast_id = url_parts[-2] if len(url_parts) > 1 else ''
                
                trends.append({
                    'id': podcast_id,  # podcast_idとして使用
                    'podcast_id': podcast_id,  # 明示的にpodcast_idも設定
                    'title': podcast.get('title', 'No Title'),
                    'description': podcast.get('description', ''),
                    'publisher': podcast.get('publisher', 'Unknown'),
                    'url': podcast.get('website', ''),
                    'image_url': podcast.get('image', ''),
                    'language': podcast.get('language', 'en'),
                    'country': podcast.get('country', 'Unknown'),
                    'total_episodes': podcast.get('total_episodes', 0),
                    'listennotes_url': podcast.get('listennotes_url', ''),
                    'explicit_content': podcast.get('explicit_content', False),
                    'latest_episode_pub_date': podcast.get('latest_episode_pub_date', ''),
                    'earliest_episode_pub_date': podcast.get('earliest_episode_pub_date', ''),
                    'trend_type': 'best_podcasts'
                })
            
            # エピソード数でソート（降順）、同じ場合はスコアでソート
            trends.sort(key=lambda x: (x.get('total_episodes', 0), x.get('score', 0)), reverse=True)
            
            # スコア計算とランキングを設定
            for i, trend in enumerate(trends, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(trends) - 1)) if len(trends) > 1 else 100
                trend['score'] = round(score, 1)
                trend['rank'] = i
            
            return trends
            
        except Exception as e:
            logger.error(f"ベストポッドキャスト取得エラー: {e}", exc_info=True)
            return None
    
    def _get_trending_searches(self, region='jp', page_size=25):
        """トレンド検索ワードを取得"""
        try:
            url = f"{self.base_url}/trending_searches"
            headers = {'X-ListenAPI-Key': self.api_key}
            
            params = {
                'region': region,
                'size': page_size
            }
            
            logger.debug(f"トレンド検索リクエスト: {params}")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Listen Notes API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            logger.debug(f"Listen Notes API レスポンス: {data}")
            
            searches = data.get('terms', [])
            logger.info(f"トレンド検索取得数: {len(searches)}件")
            
            if len(searches) == 0:
                return []
            
            trends = []
            for i, search in enumerate(searches, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(searches) - 1)) if len(searches) > 1 else 100
                
                trends.append({
                    'rank': i,
                    'title': search.get('term', 'No Term'),
                    'description': f"トレンド検索ワード #{i}",
                    'publisher': 'Listen Notes',
                    'url': f"https://www.listennotes.com/search/?q={search.get('term', '')}",
                    'image_url': '',
                    'language': 'en',
                    'country': region.upper(),
                    'score': round(score, 1),
                    'trend_type': 'trending_searches'
                })
            
            logger.info(f"トレンド検索処理完了: {len(trends)}件")
            return trends
            
        except Exception as e:
            logger.error(f"トレンド検索取得エラー: {e}", exc_info=True)
            return []
    
    def get_genres(self):
        """利用可能なジャンル一覧を取得"""
        try:
            url = f"{self.base_url}/genres"
            headers = {'X-ListenAPI-Key': self.api_key}
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Listen Notes API エラー: HTTP {response.status_code}")
                return []
            
            data = response.json()
            genres = data.get('genres', [])
            
            logger.info(f"利用可能なジャンル数: {len(genres)}件")
            return genres
            
        except Exception as e:
            logger.error(f"ジャンル取得エラー: {e}", exc_info=True)
            return []
    
    def get_regions(self):
        """利用可能な国・地域コード一覧を取得"""
        try:
            url = f"{self.base_url}/regions"
            headers = {'X-ListenAPI-Key': self.api_key}
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Listen Notes API エラー: HTTP {response.status_code}")
                return []
            
            data = response.json()
            regions = data.get('regions', [])
            
            logger.info(f"利用可能な国・地域数: {len(regions)}件")
            return regions
            
        except Exception as e:
            logger.error(f"国・地域取得エラー: {e}", exc_info=True)
            return []
    
    def is_cache_valid(self, cache_key, region):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_podcast_cache_valid(cache_key, region)
        except Exception as e:
            logger.error(f"キャッシュ有効性チェックエラー: {e}", exc_info=True)
            return False
    
    def _should_refresh_cache(self, trend_type, region):
        """今日既にキャッシュを更新したかチェック（朝5時から夜12時まで）"""
        try:
            from datetime import datetime
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
                    """, ('podcast_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
            return True
