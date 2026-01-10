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
        self.last_daily_execution_date = None  # 最後に7時のジョブが実行された日付（YYYY-MM-DD形式）
        self.last_afternoon_execution_time = None  # 最後に14時のジョブが実行された時刻（datetime形式）
        self._fetching_in_progress = False  # データ取得処理が実行中かどうかのフラグ
        # メール送信用のSubscriptionManagerを初期化
        try:
            self.subscription_manager = SubscriptionManager()
            logger.info("SubscriptionManager初期化完了")
        except Exception as e:
            logger.warning(f"⚠️ SubscriptionManager初期化エラー（メール自動送信は無効）: {e}")
            self.subscription_manager = None
        
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
                
                # 毎日昼14時（日本時間）に自動取得を実行
                self.scheduler.add_job(
                    func=self._fetch_all_trends,
                    trigger=CronTrigger(hour=14, minute=0, timezone=jst),
                    id='daily_trends_fetch_afternoon',
                    name='毎日昼14時（日本時間）のトレンド取得',
                    replace_existing=True,
                    misfire_grace_time=3600,  # 60分以内なら実行（14時から15時まで）
                    coalesce=True,  # 複数の遅延実行を1回にまとめる
                    max_instances=1  # 同時実行は1つのみ
                )
                
                # Amazon Best Sellersの個別スケジュール
                # 7時と14時にbooks取得
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('books'),
                    trigger=CronTrigger(hour=7, minute=0, timezone=jst),
                    id='amazon_books_fetch_7am',
                    name='Amazon Best Sellers (books) 7時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('books'),
                    trigger=CronTrigger(hour=14, minute=0, timezone=jst),
                    id='amazon_books_fetch_2pm',
                    name='Amazon Best Sellers (books) 14時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                
                # 8時と15時にelectronics取得
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('electronics'),
                    trigger=CronTrigger(hour=8, minute=0, timezone=jst),
                    id='amazon_electronics_fetch_8am',
                    name='Amazon Best Sellers (electronics) 8時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('electronics'),
                    trigger=CronTrigger(hour=15, minute=0, timezone=jst),
                    id='amazon_electronics_fetch_3pm',
                    name='Amazon Best Sellers (electronics) 15時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                
                # 9時と16時にcomputers取得
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('computers'),
                    trigger=CronTrigger(hour=9, minute=0, timezone=jst),
                    id='amazon_computers_fetch_9am',
                    name='Amazon Best Sellers (computers) 9時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                self.scheduler.add_job(
                    func=lambda: self._fetch_amazon_trends_by_category('computers'),
                    trigger=CronTrigger(hour=16, minute=0, timezone=jst),
                    id='amazon_computers_fetch_4pm',
                    name='Amazon Best Sellers (computers) 16時取得',
                    replace_existing=True,
                    misfire_grace_time=3600,
                    coalesce=True,
                    max_instances=1
                )
                
                # スケジューラーを開始
                self.scheduler.start()
                self.is_running = True
                
                logger.info("✅ スケジューラー開始完了")
                logger.info("📅 毎日朝7:00と昼14:00（日本時間）に全トレンドを自動取得します")
                logger.info("📅 Amazon Best Sellers: 7時/14時(books), 8時/15時(electronics), 9時/16時(computers)に個別取得します")
                
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
    
    def _fetch_amazon_trends_by_category(self, category):
        """Amazon Best Sellersの特定カテゴリを取得
        
        Args:
            category (str): カテゴリ ('books', 'electronics', 'computers')
        """
        try:
            logger.info(f"🔄 Amazon Best Sellers ({category}) 取得開始")
            
            with self.app.app_context():
                managers = self.app.config.get('TREND_MANAGERS')
                if not managers:
                    logger.error("❌ トレンドマネージャーが初期化されていません")
                    return
                
                amazon_manager = managers.get('amazon')
                if not amazon_manager:
                    logger.error("❌ Amazon Best Sellersマネージャーが初期化されていません")
                    return
                
                # 指定カテゴリのみ取得（force_refresh=True）
                result = amazon_manager.get_trends(category=category, limit=25, force_refresh=True)
                
                if result.get('success'):
                    data_count = len(result.get('data', []))
                    logger.info(f"✅ Amazon Best Sellers ({category}) 取得完了: {data_count}件")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.warning(f"⚠️ Amazon Best Sellers ({category}) 取得エラー: {error_msg}")
                    
        except Exception as e:
            logger.error(f"❌ Amazon Best Sellers ({category}) 取得エラー: {e}", exc_info=True)
    
    def _check_and_execute_missed_job(self, jst):
        """
        起動時に当日の7時または14時を過ぎている場合は自動実行
        （マシンが停止していた場合の補完処理）
        
        マシンが何時に再起動されても、当日の7時または14時を過ぎていれば実行する。
        ただし、既に実行済みの場合は実行しない。
        """
        try:
            now_jst = datetime.now(jst)
            today = now_jst.date()
            today_7am = now_jst.replace(hour=7, minute=0, second=0, microsecond=0)
            today_2pm = now_jst.replace(hour=14, minute=0, second=0, microsecond=0)
            
            # 7時と14時の両方をチェックし、必要に応じて1回だけ実行
            should_execute_7am = False
            should_execute_2pm = False
            
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
            
            # 当日の14時を過ぎているかチェック
            if now_jst >= today_2pm:
                # 既に実行済みかどうかをチェック（1時間以内に実行されていればスキップ）
                if self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 起動時チェック: 当日の14時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の14時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_2pm = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の14時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_2pm = True
            
            # 7時または14時のジョブが必要な場合、1回だけ実行
            if should_execute_7am or should_execute_2pm:
                if should_execute_7am and should_execute_2pm:
                    logger.info("🔄 当日の7時と14時の処理を自動実行します（マシン停止による実行漏れを補完）")
                elif should_execute_7am:
                    logger.info("🔄 当日の7時の処理を自動実行します（マシン停止による実行漏れを補完）")
                else:
                    logger.info("🔄 当日の14時の処理を自動実行します（マシン停止による実行漏れを補完）")
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
    
    def _fetch_all_trends(self, force=False):
        """全プラットフォームのトレンドを取得（既存のrefresh_all_trends()を使用）
        
        Args:
            force: Trueの場合、既に実行済みでも強制的に実行する
                   Falseの場合、スケジューラー実行時（通常の定期実行）
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
            # ただし、14時のジョブの場合は7時のチェックをスキップ
            if not force:
                # 7時前後（6:00-8:00）の実行の場合、当日の7時ジョブが既に実行済みかチェック
                if 6 <= now_jst.hour < 8 and self.last_daily_execution_date == today:
                    logger.info(f"⏰ 当日の7時のジョブは既に実行済みです（{today}）。重複実行をスキップします。")
                    self._fetching_in_progress = False
                    return
                # 14時前後（13:00-15:00）の実行の場合、1時間以内に14時ジョブが実行済みかチェック
                if 13 <= now_jst.hour < 15 and self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の14時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._fetching_in_progress = False
                        return
            
            logger.info("🔄 自動トレンド取得開始")
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
                # スケジューラー実行時（7時・14時）は強制更新（force_refresh=True）で実行
                # これにより、既存のキャッシュがあっても最新データを取得する
                # Amazon Best Sellersは別スケジュールで取得するため除外
                from managers.trend_managers import refresh_all_trends_except_amazon
                logger.info("🔄 refresh_all_trends実行開始 (force_refresh=True, Amazon除外)")
                result = refresh_all_trends_except_amazon(managers, force_refresh=True)
                logger.info(f"🔄 refresh_all_trends実行完了: success={result.get('success')}")
            
            # 結果をログ出力
            results = result.get('results', {})
            success_count = sum(1 for r in results.values() if r.get('success', False))
            total_count = len(results)
            failed_count = total_count - success_count
            
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
            
            # 全トレンド取得完了後、すべてのトレンドに対して同じ更新時刻を設定
            # これにより、更新時刻のバラつきを防ぐ
            try:
                logger.info(f"🔄 全トレンドの更新時刻を統一します（開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                self.db.update_all_trends_timestamp(start_time)
            except Exception as e:
                logger.warning(f"⚠️ 全トレンド更新時刻の統一に失敗しました（処理は継続）: {e}", exc_info=True)
            
            # 実行日付を記録（7時のジョブが実行されたことを記録）
            now_jst = datetime.now(jst)
            today = now_jst.date()
            
            # 7時前後（6:00-8:00）の実行は7時のジョブとして記録
            if 6 <= now_jst.hour < 8:
                self.last_daily_execution_date = today
                logger.debug(f"📅 7時のジョブ実行日付を記録: {today}")
            
            # 14時前後（13:00-15:00）の実行は14時のジョブとして記録
            if 13 <= now_jst.hour < 15:
                self.last_afternoon_execution_time = now_jst
                logger.debug(f"📅 14時のジョブ実行時刻を記録: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")
            
            # 実行履歴をデータベースに保存（簡易版）
            self._save_execution_log(execution_id, start_time, end_time, total_count, success_count, failed_count, duration)
            
            # データ保存完了後、メール自動送信を実行
            # スケジューラー実行時（朝7時・昼14時）のみメール送信
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
