"""refresh_all_trends region 引数のテスト"""

import pytest

pytest.importorskip("yfinance")

from managers import trend_managers as tm


def test_normalize_refresh_region():
    assert tm._normalize_refresh_region(None) is None
    assert tm._normalize_refresh_region("jp") == "jp"
    assert tm._normalize_refresh_region("US") == "us"
    assert tm._normalize_refresh_region("both") is None
    with pytest.raises(ValueError):
        tm._normalize_refresh_region("eu")


def test_refresh_all_trends_region_jp_only(monkeypatch):
    calls = []

    def fake_batches(tasks, call_manager, **kwargs):
        calls.append([t[0] for t in tasks])
        return {f"{t[0]}_{t[2]}": {"success": True} for t in tasks}

    monkeypatch.setattr(tm, "_execute_task_batches", fake_batches)
    monkeypatch.setattr(
        tm,
        "_build_jp_refresh_tasks",
        lambda fr, chunk_index=None, chunk_count=None: [("google", None, "JP")],
    )
    monkeypatch.setattr(tm, "_build_us_refresh_tasks", lambda m, fr: [("cnn", None, "US")])

    result = tm.refresh_all_trends({}, region="jp")
    assert result["success"] is True
    assert result["region"] == "jp"
    assert calls == [["google"]]
