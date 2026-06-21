"""cache_status 地域キー mapping のユニットテスト"""

from utils.cache_status_keys import (
    freshness_lookup_keys,
    map_refresh_result_key_to_cache_keys,
    region_refresh_stats,
    resolve_cache_status_key,
)


def test_map_refresh_result_key_regional_suffix():
    assert map_refresh_result_key_to_cache_keys("google_JP") == "google_trends_JP"
    assert map_refresh_result_key_to_cache_keys("youtube_US") == "youtube_trends_US"
    assert map_refresh_result_key_to_cache_keys("worldnews_JP") == "worldnews_trends_jp"


def test_map_refresh_result_key_special_cases():
    assert map_refresh_result_key_to_cache_keys("stock_JP") == "stock_trends_JP"
    assert map_refresh_result_key_to_cache_keys("wikipedia_US") == "wikipedia_trends_en"
    assert map_refresh_result_key_to_cache_keys("bluesky_JP") == "bluesky_trends_jp"
    note_keys = map_refresh_result_key_to_cache_keys("note_JP")
    assert isinstance(note_keys, list)
    assert "note_trends_all" in note_keys


def test_resolve_cache_status_key():
    assert resolve_cache_status_key("google_trends", region="JP") == "google_trends_JP"
    assert resolve_cache_status_key("worldnews_trends", country="us") == "worldnews_trends_us"


def test_freshness_lookup_keys_prefers_regional():
    keys = freshness_lookup_keys("google_trends", "JP")
    assert keys[0] == "google_trends_JP"
    assert "google_trends" in keys


def test_region_refresh_stats():
    results = {
        "google_JP": {"success": True},
        "qiita_JP": {"success": False},
        "cnn_US": {"success": True},
    }
    stats = region_refresh_stats(results)
    assert stats["JP"]["total"] == 2
    assert stats["JP"]["success"] == 1
    assert stats["US"]["total"] == 1
    assert stats["US"]["success"] == 1
