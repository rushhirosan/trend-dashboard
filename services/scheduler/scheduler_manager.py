import os
import json
import logging
import socket
import threading
import time
import signal
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
try:
    import fcntl
except ImportError:
    fcntl = None  # Windows等では未使用（複数ワーカー時は二重実行の可能性あり）

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database_config import TrendsCache
from services.subscription.subscription_manager import SubscriptionManager
from utils.scheduler_lock import is_local_holder_process_dead, parse_scheduler_lock_holder
from utils.scheduler_slot_key import resolve_scheduler_slot_key, slot_key_for_datetime
from utils.shutdown_errors import is_interpreter_shutdown_error

AUTO_FETCH_TRIGGERS = frozenset({"scheduler", "gap_retry", "startup_catchup"})


def _process_identity():
    """二重実行の原因調査用: ホスト名とプロセスIDを返す"""
    try:
        host = socket.gethostname()
        # Fly.ioのホスト名は長いことがあるため先頭12文字に省略
        host_short = (host[:12] + "..") if len(host) > 12 else host
        return host_short, os.getpid()
    except Exception:
        return "unknown", os.getpid()


# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 複数ワーカー時、1プロセスのみジョブ実行するためのロック。
# 1) DB分散ロック（scheduler_lockテーブル）: 複数マシン・複数プロセス間で共有、Fly.io等で二重実行を防止
# 2) ファイルロック（フォールバック）: 同一マシン内の複数ワーカー用（DB利用不可時）
SCHEDULER_LOCK_PATH = os.environ.get("TRENDS_SCHEDULER_LOCK_PATH", "/tmp/trends_scheduler.lock")
SCHEDULER_LOCK_MINUTES = int(os.environ.get("TRENDS_SCHEDULER_LOCK_MINUTES", "30"))
# 単一インスタンス運用時は false にするとDBロックを使わずファイルロックのみで確実に1本だけ実行する
USE_DB_LOCK = os.environ.get("TRENDS_SCHEDULER_USE_DB_LOCK", "true").lower() == "true"
# 一括取得の「実行時間が長い」Discord 警告の閾値（秒）。54 ソース・低同時実行では 40 分超も起こりうる
SCHEDULER_DURATION_ALERT_SECONDS = int(os.environ.get("TRENDS_SCHEDULER_DURATION_ALERT_SECONDS", "2400"))
# 定期スケジューラ実行の低負荷モード。OOM対策は維持しつつ、同時実行数/待機秒を固定値から環境変数化
SCHEDULER_LOW_MEMORY_MODE = os.environ.get("TRENDS_SCHEDULER_LOW_MEMORY_MODE", "true").lower() == "true"
try:
    SCHEDULER_LOW_MEMORY_MAX_CONCURRENT = max(
        1, min(20, int(os.environ.get("TRENDS_SCHEDULER_LOW_MEMORY_MAX_CONCURRENT", "2")))
    )
except (TypeError, ValueError):
    SCHEDULER_LOW_MEMORY_MAX_CONCURRENT = 2
try:
    SCHEDULER_LOW_MEMORY_BATCH_DELAY_SECONDS = max(
        0.0, float(os.environ.get("TRENDS_SCHEDULER_LOW_MEMORY_BATCH_DELAY_SECONDS", "1"))
    )
except (TypeError, ValueError):
    SCHEDULER_LOW_MEMORY_BATCH_DELAY_SECONDS = 1.0
# ジョブ全体の上限（秒）。DBロック(TRENDS_SCHEDULER_LOCK_MINUTES)より短めにし、finallyでフラグ解放を保証
try:
    SCHEDULER_JOB_TIMEOUT_SECONDS = max(
        600, min(7200, int(os.environ.get("TRENDS_SCHEDULER_JOB_TIMEOUT_SECONDS", "5100")))
    )
except (TypeError, ValueError):
    SCHEDULER_JOB_TIMEOUT_SECONDS = 5100
try:
    OOM_RECOVERY_ALERT_COOLDOWN_MINUTES = max(
        5, min(1440, int(os.environ.get("TRENDS_SCHEDULER_OOM_RECOVERY_ALERT_COOLDOWN_MINUTES", "60")))
    )
except (TypeError, ValueError):
    OOM_RECOVERY_ALERT_COOLDOWN_MINUTES = 60
try:
    OOM_RECOVERY_CIRCUIT_THRESHOLD = max(
        2, min(50, int(os.environ.get("TRENDS_SCHEDULER_OOM_RECOVERY_CIRCUIT_THRESHOLD", "3")))
    )
