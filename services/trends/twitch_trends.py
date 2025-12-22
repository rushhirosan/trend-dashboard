import os
import requests
import json
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class TwitchTrendsManager:
    """Twitchトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.base_url = "https://api.twitch.tv/helix"
        self.auth_url = "https://id.twitch.tv/oauth2/token"
        self.db = TrendsCache()
        # レート制限: Twitch APIは800 points/分（保守的に800リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('twitch', max_requests=800, window_seconds=60)
        self.access_token = None
        self.token_expires_at = None
        
        logger.info(f"Twitch Trends Manager初期化:")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        logger.info(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
        logger.info(f"  Base URL: {self.base_url}")
    
    def get_available_categories(self):
        """利用可能なカテゴリ一覧を取得"""
        return ['games', 'streams', 'clips']
    
    def get_trends(self, category='games', limit=25, force_refresh=False):
        """Twitchトレンドを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            logger.debug(f"🔍 Twitch: キャッシュデータ取得開始 (category: {category})")
            
            cached_data = None
            if force_refresh:
                logger.info(f"🔄 Twitch: force_refresh指定のためキャッシュをスキップします (category: {category})")
            else:
                # キャッシュからデータを取得
                cached_data = self.get_from_cache_by_category(category)
                logger.debug(f"🔍 Twitch: キャッシュデータ取得結果: {type(cached_data)}, 長さ: {len(cached_data) if cached_data else 0}")
            
            if cached_data:
                logger.info(f"✅ Twitch: キャッシュデータを使用 ({len(cached_data)}件)")
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'trend_type': category,
                    'source': 'database_cache',
                    'success': True
                }
            
            # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
            if not force_refresh:
                logger.warning(f"⚠️ Twitch: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません (category: {category})")
                return {
                    'data': [],
                    'status': 'cache_not_found',
                    'trend_type': category,
                    'source': 'database_cache',
                    'success': False,
                    'error': 'キャッシュにデータがありません'
                }
            
            logger.warning(f"⚠️ Twitch: キャッシュ未使用のため外部APIを呼び出します")
            if category == 'games':
                api_result = self._get_top_games_from_api(limit)
            elif category == 'streams':
                api_result = self._get_top_streams_from_api(limit)
            elif category == 'clips':
                api_result = self._get_top_clips_from_api(limit)
            else:
                api_result = {'error': f'Unknown category: {category}'}
            
            if api_result and isinstance(api_result, dict) and api_result.get('data'):
                trends_data = api_result['data']
                # カテゴリ情報を追加
                for item in trends_data:
                    item['category'] = category
                
                # キャッシュに保存（database_config.pyのメソッドを使用）
                success = self.db.save_twitch_trends_to_cache(trends_data, category)
                if success:
                    logger.info(f"✅ Twitch: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                else:
                    logger.warning(f"⚠️ Twitch: データ取得成功しましたが、キャッシュ保存に失敗しました")
                return {
                    'data': trends_data,
                    'status': 'api_fetched',
                    'trend_type': category,
                    'source': 'Twitch API',
                    'success': True
                }
            else:
                logger.error(f"❌ Twitch: 外部APIからデータを取得できませんでした")
                return {
                    'data': [],
                    'status': 'api_error',
                    'trend_type': category,
                    'source': 'Twitch API',
                    'success': False,
                    'error': api_result.get('error', 'Unknown error') if api_result else 'API call failed'
                }
            
        except Exception as e:
            logger.error(f"❌ Twitch: get_trendsエラー: {e}", exc_info=True)
            return {
                'data': [],
                'status': 'error',
                'trend_type': category,
                'source': 'Twitch API',
                'success': False,
                'error': f'Twitch トレンド取得エラー: {str(e)}'
            }
    
    def get_from_cache_by_category(self, category):
        """カテゴリ別のキャッシュデータを取得"""
        try:
            logger.debug(f"🔍 カテゴリ別キャッシュ取得: category='{category}'")
            # database_config.pyのメソッドを使用
            cached_data = self.db.get_twitch_trends_from_cache(category)
            
            if cached_data:
                logger.info(f"✅ カテゴリ別キャッシュ取得完了: {len(cached_data)}件")
                if len(cached_data) > 0:
                    logger.debug(f"🔍 最初のアイテムのカテゴリ: {cached_data[0].get('category', 'unknown')}")
                return cached_data
            else:
                logger.warning(f"⚠️ カテゴリ '{category}' のキャッシュデータが見つかりません")
                return None
                        
        except Exception as e:
            logger.error(f"❌ カテゴリ別キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def _save_to_cache_by_category(self, category, data):
        """カテゴリ別のデータをキャッシュに保存"""
        try:
            logger.debug(f"🔍 Twitch: カテゴリ別キャッシュ保存開始 (category: {category}, data: {len(data)}件)")
            
            conn = self.db.get_connection()
            if not conn:
                logger.warning(f"⚠️ Twitch: データベース接続が取得できませんでした (category: {category})")
                return
            
            with conn.cursor() as cursor:
                # 既存のデータを削除
                cursor.execute("DELETE FROM twitch_trends_cache WHERE category = %s", (category,))
                
                # 新しいデータを保存
                for item in data:
                    # created_atフィールドの値を適切に処理
                    created_at = item.get('created_at', '')
                    if created_at == '' or created_at is None:
                        created_at = None
                    
                    cursor.execute("""
                        INSERT INTO twitch_trends_cache 
                        (title, game_name, viewer_count, rank, category, thumbnail_url, 
                         user_name, language, started_at, view_count, creator_name, 
                         duration, created_at, url, box_art_url, game_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('game_name', ''),
                        item.get('viewer_count', 0),
                        item.get('rank', 0),
                        item.get('category', category),
                        item.get('thumbnail_url', ''),
                        item.get('user_name', ''),
                        item.get('language', ''),
                        item.get('started_at', ''),
                        item.get('view_count', 0),
                        item.get('creator_name', ''),
                        item.get('duration', 0),
                        created_at,  # NULLまたは有効な値
                        item.get('url', ''),
                        item.get('box_art_url', ''),
                        item.get('id', '')
                    ))
                
                conn.commit()
                logger.info(f"✅ Twitch: カテゴリ別キャッシュ保存完了 (category: {category}, data: {len(data)}件)")
                
                # cache_statusを更新
                from datetime import datetime
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES ('twitch_trends', %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, (datetime.now(), len(data)))
                conn.commit()
                    
        except Exception as e:
            logger.error(f"❌ Twitch: カテゴリ別キャッシュ保存エラー: {e}", exc_info=True)
    
    def _fetch_and_cache_all_categories(self):
        """全カテゴリのデータを取得してキャッシュに保存"""
        try:
            logger.info("🔍 Twitch: 全カテゴリのデータを取得開始")
            
            all_data = []
            categories = self.get_available_categories()
            
            for category in categories:
                logger.debug(f"🔍 カテゴリ '{category}': データ取得中...")
                
                if category == 'games':
                    result = self._get_top_games_from_api(25)
                elif category == 'streams':
                    result = self._get_top_streams_from_api(25)
                elif category == 'clips':
                    result = self._get_top_clips_from_api(25)
                else:
                    continue
                
                if result and result.get('data'):
                    trends_data = result['data']
                    # カテゴリ情報を追加
                    for item in trends_data:
                        item['category'] = category
                    all_data.extend(trends_data)
                    logger.info(f"✅ カテゴリ '{category}': {len(trends_data)}件取得")
                else:
                    logger.warning(f"⚠️ カテゴリ '{category}': データ取得失敗")
            
            if all_data:
                logger.info(f"🔍 Twitch: 全カテゴリのデータをキャッシュに保存開始 ({len(all_data)}件)")
                self._save_all_categories_to_cache(all_data)
                logger.info(f"✅ Twitch: 全カテゴリのデータをキャッシュに保存完了 ({len(all_data)}件)")
            else:
                logger.warning("⚠️ Twitch: 取得できるデータがありませんでした")
                
        except Exception as e:
            logger.error(f"❌ Twitch: 全カテゴリ取得エラー: {e}", exc_info=True)
    
    def _save_all_categories_to_cache(self, all_data):
        """全カテゴリのデータをキャッシュに保存"""
        try:
            logger.info(f"🔍 Twitch: データ保存開始 - {len(all_data)}件")
            
            # 一つの接続で全ての処理を実行
            conn = self.db.get_connection()
            if not conn:
                logger.warning(f"⚠️ Twitch: データベース接続が取得できませんでした")
                return
            
            with conn.cursor() as cursor:
                # 既存のテーブルを削除して再作成
                cursor.execute("DROP TABLE IF EXISTS twitch_trends_cache")
                cursor.execute("""
                    CREATE TABLE twitch_trends_cache (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(500),
                            game_name VARCHAR(255),
                            viewer_count INTEGER DEFAULT 0,
                            rank INTEGER DEFAULT 0,
                            category VARCHAR(50) NOT NULL,
                            thumbnail_url VARCHAR(500),
                            user_name VARCHAR(255),
                            language VARCHAR(10),
                            started_at VARCHAR(50),
                            view_count INTEGER DEFAULT 0,
                            creator_name VARCHAR(255),
                            duration INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            url VARCHAR(500),
                            box_art_url VARCHAR(500),
                            game_id VARCHAR(255)
                        )
                    """)
                
                # データを一括保存
                for item in all_data:
                    cursor.execute("""
                        INSERT INTO twitch_trends_cache 
                        (title, game_name, viewer_count, rank, category, thumbnail_url, 
                         user_name, language, started_at, view_count, creator_name, 
                         duration, created_at, url, box_art_url, game_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item.get('title', ''),
                        item.get('game_name', ''),
                        item.get('viewer_count', 0),
                        item.get('rank', 0),
                        item.get('category', ''),
                        item.get('thumbnail_url', ''),
                        item.get('user_name', ''),
                        item.get('language', ''),
                        item.get('started_at', ''),
                        item.get('view_count', 0),
                        item.get('creator_name', ''),
                        item.get('duration', 0),
                        item.get('created_at', ''),
                        item.get('url', ''),
                        item.get('box_art_url', ''),
                        item.get('id', '')
                    ))
                
                # コミット
                conn.commit()
                logger.info(f"✅ Twitch: データ保存完了 - {len(all_data)}件")
                
                # 保存確認
                cursor.execute("SELECT COUNT(*) FROM twitch_trends_cache")
                saved_count = cursor.fetchone()[0]
                logger.info(f"✅ Twitch: 保存確認 - テーブル内データ件数: {saved_count}件")
                
                # cache_statusを更新
                from datetime import datetime
                cursor.execute("""
                    INSERT INTO cache_status (cache_key, last_updated, data_count)
                    VALUES ('twitch_trends', %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        last_updated = EXCLUDED.last_updated,
                        data_count = EXCLUDED.data_count
                """, (datetime.now(), len(all_data)))
                
                conn.commit()
                logger.info(f"✅ Twitch: cache_status更新完了")
            
        except Exception as e:
            logger.error(f"❌ Twitch: キャッシュ保存エラー: {e}", exc_info=True)
    
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
            
            # レート制限をチェック（認証リクエストもカウント）
            self.rate_limiter.wait_if_needed()
            
            response = requests.post(self.auth_url, data=auth_data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                # トークンの有効期限を設定（実際の有効期限より少し早めに設定）
                self.token_expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)
                logger.info("✅ Twitch アクセストークン取得成功")
                return self.access_token
            else:
                logger.error(f"❌ Twitch アクセストークン取得失敗: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Twitch アクセストークン取得エラー: {e}", exc_info=True)
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
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Twitch API リクエスト失敗: {response.status_code} - {endpoint}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Twitch API リクエストエラー: {e}", exc_info=True)
            return None
    
    def _get_top_games_from_api(self, limit=25):
        """Twitch APIから人気ゲームを取得"""
        try:
            logger.info(f"Twitch API 人気ゲーム取得開始: limit={limit}")
            
            params = {'first': limit}
            data = self._make_request('games/top', params)
            
            if not data or 'data' not in data:
                return {'error': 'Twitch APIからゲームデータを取得できませんでした'}
            
            # ゲーム情報を整形
            games = []
            for i, game in enumerate(data['data']):
                # 各ゲームの現在の視聴者数を取得
                viewer_count = self._get_game_viewer_count(game['id'])
                
                games.append({
                    'rank': i + 1,
                    'name': game['name'],
                    'id': game['id'],
                    'box_art_url': game['box_art_url'].replace('{width}x{height}', '320x180'),
                    'viewer_count': viewer_count,
                    'title': game['name'],  # テーブル表示用
                    'game_name': game['name'],
                    'thumbnail_url': game['box_art_url'].replace('{width}x{height}', '320x180')
                })
            
            # 視聴者数でソート
            games.sort(key=lambda x: x['viewer_count'], reverse=True)
            
            # ランクを再設定
            for i, game in enumerate(games):
                game['rank'] = i + 1
            
            return {
                'data': games,
                'status': 'success',
                'source': 'Twitch API',
                'total_count': len(games)
            }
            
        except Exception as e:
            return {'error': f'Twitch API 人気ゲーム取得エラー: {str(e)}'}
    
    def _get_top_streams_from_api(self, limit=25):
        """Twitch APIから人気ストリームを取得"""
        try:
            logger.info(f"Twitch API 人気ストリーム取得開始: limit={limit}")
            
            params = {'first': limit, 'language': 'en'}
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
                    'started_at': stream['started_at']
                })
            
            # 視聴者数でソート
            streams.sort(key=lambda x: x['viewer_count'], reverse=True)
            
            # ランクを再設定
            for i, stream in enumerate(streams):
                stream['rank'] = i + 1
            
            return {
                'data': streams,
                'status': 'success',
                'source': 'Twitch API',
                'total_count': len(streams)
            }
            
        except Exception as e:
            return {'error': f'Twitch API 人気ストリーム取得エラー: {str(e)}'}
    
    def _get_top_clips_from_api(self, limit=25):
        """Twitch APIから人気クリップを取得"""
        try:
            logger.info(f"Twitch API 人気クリップ取得開始: limit={limit}")
            
            # まず人気ストリーマーを取得
            popular_streamers = self._get_popular_streamers()
            if not popular_streamers:
                logger.error("❌ 人気ストリーマーが取得できませんでした")
                return {'error': '人気ストリーマーが取得できませんでした'}
            
            logger.debug(f"🔍 人気ストリーマー取得: {len(popular_streamers)}人")
            
            # 最初のストリーマーのクリップを取得
            broadcaster_id = popular_streamers[0]['user_id']
            params = {
                'broadcaster_id': broadcaster_id,
                'first': limit
            }
            
            logger.debug(f"🔍 クリップ取得パラメータ: {params}")
            data = self._make_request('clips', params)
            
            logger.debug(f"🔍 クリップAPI応答: {data}")
            
            if not data:
                logger.error(f"❌ クリップAPI応答がNone")
                return {'error': 'Twitch APIからクリップデータを取得できませんでした（応答なし）'}
            
            if 'data' not in data:
                logger.error(f"❌ クリップAPI応答に'data'キーがありません: {data}")
                return {'error': f'Twitch APIからクリップデータを取得できませんでした（データキーなし）: {data}'}
            
            if not data['data']:
                logger.error(f"❌ クリップデータが空です: {data}")
                return {'error': 'Twitch APIからクリップデータを取得できませんでした（データ空）'}
            
            # クリップ情報を整形
            clips = []
            for i, clip in enumerate(data['data']):
                # game_idからgame_nameを取得
                game_name = self._get_game_name_by_id(clip.get('game_id', ''))
                
                clips.append({
                    'rank': i + 1,
                    'title': clip['title'],
                    'creator_name': clip['creator_name'],
                    'game_name': game_name,
                    'view_count': clip['view_count'],
                    'thumbnail_url': clip['thumbnail_url'],
                    'duration': clip['duration'],
                    'created_at': clip['created_at'],
                    'url': clip['url'],
                    'viewer_count': clip['view_count']  # テーブル表示用
                })
            
            # 再生回数でソート
            clips.sort(key=lambda x: x['view_count'], reverse=True)
            
            # ランクを再設定
            for i, clip in enumerate(clips):
                clip['rank'] = i + 1
            
            return {
                'data': clips,
                'status': 'success',
                'source': 'Twitch API',
                'total_count': len(clips)
            }
            
        except Exception as e:
            return {'error': f'Twitch API 人気クリップ取得エラー: {str(e)}'}
    
    def _get_popular_streamers(self):
        """人気ストリーマーを取得"""
        try:
            logger.debug("🔍 人気ストリーマー取得開始")
            
            params = {'first': 10}
            data = self._make_request('streams', params)
            
            if not data or 'data' not in data:
                logger.error("❌ ストリーマー取得失敗")
                return []
            
            streamers = []
            for stream in data['data']:
                streamers.append({
                    'user_id': stream['user_id'],
                    'user_name': stream['user_name'],
                    'viewer_count': stream['viewer_count']
                })
            
            logger.info(f"✅ 人気ストリーマー取得完了: {len(streamers)}人")
            return streamers
            
        except Exception as e:
            logger.error(f"❌ 人気ストリーマー取得エラー: {e}", exc_info=True)
            return []
    
    def _get_game_name_by_id(self, game_id):
        """game_idからgame_nameを取得"""
        try:
            if not game_id:
                return 'Unknown Game'
            
            params = {'id': game_id}
            data = self._make_request('games', params)
            
            if data and 'data' in data and data['data']:
                return data['data'][0].get('name', 'Unknown Game')
            return 'Unknown Game'
        except:
            return 'Unknown Game'
    
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
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            from datetime import datetime
            now = datetime.now()
            
            conn = self.db.get_connection()
            if not conn:
                logger.warning(f"⚠️ Twitch: データベース接続が取得できませんでした (_update_cache_status)")
                return
            
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
            logger.error(f"❌ Twitch: cache_status更新エラー: {e}", exc_info=True)
    
    def _get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        try:
            conn = self.db.get_connection()
            if not conn:
                logger.warning(f"⚠️ Twitch: データベース接続が取得できませんでした (_get_cache_info)")
                return None
            
            with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('twitch_trends',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] or 0
                        }
                    return {'last_updated': None, 'data_count': 0}
        except Exception as e:
            logger.error(f"キャッシュ情報取得エラー: {e}", exc_info=True)
            return {'last_updated': None, 'data_count': 0}