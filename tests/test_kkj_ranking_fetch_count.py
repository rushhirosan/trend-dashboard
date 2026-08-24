"""官公需 KKJ の低メモリ取得設定。"""

from services.trends import kkj_trends as kkj


def test_ranking_fetch_count_default(monkeypatch):
    monkeypatch.delenv("KKJ_RANKING_FETCH_COUNT", raising=False)
    assert kkj._ranking_fetch_count() == kkj.RANKING_COUNT


def test_ranking_fetch_count_env(monkeypatch):
    monkeypatch.setenv("KKJ_RANKING_FETCH_COUNT", "150")
    assert kkj._ranking_fetch_count() == 150


def test_ranking_fetch_count_clamped(monkeypatch):
    monkeypatch.setenv("KKJ_RANKING_FETCH_COUNT", "9999")
    assert kkj._ranking_fetch_count() == kkj.RANKING_COUNT


def test_fetch_trends_deadline_returns_stale_path(monkeypatch):
    times = iter([1000.0, 2000.0])
    monkeypatch.setattr(kkj.time, "monotonic", lambda: next(times, 2000.0))
    monkeypatch.setenv("KKJ_FETCH_DEADLINE_SECONDS", "60")
    mgr = kkj.KKJTrendsManager.__new__(kkj.KKJTrendsManager)
    mgr.rate_limiter = type("Limiter", (), {"wait_if_needed": lambda self: None})()
    result = mgr._fetch_trends()
    assert result["success"] is False
    assert result["error"] == "kkj_fetch_deadline"
