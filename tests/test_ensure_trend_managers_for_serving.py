"""ensure_trend_managers_restored: ジョブ終了後の再載せのみ（画面用ではない）"""

from managers.trend_managers import ensure_trend_managers_restored


def test_ensure_returns_existing_managers():
    existing = {"google": object()}
    config = {"TREND_MANAGERS": existing}
    assert ensure_trend_managers_restored(config) is existing


def test_ensure_does_not_reinit_explicit_empty_dict(monkeypatch):
    calls = []

    def boom():
        calls.append(1)
        return {"x": object()}

    monkeypatch.setattr("managers.trend_managers.initialize_managers", boom)
    config = {"TREND_MANAGERS": {}}
    assert ensure_trend_managers_restored(config) == {}
    assert calls == []


def test_ensure_restores_after_shed(monkeypatch):
    reloaded = {"youtube": object()}
    monkeypatch.setattr(
        "managers.trend_managers.initialize_managers",
        lambda: reloaded,
    )
    config = {}
    assert ensure_trend_managers_restored(config) is reloaded
    assert config["TREND_MANAGERS"] is reloaded
