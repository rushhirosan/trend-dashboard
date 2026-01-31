import os
import logging
import time
import signal
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database_config import TrendsCache
from services.subscription.subscription_manager import SubscriptionManager

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
        self.last_night_execution_time = None  # 最後に1時のジョブが実行された時刻（datetime形式）
        self.last_daily_execution_date = None  # 最後に7時のジョブが実行された日付（YYYY-MM-DD形式）
        self.last_afternoon_execution_time = None  # 最後に13時のジョブが実行された時刻（datetime形式）
        self.last_evening_execution_time = None  # 最後に19時のジョブが実行された時刻（datetime形式）
        self._fetching_in_progress = False  # データ取得処理が実行中かどうかのフラグ
        # メール送信用のSubscriptionManagerを初期化
        try:
            self.subscription_manager = SubscriptionManager()
            logger.info("SubscriptionManager初期化完了")
        except Exception as e:
            logger.warning(f"⚠️ SubscriptionManager初期化エラー（メール自動送信は無効）: {e}")
            self.subscription_manager = None

        # アラート送信（Discord Webhook）を初期化
        try:
            from utils.alert_service import AlertService
            self.alert_service = AlertService()
        except Exception as e:
            logger.warning("⚠️ AlertService初期化エラー（アラート無効）: %s", e)
            self.alert_service = None

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
                # 日本時間（JST）のタイムゾーンを設定
                jst = pytz.timezone('Asia/Tokyo')
                
                # 毎日深夜1時（日本時間）に自動取得を実行
                # misfire_grace_time: 実行時刻を逃しても最大3600秒（60分）以内なら実行する
                # coalesce: 複数の実行が遅延した場合、1回だけ実行する
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=1, minute=0, timezone=jst),
                    id='daily_trends_fetch_night',
                    name='毎日深夜1時（日本時間）のトレンド取得',
                    replace_existing=True,
                    misfire_grace_time=3600,  # 60分以内なら実行（1時から2時まで）
                    coalesce=True,  # 複数の遅延実行を1回にまとめる
                    max_instances=1  # 同時実行は1つのみ
                )
                
                # 毎日朝7時（日本時間）に自動取得を実行
                # misfire_grace_time: 実行時刻を逃しても最大3600秒（60分）以内なら実行する
                # coalesce: 複数の実行が遅延した場合、1回だけ実行する
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=7, minute=0, timezone=jst),
                    id='daily_trends_fetch_morning',
                    name='毎日朝7時（日本時間）のトレンド取得',
                    replace_existing=True,
                    misfire_grace_time=3600,  # 60分以内なら実行（7時から8時まで）
                    coalesce=True,  # 複数の遅延実行を1回にまとめる
                    max_instances=1  # 同時実行は1つのみ
                )
                
                # 毎日昼13時（日本時間）に自動取得を実行
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=13, minute=0, timezone=jst),
                    id='daily_trends_fetch_afternoon',
                    name='毎日昼13時（日本時間）のトレンド取得',
                    replace_existing=True,
                    misfire_grace_time=3600,  # 60分以内なら実行（13時から14時まで）
                    coalesce=True,  # 複数の遅延実行を1回にまとめる
                    max_instances=1  # 同時実行は1つのみ
                )
                
                # 毎日夜19時（日本時間）に自動取得を実行
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=19, minute=0, timezone=jst),
                    id='daily_trends_fetch_evening',
                    name='毎日夜19時（日本時間）のトレンド取得',
                    replace_existing=True,
                    misfire_grace_time=3600,  # 60分以内なら実行（19時から20時まで）
                    coalesce=True,  # 複数の遅延実行を1回にまとめる
                    max_instances=1  # 同時実行は1つのみ
                )
                
                # スケジューラーを開始
                self.scheduler.start()
                self.is_running = True
                
                logger.info("✅ スケジューラー開始完了")
                logger.info("📅 毎日深夜1:00、朝7:00、昼13:00、夜19:00（日本時間）に全トレンドを自動取得します")
                
                # 起動時の自動実行は無効化（デプロイ時の不要なAPI呼び出しとメール送信を防ぐ）
                # 環境変数SKIP_STARTUP_EXECUTION=trueの場合はスキップ
                # マシンが停止していた場合の補完は、次回のスケジュール実行時に自動的に処理される
                skip_startup = os.getenv('SKIP_STARTUP_EXECUTION', 'true').lower() == 'true'
                if not skip_startup:
                    logger.info("🔄 起動時の自動実行を実行します（SKIP_STARTUP_EXECUTION=false）")
                    self._check_and_execute_missed_job(jst)
                else:
                    logger.info("⏭️ 起動時の自動実行をスキップします（デプロイ時の不要なAPI呼び出しを防ぐため）")
                
            except Exception as e:
                logger.error(f"❌ スケジューラー開始エラー: {e}", exc_info=True)
                self.is_running = False
    
    def _fetch_ebay_trends(self):
        """eBay Popular/Trendingを取得（手動実行用）
        
        注意: 通常のスケジュール実行では、_fetch_all_trends()内で
        refresh_all_trends()が呼び出され、eBayの全カテゴリが取得されます。
        このメソッドは手動実行やテスト用に残しています。
        """
        try:
            logger.info(f"🔄 eBay Popular/Trending 取得開始")
            
            with self.app.app_context():
                managers = self.app.config.get('TREND_MANAGERS')
                if not managers:
                    logger.error("❌ トレンドマネージャーが初期化されていません")
                    return
                
                ebay_manager = managers.get('ebay')
                if not ebay_manager:
                    logger.error("❌ eBay Popular/Trendingマネージャーが初期化されていません")
                    return
                
                # 取得（force_refresh=True）
                result = ebay_manager.get_trends(limit=25, force_refresh=True)
                
                if result.get('success'):
                    data_count = len(result.get('data', []))
                    logger.info(f"✅ eBay Popular/Trending 取得完了: {data_count}件")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.warning(f"⚠️ eBay Popular/Trending 取得エラー: {error_msg}")
                    
        except Exception as e:
            logger.error(f"❌ eBay Popular/Trending 取得エラー: {e}", exc_info=True)
    
    def _check_and_execute_missed_job(self, jst):
        """
        起動時に当日の1時、7時、13時、または19時を過ぎている場合は自動実行
        （マシンが停止していた場合の補完処理）
        
        マシンが何時に再起動されても、当日の1時、7時、13時、または19時を過ぎていれば実行する。
        ただし、既に実行済みの場合は実行しない。
        """
        try:
            now_jst = datetime.now(jst)
            today = now_jst.date()
            today_1am = now_jst.replace(hour=1, minute=0, second=0, microsecond=0)
            today_7am = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
            today_1pm = now_jst.replace(hour=13, minute=0, second=0, microsecond=0)
            today_7pm = now_jst.replace(hour=19, minute=0, second=0, microsecond=0)
            
            # 1時、7時、13時、19時の全てをチェックし、必要に応じて1回だけ実行
            should_execute_1am = False
            should_execute_7am = False
            should_execute_1pm = False
            should_execute_7pm = False
            
            # 当日の1時を過ぎているかチェック
            if now_jst >= today_1am:
                # 既に実行済みかどうかをチェック（1時間以内に実行されていればスキップ）
                if self.last_night_execution_time:
                    time_diff = (now_jst - self.last_night_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 起動時チェック: 当日の1時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の1時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_1am = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の1時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_1am = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の1時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の7時を過ぎているかチェック
            if now_jst >= today_7am:
                # 既に実行済みかどうかをチェック
                if self.last_daily_execution_date == today:
                    logger.info(f"⏰ 起動時チェック: 当日の7時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の7時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_7am = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の7時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の13時を過ぎているかチェック
            if now_jst >= today_1pm:
                # 既に実行済みかどうかをチェック（1時間以内に実行されていればスキップ）
                if self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 起動時チェック: 当日の13時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の13時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_1pm = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の13時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_1pm = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の13時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の19時を過ぎているかチェック
            if now_jst >= today_7pm:
                # 既に実行済みかどうかをチェック（1時間以内に実行されていればスキップ）
                if self.last_evening_execution_time:
                    time_diff = (now_jst - self.last_evening_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 起動時チェック: 当日の19時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の19時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_7pm = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の19時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_7pm = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の19時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 1時、7時、13時、または19時のジョブが必要な場合、1回だけ実行
            if should_execute_1am or should_execute_7am or should_execute_1pm or should_execute_7pm:
                missed_times = []
                if should_execute_1am:
                    missed_times.append("1時")
                if should_execute_7am:
                    missed_times.append("7時")
                if should_execute_1pm:
                    missed_times.append("13時")
                if should_execute_7pm:
                    missed_times.append("19時")
                logger.info(f"🔄 当日の{', '.join(missed_times)}の処理を自動実行します（マシン停止による実行漏れを補完）")
                self._fetch_all_trends()
        except Exception as e:
            logger.error(f"❌ 起動時チェックエラー: {e}", exc_info=True)
            # エラーが発生してもスケジューラーの起動は継続
    
    def stop(self):
        """スケジューラーを停止"""
        if self.is_running:
            try:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("🛑 スケジューラー停止完了")
            except Exception as e:
                logger.error(f"❌ スケジューラー停止エラー: {e}")
    
    def _fetch_all_trends(self, force=False, trigger_source='scheduler'):
        """全プラットフォームのトレンドを取得（既存のrefresh_all_trends()を使用）
        
        Args:
            force: Trueの場合、既に実行済みでも強制的に実行する
                   Falseの場合、スケジューラー実行時（通常の定期実行）
            trigger_source: 呼び出し元の識別子。'scheduler'=定期実行、'api'=API（手動/外部）
        """
        # 同時実行防止: 既に実行中の場合はスキップ
        if self._fetching_in_progress:
            logger.warning("⚠️ データ取得処理が既に実行中です。重複実行をスキップします")
            return
        
        self._fetching_in_progress = True
        try:
            jst = pytz.timezone('Asia/Tokyo')
            now_jst = datetime.now(jst)
            today = now_jst.date()
            
            # 既に当日実行済みかチェック（重複実行を防ぐ）
            # force=Trueの場合はスキップしない
            if not force:
                # 1時前後（0:00-2:00）の実行の場合、1時間以内に1時ジョブが実行済みかチェック
                if 0 <= now_jst.hour < 2 and self.last_night_execution_time:
                    time_diff = (now_jst - self.last_night_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の1時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._fetching_in_progress = False
                        return
                # 7時前後（6:00-8:00）の実行の場合、当日の7時ジョブが既に実行済みかチェック
                if 6 <= now_jst.hour < 8 and self.last_daily_execution_date == today:
                    logger.info(f"⏰ 当日の7時のジョブは既に実行済みです（{today}）。重複実行をスキップします。")
                    self._fetching_in_progress = False
                    return
                # 13時前後（12:00-14:00）の実行の場合、1時間以内に13時ジョブが実行済みかチェック
                if 12 <= now_jst.hour < 14 and self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の13時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._fetching_in_progress = False
                        return
                # 19時前後（18:00-20:00）の実行の場合、1時間以内に19時ジョブが実行済みかチェック
                if 18 <= now_jst.hour < 20 and self.last_evening_execution_time:
                    time_diff = (now_jst - self.last_evening_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の19時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._fetching_in_progress = False
                        return
            
            logger.info("🔄 自動トレンド取得開始 [trigger=%s]", trigger_source)
            start_time = datetime.now(jst)
            execution_id = f"scheduler_{start_time.strftime('%Y%m%d_%H%M%S')}"
            
            # メモリ節約のため、古いキャッシュデータを削除（2日以上経過したデータ）
            try:
                logger.info("🧹 古いキャッシュデータを削除中...")
                self.db.delete_old_cache_data(days=2)
            except Exception as e:
                logger.warning(f"⚠️ 古いキャッシュデータ削除エラー（処理は継続）: {e}", exc_info=True)
            
            # app.configからマネージャーを取得
            with self.app.app_context():
                managers = self.app.config.get('TREND_MANAGERS')
                if not managers:
                    logger.error("❌ トレンドマネージャーが初期化されていません")
                    return
                
                # 既存のrefresh_all_trends()関数を使用
                # スケジューラー実行時（7時・13時）は強制更新（force_refresh=True）で実行
                # これにより、既存のキャッシュがあっても最新データを取得する
                from managers.trend_managers import refresh_all_trends
                logger.info("🔄 refresh_all_trends実行開始 (force_refresh=True)")
                result = refresh_all_trends(managers, force_refresh=True)
                logger.info(f"🔄 refresh_all_trends実行完了: success={result.get('success')}")
            
            # 結果をログ出力
            results = result.get('results', {})
            success_count = sum(1 for r in results.values() if r.get('success', False))
            total_count = len(results)
            failed_count = total_count - success_count
            
            # 失敗したトレンドをログに詳細出力し、エラー詳細を収集
            failed_trends = []
            failed_trends_details = []  # エラー詳細情報を格納
            for key, result_data in results.items():
                success = result_data.get('success', False)
                if not success:
                    failed_trends.append(key)
                    response = result_data.get('response', {})
                    error = result_data.get('error', 'unknown')
                    if isinstance(response, dict):
                        status = response.get('status', 'unknown')
                        data_count = len(response.get('data', []))
                    else:
                        status = 'unknown'
                        data_count = 0
                    logger.warning(f"❌ 失敗: {key} - error={error}, status={status}, data_count={data_count}")
                    
                    # エラー詳細情報を収集
                    error_detail = {
                        'source': key,  # ソース名（例: google_JP, youtube_US）
                        'error': str(error),
                        'status': str(status) if isinstance(response, dict) else 'unknown',
                    }
                    failed_trends_details.append(error_detail)
            
            if failed_trends:
                logger.warning(f"⚠️ 失敗したトレンド ({len(failed_trends)}件): {', '.join(failed_trends)}")
            
            # Stock Trendsの結果を詳細にログ出力
            for key in ['stock_JP', 'stock_US']:
                if key in results:
                    stock_result = results[key]
                    stock_response = stock_result.get('response', {})
                    stock_status = stock_response.get('status', 'unknown')
                    stock_data_count = len(stock_response.get('data', []))
                    stock_success = stock_result.get('success', False)
                    logger.info(f"📊 {key}: success={stock_success}, status={stock_status}, data_count={stock_data_count}")
            
            end_time = datetime.now(jst)
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"✅ 自動トレンド取得完了: {success_count}/{total_count} 成功")
            logger.info(f"⏱️ 実行時間: {duration:.2f}秒")
            
            # 成功したトレンドのみタイムスタンプを更新
            # refresh_all_trendsの結果キー（例：google_JP）をcache_key（例：google_trends）にマッピング
            # 注意: 1つのトレンドが複数のcache_keyに展開される場合がある（例：note→5つのcache_key、stock_JP/stock_US→2つのcache_key）
            def map_result_key_to_cache_key(result_key):
                """refresh_all_trendsの結果キーをcache_keyにマッピング"""
                if '_' not in result_key:
                    return None
                
                parts = result_key.rsplit('_', 1)
                if len(parts) != 2:
                    return None
                
                key, region = parts
                
                # 特殊なケース（国別・地域別に分かれるもの）
                if key == 'stock':
                    return f'stock_trends_{region}'
                elif key == 'book':
                    return f'book_trends_{region}'
                elif key == 'movie':
                    return f'movie_trends_{region}'
                elif key == 'appstore':
                    # App Storeは国別に分かれる
                    return f'appstore_trends_{region}'
                elif key == 'ebay':
                    # eBayは複数のカテゴリがあるが、cache_keyは統合されている
                    return 'ebay_trends'
                elif key == 'note':
                    # Noteは複数のカテゴリがあるため、全てのカテゴリのキャッシュキーを返す
                    # リストを返すことで、呼び出し側で展開できる
                    return ['note_trends_all', 'note_trends_tech', 'note_trends_business', 'note_trends_lifestyle', 'note_trends_entertainment']
                else:
                    # 通常のケース: {key}_trends
                    return f'{key}_trends'
            
            # 成功したトレンドのcache_keyを収集
            successful_cache_keys = []
            for result_key, result_data in results.items():
                if result_data.get('success', False):
                    cache_key = map_result_key_to_cache_key(result_key)
                    if cache_key:
                        # Noteの場合はリストなので展開する
                        if isinstance(cache_key, list):
                            successful_cache_keys.extend(cache_key)
                        else:
                            successful_cache_keys.append(cache_key)
                    else:
                        # マッピングに失敗した場合のログ
                        logger.warning(f"⚠️ cache_keyマッピング失敗: {result_key} → None")
            
            # デバッグ: 収集されたcache_keyをログ出力（Stock TrendsとApp Storeを確認）
            stock_keys = [k for k in successful_cache_keys if 'stock' in k]
            appstore_keys = [k for k in successful_cache_keys if 'appstore' in k]
            if stock_keys:
                logger.info(f"📊 Stock Trendsのcache_key: {', '.join(stock_keys)}")
            else:
                logger.warning(f"⚠️ Stock Trendsのcache_keyが収集されていません")
            if appstore_keys:
                logger.info(f"📊 App Storeのcache_key: {', '.join(appstore_keys)}")
            else:
                logger.warning(f"⚠️ App Storeのcache_keyが収集されていません")
            logger.debug(f"📋 収集された全cache_key ({len(successful_cache_keys)}件): {', '.join(sorted(successful_cache_keys))}")
            
            # 成功したトレンドのみタイムスタンプを更新（更新完了時刻を使用）
            timestamp_updated = False
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 成功したトレンドの更新時刻を更新します（{len(successful_cache_keys)}件）[試行 {attempt + 1}/{max_retries}]")
                    success = self.db.update_successful_trends_timestamp(successful_cache_keys, end_time)
                    if success:
                        timestamp_updated = True
                        # 注記: 更新されたcache_key数が成功したトレンド数より多い場合がある
                        # これは、1つのトレンドが複数のcache_keyに展開されるため（例：note→5つ、stock_JP/stock_US→2つ）
                        if len(successful_cache_keys) > success_count:
                            logger.info(f"✅ 成功したトレンドの更新時刻を更新しました: {len(successful_cache_keys)}件のcache_key ({success_count}件のトレンドから展開) ({end_time.strftime('%Y-%m-%d %H:%M:%S JST')})")
                        else:
                            logger.info(f"✅ 成功したトレンドの更新時刻を更新しました: {len(successful_cache_keys)}件 ({end_time.strftime('%Y-%m-%d %H:%M:%S JST')})")
                        break
                    else:
                        logger.warning(f"⚠️ 更新時刻の更新が失敗しました（戻り値がFalse）。再試行します...")
                except Exception as e:
                    logger.warning(f"⚠️ 成功したトレンドの更新時刻更新に失敗しました（試行 {attempt + 1}/{max_retries}）: {e}", exc_info=True)
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(1)  # 1秒待ってから再試行
            
            if not timestamp_updated:
                logger.error(f"❌ 成功したトレンドの更新時刻更新に失敗しました（{max_retries}回試行後）。これは重大な問題です。")
                self._send_alert(
                    "critical",
                    "タイムスタンプ更新失敗",
                    f"成功トレンドの更新時刻更新に失敗しました（{max_retries}回試行後）。",
                    {
                        "実行ID": execution_id,
                        "トリガー": self._trigger_label(trigger_source),
                        "成功数": str(success_count),
                        "総数": str(total_count),
                        "失敗数": str(failed_count),
                        "実行時間（秒）": f"{duration:.2f}",
                    },
                )

            # 実行日付を記録（各時刻のジョブが実行されたことを記録）
            now_jst = datetime.now(jst)
            today = now_jst.date()
            
            # 1時前後（0:00-2:00）の実行は1時のジョブとして記録
            if 0 <= now_jst.hour < 2:
                self.last_night_execution_time = now_jst
                logger.debug(f"📅 1時のジョブ実行時刻を記録: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")
            
            # 7時前後（6:00-8:00）の実行は7時のジョブとして記録
            if 6 <= now_jst.hour < 8:
                self.last_daily_execution_date = today
                logger.debug(f"📅 7時のジョブ実行日付を記録: {today}")
            
            # 13時前後（12:00-14:00）の実行は13時のジョブとして記録
            if 12 <= now_jst.hour < 14:
                self.last_afternoon_execution_time = now_jst
                logger.debug(f"📅 13時のジョブ実行時刻を記録: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")
            
            # 19時前後（18:00-20:00）の実行は19時のジョブとして記録
            if 18 <= now_jst.hour < 20:
                self.last_evening_execution_time = now_jst
                logger.debug(f"📅 19時のジョブ実行時刻を記録: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")
            
            # 実行履歴をデータベースに保存（簡易版）
            self._save_execution_log(execution_id, start_time, end_time, total_count, success_count, failed_count, duration)

            # 異常検出 → Discord アラート
            has_anomaly = self._check_and_alert_anomalies(
                execution_id, start_time, end_time,
                total_count, success_count, failed_count, duration, failed_trends, failed_trends_details,
            )
            
            # 常にDiscord通知を送信（成功時も失敗時も）
            self._send_execution_notification(
                execution_id, start_time, end_time,
                total_count, success_count, failed_count, duration, failed_trends_details, has_anomaly,
                trigger_source=trigger_source,
            )

            # データ保存完了後、メール自動送信を実行
            # スケジューラー実行時（深夜1時・朝7時・昼13時・夜19時）のみメール送信
            # デプロイ時や手動実行時は、明示的に指示された場合のみメール送信
            # 環境変数SKIP_EMAIL_ON_UPDATE=trueの場合はスキップ
            skip_email = os.getenv('SKIP_EMAIL_ON_UPDATE', 'false').lower() == 'true'
            if not skip_email:
                # スケジューラー実行時のみメール送信（force=Falseの場合）
                # force=Trueの場合は手動実行なので、メール送信をスキップ
                if not force:
                    self._send_trends_summary_emails()
                else:
                    logger.info("⏭️ 手動実行（force=True）のため、メール自動送信をスキップします")
            else:
                logger.info("⏭️ メール自動送信をスキップします（SKIP_EMAIL_ON_UPDATE=true）")
            
        except Exception as e:
            logger.error(f"❌ 自動トレンド取得エラー: {e}", exc_info=True)
            import traceback
            error_traceback = traceback.format_exc()
            # トレースバックの最初の数行のみを取得（Discordの文字数制限を考慮）
            traceback_lines = error_traceback.split('\n')[:10]
            traceback_summary = '\n'.join(traceback_lines)
            
            self._send_alert(
                "critical",
                "トレンド取得処理エラー",
                f"自動トレンド取得中にエラーが発生しました: {str(e)}",
                {
                    "実行ID": execution_id if 'execution_id' in locals() else "unknown",
                    "エラータイプ": type(e).__name__,
                    "エラーメッセージ": str(e),
                    "エラー発生箇所": traceback_summary,
                    "実行時間": f"{(datetime.now(jst) - start_time).total_seconds():.2f}秒" if 'start_time' in locals() else "不明",
                },
            )
            # エラーが発生してもメール送信を試みる（ただし、SKIP_EMAIL_ON_UPDATE=trueの場合はスキップ）
            skip_email = os.getenv('SKIP_EMAIL_ON_UPDATE', 'false').lower() == 'true'
            if not skip_email:
                try:
                    self._send_trends_summary_emails()
                except Exception as email_error:
                    logger.error(f"❌ メール送信エラー: {email_error}", exc_info=True)
            else:
                logger.info("⏭️ メール自動送信をスキップします（SKIP_EMAIL_ON_UPDATE=true）")
        finally:
            # 実行完了後にフラグをリセット
            self._fetching_in_progress = False
    
    
    
    def _send_trends_summary_emails(self):
        """トレンドサマリーメールを自動送信"""
        try:
            # サブスクリプション機能が無効化されている場合はスキップ
            from config.app_config import AppConfig
            if not AppConfig.ENABLE_SUBSCRIPTION_UI:
                logger.info("⏭️ サブスクリプション機能が無効化されているため、メール自動送信をスキップします")
                return
            
            if self.subscription_manager is None:
                logger.warning("📧 SubscriptionManagerが初期化されていないため、メール自動送信をスキップします")
                return
            
            logger.info("=" * 60)
            logger.info("📧 トレンドサマリーメール自動送信を開始します")
            logger.info("=" * 60)
            
            self.subscription_manager.send_trends_summary()
            
            logger.info("✅ トレンドサマリーメール自動送信完了")
        except Exception as e:
            # メール送信エラーはスケジューラー全体を止めないように、警告のみ
            logger.error("=" * 60)
            logger.error(f"⚠️ トレンドサマリーメール自動送信エラー（スケジューラーは継続）")
            logger.error(f"   エラー内容: {type(e).__name__}: {e}")
            logger.error("=" * 60)
            import traceback
            traceback.print_exc()

    def _send_alert(self, alert_type: str, title: str, message: str, details: dict | None = None) -> bool:
        """アラートを送信（Discord Webhook）"""
        if not self.alert_service:
            return False
        try:
            return self.alert_service.send_alert(alert_type, title, message, details)
        except Exception as e:
            logger.error("アラート送信エラー: %s", e, exc_info=True)
            return False

    def _check_and_alert_anomalies(
        self,
        execution_id: str,
        start_time: datetime,
        end_time: datetime,
        total_count: int,
        success_count: int,
        failed_count: int,
        duration: float,
        failed_trends: list,
        failed_trends_details: list,
    ) -> bool:
        """異常を検出して Discord アラート送信
        
        Returns:
            異常が検出された場合 True、正常終了の場合 False
        """
        if not self.alert_service or total_count <= 0:
            return False

        failure_rate = (failed_count / total_count) * 100
        has_anomaly = False

        # エラー詳細をフォーマット
        error_details_text = self._format_error_details(failed_trends_details)

        # 全失敗
        if success_count == 0:
            details = {
                "実行ID": execution_id,
                "総数": str(total_count),
                "実行時間": f"{duration / 60:.1f}分 ({duration:.2f}秒)",
                "開始時刻": start_time.strftime("%Y-%m-%d %H:%M:%S JST"),
                "終了時刻": end_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            }
            if error_details_text:
                details["エラー詳細"] = error_details_text
            self._send_alert(
                "critical",
                "全トレンド取得失敗",
                "全てのトレンド取得に失敗しました。",
                details,
            )
            return True

        # 失敗率 50% 以上
        if failure_rate >= 50:
            details = {
                "実行ID": execution_id,
                "成功": str(success_count),
                "失敗": str(failed_count),
                "総数": str(total_count),
                "失敗率": f"{failure_rate:.1f}%",
                "実行時間": f"{duration / 60:.1f}分 ({duration:.2f}秒)",
                "開始時刻": start_time.strftime("%Y-%m-%d %H:%M:%S JST"),
                "終了時刻": end_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            }
            if error_details_text:
                details["エラー詳細"] = error_details_text
            self._send_alert(
                "critical",
                "高失敗率検出",
                f"トレンド取得の失敗率が {failure_rate:.1f}% です（閾値: 50%）。",
                details,
            )
            has_anomaly = True

        # 実行時間 30 分以上
        if duration >= 1800:
            details = {
                "実行ID": execution_id,
                "実行時間": f"{duration / 60:.1f}分 ({duration:.2f}秒)",
                "開始時刻": start_time.strftime("%Y-%m-%d %H:%M:%S JST"),
                "終了時刻": end_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            }
            if error_details_text:
                details["エラー詳細"] = error_details_text
            self._send_alert(
                "warning",
                "実行時間が異常に長い",
                f"トレンド取得の実行時間が {duration / 60:.1f} 分です（閾値: 30 分）。",
                details,
            )
            has_anomaly = True
        
        return has_anomaly
    
    def _trigger_label(self, trigger_source: str) -> str:
        """トリガー元をDiscord表示用のラベルに変換"""
        labels = {
            'scheduler': 'スケジューラ(定期)',
            'api': 'API（手動/外部）',
        }
        return labels.get(trigger_source, trigger_source or '不明')
    
    def _format_error_details(self, failed_trends_details: list) -> str:
        """エラー詳細をフォーマットして文字列として返す"""
        if not failed_trends_details:
            return ""
        
        # Discordのフィールド値の最大長（1024文字）を考慮して、最初の10件まで表示
        max_items = 10
        details_lines = []
        for i, detail in enumerate(failed_trends_details[:max_items]):
            source = detail.get('source', 'unknown')
            error = detail.get('error', 'unknown')
            status = detail.get('status', 'unknown')
            details_lines.append(f"• {source}: {error} (status: {status})")
        
        if len(failed_trends_details) > max_items:
            details_lines.append(f"... 他 {len(failed_trends_details) - max_items}件")
        
        return "\n".join(details_lines)
    
    def _send_execution_notification(
        self,
        execution_id: str,
        start_time: datetime,
        end_time: datetime,
        total_count: int,
        success_count: int,
        failed_count: int,
        duration: float,
        failed_trends_details: list,
        has_anomaly: bool,
        trigger_source: str = 'scheduler',
    ) -> None:
        """スケジューラ実行結果をDiscord通知（成功時も失敗時も）"""
        if not self.alert_service:
            return
        
        duration_min = duration / 60
        
        # 失敗率を計算
        failure_rate = (failed_count / total_count) * 100 if total_count > 0 else 0
        
        # アラートタイプを決定
        if has_anomaly:
            alert_type = "warning" if failed_count > 0 else "warning"
        elif failed_count == 0:
            alert_type = "success"
        else:
            alert_type = "warning"  # 一部失敗があるが異常ではない場合
        
        # タイトルとメッセージを構築
        if failed_count == 0:
            title = "✅ トレンド取得正常終了"
            message = f"全てのトレンド取得が正常に完了しました。"
        else:
            title = "⚠️ トレンド取得完了（一部失敗）"
            message = f"トレンド取得が完了しましたが、{failed_count}件の失敗があります。"
        
        # 詳細情報を構築（トリガー元を先頭付近に表示）
        details = {
            "実行ID": execution_id,
            "トリガー": self._trigger_label(trigger_source),
            "成功": f"{success_count}/{total_count}",
            "失敗": str(failed_count),
            "失敗率": f"{failure_rate:.1f}%",
            "実行時間": f"{duration_min:.1f}分 ({duration:.2f}秒)",
            "開始時刻": start_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            "終了時刻": end_time.strftime("%Y-%m-%d %H:%M:%S JST"),
        }
        
        # エラー詳細を追加
        if failed_trends_details:
            error_details_text = self._format_error_details(failed_trends_details)
            if error_details_text:
                details["エラー詳細"] = error_details_text
        
        self._send_alert(
            alert_type,
            title,
            message,
            details,
        )

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
        """スケジューラー実行履歴をデータベースに保存（メソッドが存在しない場合はスキップ）"""
        try:
            # save_scheduler_execution_logメソッドが存在するかチェック
            if hasattr(self.db, 'save_scheduler_execution_log'):
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
            else:
                # メソッドが存在しない場合はログのみ出力
                logger.debug(f"📝 実行履歴: {execution_id} - {successful_platforms}/{total_platforms} 成功, 実行時間: {execution_time:.2f}秒")
            
        except Exception as e:
            logger.warning(f"⚠️ 実行履歴保存エラー（スケジューラーは継続）: {e}")
    
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
