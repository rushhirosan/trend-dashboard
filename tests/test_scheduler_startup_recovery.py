"""起動時補完（OOM ループ防止）のテスト。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytz

from services.scheduler.scheduler_manager import TrendsScheduler


def _make_scheduler(db=None):
    app = MagicMock()
    app.config = {"TREND_MANAGERS": {}}
    sched = TrendsScheduler(app)
    sched.db = db or MagicMock()
    sched._fetching_in_progress = False
    return sched


def test_schedule_startup_skips_when_oom_recovery_recorded():
    db = MagicMock()
    db.count_oom_lock_recoveries.return_value = 2
    db.is_oom_circuit_open.return_value = False
    sched = _make_scheduler(db)
    jst = pytz.timezone("Asia/Tokyo")

    with patch.object(sched, "_retry_slot_by_key") as retry_mock:
        sched._schedule_startup_slot_recovery(["7時"], ["7am_2026-06-20"], jst)
        retry_mock.assert_not_called()


def test_schedule_startup_schedules_gap_retry_not_full_catchup():
    db = MagicMock()
    db.count_oom_lock_recoveries.return_value = 0
    db.has_slot_completed.return_value = False
    sched = _make_scheduler(db)
    jst = pytz.timezone("Asia/Tokyo")

    with patch.object(sched, "_retry_slot_by_key") as retry_mock:
        with patch("services.scheduler.scheduler_manager.threading.Timer") as timer_mock:
            with patch(
                "services.snapshot_slot_health.slot_needs_recovery",
                return_value=True,
            ):
                fixed = jst.localize(__import__("datetime").datetime(2026, 6, 20, 8, 0, 0))
                with patch("services.scheduler.scheduler_manager.datetime") as dt_mock:
                    dt_mock.now.return_value = fixed
                    sched._schedule_startup_slot_recovery(["7時"], ["7am_2026-06-20"], jst)
                timer_mock.assert_called_once()
                callback = timer_mock.call_args[0][1]
                callback()
                retry_mock.assert_called_once_with("7am_2026-06-20")


def test_retry_slot_by_key_marks_gap_retry_only_when_slot_completed():
    db = MagicMock()
    db.has_slot_completed.side_effect = lambda key: key == "7am_2026-06-20"
    db.is_oom_circuit_open.return_value = False
    sched = _make_scheduler(db)

    with patch.object(sched, "_fetch_all_trends", return_value=True):
        with patch(
            "services.snapshot_slot_health.slot_needs_recovery", return_value=True
        ):
            with patch(
                "services.snapshot_slot_health.slot_is_fully_done", return_value=True
            ):
                sched._retry_slot_by_key("7am_2026-06-20")

    db.mark_slot_completed.assert_called_once_with("gap_retry_7am_2026-06-20")


def test_retry_slot_by_key_does_not_mark_gap_retry_when_slot_incomplete():
    db = MagicMock()
    db.has_slot_completed.return_value = False
    db.is_oom_circuit_open.return_value = False
    sched = _make_scheduler(db)

    with patch.object(sched, "_fetch_all_trends", return_value=True):
        with patch(
            "services.snapshot_slot_health.slot_needs_recovery", return_value=True
        ):
            sched._retry_slot_by_key("7am_2026-06-20")

    db.mark_slot_completed.assert_not_called()


def test_schedule_startup_retries_in_window_slot_before_gap_retry():
    """07:12 起動でも 7am 未完了なら T+35 を待たずに delayed gap_retry する。"""
    db = MagicMock()
    db.count_oom_lock_recoveries.return_value = 0
    db.has_slot_completed.return_value = False
    sched = _make_scheduler(db)
    jst = pytz.timezone("Asia/Tokyo")

    with patch.object(sched, "_retry_slot_by_key") as retry_mock:
        with patch("services.scheduler.scheduler_manager.threading.Timer") as timer_mock:
            with patch(
                "services.snapshot_slot_health.slot_needs_recovery",
                return_value=True,
            ):
                fixed = jst.localize(datetime(2026, 6, 20, 7, 12, 0))
                with patch("services.scheduler.scheduler_manager.datetime") as dt_mock:
                    dt_mock.now.return_value = fixed
                    sched._schedule_startup_slot_recovery(
                        ["7時"], ["7am_2026-06-20"], jst
                    )
                timer_mock.assert_called_once()
                callback = timer_mock.call_args[0][1]
                callback()
                retry_mock.assert_called_once_with("7am_2026-06-20")


def test_try_acquire_retries_after_stale_recover_for_gap_retry():
    db = MagicMock()
    db.try_acquire_scheduler_lock_db.side_effect = [False, True]
    sched = _make_scheduler(db)

    with patch("services.scheduler.scheduler_manager.USE_DB_LOCK", True):
        with patch.object(sched, "_try_recover_stale_scheduler_lock", return_value=True):
            handle = sched._try_acquire_scheduler_lock(resume_after_recover=True)

    assert handle is not None
    assert handle[0] == "db"
    assert db.try_acquire_scheduler_lock_db.call_count == 2


def test_try_acquire_does_not_resume_after_stale_recover_by_default():
    db = MagicMock()
    db.try_acquire_scheduler_lock_db.return_value = False
    sched = _make_scheduler(db)

    with patch("services.scheduler.scheduler_manager.USE_DB_LOCK", True):
        with patch.object(sched, "_try_recover_stale_scheduler_lock", return_value=True):
            handle = sched._try_acquire_scheduler_lock()

    assert handle is None
    assert db.try_acquire_scheduler_lock_db.call_count == 1


def test_recover_stale_lock_on_startup_when_holder_dead():
    db = MagicMock()
    db.get_scheduler_lock_status.return_value = {"holder_id": "host-999999-1"}
    sched = _make_scheduler(db)

    with patch("services.scheduler.scheduler_manager.USE_DB_LOCK", True):
        with patch(
            "services.scheduler.scheduler_manager.is_local_holder_process_dead",
            return_value=True,
        ):
            with patch.object(sched, "_try_recover_stale_scheduler_lock") as recover_mock:
                sched._recover_stale_lock_on_startup()
                recover_mock.assert_called_once()
