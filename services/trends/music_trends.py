import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from dotenv import load_dotenv
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

class MusicTrendsManager(BaseTrendsManager):
    def __init__(self):
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='music', max_requests=10, window_seconds=1)
        
        self.sp = None
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
            logger.debug("Spotify API接続テスト（キャッシュモードでは無効化）")
            
        except Exception as e:
            logger.error(f"Spotify API初期化エラー: {e}", exc_info=True)
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'music_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.get_music_trends_from_cache(service, region)
        except Exception as e:
            logger.error(f"❌ Music: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.save_music_trends_to_cache(data, service, region)
        except Exception as e:
            logger.error(f"❌ Music キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.clear_music_trends_cache(service, region)
        except Exception as e:
            logger.error(f"❌ Music キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Music: cache_status更新エラー: {e}")
            return False

    def get_trends(self, service='spotify', region='JP', force_refresh=False):
        """音楽トレンドデータを取得（キャッシュ優先、popularityでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='popularity'で人気度でソート
        result = super().get_trends(
            limit=25,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='popularity',  # 人気度でソート
            sort_reverse=True,  # 降順
            service=service,
            region=region
        )
        # serviceとregionパラメータを結果に追加
        if result and isinstance(result, dict):
            result['service'] = service
            result['region_code'] = region
        return result
    
    def _fetch_trends(self, service='spotify', region='JP', *args, **kwargs):
        """Spotifyからトレンドデータを取得"""
        if not self.sp:
            logger.warning("Spotify APIが初期化されていません")
            return {
                'success': False,
                'error': 'Spotify APIが初期化されていません',
                'data': []
            }
        
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
                return {
                    'success': False,
                    'error': '楽曲が見つかりません',
                    'data': []
                }
            
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
            return {
                'success': True,
                'data': trends,
                'status': 'api_fetched',
                'source': 'Spotify API',
                'service': service,
                'region_code': region
            }
            
        except Exception as e:
            logger.error(f"Spotify API エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Spotify API エラー: {str(e)}',
                'data': []
            }
    
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
