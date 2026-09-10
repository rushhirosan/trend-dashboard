"""cache_status 地域キー mapping のユニットテスト"""

from datetime import datetime

from utils.cache_status_keys import (
    freshness_lookup_keys,
    map_refresh_result_key_to_cache_keys,
    region_refresh_stats,
    resolve_cache_status_key,
    select_freshness_cache_info,
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


def test_freshness_lookup_keys_us_source_includes_us_suffix():
    keys = freshness_lookup_keys("cnn_trends", "US")
    assert keys[0] == "cnn_trends_US"
    assert "cnn_trends" in keys


def test_select_freshness_skips_empty_regional_stub():
    """スケジューラが作った count=0 の地域キーより、本体キーの件数・時刻を優先。"""
    status = {
        "nhk_trends_JP": {
            "last_updated": datetime(2026, 9, 10, 16, 23, 55),
            "data_count": 0,
        },
        "nhk_trends": {
            "last_updated": datetime(2026, 9, 10, 16, 5, 2),
            "data_count": 24,
        },
    }
    picked = select_freshness_cache_info(
        status, freshness_lookup_keys("nhk_trends", "JP")
    )
    assert picked is not None
    assert picked["data_count"] == 24
    assert picked["last_updated"] == datetime(2026, 9, 10, 16, 5, 2)


def test_select_freshness_prefers_newer_among_populated():
    status = {
        "google_trends_JP": {
            "last_updated": datetime(2026, 9, 10, 16, 23, 55),
            "data_count": 10,
        },
        "google_trends": {
            "last_updated": datetime(2026, 9, 10, 16, 14, 24),
            "data_count": 10,
        },
    }
    picked = select_freshness_cache_info(
        status, freshness_lookup_keys("google_trends", "JP")
    )
    assert picked is not None
    assert picked["last_updated"] == datetime(2026, 9, 10, 16, 23, 55)


def test_select_freshness_falls_back_to_stub_when_only_empty():
    status = {
        "qiita_trends_JP": {
            "last_updated": datetime(2026, 9, 10, 16, 23, 55),
            "data_count": 0,
        },
    }
    picked = select_freshness_cache_info(
        status, freshness_lookup_keys("qiita_trends", "JP")
    )
    assert picked is not None
    assert picked["data_count"] == 0


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
