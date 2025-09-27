import os
import logging
import time
import signal
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database_config import TrendsCache

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrendsScheduler:
    """トレンド自動取得スケジューラークラス"""
    
    def __init__(self, app):
        """初期化"""
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.db = TrendsCache()
        self.is_running = False
        
        logger.info("TrendsScheduler初期化完了")
    
    def _execute_with_timeout(self, func, timeout_seconds=30):
        """タイムアウト付きで関数を実行（簡易版）"""
        try:
            # 簡易的なタイムアウト処理（signal.SIGALRMはメインスレッドでのみ動作）
            result = func()
            return result
        except Exception as e:
            logger.error(f"関数実行エラー: {e}")
            raise e
    
    def start(self):
        """スケジューラーを開始"""
        if not self.is_running:
            try:
                # 毎日朝5時に自動取得を実行
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=5, minute=0),
                    id='daily_trends_fetch',
                    name='毎日朝5時のトレンド取得',
                    replace_existing=True
                )
                
                # スケジューラーを開始
                self.scheduler.start()
                self.is_running = True
                
                logger.info("✅ スケジューラー開始完了")
                logger.info("📅 自動取得は無効化されています（手動実行のみ）")
                
                # 初回起動時の自動実行も無効化
                # self._fetch_all_trends()
                
            except Exception as e:
                logger.error(f"❌ スケジューラー開始エラー: {e}")
                self.is_running = False
    
    def stop(self):
        """スケジューラーを停止"""
        if self.is_running:
            try:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("🛑 スケジューラー停止完了")
            except Exception as e:
                logger.error(f"❌ スケジューラー停止エラー: {e}")
    
    def _fetch_all_trends(self):
        """全プラットフォームのトレンドを取得"""
        try:
            logger.info("🔄 自動トレンド取得開始")
            jst = pytz.timezone('Asia/Tokyo')
            start_time = datetime.now(jst)
            execution_id = f"scheduler_{start_time.strftime('%Y%m%d_%H%M%S')}"
            
            # 各プラットフォームのトレンドを取得
            results = {
                'google_trends': self._fetch_google_trends(),
                'youtube_jp': self._fetch_youtube_trends('JP'),
                'spotify': self._fetch_spotify_trends(),
                'world_news': self._fetch_world_news(),
                'podcast': self._fetch_podcast_trends(),
                'hatena': self._fetch_hatena_trends(),
                'twitch': self._fetch_twitch_trends(),
                'rakuten': self._fetch_rakuten_trends()
            }
            
            # 結果をログ出力
            success_count = sum(1 for result in results.values() if result.get('success', False))
            total_count = len(results)
            failed_count = total_count - success_count
            
            end_time = datetime.now(jst)
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"✅ 自動トレンド取得完了: {success_count}/{total_count} 成功")
            logger.info(f"⏱️ 実行時間: {duration:.2f}秒")
            
            # 各プラットフォームのデータをデータベースに保存
            self._save_trends_to_database(results)
            
            # 実行履歴をデータベースに保存
            self._save_execution_log(execution_id, start_time, end_time, total_count, success_count, failed_count, duration)
            
        except Exception as e:
            logger.error(f"❌ 自動トレンド取得エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def _fetch_youtube_trends(self, region):
        """YouTubeトレンドを取得（強制更新）"""
        try:
            with self.app.app_context():
                from app import youtube_manager
                if youtube_manager:
                    result = youtube_manager.get_trends(region, 25, force_refresh=True)
                    logger.info(f"YouTube {region}: {'成功' if result.get('data') else '失敗'}")
                    return {'success': bool(result.get('data')), 'data': result}
                else:
                    logger.warning("YouTube Managerが初期化されていません")
                    return {'success': False, 'error': 'YouTube Manager未初期化'}
        except Exception as e:
            logger.error(f"YouTube {region} 取得エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_google_trends(self):
        """Google Trendsを取得"""
        try:
            with self.app.app_context():
                from app import get_trends_from_bigquery
                trends_df, status = get_trends_from_bigquery('JP')
                
                if trends_df is not None and not trends_df.empty:
                    # DataFrameを辞書形式に変換
                    trends_data = trends_df.to_dict('records')
                    logger.info(f"Google Trends: 成功 - {len(trends_data)}件")
                    return {'success': True, 'data': trends_data}
                else:
                    logger.warning(f"Google Trends: データが取得できませんでした - {status}")
                    return {'success': False, 'error': f'データ取得失敗: {status}'}
        except Exception as e:
            logger.error(f"Google Trends 取得エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_spotify_trends(self):
        """Spotifyトレンドを取得（強制更新）"""
        try:
            with self.app.app_context():
                from app import music_manager
                if music_manager:
                    result = music_manager.get_trends('spotify', 'JP', force_refresh=True)
                    logger.info(f"Spotify: {'成功' if result.get('data') else '失敗'}")
                    return {'success': bool(result.get('data')), 'data': result}
                else:
                    logger.warning("Music Managerが初期化されていません")
                    return {'success': False, 'error': 'Music Manager未初期化'}
        except Exception as e:
            logger.error(f"Spotify 取得エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_world_news(self):
        """World Newsを取得"""
        try:
            with self.app.app_context():
                from app import get_world_news_trends
                result = get_world_news_trends()
                logger.info(f"World News: {'成功' if result else '失敗'}")
                return {'success': bool(result), 'data': result}
        except Exception as e:
            logger.error(f"World News 取得エラー: {e}")
            return {'success': False, 'error': str(e)}
    
    def _fetch_podcast_trends(self):
        """Podcastトレンドを取得"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                def fetch_func():
                    with self.app.app_context():
                        from services.trends.podcast_trends import PodcastTrendsManager
                        podcast_manager = PodcastTrendsManager()
                        return podcast_manager.get_trends('best_podcasts')
                
                result = self._execute_with_timeout(fetch_func, timeout_seconds=30)
                
                if result:
                    logger.info(f"Podcast: 成功 (試行 {attempt + 1}/{max_retries})")
                    return {'success': True, 'data': result}
                else:
                    logger.warning(f"Podcast: データが取得できませんでした (試行 {attempt + 1}/{max_retries})")
                        
            except TimeoutError as e:
                logger.error(f"Podcast タイムアウト (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                logger.error(f"Podcast 取得エラー (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                
            if attempt < max_retries - 1:
                logger.info(f"Podcast: {retry_delay}秒後にリトライします...")
                time.sleep(retry_delay)
                retry_delay *= 2
        
        return {'success': False, 'error': '最大リトライ回数に達しました'}
    
    def _fetch_hatena_trends(self):
        """はてなブックマークトレンドを取得"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                def fetch_func():
                    with self.app.app_context():
                        # はてなブックマークのマネージャーを直接使用
                        from services.trends.hatena_trends import HatenaTrendsManager
                        hatena_manager = HatenaTrendsManager()
                        return hatena_manager.get_trends()
                
                # タイムアウト付きで実行
                result = self._execute_with_timeout(fetch_func, timeout_seconds=30)
                
                if result:
                    logger.info(f"はてなブックマーク: 成功 (試行 {attempt + 1}/{max_retries})")
                    return {'success': True, 'data': result}
                else:
                    logger.warning(f"はてなブックマーク: データが取得できませんでした (試行 {attempt + 1}/{max_retries})")
                        
            except TimeoutError as e:
                logger.error(f"はてなブックマーク タイムアウト (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                logger.error(f"はてなブックマーク 取得エラー (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                
            if attempt < max_retries - 1:
                logger.info(f"はてなブックマーク: {retry_delay}秒後にリトライします...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数バックオフ
        
        return {'success': False, 'error': '最大リトライ回数に達しました'}
    
    def _fetch_twitch_trends(self):
        """Twitchトレンドを取得"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                def fetch_func():
                    with self.app.app_context():
                        # Twitchのマネージャーを直接使用
                        from services.trends.twitch_trends import TwitchTrendsManager
                        twitch_manager = TwitchTrendsManager()
                        return twitch_manager.get_trends()
                
                # タイムアウト付きで実行
                result = self._execute_with_timeout(fetch_func, timeout_seconds=30)
                
                if result:
                    logger.info(f"Twitch: 成功 (試行 {attempt + 1}/{max_retries})")
                    return {'success': True, 'data': result}
                else:
                    logger.warning(f"Twitch: データが取得できませんでした (試行 {attempt + 1}/{max_retries})")
                        
            except TimeoutError as e:
                logger.error(f"Twitch タイムアウト (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                logger.error(f"Twitch 取得エラー (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                
            if attempt < max_retries - 1:
                logger.info(f"Twitch: {retry_delay}秒後にリトライします...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数バックオフ
        
        return {'success': False, 'error': '最大リトライ回数に達しました'}
    
    def _fetch_rakuten_trends(self):
        """楽天トレンドを取得"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                def fetch_func():
                    with self.app.app_context():
                        # 楽天のマネージャーを直接使用
                        from services.trends.rakuten_trends import RakutenTrendsManager
                        rakuten_manager = RakutenTrendsManager()
                        return rakuten_manager.get_trends()
                
                # タイムアウト付きで実行
                result = self._execute_with_timeout(fetch_func, timeout_seconds=30)
                
                if result:
                    logger.info(f"楽天: 成功 (試行 {attempt + 1}/{max_retries})")
                    return {'success': True, 'data': result}
                else:
                    logger.warning(f"楽天: データが取得できませんでした (試行 {attempt + 1}/{max_retries})")
                        
            except TimeoutError as e:
                logger.error(f"楽天 タイムアウト (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                logger.error(f"楽天 取得エラー (試行 {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                
            if attempt < max_retries - 1:
                logger.info(f"楽天: {retry_delay}秒後にリトライします...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数バックオフ
        
        return {'success': False, 'error': '最大リトライ回数に達しました'}
    
    def _save_trends_to_database(self, results: dict):
        """各プラットフォームのトレンドデータをデータベースに保存"""
        try:
            logger.info(f"🔄 トレンドデータ保存開始: {len(results)}プラットフォーム")
            
            # 古いtrends_cacheデータを削除
            self._clear_old_trends_cache()
            
            for platform, result in results.items():
                logger.info(f"📊 {platform}の結果: success={result.get('success')}, data_type={type(result.get('data'))}")
                
                if result.get('success') and result.get('data'):
                    try:
                        # プラットフォーム名とトレンドタイプを決定
                        if platform == 'google_trends':
                            platform_name = 'Google Trends'
                            trend_type = 'general'
                        elif platform == 'youtube_jp':
                            platform_name = 'YouTube'
                            trend_type = 'JP'
                        else:
                            platform_name = platform.replace('_', ' ').title()
                            trend_type = 'general'
                        
                        # データの件数を計算（プラットフォーム別）
                        data_count = 1  # デフォルト値
                        if platform == 'google_trends':
                            # Google Trends: データ構造に応じて件数を計算
                            if isinstance(result['data'], dict):
                                if 'data' in result['data'] and isinstance(result['data']['data'], list):
                                    data_count = len(result['data']['data'])
                                elif 'success' in result['data'] and not result['data']['success']:
                                    data_count = 0  # エラーの場合は0件
                                else:
                                    data_count = 1
                            elif isinstance(result['data'], list):
                                data_count = len(result['data'])
                            else:
                                data_count = 0
                        elif platform == 'youtube_jp':
                            # YouTube: リストの長さ
                            data_count = len(result['data']) if isinstance(result['data'], list) else 1
                        elif platform == 'spotify':
                            # Spotify: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        elif platform == 'world_news':
                            # World News: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        elif platform == 'podcast':
                            # Podcast: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        elif platform == 'hatena':
                            # Hatena: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        elif platform == 'twitch':
                            # Twitch: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        elif platform == 'rakuten':
                            # Rakuten: データ内の件数
                            if isinstance(result['data'], dict) and 'data' in result['data']:
                                data_count = len(result['data']['data']) if isinstance(result['data']['data'], list) else 1
                        logger.info(f"💾 {platform_name}の{trend_type}トレンドデータを保存中: {data_count}件")
                        
                        # データベースに保存
                        self.db.save_scheduler_trends(
                            platform=platform_name,
                            trend_type=trend_type,
                            data=result['data'],
                            status='success',
                            total_count=data_count,
                            execution_time=None
                        )
                        
                        # trends_cacheテーブルにも保存
                        self._save_to_trends_cache(platform, result['data'], data_count)
                        
                        logger.info(f"✅ {platform_name}の{trend_type}トレンドデータを保存しました")
                        
                    except Exception as e:
                        logger.error(f"❌ {platform}のデータ保存エラー: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # 失敗した場合も記録
                    try:
                        platform_name = platform.replace('_', ' ').title()
                        error_msg = result.get('error', 'Unknown error')
                        logger.info(f"❌ {platform_name}の失敗データを記録中: {error_msg}")
                        
                        self.db.save_scheduler_trends(
                            platform=platform_name,
                            trend_type='general',
                            data={'error': error_msg},
                            status='failed',
                            total_count=0,
                            execution_time=None
                        )
                        logger.info(f"❌ {platform_name}の失敗データを記録しました")
                    except Exception as e:
                        logger.error(f"❌ {platform}の失敗データ記録エラー: {e}")
                        import traceback
                        traceback.print_exc()
                        
        except Exception as e:
            logger.error(f"❌ トレンドデータ保存エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_to_trends_cache(self, platform: str, data: dict, data_count: int):
        """trends_cacheテーブルにデータを保存（Google Trends専用）"""
        try:
            # Google Trendsのみtrends_cacheテーブルに保存
            if platform == 'google_trends':
                self._save_google_trends_to_cache(data)
            else:
                # 他のプラットフォームはtrends_cacheに保存しない
                logger.info(f"📊 {platform}のデータはtrends_cacheに保存しません（Google Trends専用）")
                
        except Exception as e:
            logger.error(f"❌ trends_cache保存エラー ({platform}): {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_old_trends_cache(self):
        """古いtrends_cacheデータを削除"""
        try:
            self.db.clear_trends_cache_by_country('JP')
            logger.info("✅ 古いtrends_cacheデータを削除しました")
        except Exception as e:
            logger.error(f"❌ 古いtrends_cacheデータ削除エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_google_trends_to_cache(self, data: dict):
        """Google Trendsデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('term'):  # 空のtermはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('term', ''),
                        rank=item.get('rank', 0),
                        score=item.get('score', 0)
                    )
    
    def _save_youtube_trends_to_cache(self, data: dict):
        """YouTubeデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('title'):  # 空のtitleはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('title', ''),
                        rank=item.get('rank', 0),
                        score=item.get('view_count', 0),
                        region_count=0
                    )
    
    def _save_spotify_trends_to_cache(self, data: dict):
        """Spotifyデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('title') and item.get('artist'):  # 空のtitleやartistはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=f"{item.get('title', '')} - {item.get('artist', '')}",
                        rank=item.get('rank', 0),
                        score=item.get('popularity', 0),
                        region_count=0
                    )
    
    def _save_world_news_to_cache(self, data: dict):
        """World Newsデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('title'):  # 空のtitleはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('title', ''),
                        rank=item.get('rank', 0),
                        score=item.get('score', 0),
                        region_count=0
                    )
    
    def _save_podcast_trends_to_cache(self, data: dict):
        """Podcastデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('title'):  # 空のtitleはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('title', ''),
                        rank=item.get('rank', 0),
                        score=item.get('score', 0),
                        region_count=0
                    )
    
    def _save_hatena_trends_to_cache(self, data: dict):
        """Hatenaデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('title'):  # 空のtitleはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('title', ''),
                        rank=item.get('rank', 0),
                        score=item.get('bookmark_count', 0),
                        region_count=0
                    )
    
    def _save_twitch_trends_to_cache(self, data: dict):
        """Twitchデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('name'):  # 空のnameはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('name', ''),
                        rank=item.get('rank', 0),
                        score=item.get('viewer_count', 0),
                        region_count=0
                    )
    
    def _save_rakuten_trends_to_cache(self, data: dict):
        """Rakutenデータをtrends_cacheに保存"""
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                if item.get('itemName'):  # 空のitemNameはスキップ
                    self.db.save_trends_cache(
                        country_code='JP',
                        term=item.get('itemName', ''),
                        rank=item.get('rank', 0),
                        score=item.get('reviewCount', 0),
                        region_count=0
                    )
    
    def _save_execution_log(self, execution_id: str, start_time: datetime, end_time: datetime, 
                           total_platforms: int, successful_platforms: int, failed_platforms: int, 
                           execution_time: float):
        """スケジューラー実行履歴をデータベースに保存"""
        try:
            status = 'success' if failed_platforms == 0 else 'partial_success' if successful_platforms > 0 else 'failed'
            
            self.db.save_scheduler_execution_log(
                execution_id=execution_id,
                start_time=start_time,
                end_time=end_time,
                total_platforms=total_platforms,
                successful_platforms=successful_platforms,
                failed_platforms=failed_platforms,
                execution_time=execution_time,
                status=status,
                error_details=None
            )
            
            logger.info(f"✅ 実行履歴を保存しました: {execution_id} - {status}")
            
        except Exception as e:
            logger.error(f"❌ 実行履歴保存エラー: {e}")
    
    def _update_last_fetch_timestamp(self):
        """最終取得時刻をデータベースに記録"""
        try:
            jst = pytz.timezone('Asia/Tokyo')
            timestamp = datetime.now(jst).isoformat()
            # データベースに最終更新時刻を保存
            # ここでは簡単なログ出力のみ
            logger.info(f"📅 最終自動取得時刻: {timestamp}")
        except Exception as e:
            logger.error(f"最終取得時刻記録エラー: {e}")
    
    def get_status(self):
        """スケジューラーの状態を取得"""
        return {
            'is_running': self.is_running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }
