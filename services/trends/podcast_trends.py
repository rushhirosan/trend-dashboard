import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class PodcastTrendsManager:
    """Listen Notes APIを使用してポッドキャストトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.api_key = os.getenv('LISTEN_API_KEY')
        self.base_url = "https://listen-api.listennotes.com/api/v2"
        self.db = TrendsCache()
        # レート制限: Listen Notes APIは300 requests/月（保守的に10リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('podcast', max_requests=10, window_seconds=60)
        
        if not self.api_key:
            logger.warning("Warning: LISTEN_API_KEYが設定されていません")
        
        logger.debug(f"Listen Notes API認証情報確認:")
        logger.debug(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
        
        # Listen Notes API接続テスト（キャッシュモードでは無効化）
        # if self.api_key:
        #     self._test_connection()
    
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
    
    def get_trends(self, trend_type='best_podcasts', genre_id=None, region='jp', page_size=25, force_refresh=False):
        """ポッドキャストトレンドを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            logger.debug(f"🔍 Podcast: キャッシュデータ取得開始 (trend_type: {trend_type}, region: {region})")
            
            # キャッシュチェック
            cache_key = f"{trend_type}_{genre_id or 'all'}_{region}"
            cached_data = None
            if force_refresh:
                logger.info(f"🔄 Podcast: force_refresh指定のためキャッシュをスキップします (cache_key: {cache_key})")
            else:
                cached_data = self.get_from_cache(cache_key, region)
                if cached_data:
                    logger.info(f"✅ Podcast: キャッシュデータを取得しました ({len(cached_data)}件, cache_key: {cache_key})")
                else:
                    logger.debug(f"🔍 Podcast: キャッシュデータが見つかりませんでした (cache_key: {cache_key})")
            
            if cached_data:
                # エピソード数でソート（降順）、同じ場合はスコアでソート
                cached_data.sort(key=lambda x: (x.get('total_episodes', 0), x.get('score', 0)), reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                    # スコアも再計算
                    score = 100 * (1 - (i - 1) / (len(cached_data) - 1)) if len(cached_data) > 1 else 100
                    item['score'] = round(score, 1)
                
                logger.info(f"✅ Podcast: キャッシュデータを使用し、エピソード数でソートしました ({len(cached_data)}件)")
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'trend_type': trend_type,
                    'genre_id': genre_id,
                    'region': region.upper()
                }
            logger.warning(f"⚠️ Podcast: キャッシュ未使用のため外部APIを呼び出します")
            if trend_type == 'best_podcasts':
                trends_data = self._get_best_podcasts(genre_id, page_size, region)
            elif trend_type == 'trending_searches':
                trends_data = self._get_trending_searches(region, page_size)
            else:
                logger.error(f"❌ 未対応のトレンドタイプ: {trend_type}")
                return {
                    'data': [],
                    'status': 'unsupported_type',
                    'trend_type': trend_type,
                    'genre_id': genre_id,
                    'region': region.upper()
                }
            
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, cache_key, region)
                logger.info(f"✅ Podcast: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                return {
                    'data': trends_data,
                    'status': 'api_fetched',
                    'trend_type': trend_type,
                    'genre_id': genre_id,
                    'region': region.upper(),
                    'source': 'Listen Notes API'
                }
            else:
                logger.error(f"❌ Podcast: 外部APIからデータを取得できませんでした")
                return {
                    'data': [],
                    'status': 'api_error',
                    'trend_type': trend_type,
                    'genre_id': genre_id,
                    'region': region.upper()
                }
                
        except Exception as e:
            logger.error(f"ポッドキャストトレンド取得エラー: {e}", exc_info=True)
            return {'error': f'ポッドキャストトレンドの取得に失敗しました: {str(e)}'}
    
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
    
    def get_from_cache(self, cache_key, region):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_podcast_trends_from_cache('podcast_trends', region)
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def save_to_cache(self, data, cache_key, region):
        """データをキャッシュに保存"""
        try:
            self.db.save_podcast_trends_to_cache(data, 'podcast_trends', region)
            # cache_statusテーブルも更新
            self._update_cache_status('podcast_trends', len(data))
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            
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
            logger.error(f"cache_status更新エラー: {e}", exc_info=True)
    
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