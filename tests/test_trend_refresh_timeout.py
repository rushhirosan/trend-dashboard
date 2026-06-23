"""refresh_all_trends のタスク/ジョブタイムアウト"""

import time
from contextlib import contextmanager

import pytest

pytest.importorskip("yfinance")
pytest.importorskip("apscheduler")

from managers import trend_managers as tm
from services.scheduler.scheduler_manager import TrendsScheduler


def _call_manager_with_delay(key, handler, region):
    """handler に sleep 秒数を渡すテスト用 call_manager。"""
    delay = handler
    time.sleep(delay)
    return f"{key}_{region}", {"success": True, "response": {"data": [1]}}


def test_get_task_timeout_defaults(monkeypatch):
    monkeypatch.delenv("TREND_REFRESH_TASK_TIMEOUT_SECONDS", raising=False)
    assert tm._get_task_timeout_seconds() == 600.0
    assert tm._get_task_timeout_seconds(120) == 120.0


def test_execute_task_batches_marks_stalled_tasks_failed():
    tasks = [
        ("fast", 0, "JP"),
        ("slow", 35, "JP"),
    ]
    results = tm._execute_task_batches(
        tasks,
        _call_manager_with_delay,
        max_concurrent=1,
        batch_delay_seconds=0,
        task_timeout_seconds=30,
    )
    assert results["fast_JP"]["success"] is True
    assert results["slow_JP"]["success"] is False
    assert "task_timeout" in results["slow_JP"]["error"]


class _FakeApp:
    config = {"TREND_MANAGERS": {"google": object()}}

    @contextmanager
    def app_context(self):
        yield


def test_scheduler_job_timeout(monkeypatch):
    def slow_refresh(*_args, **_kwargs):
        time.sleep(5)
        return {"success": True, "results": {"done_JP": {"success": True}}}

    monkeypatch.setattr(tm, "refresh_all_trends", slow_refresh)
    scheduler = TrendsScheduler(_FakeApp())
    result, job_timed_out = scheduler._run_refresh_all_trends_with_job_timeout(
        low_memory_mode=False,
        job_timeout_seconds=1,
    )
    assert job_timed_out is True
    assert result.get("job_timed_out") is True
    assert result.get("success") is False


def test_send_scheduler_skip_notification_only_for_scheduler():
    scheduler = TrendsScheduler(_FakeApp())
    scheduler.alert_service = object()
    sent = []

    def fake_send(level, title, message, details):
        sent.append((level, title, message))

    scheduler._send_alert = fake_send
    scheduler._send_scheduler_skip_notification("scheduler", "test reason")
    assert len(sent) == 1
    assert sent[0][1] == "⏭️ トレンド取得ジョブをスキップ"

    sent.clear()
    scheduler._send_scheduler_skip_notification("api", "ignored")
    assert len(sent) == 0
