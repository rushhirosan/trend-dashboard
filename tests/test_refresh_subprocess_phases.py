"""scheduler subprocess フェーズ分割（JP/US）のユニットテスト"""

import json
from contextlib import contextmanager

from services.scheduler import scheduler_manager as sm


def test_parse_refresh_subprocess_stdout():
    payload = {"success": True, "results": {"google_JP": {"success": True}}}
    stdout = f"log line\n{sm._REFRESH_RESULT_PREFIX}{json.dumps(payload)}\n"
    assert sm._parse_refresh_subprocess_stdout(stdout) == payload
    assert sm._parse_refresh_subprocess_stdout("")["success"] is False


def test_merge_phase_refresh_results():
    jp = {"success": True, "results": {"a_JP": {"success": True}}}
    us = {"success": False, "results": {"b_US": {"success": False, "error": "x"}}}
    merged = sm._merge_phase_refresh_results(jp, us)
    assert merged["success"] is False
    assert "a_JP" in merged["results"]
    assert "b_US" in merged["results"]
    assert merged["phases"]["jp"]["success"] is True


class _FakeApp:
    config = {"TREND_MANAGERS": {}}

    @contextmanager
    def app_context(self):
        yield


def test_scheduler_subprocess_phases_merges_results(monkeypatch):
    jp_payload = {"success": True, "results": {"google_JP": {"success": True}}, "region": "jp"}
    us_payload = {"success": True, "results": {"cnn_US": {"success": True}}, "region": "us"}

    def fake_subprocess(self, region, *, low_memory_mode, timeout_seconds):
        if region == "jp":
            return jp_payload, False
        return us_payload, False

    monkeypatch.setattr(sm.TrendsScheduler, "_run_refresh_region_subprocess", fake_subprocess)
    scheduler = sm.TrendsScheduler(_FakeApp())
    result, timed_out = scheduler._run_refresh_all_trends_with_job_timeout(
        low_memory_mode=True,
        job_timeout_seconds=1200,
    )
    assert timed_out is False
    assert result["success"] is True
    assert "google_JP" in result["results"]
    assert "cnn_US" in result["results"]
