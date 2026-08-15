"""trend_snapshot_service._label_from_item URL extraction."""

from services.trend_snapshot_service import _label_from_item


def test_label_from_youtube_video_id():
    item = {
        "title": "モンストニュース[8/13]TVアニメ『ブルーロック』コラボ開催決定！",
        "rank": 3,
        "video_id": "abc123XYZ",
    }
    out = _label_from_item(item, 0)
    assert out is not None
    assert out["t"].startswith("モンストニュース")
    assert out["u"] == "https://www.youtube.com/watch?v=abc123XYZ"


def test_label_from_google_search_url():
    item = {
        "keyword": "シューヤ 超 特急",
        "rank": 1,
        "google_search_url": "https://www.google.com/search?q=%E3%82%B7%E3%83%A5%E3%83%BC%E3%83%A4",
    }
    out = _label_from_item(item, 0)
    assert out is not None
    assert out["u"].startswith("https://www.google.com/search?q=")


def test_label_from_item_url():
    item = {"title": "Some Movie", "rank": 2, "item_url": "https://www.themoviedb.org/movie/1"}
    out = _label_from_item(item, 1)
    assert out is not None
    assert out["u"] == "https://www.themoviedb.org/movie/1"


def test_label_prefers_explicit_url_over_video_id():
    item = {
        "title": "Clip",
        "url": "https://example.com/clip",
        "video_id": "ignored",
    }
    out = _label_from_item(item, 0)
    assert out is not None
    assert out["u"] == "https://example.com/clip"
