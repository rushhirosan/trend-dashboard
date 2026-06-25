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
    assert merged["region_stats"]["JP"]["success"] == 1
    assert merged["region_stats"]["US"]["success"] == 0


def test_subprocess_phase_ok():
    assert sm._subprocess_phase_ok({"success": True, "results": {"a": {}}}, False)
    assert not sm._subprocess_phase_ok({"success": False, "results": {}}, False)
    assert not sm._subprocess_phase_ok({"success": False, "results": {}, "oom_killed": True}, False)
    assert sm._subprocess_phase_ok(
        {
            "success": True,
            "results": {"a": {}},
            "oom_killed": True,
            "recovered_from_result_file": True,
        },
        False,
    )
    assert not sm._subprocess_phase_ok({"success": True, "results": {}}, True)


def test_load_refresh_subprocess_result_from_file(tmp_path):
    payload = {"success": True, "results": {"google_JP": {"success": True}}}
    result_file = tmp_path / "refresh.json"
    result_file.write_text(
        f"{sm._REFRESH_RESULT_PREFIX}{json.dumps(payload)}\n",
        encoding="utf-8",
    )
    loaded = sm._load_refresh_subprocess_result("", str(result_file))
    assert loaded["success"] is True
    assert loaded.get("recovered_from_result_file") is True
    assert "google_JP" in loaded["results"]


def test_merge_jp_chunk_results():
    chunks = [
        {"success": True, "results": {"google_JP": {"success": True}}},
        {"success": True, "results": {"youtube_JP": {"success": True}}},
    ]
    merged = sm._merge_jp_chunk_results(chunks)
    assert merged["success"] is True
    assert "google_JP" in merged["results"]
    assert "youtube_JP" in merged["results"]


def test_jp_failure_skips_us_subprocess(monkeypatch):
    jp_payload = {
        "success": False,
        "results": {"google_JP": {"success": True}},
        "region": "jp",
        "oom_killed": True,
        "error": "subprocess_exit_-9",
    }
    calls = []

    def fake_subprocess(self, region, *, low_memory_mode, timeout_seconds, jp_chunk=None, jp_chunks=None):
        calls.append((region, jp_chunk))
        if region == "jp":
            return jp_payload, False
        return {"success": True, "results": {}}, False

    monkeypatch.setattr(sm, "SCHEDULER_JP_SUBCHUNKS", 1)
    monkeypatch.setattr(sm.TrendsScheduler, "_run_refresh_region_subprocess", fake_subprocess)
    scheduler = sm.TrendsScheduler(_FakeApp())
    result, timed_out = scheduler._run_refresh_all_trends_with_job_timeout(
        low_memory_mode=True,
        job_timeout_seconds=1200,
    )
    assert timed_out is False
    assert calls == [("jp", None)]
    assert result["success"] is False
    assert result["jp_phase_failed"] is True
    assert result["us_phase_skipped"] is True
    assert "cnn_US" not in result["results"]


def test_subprocess_phase_timeouts_reserves_us_budget():
    jp_timeout, us_timeout = sm._subprocess_phase_timeouts(8, 5100)
    assert us_timeout >= 2400
    assert jp_timeout >= 600
    assert us_timeout > jp_timeout or us_timeout >= 1200


def test_us_subprocess_gets_longer_timeout_than_jp_chunks(monkeypatch):
    calls = []

    def fake_subprocess(self, region, *, low_memory_mode, timeout_seconds, jp_chunk=None, jp_chunks=None):
        calls.append((region, timeout_seconds, jp_chunk))
        return {"success": True, "results": {f"{region}_x": {"success": True}}}, False

    monkeypatch.setattr(sm, "SCHEDULER_JP_SUBCHUNKS", 8)
    monkeypatch.setattr(sm.TrendsScheduler, "_run_refresh_region_subprocess", fake_subprocess)
    monkeypatch.setattr(sm.TrendsScheduler, "_pause_between_subprocess_phases", lambda self: None)
    scheduler = sm.TrendsScheduler(_FakeApp())
    result, timed_out = scheduler._run_refresh_all_trends_with_job_timeout(
        low_memory_mode=True,
        job_timeout_seconds=5100,
    )
    assert timed_out is False
    assert result["success"] is True
    us_calls = [c for c in calls if c[0] == "us"]
    jp_calls = [c for c in calls if c[0] == "jp"]
    assert len(us_calls) == 1
    assert len(jp_calls) == 8
    assert us_calls[0][1] >= 2400
    assert all(call[1] >= 600 for call in jp_calls)


def test_shed_and_restore_parent_managers(monkeypatch):
    sentinel = {"google": object()}
    app = _FakeApp()
    app.config["TREND_MANAGERS"] = sentinel
    scheduler = sm.TrendsScheduler(app)
    reloaded = {"youtube": object()}

    monkeypatch.setattr(
        "managers.trend_managers.initialize_managers",
        lambda: reloaded,
    )
    scheduler._shed_parent_managers()
    assert app.config.get("TREND_MANAGERS") is None
    assert scheduler._ensure_parent_managers() is reloaded
    assert app.config["TREND_MANAGERS"] is reloaded


class _FakeApp:
    config = {"TREND_MANAGERS": {}}

    @contextmanager
    def app_context(self):
        yield


def test_scheduler_subprocess_phases_merges_results(monkeypatch):
    jp_payload = {"success": True, "results": {"google_JP": {"success": True}}, "region": "jp"}
    us_payload = {"success": True, "results": {"cnn_US": {"success": True}}, "region": "us"}

    def fake_subprocess(self, region, *, low_memory_mode, timeout_seconds, jp_chunk=None, jp_chunks=None):
        if region == "jp":
            return jp_payload, False
        return us_payload, False

    monkeypatch.setattr(sm, "SCHEDULER_JP_SUBCHUNKS", 1)
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


def test_jp_two_chunks_then_us(monkeypatch):
    calls = []
    jp1 = {"success": True, "results": {"google_JP": {"success": True}}, "region": "jp"}
    jp2 = {"success": True, "results": {"youtube_JP": {"success": True}}, "region": "jp"}
    us_payload = {"success": True, "results": {"cnn_US": {"success": True}}, "region": "us"}

    def fake_subprocess(self, region, *, low_memory_mode, timeout_seconds, jp_chunk=None, jp_chunks=None):
        calls.append((region, jp_chunk, jp_chunks))
        if region == "jp":
            return (jp1 if jp_chunk == 1 else jp2), False
        return us_payload, False

    monkeypatch.setattr(sm, "SCHEDULER_JP_SUBCHUNKS", 4)
    monkeypatch.setattr(sm.TrendsScheduler, "_run_refresh_region_subprocess", fake_subprocess)
    monkeypatch.setattr(sm.TrendsScheduler, "_pause_between_subprocess_phases", lambda self: None)
    scheduler = sm.TrendsScheduler(_FakeApp())
    result, timed_out = scheduler._run_refresh_all_trends_with_job_timeout(
        low_memory_mode=True,
        job_timeout_seconds=1200,
    )
    assert timed_out is False
    assert result["success"] is True
    assert calls == [
        ("jp", 1, 4),
        ("jp", 2, 4),
        ("jp", 3, 4),
        ("jp", 4, 4),
        ("us", None, None),
    ]