except (TypeError, ValueError):
    OOM_RECOVERY_CIRCUIT_THRESHOLD = 3


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

    def _try_recover_stale_scheduler_lock(self, slot_key: str | None = None) -> bool:
        """OOM 等で holder プロセスが死んだまま残った DB ロックを解放する（同一ホストのみ）。"""
        if not self.db or not hasattr(self.db, "get_scheduler_lock_status"):
            return False
        try:
            lock_status = self.db.get_scheduler_lock_status()
        except Exception as e:
            logger.warning("⚠️ スケジューラーDBロック状態取得エラー（回収スキップ）: %s", e)
            return False
        if not lock_status or not lock_status.get("holder_id"):
            return False
        stale_holder = lock_status["holder_id"]
        if not is_local_holder_process_dead(stale_holder):
            return False
        parsed = parse_scheduler_lock_holder(stale_holder)
        dead_pid = parsed[1] if parsed else None
        logger.warning(
            "🔓 [OOM回復] スケジューラーDBロックが終了済みプロセスに残っています。"
            " holder=%s dead_pid=%s lock_status=%s → ロックを解放します",
            stale_holder,
            dead_pid,
            lock_status,
        )
        if not hasattr(self.db, "clear_scheduler_lock_db"):
            return False
        if not self.db.clear_scheduler_lock_db():
            return False

        recovery_slot = slot_key
        if not recovery_slot:
            try:
                jst = pytz.timezone("Asia/Tokyo")
                recovery_slot = self._resolve_scheduler_slot_key(
                    datetime.now(jst),
                    stale_holder,
                )
            except Exception:
                recovery_slot = None

        recovery_count = 0
        circuit_opened = False
        recent_deploy = self._is_recent_deploy()
        if (
            recovery_slot
            and hasattr(self.db, "record_oom_lock_recovery")
            and not recent_deploy
        ):
            recovery_count = self.db.record_oom_lock_recovery(recovery_slot)
            if (
                recovery_count >= OOM_RECOVERY_CIRCUIT_THRESHOLD
                and hasattr(self.db, "open_oom_circuit")
                and not self.db.is_oom_circuit_open(recovery_slot)
            ):
                self.db.open_oom_circuit(recovery_slot)
                circuit_opened = True
                logger.error(
                    "🛑 [OOMサーキット] slot=%s で OOM ロック回収が %s 回に達したため、"
                    "当該スロットの自動再取得を停止します",
                    recovery_slot,
                    recovery_count,
                )

        if self.alert_service:
            host_short, pid = _process_identity()
            alert_key = None
            if recovery_slot and hasattr(self.db, "oom_recovery_alert_slot_key"):
                alert_key = self.db.oom_recovery_alert_slot_key(recovery_slot)
            recently_alerted = False
            if alert_key and hasattr(self.db, "has_slot_completed_recently"):
                recently_alerted = self.db.has_slot_completed_recently(
                    alert_key,
                    window_minutes=OOM_RECOVERY_ALERT_COOLDOWN_MINUTES,
                )
            should_alert = (circuit_opened or not recently_alerted) and not recent_deploy
            if recent_deploy:
                logger.info(
                    "⏭️ 直近デプロイのため stale lock 回収 Discord 通知を抑制（deploy による worker 切替）"
                )
            elif should_alert:
                try:
                    if circuit_opened:
                        self._send_alert(
                            "critical",
                            "OOM連続 — トレンド取得を一時停止",
                            (
                                f"同一スロット({recovery_slot})で OOM によるロック回収が "
                                f"{recovery_count} 回に達しました。自動再取得を停止します。"
                                " VM メモリ増や取得負荷の見直し後、次スロットまで待つか手動で再実行してください。"
                            ),
                            {
                                "スロット": recovery_slot or "不明",
                                "回収回数": str(recovery_count),
                                "閾値": str(OOM_RECOVERY_CIRCUIT_THRESHOLD),
                                "解放した holder": stale_holder,
                                "ホスト": host_short,
                                "PID": str(pid),
                            },
                        )
                    else:
                        self._send_alert(
                            "warning",
                            "スケジューラロック回収（OOM回復）",
                            "前回のトレンド取得プロセスが異常終了したため、DBロックを解放しました。"
                            "このプロセスでは再取得せず、gap_retry または次スロットで補完します。",
                            {
                                "スロット": recovery_slot or "不明",
                                "解放した holder": stale_holder,
                                "回収回数": str(recovery_count) if recovery_count else "不明",
                                "ホスト": host_short,
                                "PID": str(pid),
                            },
                        )
                    if alert_key and hasattr(self.db, "mark_slot_completed"):
                        self.db.mark_slot_completed(alert_key)
                except Exception as e:
                    logger.warning("⚠️ ロック回収Discord送信スキップ: %s", e)
            else:
                logger.info(
                    "⏭️ OOM回収Discord通知を抑制（%s分以内に送信済み） slot=%s",
                    OOM_RECOVERY_ALERT_COOLDOWN_MINUTES,
                    recovery_slot,
                )
        return True

    def _is_oom_fetch_blocked(self, slot_key: str | None) -> bool:
        """OOM サーキットが開いているスロットは自動再取得しない。"""
        if not slot_key or not self.db or not hasattr(self.db, "is_oom_circuit_open"):
            return False
        if not self.db.is_oom_circuit_open(slot_key):
            return False
        logger.warning(
            "🛑 [OOMサーキット] slot=%s の自動再取得は停止中です（手動/API または次スロットまで待機）",
            slot_key,
        )
        return True

    def _try_acquire_scheduler_lock(self):
        """分散ロックを取得（非ブロッキング）。
        
        1) DB分散ロックを優先: 複数マシン間で二重実行を防止
        2) DB失敗時はファイルロックにフォールバック: 同一マシン内の複数ワーカー用
        
        Returns:
            ('db', holder_id) or ('file', fd): 取得成功時
            None: 取得失敗（他プロセスが実行中）
        """
        holder_id = f"{socket.gethostname()}-{os.getpid()}-{int(time.time())}"
        
        # 1) DB分散ロック（USE_DB_LOCK=true のときのみ。単一インスタンスでは false にして確実に1本動かす）
        if USE_DB_LOCK:
            try:
                if self.db and hasattr(self.db, 'try_acquire_scheduler_lock_db'):
                    if self.db.try_acquire_scheduler_lock_db(holder_id, SCHEDULER_LOCK_MINUTES):
                        logger.debug("🔒 スケジューラーDB分散ロックを取得しました")
                        return ('db', holder_id)
                    # OOM 等で holder が死んでいればロックを回収（同一呼び出しでは再取得しない）
                    if self._try_recover_stale_scheduler_lock():
                        jst = pytz.timezone("Asia/Tokyo")
                        recovery_slot = self._resolve_scheduler_slot_key(datetime.now(jst))
                        logger.info(
                            "⏭️ stale lock 回収のみ。このプロセスでは取得を再開しません（OOMループ防止） slot=%s",
                            recovery_slot,
                        )
                        return None
                    # DBロックが「他が保持中」の場合はここで終了。ファイルロックにフォールバックしない
                    lock_status = None
                    if hasattr(self.db, 'get_scheduler_lock_status'):
                        try:
                            lock_status = self.db.get_scheduler_lock_status()
                        except Exception:
                            pass
                    host_short, pid = _process_identity()
                    logger.warning(
                        "⏭️ [二重実行防止] スケジューラーDB分散ロックは他プロセスが保持中のためスキップ "
                        "host=%s pid=%s lock_status=%s",
                        host_short, pid, lock_status,
                    )
                    return None
            except Exception as e:
                logger.warning("⚠️ スケジューラーDBロック取得スキップ（フォールバック）: %s", e)
        else:
            logger.info("🔒 スケジューラー: DBロック無効（TRENDS_SCHEDULER_USE_DB_LOCK=false）。ファイルロックのみで1本実行します。")
        
        # 2) ファイルロック（同一マシン内で1本のみ。DBロック無効時またはDB障害時のフォールバック）
        if fcntl is None:
            # Windows等: ロックなしで実行（単一ワーカー推奨）
            return ('none', -1)
        try:
            fd = os.open(SCHEDULER_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.debug("🔒 スケジューラーファイルロックを取得しました（DBロック未使用）")
            return ('file', fd)
        except (BlockingIOError, OSError):
            host_short, pid = _process_identity()
            logger.warning(
                "⏭️ [二重実行防止] スケジューラーファイルロック取得失敗（他プロセスが保持中） "
                "host=%s pid=%s",
                host_short, pid,
            )
            return None
        except Exception as e:
            logger.warning("⚠️ スケジューラロック取得エラー: %s", e)
            return None

    def _release_scheduler_lock(self, lock_handle):
        """分散ロックを解放。"""
        if lock_handle is None:
            return
        lock_type, value = lock_handle[0], lock_handle[1]
        if lock_type == 'none':
            return
        if lock_type == 'db' and value:
            try:
                if self.db and hasattr(self.db, 'release_scheduler_lock_db'):
                    self.db.release_scheduler_lock_db(value)
                    logger.debug("🔓 スケジューラーDB分散ロックを解放しました")
            except Exception as e:
                logger.warning("⚠️ スケジューラーDBロック解放エラー: %s", e)
        elif lock_type == 'file' and value is not None and value >= 0 and fcntl:
            try:
                fcntl.flock(value, fcntl.LOCK_UN)
                os.close(value)
            except Exception as e:
                logger.warning("⚠️ スケジューラーファイルロック解放エラー: %s", e)

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

                try:
                    gap_retry_minute = int(os.getenv("TRENDS_SLOT_GAP_RETRY_MINUTE", "35"))
                except (TypeError, ValueError):
                    gap_retry_minute = 35
                gap_retry_minute = max(5, min(55, gap_retry_minute))
                for hour, job_id in (
                    (1, "gap_retry_1am"),
                    (7, "gap_retry_7am"),
                    (13, "gap_retry_1pm"),
                    (19, "gap_retry_7pm"),
                ):
                    self.scheduler.add_job(
                        func=self._retry_missed_slot_if_needed,
                        trigger=CronTrigger(
                            hour=hour, minute=gap_retry_minute, timezone=jst
                        ),
                        id=job_id,
                        name=f"スロット欠損リトライ ({hour:02d}:{gap_retry_minute:02d} JST)",
                        replace_existing=True,
                        misfire_grace_time=1800,
                        coalesce=True,
                        max_instances=1,
                    )
                
                # スケジューラーを開始
                self.scheduler.start()
                self.is_running = True
                
                logger.info("✅ スケジューラー開始完了")
                logger.info(
                    "📅 毎日1:00/7:00/13:00/19:00 JST に全トレンド取得。"
                    " 各スロット+%s分に欠損リトライ",
                    gap_retry_minute,
                )
                
                # 起動時の自動実行: SKIP_STARTUP_EXECUTION=false のときのみ補完を検討
                # デプロイ直後（deploy_marker が直近）の場合は補完スキップ＝クラッシュ時のみ補完
                skip_startup = os.getenv('SKIP_STARTUP_EXECUTION', 'true').lower() == 'true'
                if not skip_startup:
                    if self._is_recent_deploy():
                        logger.info(
                            "⏭️ 起動時補完をスキップします（直近にデプロイされたため。クラッシュ再起動時のみ補完します）"
                        )
                    else:
                        logger.info("🔄 起動時の自動実行を実行します（デプロイ以外の再起動と判定）")
                        self._check_and_execute_missed_job(jst)
                else:
                    logger.info("⏭️ 起動時の自動実行をスキップします（SKIP_STARTUP_EXECUTION=true）")
                
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
    
    def _is_recent_deploy(self) -> bool:
        """
        直近にデプロイされたかどうかを判定する（deploy_marker の last_deploy_at を使用）。
        True の場合は起動時補完をスキップ（デプロイによる起動とみなす）。
        """
        try:
            window_sec = int(os.getenv("DEPLOY_CATCHUP_SKIP_WINDOW_SECONDS", "300"))
            window_sec = max(60, min(600, window_sec))  # 1分〜10分にクランプ
        except (ValueError, TypeError):
            window_sec = 300
        last_deploy = self.db.get_last_deploy_timestamp() if self.db else None
        if last_deploy is None:
            return False
        now_utc = datetime.now(timezone.utc)
        if last_deploy.tzinfo is None:
            last_deploy = last_deploy.replace(tzinfo=timezone.utc)
        elapsed = (now_utc - last_deploy).total_seconds()
        return elapsed <= window_sec

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
            
            # 当日の1時を過ぎているかチェック（DBのscheduler_slot_runで他プロセスの完了済みも判定）
            if now_jst >= today_1am:
                slot_1am = self._slot_key_for_slot('1am', today)
                if self.db and hasattr(self.db, 'has_slot_completed') and self.db.has_slot_completed(slot_1am):
                    logger.info(f"⏰ 起動時チェック: 当日の1時のジョブは既に実行済みです（DB: {slot_1am}）（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                elif self.last_night_execution_time:
                    time_diff = (now_jst - self.last_night_execution_time).total_seconds()
                    if time_diff < 3600:
                        logger.info(f"⏰ 起動時チェック: 当日の1時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の1時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_1am = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の1時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_1am = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の1時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の7時を過ぎているかチェック（DBのscheduler_slot_runで他プロセスの完了済みも判定）
            if now_jst >= today_7am:
                slot_7am = self._slot_key_for_slot('7am', today)
                if self.db and hasattr(self.db, 'has_slot_completed') and self.db.has_slot_completed(slot_7am):
                    logger.info(f"⏰ 起動時チェック: 当日の7時のジョブは既に実行済みです（DB: {slot_7am}）（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                elif self.last_daily_execution_date == today:
                    logger.info(f"⏰ 起動時チェック: 当日の7時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の7時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_7am = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の7時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の13時を過ぎているかチェック（DBのscheduler_slot_runで他プロセスの完了済みも判定）
            if now_jst >= today_1pm:
                slot_1pm = self._slot_key_for_slot('1pm', today)
                if self.db and hasattr(self.db, 'has_slot_completed') and self.db.has_slot_completed(slot_1pm):
                    logger.info(f"⏰ 起動時チェック: 当日の13時のジョブは既に実行済みです（DB: {slot_1pm}）（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                elif self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:
                        logger.info(f"⏰ 起動時チェック: 当日の13時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の13時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_1pm = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の13時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_1pm = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の13時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 当日の19時を過ぎているかチェック（DBのscheduler_slot_runで他プロセスの完了済みも判定）
            if now_jst >= today_7pm:
                slot_7pm = self._slot_key_for_slot('7pm', today)
                if self.db and hasattr(self.db, 'has_slot_completed') and self.db.has_slot_completed(slot_7pm):
                    logger.info(f"⏰ 起動時チェック: 当日の19時のジョブは既に実行済みです（DB: {slot_7pm}）（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                elif self.last_evening_execution_time:
                    time_diff = (now_jst - self.last_evening_execution_time).total_seconds()
                    if time_diff < 3600:
                        logger.info(f"⏰ 起動時チェック: 当日の19時のジョブは既に実行済みです（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    else:
                        logger.info(f"⏰ 起動時チェック: 当日の19時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                        should_execute_7pm = True
                else:
                    logger.info(f"⏰ 起動時チェック: 当日の19時を過ぎています（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
                    should_execute_7pm = True
            else:
                logger.info(f"⏰ 起動時チェック: 当日の19時前です（現在: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}）")
            
            # 1時、7時、13時、または19時のジョブが必要な場合、遅延後に1回だけ実行
            # OOM防止: 起動直後はメモリ逼迫のため、2〜3分待ってから低負荷モードで補完
            if should_execute_1am or should_execute_7am or should_execute_1pm or should_execute_7pm:
                missed_times = []
                missed_slot_keys: list[str] = []
                if should_execute_1am:
                    missed_times.append("1時")
                    missed_slot_keys.append(self._slot_key_for_slot("1am", today))
                if should_execute_7am:
                    missed_times.append("7時")
                    missed_slot_keys.append(self._slot_key_for_slot("7am", today))
                if should_execute_1pm:
                    missed_times.append("13時")
                    missed_slot_keys.append(self._slot_key_for_slot("1pm", today))
                if should_execute_7pm:
                    missed_times.append("19時")
                    missed_slot_keys.append(self._slot_key_for_slot("7pm", today))
                filtered_pairs = [
                    (label, sk)
                    for label, sk in zip(missed_times, missed_slot_keys)
                    if not (
                        self.db
                        and hasattr(self.db, "is_oom_circuit_open")
                        and self.db.is_oom_circuit_open(sk)
                    )
                ]
                if len(filtered_pairs) < len(missed_slot_keys):
                    blocked = [
                        sk for sk in missed_slot_keys
                        if self.db
                        and hasattr(self.db, "is_oom_circuit_open")
                        and self.db.is_oom_circuit_open(sk)
                    ]
                    logger.warning(
                        "⏭️ 起動時補完をスキップ（OOMサーキット開放中）: %s",
                        ", ".join(blocked),
                    )
                missed_times = [label for label, _ in filtered_pairs]
                missed_slot_keys = [sk for _, sk in filtered_pairs]
                if not missed_slot_keys:
                    return
                delay_sec = int(os.getenv('TREND_STARTUP_CATCHUP_DELAY_SECONDS', '120'))
                logger.info(f"🔄 当日の{', '.join(missed_times)}の処理を{delay_sec}秒後に実行します（低負荷モード・OOM対策）")
                def _run_catchup(keys=list(missed_slot_keys)):
                    try:
                        logger.info("🔄 起動時補完: 遅延実行を開始します")
                        self._fetch_all_trends(
                            force=True,
                            low_memory_mode=True,
                            trigger_source="startup_catchup",
                            slot_key_override=keys[0] if keys else None,
                            backfill_slot_keys=keys,
                        )
                    except Exception as e:
                        logger.error(f"❌ 起動時補完エラー: {e}", exc_info=True)
                threading.Timer(delay_sec, _run_catchup).start()
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

    def _run_refresh_all_trends_with_job_timeout(self, low_memory_mode, job_timeout_seconds):
        """refresh_all_trends を別スレッドで実行し、上限超過時も呼び出し元へ制御を返す。"""
        result_holder = {}

        def _run():
            with self.app.app_context():
                from managers.trend_managers import refresh_all_trends

                managers = self.app.config.get('TREND_MANAGERS')
                if not managers:
                    result_holder['result'] = {'success': False, 'results': {}}
                    return
                if low_memory_mode:
                    logger.info(
                        "🔄 refresh_all_trends実行開始 (force_refresh=True, low_memory: max_concurrent=%s, batch_delay=%s)",
                        SCHEDULER_LOW_MEMORY_MAX_CONCURRENT,
                        SCHEDULER_LOW_MEMORY_BATCH_DELAY_SECONDS,
                    )
                    result_holder['result'] = refresh_all_trends(
                        managers,
                        force_refresh=True,
                        max_concurrent=SCHEDULER_LOW_MEMORY_MAX_CONCURRENT,
                        batch_delay_seconds=SCHEDULER_LOW_MEMORY_BATCH_DELAY_SECONDS,
                    )
                else:
                    logger.info("🔄 refresh_all_trends実行開始 (force_refresh=True)")
                    result_holder['result'] = refresh_all_trends(managers, force_refresh=True)

        job_timed_out = False
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='scheduler-refresh')
        try:
            future = executor.submit(_run)
            future.result(timeout=job_timeout_seconds)
        except FuturesTimeoutError:
            job_timed_out = True
            logger.error(
                "❌ refresh_all_trends がジョブ上限 %s 秒を超過しました",
                job_timeout_seconds,
            )
        except RuntimeError as e:
            if is_interpreter_shutdown_error(e):
                logger.warning(
                    "⏭️ refresh_all_trends: worker シャットダウン中のため中断 (%s)",
                    e,
                )
                result_holder["result"] = {
                    "success": False,
                    "results": {},
                    "worker_shutdown": True,
                }
            else:
                raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        result = result_holder.get('result') or {'success': False, 'results': {}}
        if job_timed_out:
            result = dict(result)
            result['job_timed_out'] = True
            result['success'] = False
        return result, job_timed_out
    
    def _fetch_all_trends(
        self,
        force=False,
        trigger_source='scheduler',
        low_memory_mode=False,
        slot_key_override=None,
        backfill_slot_keys=None,
    ):
        """全プラットフォームのトレンドを取得（既存のrefresh_all_trends()を使用）
        
        Args:
            force: Trueの場合、既に実行済みでも強制的に実行する
                   Falseの場合、スケジューラー実行時（通常の定期実行）
            trigger_source: 呼び出し元の識別子。'scheduler'=定期実行、'api'=API（手動/外部）
            low_memory_mode: Trueの場合、max_concurrent=1, batch_delay=5で実行（OOM対策・起動時補完用）
            slot_key_override: スナップショット保存用 slot_key（例: 7am_2026-06-12）
            backfill_slot_keys: 起動時補完など、複数スロットの snapshot バックフィル

        Returns:
            メイン処理（トレンド取得）まで到達したら True。ロック競合等でスキップしたら False。
        """
        # 定時実行（1/7/13/19時）は低負荷モードを環境変数で制御（API手動実行は従来どおり）
        if trigger_source == 'scheduler' and not force:
            low_memory_mode = SCHEDULER_LOW_MEMORY_MODE
        jst_prefetch = pytz.timezone('Asia/Tokyo')
        prefetch_slot_key = slot_key_override or self._resolve_scheduler_slot_key(
            datetime.now(jst_prefetch),
        )
        if trigger_source != 'api' and prefetch_slot_key and self._is_oom_fetch_blocked(prefetch_slot_key):
            if trigger_source == 'scheduler':
                self._send_scheduler_skip_notification(
                    trigger_source=trigger_source,
                    reason=f"OOM 連続回収により slot({prefetch_slot_key}) の自動再取得を停止しています。",
                )
            return False
        if trigger_source in AUTO_FETCH_TRIGGERS and self._is_recent_deploy():
            logger.info(
                "⏭️ 直近デプロイのため自動トレンド取得をスキップします（trigger=%s）",
                trigger_source,
            )
            if trigger_source == "scheduler":
                self._send_scheduler_skip_notification(
                    trigger_source=trigger_source,
                    reason="直近にデプロイされたため、定時取得をスキップします（次スロットまたは gap_retry で補完）。",
                )
            return False
        # 同時実行防止: 既に実行中の場合はスキップ（同一プロセス内）
        if self._fetching_in_progress:
            logger.warning("⚠️ データ取得処理が既に実行中です。重複実行をスキップします")
            self._send_scheduler_skip_notification(
                trigger_source=trigger_source,
                reason="同一プロセスで既にトレンド取得が実行中のためスキップしました。",
            )
            return False

        # 分散ロック取得（DB優先→ファイルロック、複数マシン・二重Discord通知を防ぐ）
        lock_handle = self._try_acquire_scheduler_lock()
        if lock_handle is None:
            host_short, pid = _process_identity()
            logger.warning(
                "⏭️ [二重実行防止] 他プロセス/他マシンがスケジューラを実行中のためスキップ host=%s pid=%s",
                host_short, pid,
            )
            self._send_scheduler_skip_notification(
                trigger_source=trigger_source,
                reason="他プロセス/他マシンでトレンド取得が実行中のためスキップしました。",
            )
            return False

        self._fetching_in_progress = True
        executed = False
        try:
            jst = pytz.timezone('Asia/Tokyo')
            now_jst = datetime.now(jst)
            today = now_jst.date()

            # スロット単位の二重実行防止（「完了済み」をDBで共有。成功した実行が1本になるよう、完了時のみ記録）
            slot_key = slot_key_override or self._slot_key_for_now(now_jst)
            if not force and slot_key and self.db and hasattr(self.db, 'has_slot_completed_recently'):
                if self.db.has_slot_completed_recently(slot_key, window_minutes=25):
                    logger.info("⏰ 同一スロットが既に完了済みのためスキップします（slot=%s）", slot_key)
                    self._send_scheduler_skip_notification(
                        trigger_source=trigger_source,
                        reason=f"同一スロット({slot_key})が直近に完了済みのためスキップしました。",
                    )
                    self._release_scheduler_lock(lock_handle)
                    self._fetching_in_progress = False
                    return False

            # 既に当日実行済みかチェック（重複実行を防ぐ・同一プロセス用）
            # force=Trueの場合はスキップしない
            if not force:
                # 1時前後（0:00-2:00）の実行の場合、1時間以内に1時ジョブが実行済みかチェック
                if 0 <= now_jst.hour < 2 and self.last_night_execution_time:
                    time_diff = (now_jst - self.last_night_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の1時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._send_scheduler_skip_notification(
                            trigger_source=trigger_source,
                            reason=f"当日の1時ジョブが{time_diff:.0f}秒前に実行済みのためスキップしました。",
                        )
                        self._release_scheduler_lock(lock_handle)
                        self._fetching_in_progress = False
                        return False
                # 7時前後（6:00-8:00）の実行の場合、当日の7時ジョブが既に実行済みかチェック
                if 6 <= now_jst.hour < 8 and self.last_daily_execution_date == today:
                    logger.info(f"⏰ 当日の7時のジョブは既に実行済みです（{today}）。重複実行をスキップします。")
                    self._send_scheduler_skip_notification(
                        trigger_source=trigger_source,
                        reason=f"当日の7時ジョブが実行済み（{today}）のためスキップしました。",
                    )
                    self._release_scheduler_lock(lock_handle)
                    self._fetching_in_progress = False
                    return False
                # 13時前後（12:00-14:00）の実行の場合、1時間以内に13時ジョブが実行済みかチェック
                if 12 <= now_jst.hour < 14 and self.last_afternoon_execution_time:
                    time_diff = (now_jst - self.last_afternoon_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の13時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._send_scheduler_skip_notification(
                            trigger_source=trigger_source,
                            reason=f"当日の13時ジョブが{time_diff:.0f}秒前に実行済みのためスキップしました。",
                        )
                        self._release_scheduler_lock(lock_handle)
                        self._fetching_in_progress = False
                        return False
                # 19時前後（18:00-20:00）の実行の場合、1時間以内に19時ジョブが実行済みかチェック
                if 18 <= now_jst.hour < 20 and self.last_evening_execution_time:
                    time_diff = (now_jst - self.last_evening_execution_time).total_seconds()
                    if time_diff < 3600:  # 1時間以内
                        logger.info(f"⏰ 当日の19時のジョブは既に実行済みです（{time_diff:.0f}秒前）。重複実行をスキップします。")
                        self._send_scheduler_skip_notification(
                            trigger_source=trigger_source,
                            reason=f"当日の19時ジョブが{time_diff:.0f}秒前に実行済みのためスキップしました。",
                        )
                        self._release_scheduler_lock(lock_handle)
                        self._fetching_in_progress = False
                        return False
            
            executed = True
            logger.info("🔄 自動トレンド取得開始 [trigger=%s]", trigger_source)
            # 終了時刻ではなく「開始時」の slot_key で business_day / slot を確定（長時間バッチでもずれない）
            snapshot_slot_key = slot_key
            start_time = datetime.now(jst)
            # 同一秒で複数実行された場合にアラートで区別できるようミリ秒・プロセスIDを含める
            host_short, pid = _process_identity()
            execution_id = f"scheduler_{start_time.strftime('%Y%m%d_%H%M%S')}_{start_time.microsecond // 1000:03d}_p{pid}"

            # 長時間バッチの途中で OOM 等すると「完了」Discordが届かない。任意で開始時に1通送り状態を可視化（課金なし・既定オフ）
            if (
                trigger_source == "scheduler"
                and os.getenv("DISCORD_NOTIFY_SCHEDULER_START", "").lower() in ("1", "true", "yes")
                and self.alert_service
            ):
                try:
                    self._send_alert(
                        "success",
                        "トレンド取得ジョブ開始",
                        "一括取得を開始しました。完了時は別途「正常終了」通知が届きます。",
                        {
                            "実行ID": execution_id,
                            "トリガー": self._trigger_label(trigger_source),
                            "ホスト": host_short,
                            "PID": str(pid),
                        },
                    )
                except Exception as e:
                    logger.warning("⚠️ 開始通知Discord送信スキップ: %s", e)

            # メモリ節約のため、古いキャッシュデータを削除（2日以上経過したデータ）
            try:
                logger.info("🧹 古いキャッシュデータを削除中...")
                self.db.delete_old_cache_data(days=2)
            except Exception as e:
                logger.warning(f"⚠️ 古いキャッシュデータ削除エラー（処理は継続）: {e}", exc_info=True)
            
            # app.configからマネージャーを取得し refresh_all_trends をジョブ全体タイムアウト付きで実行
            managers = self.app.config.get('TREND_MANAGERS')
            if not managers:
                logger.error("❌ トレンドマネージャーが初期化されていません")
                self._release_scheduler_lock(lock_handle)
                self._fetching_in_progress = False
                return True

            result, job_timed_out = self._run_refresh_all_trends_with_job_timeout(
                low_memory_mode=low_memory_mode,
                job_timeout_seconds=SCHEDULER_JOB_TIMEOUT_SECONDS,
            )
            logger.info(
                "🔄 refresh_all_trends実行完了: success=%s job_timed_out=%s",
                result.get('success'),
                job_timed_out,
            )
            if result.get("worker_shutdown"):
                logger.warning(
                    "⏭️ worker シャットダウンのため取得を中断（deploy/SIGTERM 想定・Discord 通知なし）"
                )
                return executed
            if job_timed_out:
                self._send_alert(
                    "critical",
                    "トレンド取得ジョブ全体タイムアウト",
                    (
                        f"一括取得が {SCHEDULER_JOB_TIMEOUT_SECONDS} 秒以内に終わりませんでした。"
                        " _fetching_in_progress は解放済みです。未完了タスクのスレッドはプロセス再起動まで残る可能性があります。"
                    ),
                    {
                        "実行ID": execution_id,
                        "トリガー": self._trigger_label(trigger_source),
                        "ジョブ上限（秒）": str(SCHEDULER_JOB_TIMEOUT_SECONDS),
                        "ホスト": host_short,
                        "PID": str(pid),
                    },
                )

            snapshot_status: dict = {}
            prior_slot_gaps: list[str] = []
            try:
                with self.app.app_context():
                    managers = self.app.config.get('TREND_MANAGERS') or managers
                    from services.snapshot_slot_health import (
                        find_missing_prior_slots,
                        parse_slot_key,
                        slot_has_snapshot,
                        write_and_verify_snapshot,
                    )

                    cap = datetime.now(jst)
                    if snapshot_slot_key:
                        snapshot_status = write_and_verify_snapshot(
                            managers,
                            self.db,
                            snapshot_slot_key,
                            trigger_source,
                            cap,
                        )
                        parsed_sk = parse_slot_key(snapshot_slot_key)
                        if parsed_sk:
                            bd, cur_slot = parsed_sk
                            prior_slot_gaps = find_missing_prior_slots(
                                self.db, bd, cur_slot
                            )
                    for sk in backfill_slot_keys or []:
                        if sk == snapshot_slot_key:
                            continue
                        parsed_bf = parse_slot_key(sk)
                        if not parsed_bf:
                            continue
                        bf_day, bf_slot = parsed_bf
                        if not slot_has_snapshot(self.db, bf_day, bf_slot):
                            write_and_verify_snapshot(
                                managers,
                                self.db,
                                sk,
                                trigger_source,
                                cap,
                            )
            except Exception as snap_exc:
                logger.warning(
                    "⚠️ トレンドスナップショット保存/検証失敗: %s",
                    snap_exc,
                    exc_info=True,
                )
            
            # 結果をログ出力
            results = result.get('results', {})
            success_count = sum(1 for r in results.values() if r.get('success', False))
            total_count = len(results)
            failed_count = total_count - success_count
            
            # 失敗したトレンドをログに詳細出力し、エラー詳細を収集
            failed_trends = []
            failed_trends_details = []
            if result.get('job_timed_out'):
                failed_trends_details.append({
                    'source': '_job',
                    'error': f'job_timeout after {SCHEDULER_JOB_TIMEOUT_SECONDS}s',
                    'status': 'timeout',
                })
            for key, result_data in results.items():
                success = result_data.get('success', False)
                if not success:
                    failed_trends.append(key)
                    response = result_data.get('response', {})
                    # マネージャーが response 内に error を返す場合があるため、両方参照する
                    error = (response.get('error') if isinstance(response, dict) else None) or result_data.get('error', 'unknown')
                    if isinstance(response, dict):
                        status = response.get('status', 'unknown')
                        data_count = len(response.get('data', []))
                    else:
                        status = 'unknown'
                        data_count = 0
                    logger.warning(f"❌ 失敗: {key} - error={error}, status={status}, data_count={data_count}")

                    # ログ検索・再発分析用にレスポンス主要キーを JSON で1行記録（全文・切り詰めなし）
                    if isinstance(response, dict):
                        log_excerpt = {
                            k: response[k]
                            for k in ("error", "status", "source", "message", "detail")
                            if k in response and response[k] is not None
                        }
                        try:
                            logger.warning(
                                "❌ 失敗(レスポンス抜粋JSON): %s %s",
                                key,
                                json.dumps(log_excerpt, ensure_ascii=False, default=str),
                            )
                        except Exception:
                            logger.warning("❌ 失敗(レスポンス抜粋JSON): %s シリアライズ不可", key)
                    
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
                elif key == 'wikipedia':
                    # Wikipediaは言語別: JP→ja, US→en（サービス側のcache_keyと一致させる）
                    return f'wikipedia_trends_{"ja" if region == "JP" else "en"}'
                elif key == 'music':
                    # Spotifyは地域別: music_trends_JP / music_trends_US
                    return f'music_trends_{region}'
                elif key == 'bluesky':
                    # Bluesky: JP=日本語投稿(bluesky_trends_jp)、US=言語制限なし(bluesky_trends)
                    return 'bluesky_trends_jp' if region == 'JP' else 'bluesky_trends'
                elif key == 'openalex':
                    # OpenAlexはカテゴリ別×地域別: trending_jp, ai_jp, ... (JP) / trending, ai, ... (US)
                    cats = ('trending', 'ai', 'nlp', 'climate', 'biotech', 'quantum', 'medical')
                    if region == 'JP':
                        return [f'openalex_trends_{c}_jp' for c in cats]
                    return [f'openalex_trends_{c}' for c in cats]
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
                snapshot_status=snapshot_status,
                prior_slot_gaps=prior_slot_gaps,
            )

            # スロットを「完了済み」として記録（二重実行防止。成功時のみ記録するため、クラッシュした場合は別プロセスが再実行可能）
            # 重要: トリガー時刻のスロットを記録する。完了時刻で判定すると、7:00開始のジョブが12:04に終わった場合に
            # 1pm が記録され、13:00の本来の実行が「既に完了済み」と誤判定されてスキップされる不具合を防ぐ。
            completed_slot = slot_key  # 開始時に判定したスロット（トリガー時刻ベース）
            if result.get('job_timed_out'):
                logger.warning(
                    "⏭️ ジョブ全体タイムアウトのためスロット完了は記録しません（slot=%s）",
                    completed_slot,
                )
            elif completed_slot and self.db and hasattr(self.db, 'mark_slot_completed'):
                self.db.mark_slot_completed(completed_slot)

            # 19 時スロット完了後: X 投稿案 Discord（07/13/19 スナップ確定直後）
            if (
                trigger_source == "scheduler"
                and not force
                and completed_slot
                and str(completed_slot).startswith("7pm_")
                and not result.get("job_timed_out")
            ):
                try:
                    from services.daily_x_post_notify import schedule_evening_x_post_discord_notify

                    schedule_evening_x_post_discord_notify(self.db)
                except Exception as xpost_exc:
                    logger.warning(
                        "⚠️ X 投稿案 Discord スケジュール失敗: %s",
                        xpost_exc,
                        exc_info=True,
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
            return True
            
        except Exception as e:
            if is_interpreter_shutdown_error(e):
                logger.warning(
                    "⏭️ 自動トレンド取得: worker シャットダウン中のため中断 (%s)",
                    e,
                )
                return executed
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
            return executed
        finally:
            # 分散ロックを解放し、フラグをリセット
            self._release_scheduler_lock(lock_handle)
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

        # 実行時間が閾値以上（デフォルト 40 分 = 2400 秒、TRENDS_SCHEDULER_DURATION_ALERT_SECONDS で変更可）
        if duration >= SCHEDULER_DURATION_ALERT_SECONDS:
            thr_min = SCHEDULER_DURATION_ALERT_SECONDS / 60.0
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
                f"トレンド取得の実行時間が {duration / 60:.1f} 分です（閾値: {thr_min:g} 分）。",
                details,
            )
            has_anomaly = True
        
        return has_anomaly
    
    def _retry_missed_slot_if_needed(self) -> None:
        """各スロット T+35 分: スナップショット欠損時のみ1回リトライ（通知数は完了1通のみ）。"""
        if self._fetching_in_progress:
            logger.info("⏭️ 欠損リトライ: 取得処理実行中のためスキップ")
            return
        jst = pytz.timezone("Asia/Tokyo")
        now_jst = datetime.now(jst)
        slot_key = self._slot_key_for_now(now_jst)
        if not slot_key:
            return
        retry_marker = f"gap_retry_{slot_key}"
        if self.db and hasattr(self.db, "has_slot_completed"):
            if self.db.has_slot_completed(retry_marker):
                return
        from services.snapshot_slot_health import slot_needs_recovery

        if not slot_needs_recovery(self.db, slot_key):
            return
        logger.warning("🔄 スロット欠損を検知 — リトライします: %s", slot_key)
        ran = False
        try:
            ran = self._fetch_all_trends(
                force=True,
                trigger_source="gap_retry",
                low_memory_mode=True,
                slot_key_override=slot_key,
            )
        finally:
            if (
                ran
                and self.db
                and hasattr(self.db, "mark_slot_completed")
            ):
                try:
                    self.db.mark_slot_completed(retry_marker)
                except Exception as e:
                    logger.warning("⚠️ gap_retry マーカー記録失敗: %s", e)

    def _resolve_scheduler_slot_key(self, now_jst, stale_holder_id: str | None = None) -> str | None:
        """OOM 回収・サーキット判定用。14時台などウィンドウ外でも未完了スロットを特定する。"""
        is_completed = None
        if self.db and hasattr(self.db, "has_slot_completed"):
            is_completed = self.db.has_slot_completed
        return resolve_scheduler_slot_key(
            now_jst,
            stale_holder_id,
            misfire_grace_seconds=3600,
            job_timeout_seconds=SCHEDULER_JOB_TIMEOUT_SECONDS,
            is_slot_completed=is_completed,
        )

    def _slot_key_for_now(self, now_jst) -> str | None:
        """現在時刻が属するスロットのキーを返す（例: 7am_2026-02-10）。該当しなければ None。"""
        return slot_key_for_datetime(now_jst)

    def _slot_key_for_slot(self, slot_name: str, date_obj) -> str:
        """指定スロット・日付の slot_key を返す（例: 7am_2026-03-03）。
        slot_name: '1am' | '7am' | '1pm' | '7pm'
        """
        date_str = date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)
        return f"{slot_name}_{date_str}"

    def _trigger_label(self, trigger_source: str) -> str:
        """トリガー元をDiscord表示用のラベルに変換"""
        labels = {
            'scheduler': 'スケジューラ(定期)',
            'startup_catchup': '起動時補完',
            'gap_retry': '欠損リトライ',
            'api': 'API（手動/外部）',
        }
        return labels.get(trigger_source, trigger_source or '不明')

    def _send_scheduler_skip_notification(self, trigger_source: str, reason: str) -> None:
        """スケジューラ実行がスキップされた理由をDiscord通知する。"""
        if trigger_source != 'scheduler' or not self.alert_service:
            return
        host_short, pid = _process_identity()
        self._send_alert(
            "warning",
            "⏭️ トレンド取得ジョブをスキップ",
            reason,
            {
                "トリガー": self._trigger_label(trigger_source),
                "ホスト": host_short,
                "PID": str(pid),
            },
        )
    
    def _format_error_details(self, failed_trends_details: list) -> str:
        """エラー詳細をフォーマットして文字列として返す"""
        if not failed_trends_details:
            return ""
        
        # 件数が多い実行向けに先頭のみ列挙（各行の error は切り詰めない。Discord 側でフィールド分割する）
        max_items = 10
        details_lines = []
        for i, detail in enumerate(failed_trends_details[:max_items]):
            source = detail.get('source', 'unknown')
            error = detail.get('error', 'unknown')
            status = detail.get('status', 'unknown')
            # 汎用メッセージの場合は status を前面に出す（原因切り分けのため）
            if str(error).strip().lower() in ('unknown', 'unknown error'):
                error = f"エラー詳細なし (status: {status})"
            details_lines.append(f"• {source}\n  status: {status}\n  error: {error}")
        
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
        snapshot_status: dict | None = None,
        prior_slot_gaps: list | None = None,
    ) -> None:
        """スケジューラ実行結果をDiscord通知（成功時も失敗時も）"""
        if not self.alert_service:
            return
        
        duration_min = duration / 60
        
        # 失敗率を計算
        failure_rate = (failed_count / total_count) * 100 if total_count > 0 else 0
        
        snapshot_bad = bool(
            snapshot_status
            and snapshot_status.get("scheduler_slot_key")
            and not snapshot_status.get("verified_ok")
        )
        gaps = list(prior_slot_gaps or [])
        gaps_bad = bool(gaps)

        # アラートタイプを決定
        if has_anomaly or snapshot_bad or gaps_bad:
            alert_type = "warning"
        elif failed_count == 0:
            alert_type = "success"
        else:
            alert_type = "warning"  # 一部失敗があるが異常ではない場合
        
        # トリガー表示用ラベル（通知でどの実行か判別しやすくする）
        trigger_label = self._trigger_label(trigger_source)

        # タイトルとメッセージを構築（トリガーをメッセージにも含めて一覧で分かるようにする）
        if failed_count == 0 and not snapshot_bad and not gaps_bad:
            title = "✅ トレンド取得正常終了"
            message = f"全てのトレンド取得が正常に完了しました。\nトリガー: {trigger_label}"
        elif failed_count == 0 and (snapshot_bad or gaps_bad):
            title = "⚠️ トレンド取得完了（スナップショット欠損）"
            message = (
                f"トレンド取得は完了しましたが、スナップショットに問題があります。\n"
                f"トリガー: {trigger_label}"
            )
        elif failed_count == 0:
            title = "✅ トレンド取得正常終了"
            message = f"全てのトレンド取得が正常に完了しました。\nトリガー: {trigger_label}"
        else:
            title = "⚠️ トレンド取得完了（一部失敗）"
            message = f"トレンド取得が完了しましたが、{failed_count}件の失敗があります。\nトリガー: {trigger_label}"

        # 詳細情報を構築（トリガー元を先頭付近に表示。二重実行調査用にホスト・PIDを追加）
        host_short, pid = _process_identity()
        from services.snapshot_slot_health import (
            format_prior_slot_gaps,
            format_snapshot_status_for_discord,
        )

        details = {
            "実行ID": execution_id,
            "トリガー": trigger_label,
            "ホスト": host_short,
            "プロセスID": str(pid),
            "成功": f"{success_count}/{total_count}",
            "失敗": str(failed_count),
            "失敗率": f"{failure_rate:.1f}%",
            "実行時間": f"{duration_min:.1f}分 ({duration:.2f}秒)",
            "開始時刻": start_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            "終了時刻": end_time.strftime("%Y-%m-%d %H:%M:%S JST"),
            "スナップショット": format_snapshot_status_for_discord(snapshot_status),
        }
        if gaps_bad and snapshot_status and snapshot_status.get("business_day"):
            from datetime import date as date_cls
            try:
                bd = date_cls.fromisoformat(str(snapshot_status["business_day"]))
            except ValueError:
                bd = None
            if bd:
                gap_line = format_prior_slot_gaps(gaps, bd)
                if gap_line:
                    details["前スロット欠損"] = gap_line
        
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
