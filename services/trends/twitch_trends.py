import gc
import os
import requests
import json
from datetime import datetime, timedelta
import pytz
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class TwitchTrendsManager(BaseTrendsManager):
    """Twitchトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='twitch', max_requests=800, window_seconds=60)
        
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.base_url = "https://api.twitch.tv/helix"
        self.auth_url = "https://id.twitch.tv/oauth2/token"
        self.access_token = None
        self.token_expires_at = None
        
        logger.info(f"Twitch Trends Manager初期化:")
        logger.info(f"  Client ID: {'設定済み' if self.client_id else '未設定'}")
        logger.info(f"  Client Secret: {'設定済み' if self.client_secret else '未設定'}")
        logger.info(f"  Base URL: {self.base_url}")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'twitch_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            category = kwargs.get('category', 'games')
            cached_data = self.db.get_twitch_trends_from_cache(category)
            
            if cached_data and len(cached_data) > 0:
                logger.info(f"✅ Twitch: キャッシュから{len(cached_data)}件のデータを取得 (category: {category})")
                return cached_data
            else:
                logger.warning(f"⚠️ Twitch: キャッシュにデータがありません (category: {category}, cached_data: {cached_data})")
                return None  # Noneを返すことで、base_trends_managerでキャッシュがないと判断される
        except Exception as e:
            logger.error(f"❌ Twitch: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            category = kwargs.get('category', 'games')
            logger.info(f"💾 Twitch: キャッシュに保存開始 (category: {category}, data: {len(data)}件)")
            success = self.db.save_twitch_trends_to_cache(data, category)
            if success:
                logger.info(f"✅ Twitch: キャッシュに保存完了 (category: {category}, data: {len(data)}件)")
            else:
                logger.warning(f"⚠️ Twitch: キャッシュ保存失敗 (category: {category})")
            return success
        except Exception as e:
            logger.error(f"❌ Twitch キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            category = kwargs.get('category', 'games')
            return self.db.clear_twitch_trends_cache(category)
        except Exception as e:
            logger.error(f"❌ Twitch キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Twitch: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, category='games', limit=25, *args, **kwargs):
        """外部APIからTwitchデータを取得"""
        if category == 'games':
            api_result = self._get_top_games_from_api(limit)
        elif category == 'streams':
            api_result = self._get_top_streams_from_api(limit)
        elif category == 'clips':
            api_result = self._get_top_clips_from_api(limit)
        else:
            return {
                'success': False,
                'error': f'Unknown category: {category}',
                'data': []
            }
        
        if api_result and isinstance(api_result, dict) and api_result.get('data'):
            trends_data = api_result['data']
            # カテゴリ情報を追加
            for item in trends_data:
                item['category'] = category
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'trend_type': category,
                'source': 'Twitch API'
            }
        else:
            return {
                'success': False,
                'error': api_result.get('error', 'Unknown error') if api_result else 'API call failed',
                'data': []
            }

    def get_available_categories(self):
        """利用可能なカテゴリ一覧を取得"""
        return ['games', 'streams', 'clips']
    
    def get_trends(self, category='games', limit=25, force_refresh=False):
        """Twitchトレンドを取得（BaseTrendsManagerの共通処理を使用）"""
        # 視聴者数で降順ソート（games/streams: viewer_count, clips: view_count→viewer_count）
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key='viewer_count',
            sort_reverse=True,  # 視聴者数の多い順
            category=category
        )
        
        # categoryパラメータを結果に追加（trend_typeとしても保持）
        if result and isinstance(result, dict):
            result['trend_type'] = category
            result['category'] = category
        return result
    
    def get_from_cache_by_category(self, category):
        """カテゴリ別のキャッシュデータを取得（後方互換性のため、_get_from_cacheを呼び出す）"""
        # 後方互換性のため、_get_from_cacheを呼び出す
        return self._get_from_cache(category=category)
    
    def _save_to_cache_by_category(self, category, data):
        """カテゴリ別のデータをキャッシュに保存"""
        try:
            logger.debug(f"🔍 Twitch: カテゴリ別キャッシュ保存開始 (category: {category}, data: {len(data)}件)")
            
            with self.db.get_connection() as conn:
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
        """全カテゴリを順に取得し、カテゴリごとにキャッシュへ保存（ピークメモリ抑制）"""
        try:
            logger.info("🔍 Twitch: 全カテゴリのデータを取得開始")

            if not self.client_id or not self.client_secret:
                error_msg = "Twitch API認証情報が設定されていません（TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET）"
                logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'data': []
                }

            categories = self.get_available_categories()
            errors = []
            total_saved = 0

            for category in categories:
                logger.debug(f"🔍 カテゴリ '{category}': データ取得中...")
                try:
                    if category == 'games':
                        result = self._get_top_games_from_api(25)
                    elif category == 'streams':
                        result = self._get_top_streams_from_api(25)
                    elif category == 'clips':
                        result = self._get_top_clips_from_api(25)
                    else:
                        gc.collect()
                        continue

                    if result and result.get('data'):
                        trends_data = result['data']
                        for item in trends_data:
                            item['category'] = category
                        if self._save_to_cache(trends_data, category=category):
                            total_saved += len(trends_data)
                            logger.info(f"✅ カテゴリ '{category}': {len(trends_data)}件取得・キャッシュ保存")
                        else:
                            logger.warning(f"⚠️ Twitch: カテゴリ '{category}' のキャッシュ保存失敗")
                    else:
                        error_msg = result.get('error', 'Unknown error') if result else 'API call failed'
                        logger.warning(f"⚠️ カテゴリ '{category}': データ取得失敗 - {error_msg}")
                        errors.append(f"{category}: {error_msg}")
                except Exception as e:
                    error_msg = f"カテゴリ '{category}' 取得エラー: {str(e)}"
                    logger.error(f"❌ {error_msg}", exc_info=True)
                    errors.append(error_msg)
                finally:
                    gc.collect()

            if total_saved > 0:
                # save_to_cache がカテゴリごとに data_count を上書きするため、合計件数で最終反映
                self._update_cache_status('twitch_trends', total_saved)
                logger.info(f"✅ Twitch: 全カテゴリのデータをキャッシュに保存完了 ({total_saved}件)")
                return {
                    'success': True,
                    'data': [],
                    'status': 'api_fetched',
                    'source': 'Twitch API',
                    'total_count': total_saved,
                    'errors': errors if errors else None
                }

            error_msg = "取得できるデータがありませんでした"
            if errors:
                error_msg += f" (エラー: {', '.join(errors)})"
            logger.warning(f"⚠️ Twitch: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'data': [],
                'errors': errors
            }

        except Exception as e:
            error_msg = f"全カテゴリ取得エラー: {str(e)}"
            logger.error(f"❌ Twitch: {error_msg}", exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'data': []
            }
    
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
    
    def _get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
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