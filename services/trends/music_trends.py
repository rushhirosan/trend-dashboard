import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from dotenv import load_dotenv
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

class MusicTrendsManager:
    def __init__(self):
        self.db = TrendsCache()
        self.sp = None
        # レート制限: Spotify APIは10リクエスト/秒（開発モード）
        self.rate_limiter = get_rate_limiter('spotify', max_requests=10, window_seconds=1)
        self._initialize_spotify()
    
    def _initialize_spotify(self):
        """Spotify APIの初期化"""
        try:
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            logger.debug(f"Spotify API認証情報確認:")
            logger.debug(f"  Client ID: {client_id[:10]}..." if client_id else "  Client ID: 未設定")
            logger.debug(f"  Client Secret: {client_secret[:10]}..." if client_secret else "  Client Secret: 未設定")
            
            if not client_id or not client_secret:
                logger.warning("警告: Spotify API認証情報が設定されていません")
                return
            
            client_credentials_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
            self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            logger.info("Spotify API初期化成功")
            
            # テスト用のAPI呼び出し（キャッシュモードでは無効化）
            # try:
            #     test_result = self.sp.search(q='test', type='track', limit=1)
            #     logger.info("Spotify API接続テスト成功")
            # except Exception as e:
            #     logger.error(f"Spotify API接続テスト失敗: {e}")
            logger.debug("Spotify API接続テスト（キャッシュモードでは無効化）")
            
        except Exception as e:
            logger.error(f"Spotify API初期化エラー: {e}", exc_info=True)
    
    def get_trends(self, service='spotify', region='JP', force_refresh=False):
        """音楽トレンドデータを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            if force_refresh:
                logger.info(f"🔄 {service} Music force_refresh: キャッシュをクリアします")
                self.db.clear_music_trends_cache(service, region)
            
            logger.debug(f"🔍 {service} Music: キャッシュデータ取得開始 (region: {region})")
            
            # キャッシュから取得を試行
            cached_data = self.db.get_music_trends_from_cache(service, region)
            logger.debug(f"🔍 {service} Music: キャッシュデータ取得結果: {type(cached_data)}, 長さ: {len(cached_data) if cached_data else 0}")
            
            # デバッグ: キャッシュの詳細情報を確認
            if cached_data:
                logger.debug(f"🔍 {service} Music: キャッシュデータ詳細: {cached_data[:2] if len(cached_data) > 0 else 'empty'}")
            else:
                logger.debug(f"🔍 {service} Music: キャッシュデータが空です")
            
            if cached_data:
                logger.info(f"✅ {service} Music: キャッシュデータを使用 ({len(cached_data)}件)")
                # キャッシュ情報を取得
                cache_info = self._get_cache_info(service, region)
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'region_code': region,
                    'service': service,
                    'cache_info': cache_info
                }
            else:
                logger.warning(f"⚠️ {service} Music: キャッシュデータが見つかりません。外部APIを呼び出します")
                # キャッシュデータが存在しない場合のみ外部APIを呼び出し
                trends_data = self._get_spotify_trends(region)
                if trends_data:
                    # キャッシュに保存
                    self.save_to_cache(trends_data, service, region)
                    logger.info(f"✅ {service} Music: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                    return {
                        'data': trends_data,
                        'status': 'api_fetched',
                        'region_code': region,
                        'service': service,
                        'source': 'Spotify API'
                    }
                else:
                    logger.error(f"❌ {service} Music: 外部APIからデータを取得できませんでした")
                    return {
                        'data': [],
                        'status': 'api_error',
                        'region_code': region,
                        'service': service
                    }
                
        except Exception as e:
            logger.error(f"音楽トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'音楽トレンドの取得に失敗しました: {str(e)}'}
    
    def _get_spotify_trends(self, region='JP'):
        """Spotifyからトレンドデータを取得"""
        if not self.sp:
            logger.warning("Spotify APIが初期化されていません")
            return None
        
        try:
            logger.info(f"Spotify トレンド取得開始 (地域: {region})")
            
            # グローバルチャート：人気度でソートされた最新楽曲を取得
            if region == 'US':
                logger.info(f"🌍 USの場合、グローバルに人気の楽曲を取得します (region={region})")
                tracks = self._get_global_popular_tracks()
                if tracks:
                    logger.info(f"✅ グローバル楽曲取得成功: {len(tracks)}件")
                else:
                    logger.warning("❌ グローバル楽曲取得失敗")
            else:
                # 日本の場合は従来の方法
                logger.info(f"🇯🇵 日本の場合、日本の楽曲を取得します (region={region})")
                tracks = self._get_spotify_api_data(region)
                if tracks:
                    logger.info(f"✅ 日本楽曲取得成功: {len(tracks)}件")
                else:
                    logger.warning("❌ 日本楽曲取得失敗")
            
            if not tracks:
                logger.warning("楽曲が見つかりません")
                return None
            
            trends = []
            seen_tracks = set()  # 重複チェック用
            
            for i, item in enumerate(tracks, 1):
                # プレイリストの場合はitem['track']、検索の場合はitem
                track = item.get('track', item) if isinstance(item, dict) and 'track' in item else item
                if not track:
                    continue
                    
                # 重複チェック（タイトル + アーティスト）
                track_key = f"{track['name']}_{track['artists'][0]['name'] if track['artists'] else 'Unknown'}"
                
                if track_key in seen_tracks:
                    logger.debug(f"重複をスキップ: {track['name']} - {track['artists'][0]['name'] if track['artists'] else 'Unknown'}")
                    continue
                
                seen_tracks.add(track_key)
                
                # 推定再生回数（popularity * 1000）
                estimated_plays = track['popularity'] * 1000
                
                # Spotify URLを取得（デバッグ情報付き）
                spotify_url = track['external_urls'].get('spotify', '')
                if not spotify_url:
                    # external_urlsが空の場合は、track IDからURLを構築
                    spotify_url = f"https://open.spotify.com/track/{track['id']}"
                
                trends.append({
                    'rank': len(trends) + 1,  # 重複除去後の正しい順位
                    'title': track['name'],
                    'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                    'play_count': estimated_plays,
                    'album': track['album']['name'] if track['album'] else 'Unknown',
                    'spotify_url': spotify_url,
                    'popularity': track['popularity'],
                    'days_since_published': 0,  # Spotifyでは取得困難
                    'view_density': estimated_plays,  # 再生回数密度
                    'trend_score': estimated_plays,  # トレンドスコア
                    'service': 'spotify',
                    'region_code': region,
                    'created_at': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                    'track_id': track['id']
                })
            
            logger.info(f"処理完了: {len(trends)}件のトレンドデータ（重複除去後）")
            return trends
            
        except Exception as e:
            logger.error(f"Spotify API エラー: {e}", exc_info=True)
            return None
    
    def _get_spotify_charts_us(self):
        """Spotify Chartsの公式データを取得（US）"""
        try:
            logger.info("Spotify Charts USデータを取得中...")
            # Spotify Chartsの公式エンドポイント
            url = "https://spotifycharts.com/regional/us/daily/latest/download"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # CSVデータを解析
                lines = response.text.strip().split('\n')
                tracks = []
                
                for i, line in enumerate(lines[1:26], 1):  # ヘッダーをスキップ、25件まで
                    if not line.strip():
                        continue
                    
                    parts = line.split(',')
                    if len(parts) >= 3:
                        # CSV形式: Position, Track Name, Artist
                        track_name = parts[1].strip('"')
                        artist_name = parts[2].strip('"')
                        
                        # Spotify APIで詳細情報を取得
                        try:
                            search_result = self.sp.search(
                                q=f"track:{track_name} artist:{artist_name}",
                                type='track',
                                limit=1,
                                market='US'
                            )
                            
                            if search_result['tracks']['items']:
                                track = search_result['tracks']['items'][0]
                                tracks.append({
                                    'name': track['name'],
                                    'artists': track['artists'],
                                    'album': track['album'],
                                    'popularity': track['popularity'],
                                    'external_urls': track['external_urls'],
                                    'id': track['id']
                                })
                        except Exception as e:
                            logger.warning(f"楽曲詳細取得エラー: {e}", exc_info=True)
                            continue
                
                logger.info(f"Spotify Chartsから{len(tracks)}件の楽曲を取得")
                return tracks
            else:
                logger.warning(f"Spotify Charts取得失敗: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Spotify Charts取得エラー: {e}", exc_info=True)
            return None
    
    def _get_global_popular_tracks(self):
        """グローバルに人気の楽曲を取得（人気度でソート）"""
        try:
            logger.info("グローバル人気楽曲を取得中...")
            
            # 2024年の楽曲を検索（より多く取得してソート）
            results = self.sp.search(q='year:2024', type='track', limit=50)
            tracks = results['tracks']['items']
            
            if not tracks:
                logger.warning("楽曲が見つかりません")
                return None
            
            # 人気度（popularity）でソート
            sorted_tracks = sorted(tracks, key=lambda x: x.get('popularity', 0), reverse=True)
            
            # 重複を除去（同じトラックIDは1回だけ）
            seen_ids = set()
            unique_tracks = []
            for track in sorted_tracks:
                if track['id'] not in seen_ids:
                    seen_ids.add(track['id'])
                    unique_tracks.append(track)
                    if len(unique_tracks) >= 25:
                        break
            
            logger.info(f"グローバル人気楽曲取得完了: {len(unique_tracks)}件")
            return unique_tracks
            
        except Exception as e:
            logger.error(f"グローバル人気楽曲取得エラー: {e}", exc_info=True)
            return None
    
    def _get_spotify_api_data(self, region):
        """Spotify APIからデータを取得（日本向け）"""
        try:
            logger.info(f"日本向け楽曲を取得中 (region: {region})...")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # 日本の楽曲を検索
            query = 'year:2024 genre:j-pop'
            market = 'JP'
            
            results = self.sp.search(q=query, type='track', limit=50, market=market)
            tracks = results['tracks']['items']
            
            if not tracks:
                logger.warning("日本の楽曲が見つかりません")
                return None
            
            # 日本のアーティストを優先的にフィルタリング
            # 人気度でソート
            sorted_tracks = sorted(tracks, key=lambda x: x.get('popularity', 0), reverse=True)
            
            # 重複を除去
            seen_ids = set()
            unique_tracks = []
            for track in sorted_tracks:
                if track['id'] not in seen_ids:
                    seen_ids.add(track['id'])
                    unique_tracks.append(track)
                    if len(unique_tracks) >= 25:
                        break
            
            logger.info(f"日本向け楽曲取得完了: {len(unique_tracks)}件")
            return unique_tracks
            
        except Exception as e:
            logger.error(f"Spotify API検索エラー: {e}", exc_info=True)
            return None
    
    def get_from_cache(self, service, region):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_music_trends_from_cache(service, region)
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def save_to_cache(self, data, service, region):
        """データをキャッシュに保存"""
        try:
            self.db.save_music_trends_to_cache(data, service, region)
            # cache_statusテーブルも更新
            self._update_cache_status(service, len(data))
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
    def _update_cache_status(self, service, data_count):
        """cache_statusテーブルを更新"""
        try:
            from datetime import datetime
            now = datetime.now()
            cache_key = 'music_trends'  # 正しいキャッシュキーを使用
            
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
    
    def is_cache_valid(self, service, region):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_music_cache_valid(service)
        except Exception as e:
            logger.error(f"キャッシュ有効性チェックエラー: {e}", exc_info=True)
            return False
    
    def _should_refresh_cache(self, service, region):
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
                    """, ('music_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
            return True
    
    def _update_refresh_time(self, service, region):
        """キャッシュ更新日時を記録"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (country_code, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (country_code) 
                        DO UPDATE SET last_updated = %s, data_count = %s
                    """, (region, now, 0, now, 0))
                    conn.commit()
        except Exception as e:
            logger.error(f"キャッシュ更新日時記録エラー: {e}", exc_info=True)
    
    def _get_cache_info(self, service, region):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('music_trends',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] if result[1] else 0
                        }
                    return None
        except Exception as e:
            logger.error(f"キャッシュ情報取得エラー: {e}", exc_info=True)
            return None 