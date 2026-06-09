"""Tests for scripts/generate_daily_x_post_series.py."""

import importlib.util
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_daily_x_post_series.py"


@pytest.fixture(scope="module")
def gx():
    spec = importlib.util.spec_from_file_location("generate_daily_x_post_series", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_resp(payload: dict):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = payload
    return r


def _jp_payloads():
    return [
        {"data": [{"keyword": "g1"}, {"keyword": "g2"}]},
        {"data": [{"title": "yt"}]},
        {"data": [{"title": "nh"}]},
        {"data": [{"title": "wn"}]},
        {"data": [{"title": "z"}]},
        {"data": [{"title": "jp"}]},
        {"data": [{"title": "mu"}]},
        {"data": [{"title": "mv"}]},
    ]


def _us_payloads():
    return [
        {"data": [{"keyword": "ug1"}, {"keyword": "ug2"}]},
        {"data": [{"title": "uyt"}]},
        {"data": [{"title": "cnn"}]},
        {"data": [{"cve_id": "CVE-1"}]},
        {"data": [{"title": "dev"}]},
        {"data": [{"title": "thn"}]},
        {"data": [{"title": "umu"}]},
        {"data": [{"title": "umv"}]},
    ]


def _triple_flat(series: dict) -> dict:
    return {"07": dict(series), "13": dict(series), "19": dict(series)}


@pytest.mark.parametrize("force_refresh,needle", [(True, "force_refresh=true"), (False, "force_refresh=false")])
def test_build_jp_block_request_urls_include_force_refresh_flag(gx, monkeypatch, force_refresh, needle):
    payloads = _jp_payloads()
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _mk_resp(payloads[len(calls) - 1])

    monkeypatch.setattr(gx.requests, "get", fake_get)
    gx.build_jp_block("https://example.com", "2026-05-12", force_refresh=force_refresh)
    assert len(calls) == 8
    for u in calls:
        assert needle in u


@pytest.mark.parametrize("force_refresh,needle", [(True, "force_refresh=true"), (False, "force_refresh=false")])
def test_build_us_block_request_urls_include_force_refresh_flag(gx, monkeypatch, force_refresh, needle):
    payloads = _us_payloads()
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _mk_resp(payloads[len(calls) - 1])

    monkeypatch.setattr(gx.requests, "get", fake_get)
    gx.build_us_block("https://example.com", "2026-05-12", force_refresh=force_refresh)
    assert len(calls) == 8
    for u in calls:
        assert needle in u


def test_google_line_snapshot_pair_and_single(gx):
    pair = [{"t": "A"}, {"t": "B"}]
    assert gx._google_line_snapshot(pair, sep="／") == "A／B"
    single = [{"t": "Only"}]
    assert gx._google_line_snapshot(single, sep=" / ") == "Only"


def test_build_blocks_from_snapshots_rising_format(gx):
    bundle = {
        "07": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 18}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 20}],
        },
        "13": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 9}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 11}],
        },
        "19": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 2}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 3}],
        },
    }
    jp = gx.build_jp_block_from_snapshots(bundle, "2026-05-12", max_jp_x_weighted=0)
    assert "急上昇3つ" in jp
    assert "ClimberJP" in jp
    assert "① ClimberJP" in jp
    assert "② FlatJP" not in jp
    us = gx.build_us_block_from_snapshots(bundle, "2026-05-12", max_chars=0)
    assert "Today's rising 3" in us
    assert "ClimberUS" in us
    assert gx.US_LIST_LINE in us


def test_us_rising_fits_x_budget_when_article_urls_are_long(gx):
    """長い記事 URL でも ValueError にせず、件数削減またはリンク省略で 280 字以内に収める。"""
    long_url = "https://edition.cnn.com/2026/06/06/politics/example-story-with-a-very-long-path-segment/index.html"
    bundle = {
        "07": {
            "cnn_us": [{"t": "Story A", "r": 10}],
            "google_trends_us": [{"t": "Trend B", "r": 18}],
            "youtube_trends_us": [{"t": "Video C", "r": 20}],
        },
        "13": {
            "cnn_us": [{"t": "Story A", "r": 6}],
            "google_trends_us": [{"t": "Trend B", "r": 9}],
            "youtube_trends_us": [{"t": "Video C", "r": 11}],
        },
        "19": {
            "cnn_us": [{"t": "Story A", "r": 2, "u": long_url}],
            "google_trends_us": [{"t": "Trend B", "r": 3, "u": long_url}],
            "youtube_trends_us": [{"t": "Video C", "r": 4, "u": long_url}],
        },
    }
    us = gx.build_us_block_from_snapshots(
        bundle, "2026-06-06", max_chars=gx.X_FREE_CHARACTER_LIMIT
    )
    assert "Rising" in us
    assert gx._us_body_x_weight(us) <= gx.X_FREE_CHARACTER_LIMIT


