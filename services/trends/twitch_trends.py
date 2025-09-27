import os
import requests
import json
from datetime import datetime, timedelta
from database_config import TrendsCache

class TwitchTrendsManager:
    """Twitchトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.base_url = "https://api.twitch.tv/helix"
        self.auth_url = "https://id.twitch.tv/oauth2/token"
        self.db = TrendsCache()
        self.access_token = None
        self.token_expires_at = None
        
        print(f"Twitch Trends Manager初期化:")
        print(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        print(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
        print(f"  Base URL: {self.base_url}")
    
    def _get_access_token(self):
        """アクセストークンを取得・更新"""
        try:
            # トークンが有効期限切れでない場合は既存のものを使用
            if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
                return self.access_token
            
            # 新しいトークンを取得
            auth_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(self.auth_url, data=auth_data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                # トークンの有効期限を設定（実際の有効期限より少し早めに設定）
                self.token_expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)
                print("✅ Twitch アクセストークン取得成功")
                return self.access_token
            else:
                print(f"❌ Twitch アクセストークン取得失敗: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Twitch アクセストークン取得エラー: {e}")
            return None
    
    def _make_request(self, endpoint, params=None):
        """Twitch APIにリクエストを送信"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return None
            
            headers = {
                'Client-ID': self.client_id,
                'Authorization': f'Bearer {access_token}'
            }
            
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Twitch API リクエスト失敗: {response.status_code} - {endpoint}")
                return None
                
        except Exception as e:
            print(f"❌ Twitch API リクエストエラー: {e}")
            return None
    
    def get_trends(self, limit=25, force_refresh=False):
        """Twitchトレンドを取得（get_top_gamesのエイリアス）"""
        return self.get_top_games(limit, force_refresh)
    
    def get_japanese_streams(self, limit=25):
        """日本語ストリームを取得"""
        return self.get_top_streams(limit, 'ja')
    
    def get_top_games(self, limit=25, force_refresh=False):
        """人気ゲームを取得"""
        try:
            # キャッシュから取得を試行
            cache_key = 'twitch_trends'
            cached_data = self.get_from_cache(cache_key)
            if cached_data and not force_refresh:
                cache_info = self._get_cache_info(cache_key)
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'trend_type': 'games',
                    'cache_info': cache_info
                }
            
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache('twitch_trends'):
                print(f"⚠️ Twitchのキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                if cached_data:
                    cache_info = self._get_cache_info(cache_key)
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'trend_type': 'games',
                        'cache_info': cache_info
                    }
                else:
                    # キャッシュデータがない場合は空のデータを返す
                    return {
                        'data': [],
                        'status': 'no_cache',
                        'trend_type': 'games',
                        'cache_info': {'last_updated': None, 'data_count': 0}
                    }
            
            print(f"Twitch 人気ゲーム取得開始: limit={limit}")
            
            params = {'first': limit}
            data = self._make_request('games/top', params)
            
            if not data or 'data' not in data:
                return {'error': 'Twitch APIからゲームデータを取得できませんでした'}
            
            # ゲーム情報を整形
            games = []
            for i, game in enumerate(data['data']):
                # ゲームの視聴者数を取得
                viewer_count = self._get_game_viewer_count(game['id'])
                
                games.append({
                    'rank': i + 1,
                    'name': game['name'],
                    'id': game['id'],
                    'box_art_url': game['box_art_url'].replace('{width}x{height}', '285x380'),
                    'viewer_count': viewer_count,
                    'score': viewer_count,  # スコアとして視聴者数を使用
                    'category': 'ゲーム'
                })
            
            # キャッシュに保存
            self.save_to_cache(games, cache_key)
            # 更新日時を記録
            self._update_refresh_time(cache_key)
            
            return {
                'data': games,
                'status': 'success',
                'source': 'Twitch 人気ゲーム',
                'total_count': len(games)
            }
            
        except Exception as e:
            return {'error': f'Twitch 人気ゲーム取得エラー: {str(e)}'}
    
    def get_top_streams(self, limit=25, language='ja'):
        """人気ストリームを取得"""
        try:
            print(f"Twitch 人気ストリーム取得開始: limit={limit}, language={language}")
            
            params = {'first': limit}
            if language:
                params['language'] = language
            data = self._make_request('streams', params)
            
            if not data or 'data' not in data:
                return {'error': 'Twitch APIからストリームデータを取得できませんでした'}
            
            # ストリーム情報を整形
            streams = []
            for i, stream in enumerate(data['data']):
                streams.append({
                    'rank': i + 1,
                    'title': stream['title'],
                    'user_name': stream['user_name'],
                    'game_name': stream['game_name'],
                    'viewer_count': stream['viewer_count'],
                    'language': stream['language'],
                    'thumbnail_url': stream['thumbnail_url'].replace('{width}x{height}', '320x180'),
                    'started_at': stream['started_at'],
                    'category': 'ストリーム'
                })
            
            # 視聴者数でソート
            streams.sort(key=lambda x: x['viewer_count'], reverse=True)
            
            # ランクを再設定
            for i, stream in enumerate(streams):
                stream['rank'] = i + 1
            
            return {
                'data': streams,
                'status': 'success',
                'source': 'Twitch 人気ストリーム',
                'total_count': len(streams)
            }
            
        except Exception as e:
            return {'error': f'Twitch 人気ストリーム取得エラー: {str(e)}'}
    
    def get_top_clips(self, limit=25):
        """人気クリップを取得"""
        try:
            print(f"Twitch 人気クリップ取得開始: limit={limit}")
            
            # 最近の日付を取得
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            params = {
                'first': limit,
                'started_at': start_date.isoformat() + 'Z',
                'ended_at': end_date.isoformat() + 'Z'
            }
            
            data = self._make_request('clips', params)
            
            if not data or 'data' not in data:
                return {'error': 'Twitch APIからクリップデータを取得できませんでした'}
            
            # クリップ情報を整形
            clips = []
            for i, clip in enumerate(data['data']):
                clips.append({
                    'rank': i + 1,
                    'title': clip['title'],
                    'creator_name': clip['creator_name'],
                    'game_name': clip['game_name'],
                    'view_count': clip['view_count'],
                    'thumbnail_url': clip['thumbnail_url'],
                    'duration': clip['duration'],
                    'created_at': clip['created_at'],
                    'url': clip['url'],
                    'category': 'クリップ'
                })
            
            # 再生回数でソート
            clips.sort(key=lambda x: x['view_count'], reverse=True)
            
            # ランクを再設定
            for i, clip in enumerate(clips):
                clip['rank'] = i + 1
            
            return {
                'data': clips,
                'status': 'success',
                'source': 'Twitch 人気クリップ',
                'total_count': len(clips)
            }
            
        except Exception as e:
            return {'error': f'Twitch 人気クリップ取得エラー: {str(e)}'}
    
    def get_game_categories(self):
        """ゲームカテゴリー一覧を取得"""
        try:
            print("Twitch ゲームカテゴリー取得開始")
            
            # 人気ゲームからカテゴリーを抽出
            games_data = self.get_top_games(100)
            
            if 'error' in games_data:
                return []
            
            # ゲーム名をカテゴリーとして返す
            categories = [game['name'] for game in games_data['data']]
            
            return categories
            
        except Exception as e:
            print(f"❌ Twitch ゲームカテゴリー取得エラー: {e}")
            return []
    
    def get_twitch_trends_summary(self):
        """Twitchトレンドの概要を取得"""
        return {
            'twitch_api': {
                'available': bool(self.client_id and self.client_secret),
                'note': 'Twitch公式API: 人気ゲーム、ストリーム、クリップ',
                'features': [
                    '人気ゲーム取得',
                    '人気ストリーム取得',
                    '人気クリップ取得',
                    'ゲームカテゴリー分類',
                    '視聴者数・再生回数表示',
                    '公式API使用'
                ]
            },
            'limitations': [
                'レート制限: 1分間に800リクエスト',
                'アクセストークンの有効期限管理',
                '一部データはリアルタイム更新'
            ],
            'setup_required': [
                'Twitch Developer Consoleでのアプリケーション登録',
                'Client ID と Client Secret',
                'twitchioライブラリ'
            ]
        }
    
    def _get_game_viewer_count(self, game_id):
        """特定のゲームの現在の視聴者数を取得"""
        try:
            params = {'game_id': game_id, 'first': 1}
            data = self._make_request('streams', params)
            
            if data and 'data' in data and data['data']:
                return data['data'][0].get('viewer_count', 0)
            return 0
        except:
            return 0
    
    def get_from_cache(self, cache_key):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_from_cache('twitch_trends', '')
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, cache_key):
        """データをキャッシュに保存"""
        try:
            self.db.save_twitch_trends_to_cache(data, trend_type)
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def is_cache_valid(self, cache_key):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_twitch_cache_valid(cache_key)
        except Exception as e:
            print(f"キャッシュ有効性チェックエラー: {e}")
            return False
    
    def _should_refresh_cache(self, cache_key):
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
                print(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('twitch_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            print(f"キャッシュ更新日時チェックエラー: {e}")
            return True
    
    def _update_refresh_time(self, cache_key):
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
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) 
                        DO UPDATE SET 
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('twitch_trends', now, 25))  # 正しいキャッシュキーを使用
                    conn.commit()
        except Exception as e:
            print(f"更新日時記録エラー: {e}")
    
    def _get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE country_code = %s
                    """, (f'twitch',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] or 0
                        }
                    return {'last_updated': None, 'data_count': 0}
        except Exception as e:
            print(f"キャッシュ情報取得エラー: {e}")
            return {'last_updated': None, 'data_count': 0}