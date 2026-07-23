"""cache_serving: shed 中は TrendsCache 直読み（manager 再載せなし）"""

from services.cache_serving import (
    CacheOnlyManagerProxy,
    cached_trends_result,
    resolve_manager_for_request,
)
from managers.trend_managers import ensure_trend_managers_restored


def test_resolve_prefers_real_manager():
    real = object()
    assert resolve_manager_for_request("google", {"google": real}) is real


def test_resolve_falls_back_to_cache_proxy_when_shed():
    proxy = resolve_manager_for_request("google", {})
    assert isinstance(proxy, CacheOnlyManagerProxy)
    assert proxy.manager_key == "google"


def test_cached_trends_result_shape(monkeypatch):
    monkeypatch.setattr(
        "services.cache_serving.read_cached_data",
        lambda key, *a, **k: [{"keyword": "a", "score": 1}],
    )
    result = cached_trends_result("google", region="JP")
    assert result["success"] is True
    assert result["status"] == "cached"
    assert result["source"] == "database_cache"
    assert len(result["data"]) == 1


def test_cached_trends_result_empty(monkeypatch):
    monkeypatch.setattr(
        "services.cache_serving.read_cached_data",
        lambda key, *a, **k: [],
    )
    result = cached_trends_result("nhk")
    assert result["success"] is True
    assert result["status"] == "cache_only_empty"
    assert result["data"] == []


def test_proxy_get_trends_ignores_force_refresh(monkeypatch):
    calls = []

    def fake_read(key, *a, **k):
        calls.append({"args": a, "kwargs": k})
        return [{"title": "x"}]

    monkeypatch.setattr("services.cache_serving.read_cached_data", fake_read)
    proxy = CacheOnlyManagerProxy("nhk")
    result = proxy.get_trends(limit=5, force_refresh=True)
    assert result["success"] is True
    assert result["data"][0]["title"] == "x"
    assert calls[0]["kwargs"].get("force_refresh") is None
    assert calls[0]["kwargs"].get("limit") == 5


def test_openalex_jp_uses_trending_jp_bucket(monkeypatch):
    seen = {}

    class FakeDB:
        def get_openalex_trends_from_cache(self, category="trending"):
            seen["category"] = category
            return [{"title": "jp-paper", "rank": 1}]

    monkeypatch.setattr("services.cache_serving.TrendsCache", FakeDB)
    result = cached_trends_result("openalex", category="trending", region="jp", limit=5)
    assert seen["category"] == "trending_jp"
    assert result["status"] == "cached"
    assert result["data"][0]["title"] == "jp-paper"


def test_openalex_non_jp_uses_plain_category(monkeypatch):
    seen = {}

    class FakeDB:
        def get_openalex_trends_from_cache(self, category="trending"):
            seen["category"] = category
            return [{"title": "global", "rank": 1}]

    monkeypatch.setattr("services.cache_serving.TrendsCache", FakeDB)
    result = cached_trends_result("openalex", category="ai", region=None, limit=5)
    assert seen["category"] == "ai"
    assert result["data"][0]["title"] == "global"


def test_kkj_empty_shape_matches_manager(monkeypatch):
    monkeypatch.setattr("services.cache_serving.read_cached_data", lambda key, *a, **k: None)
    result = cached_trends_result("kkj")
    assert result["success"] is True
    assert result["status"] == "cache_only_empty"
    assert result["data"] is not None
    assert result["data"]["signals"] == []
    assert result["data"]["prefecture_rankings"] == {}
    assert "period_months" in result["data"]
    assert result["data"]["as_of"] == ""


def test_kkj_hit_fills_defaults(monkeypatch):
    monkeypatch.setattr(
        "services.cache_serving.read_cached_data",
        lambda key, *a, **k: {"signals": [{"key": "ai", "count": 1}], "prefecture_rankings": {}},
    )
    result = cached_trends_result("kkj")
    assert result["status"] == "cached"
    assert "category_labels" in result["data"]
    assert "category_order" in result["data"]
    assert result["data"]["keyword_top_cases"] == {}


def test_ensure_restored_still_for_scheduler_finally(monkeypatch):
    reloaded = {"youtube": object()}
    monkeypatch.setattr(
        "managers.trend_managers.initialize_managers",
        lambda: reloaded,
    )
    config = {}
    assert ensure_trend_managers_restored(config) is reloaded
    assert config["TREND_MANAGERS"] is reloaded