def test_x_budget_uses_compact_header_and_short_categories(gx):
    bundle = {
        "07": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 18}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 20}],
        },
        "13": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 9}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 11}],
        },
        "19": {
            "google_trends_jp": [{"t": "FlatJP", "r": 1}],
            "youtube_trends_jp": [{"t": "ClimberJP", "r": 2}],
            "google_trends_us": [{"t": "FlatUS", "r": 1}],
            "youtube_trends_us": [{"t": "ClimberUS", "r": 3}],
        },
    }
    jp = gx.build_jp_block_from_snapshots(bundle, "2026-05-12")
    assert "【5/12】急上昇" in jp
    assert "（検索）" not in jp and "（動画）" not in jp
    assert gx._jp_body_x_weight(jp) <= gx.X_FREE_CHARACTER_LIMIT
    us = gx.build_us_block_from_snapshots(bundle, "2026-05-12")
    assert "Rising" in us
    assert gx._us_body_x_weight(us) <= gx.X_FREE_CHARACTER_LIMIT


def test_discord_copy_blocks_omit_article_urls_when_too_long(gx):
    article = "https://www3.nhk.or.jp/news/html/20260529/k100.html"
    long_url = "https://edition.cnn.com/2026/06/06/politics/example-story-with-a-very-long-path-segment/index.html"
    bundle = {
        "07": {
            "nhk_jp": [{"t": "Typhoon News", "r": 10}],
            "worldnews_jp": [{"t": "Long Headline One", "r": 12}],
            "zenn_jp": [{"t": "Long Headline Two", "r": 14}],
        },
        "13": {
            "nhk_jp": [{"t": "Typhoon News", "r": 5}],
            "worldnews_jp": [{"t": "Long Headline One", "r": 6}],
            "zenn_jp": [{"t": "Long Headline Two", "r": 7}],
        },
        "19": {
            "nhk_jp": [{"t": "Typhoon News", "r": 1, "u": article}],
            "worldnews_jp": [{"t": "Long Headline One", "r": 2, "u": long_url}],
            "zenn_jp": [{"t": "Long Headline Two", "r": 3, "u": long_url}],
        },
    }
    jp_copy, _ = gx.build_x_post_blocks_for_discord_copy(bundle, "2026-06-04")
    assert gx._jp_body_x_weight(jp_copy) <= gx.X_FREE_CHARACTER_LIMIT
    # 1件+長URLでも収まる日は URL 付きになる（件数削減優先）
    assert "①" in jp_copy


def test_build_blocks_include_article_urls_when_present(gx):
    article = "https://www3.nhk.or.jp/news/html/20260529/k100.html"
    bundle = {
        "07": {
            "nhk_jp": [{"t": "Typhoon News", "r": 10}],
            "cnn_us": [{"t": "US Story", "r": 12}],
        },
        "13": {
            "nhk_jp": [{"t": "Typhoon News", "r": 5}],
            "cnn_us": [{"t": "US Story", "r": 6}],
        },
        "19": {
            "nhk_jp": [{"t": "Typhoon News", "r": 1, "u": article}],
            "cnn_us": [{"t": "US Story", "r": 2, "u": "https://edition.cnn.com/story"}],
        },
    }
    jp = gx.build_jp_block_from_snapshots(bundle, "2026-06-04", max_jp_x_weighted=0)
    assert article in jp
    us = gx.build_us_block_from_snapshots(bundle, "2026-06-04", max_chars=0)
    assert "https://edition.cnn.com/story" in us


