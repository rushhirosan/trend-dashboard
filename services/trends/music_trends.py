import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from datetime import datetime, timedelta
from database_config import TrendsCache
from dotenv import load_dotenv

load_dotenv()

class MusicTrendsManager:
    def __init__(self):
        self.db = TrendsCache()
        self.sp = None
        self._initialize_spotify()
    
    def _initialize_spotify(self):
        """Spotify APIの初期化"""
        try:
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            print(f"Spotify API認証情報確認:")
            print(f"  Client ID: {client_id[:10]}..." if client_id else "  Client ID: 未設定")
            print(f"  Client Secret: {client_secret[:10]}..." if client_secret else "  Client Secret: 未設定")
            
            if not client_id or not client_secret:
                print("警告: Spotify API認証情報が設定されていません")
                return
            
            client_credentials_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
            self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            print("Spotify API初期化成功")
            
            # テスト用のAPI呼び出し（キャッシュモードでは無効化）
            # try:
            #     test_result = self.sp.search(q='test', type='track', limit=1)
            #     print("Spotify API接続テスト成功")
            # except Exception as e:
            #     print(f"Spotify API接続テスト失敗: {e}")
            print("Spotify API接続テスト（キャッシュモードでは無効化）")
            
        except Exception as e:
            print(f"Spotify API初期化エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def get_trends(self, service='spotify', region='JP', force_refresh=False):
        """音楽トレンドデータを取得"""
        try:
            # force_refresh=trueの場合、古いキャッシュデータを削除
            if force_refresh:
                print(f"🔄 {service} Music Trends 強制更新: 古いキャッシュデータを削除します")
                self.db.clear_music_trends_cache(service)
                print(f"✅ {service} Music Trends 古いキャッシュデータを削除しました")
            
            # キャッシュから取得を試行
            cached_data = self.db.get_music_trends_from_cache(service)
            if cached_data and not force_refresh:
                # キャッシュ情報を取得
                cache_info = self._get_cache_info(service, region)
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'region_code': region,
                    'service': service,
                    'cache_info': cache_info
                }
            
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache(service, region):
                print(f"⚠️ {service}のキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                if cached_data:
                    cache_info = self._get_cache_info(service, region)
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'region_code': region,
                        'service': service,
                        'cache_info': cache_info
                    }
            
            # 新しいデータを取得
            if service == 'spotify':
                trends_data = self._get_spotify_trends(region)
            else:
                return {'error': f'未対応のサービス: {service}'}
            
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, service, region)
                # 更新日時を記録
                self._update_refresh_time(service, region)
                # キャッシュ情報を取得
                cache_info = self._get_cache_info(service, region)
                return {
                    'data': trends_data,
                    'status': 'fresh',
                    'region_code': region,
                    'service': service,
                    'cache_info': cache_info
                }
            else:
                return {'error': 'Spotify APIからデータを取得できませんでした。API認証情報を確認してください。'}
                
        except Exception as e:
            print(f"音楽トレンド取得エラー: {e}")
            return {'error': f'音楽トレンドの取得に失敗しました: {str(e)}'}
    
    def _get_spotify_trends(self, region='JP'):
        """Spotifyからトレンドデータを取得"""
        if not self.sp:
            print("Spotify APIが初期化されていません")
            return None
        
        try:
            # 人気曲検索を使用
            print(f"人気曲検索開始 (地域: {region})")
            
            # 地域に応じた検索クエリ
            search_queries = {
                'JP': 'genre:j-pop',
                'US': 'genre:pop',
                'GB': 'genre:pop'
            }
            
            query = search_queries.get(region, search_queries['JP'])
            
            # 人気曲を検索
            results = self.sp.search(q=query, type='track', limit=25, market=region)
            print(f"検索結果: {len(results['tracks']['items'])}件")
            
            if not results['tracks']['items']:
                print("検索結果に曲が見つかりません")
                return None
            
            trends = []
            seen_tracks = set()  # 重複チェック用
            
            for i, track in enumerate(results['tracks']['items'], 1):
                # 重複チェック（タイトル + アーティスト）
                track_key = f"{track['name']}_{track['artists'][0]['name'] if track['artists'] else 'Unknown'}"
                
                if track_key in seen_tracks:
                    print(f"重複をスキップ: {track['name']} - {track['artists'][0]['name'] if track['artists'] else 'Unknown'}")
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
                    'trend_score': estimated_plays  # トレンドスコア
                })
            
            print(f"処理完了: {len(trends)}件のトレンドデータ（重複除去後）")
            return trends
            
        except Exception as e:
            print(f"Spotify API エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_from_cache(self, service, region):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_music_trends_from_cache(service)
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, service, region):
        """データをキャッシュに保存"""
        try:
            self.db.save_music_trends_to_cache(data, service)
            # cache_statusテーブルも更新
            self._update_cache_status(service, len(data))
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
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
            print(f"cache_status更新エラー: {e}")
    
    def is_cache_valid(self, service, region):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_music_cache_valid(service)
        except Exception as e:
            print(f"キャッシュ有効性チェックエラー: {e}")
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
                print(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
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
            print(f"キャッシュ更新日時チェックエラー: {e}")
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
            print(f"キャッシュ更新日時記録エラー: {e}")
    
    def _get_cache_info(self, service, region):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count
                        FROM cache_status 
                        WHERE country_code = %s
                    """, (region,))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] if result[1] else 0
                        }
                    return None
        except Exception as e:
            print(f"キャッシュ情報取得エラー: {e}")
            return None 