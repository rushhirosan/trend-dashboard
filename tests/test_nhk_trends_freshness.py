"""NHK: 古い記事（published_date / URL 日付）を除外する。"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from services.trends.nhk_trends import NHKTrendsManager


def _manager() -> NHKTrendsManager:
    m = NHKTrendsManager.__new__(NHKTrendsManager)
    m.db = MagicMock()
    m.service_name = "nhk"
    return m


def test_filter_fresh_drops_old_url_date():
    m = _manager()
    old = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    fresh = datetime.now().strftime("%Y%m%d")
    items = [
        {
            "title": "古い気象",
            "url": f"http://www3.nhk.or.jp/news/html/{old}/k10015200211000.html",
        },
        {
            "title": "新しい記事",
            "url": f"http://www3.nhk.or.jp/news/html/{fresh}/k10019999991000.html",
            "published_date": datetime.now().isoformat(),
        },
    ]
    out = m._filter_fresh(items, max_age_days=3)
    assert len(out) == 1
    assert out[0]["title"] == "新しい記事"


def test_filter_fresh_keeps_unknown_date():
    m = _manager()
    items = [{"title": "日付不明", "url": "https://example.com/no-date"}]
    assert m._filter_fresh(items) == items


def test_get_from_cache_applies_fresh_filter():
    m = _manager()
    old = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
    m.db.get_nhk_trends_from_cache.return_value = [
        {
            "title": "張り付き天気",
            "url": f"http://www3.nhk.or.jp/news/html/{old}/k10015200211000.html",
            "published_date": (datetime.now() - timedelta(days=20)).isoformat(),
        }
    ]
    assert m._get_from_cache() == []