def test_pick_prefers_label_in_more_slots(gx):
    """3スロットに同じラベルがあるほどスコアが上がり、Google の②語目に選ばれやすい。"""
    bundle = {
        "07": {"google_trends_jp": [{"t": "RareSecond", "r": 2}, {"t": "AlwaysTop", "r": 1}]},
        "13": {"google_trends_jp": [{"t": "AlwaysTop", "r": 1}]},
        "19": {"google_trends_jp": [{"t": "AlwaysTop", "r": 1}]},
    }
    line = gx.google_line_from_slots(bundle, "google_trends_jp", sep="／")
    assert "AlwaysTop" in line
    assert line.startswith("AlwaysTop")


def test_pick_prefers_rank_jump_when_freq_equal(gx):
    bundle = {
        "07": {"google_trends_jp": [{"t": "Climber", "r": 20}, {"t": "Flat", "r": 2}]},
        "13": {"google_trends_jp": [{"t": "Climber", "r": 12}, {"t": "Flat", "r": 2}]},
        "19": {"google_trends_jp": [{"t": "Climber", "r": 3}, {"t": "Flat", "r": 2}]},
    }
    top = gx.pick_top_labels(bundle, "google_trends_jp", count=2)
    assert top[0] == "Climber"


def test_rank_jump_score_treats_missing_early_slot_as_out_of_range(gx):
    """07 未出現・13 で1位・19 で2位 → 圏外→1→2（13→19 の下落で net は AI と同じ）。"""
    oor = gx._rank_out_of_range()
    assert gx.rank_jump_score({"13": 1, "19": 2}) == float((oor - 1) + (1 - 2))
    assert gx.rising_qualifies({"13": 1, "19": 2}, gx.rank_jump_score({"13": 1, "19": 2})) is False


def test_rank_jump_score_07_19_without_13_no_double_count(gx):
    assert gx.rank_jump_score({"07": 20, "19": 5}) == 15.0


def test_pick_rising_topics_excludes_peak_then_fade(gx):
    """13→19 で順位が悪化するだけのラベルは AI サマリーと同様に選ばない。"""
    bundle = {
        "07": {"google_trends_jp": [{"t": "Always", "r": 1}]},
        "13": {"google_trends_jp": [{"t": "Always", "r": 1}, {"t": "FadeAt19", "r": 1}]},
        "19": {
            "google_trends_jp": [{"t": "Always", "r": 1}, {"t": "FadeAt19", "r": 2}],
        },
    }
    picks = gx.pick_rising_topics(
        bundle,
        gx.JP_SERIES_KEYS,
        category_by_series=gx.SERIES_CATEGORY_JP,
        count=2,
    )
    labels = [p[0] for p in picks]
    assert "FadeAt19" not in labels


def test_pick_rising_topics_prefers_rank_jump_across_series(gx):
    bundle = {
        "07": {
            "google_trends_jp": [{"t": "Slow", "r": 5}],
            "zenn_jp": [{"t": "Fast", "r": 30}],
        },
        "13": {
            "google_trends_jp": [{"t": "Slow", "r": 4}],
            "zenn_jp": [{"t": "Fast", "r": 8}],
        },
        "19": {
            "google_trends_jp": [{"t": "Slow", "r": 3}],
            "zenn_jp": [{"t": "Fast", "r": 1}],
        },
    }
    picks = gx.pick_rising_topics(
        bundle,
        gx.JP_SERIES_KEYS,
        category_by_series=gx.SERIES_CATEGORY_JP,
        count=2,
    )
    assert picks[0][0] == "Fast"
    assert picks[0][1] == "IT"


def test_is_weak_rising_label_filters_pickup(gx):
    assert gx.is_weak_rising_label("Pickup")
    assert gx.is_weak_rising_label("【動画】")
    assert not gx.is_weak_rising_label("イラン船舶攻撃")


def test_compose_daily_markdown_includes_date_and_fenced_blocks(gx):
    md = gx.compose_daily_markdown("2026-05-20", "【2026-05-20】jp", "us body")
    assert "# 日次 X ツイート案 — 2026-05-20" in md
    assert "## 2026-05-20" in md
    assert "### JP — 今日の急上昇3つ" in md
    assert "【2026-05-20】jp" in md
    assert "### US — 今日の急上昇3つ（英語）" in md
    assert "us body" in md


