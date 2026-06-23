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