def test_load_snapshots_daytime_slots_from_api_parses_payload(gx, monkeypatch):
    api_rows = [
        {"slot": "07", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]},
        {"slot": "01", "series_key": "google_trends_jp", "items": [{"t": "ignore", "r": 1}]},
        {"slot": "19", "series_key": "google_trends_jp", "items": [{"t": "b", "r": 1}]},
    ]

    def fake_get(url, **_kwargs):
        assert "daily-snapshots" in url
        assert "business_day=2026-05-12" in url
        return _mk_resp({"success": True, "data": api_rows})

    monkeypatch.setattr(gx.requests, "get", fake_get)
    out = gx.load_snapshots_daytime_slots_from_api("https://example.com", date(2026, 5, 12))
    assert out["07"]["google_trends_jp"][0]["t"] == "a"
    assert out["19"]["google_trends_jp"][0]["t"] == "b"
    assert "01" not in out


def test_default_business_day_evening_post_anchor(gx):
    tz = ZoneInfo("Asia/Tokyo")
    fn = gx.default_business_day_for_evening_x_post_jst
    assert fn(datetime(2026, 6, 1, 20, 10, tzinfo=tz)) == date(2026, 6, 1)
    assert fn(datetime(2026, 6, 2, 1, 45, tzinfo=tz)) == date(2026, 6, 1)
    assert fn(datetime(2026, 6, 2, 8, 0, tzinfo=tz)) == date(2026, 6, 1)
    assert fn(datetime(2026, 6, 2, 20, 10, tzinfo=tz)) == date(2026, 6, 2)


def test_load_snapshots_daytime_slots_from_api_empty_raises(gx, monkeypatch):
    def fake_get(url, **_kwargs):
        return _mk_resp({"success": True, "data": []})

    monkeypatch.setattr(gx.requests, "get", fake_get)
    with pytest.raises(ValueError, match="No trend_daily_snapshots"):
        gx.load_snapshots_daytime_slots_from_api("https://example.com", date(2026, 5, 12))


def test_load_snapshots_daytime_slots_from_api_require_slots_raises(gx, monkeypatch):
    api_rows = [
        {"slot": "07", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]},
    ]

    def fake_get(url, **_kwargs):
        return _mk_resp({"success": True, "data": api_rows})

    monkeypatch.setattr(gx.requests, "get", fake_get)
    with pytest.raises(ValueError, match="missing slot\\(s\\) 13, 19"):
        gx.load_snapshots_daytime_slots_from_api(
            "https://example.com",
            date(2026, 5, 12),
            required_slots=("07", "13", "19"),
        )


def test_load_snapshots_daytime_slots_from_api_wait_until_complete(gx, monkeypatch):
    calls = {"n": 0}
    partial = [{"slot": "07", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]}]
    complete = partial + [
        {"slot": "13", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]},
        {"slot": "19", "series_key": "google_trends_jp", "items": [{"t": "a", "r": 1}]},
    ]

    def fake_get(url, **_kwargs):
        calls["n"] += 1
        data = partial if calls["n"] == 1 else complete
        return _mk_resp({"success": True, "data": data})

    sleeps: list[int] = []

    monkeypatch.setattr(gx.requests, "get", fake_get)
    monkeypatch.setattr(gx.time, "sleep", lambda s: sleeps.append(s))
    out = gx.load_snapshots_daytime_slots_from_api(
        "https://example.com",
        date(2026, 5, 12),
        required_slots=("07", "13", "19"),
        wait_timeout_seconds=120,
        poll_interval_seconds=5,
    )
    assert out["19"]["google_trends_jp"][0]["t"] == "a"
    assert calls["n"] == 2
    assert sleeps == [5]


def test_load_snapshots_daytime_merges_slots(gx, monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            pass

        def fetchall(self):
            return [
                {
                    "slot": "07",
                    "series_key": "google_trends_jp",
                    "items": [{"t": "morning", "r": 1}],
                },
                {
                    "slot": "19",
                    "series_key": "google_trends_jp",
                    "items": [{"t": "eve", "r": 1}],
                },
            ]

    class FakeConn:
        def cursor(self, cursor_factory=None):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(gx.psycopg2, "connect", lambda url, connect_timeout=15: FakeConn())
    out = gx.load_snapshots_daytime_slots("postgresql://test/db", date(2026, 5, 12))
    assert out["07"]["google_trends_jp"][0]["t"] == "morning"
    assert out["19"]["google_trends_jp"][0]["t"] == "eve"
