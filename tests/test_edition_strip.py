"""号外帯: 版解決・隣接スロット差分の単体テスト。"""

from datetime import date, datetime, timedelta

import pytz

from services.dashboard import edition_strip as es

JST = pytz.timezone("Asia/Tokyo")


def test_resolve_current_edition_morning():
    now = JST.localize(datetime(2026, 9, 23, 8, 30))
    start, bd, slot = es.resolve_current_edition(now)
    assert slot == "07"
    assert bd == date(2026, 9, 23)
    assert start.hour == 7


def test_resolve_current_edition_before_1am_is_prev_19():
    now = JST.localize(datetime(2026, 9, 23, 0, 30))
    start, bd, slot = es.resolve_current_edition(now)
    assert slot == "19"
    assert bd == date(2026, 9, 22)
    assert start.day == 22


def test_resolve_current_edition_after_1am():
    now = JST.localize(datetime(2026, 9, 23, 2, 0))
    start, bd, slot = es.resolve_current_edition(now)
    assert slot == "01"
    # 1am on Sep 23 → business_day Sep 22
    assert bd == date(2026, 9, 22)
    assert start.hour == 1


def test_resolve_next_refresh():
    now = JST.localize(datetime(2026, 9, 23, 8, 0))
    nxt = es.resolve_next_refresh(now)
    assert nxt.hour == 13
    assert nxt.date() == date(2026, 9, 23)
    assert nxt.utcoffset() == timedelta(hours=9)
    assert nxt.isoformat().endswith("+09:00")


def test_resolve_next_refresh_after_13_is_19_not_lmt():
    """tzinfo=JST 直指定だと +09:19 → ブラウザ表示が 18:41 になる回帰を防ぐ。"""
    now = JST.localize(datetime(2026, 9, 23, 14, 0))
    nxt = es.resolve_next_refresh(now)
    assert nxt.hour == 19
    assert nxt.minute == 0
    assert nxt.utcoffset() == timedelta(hours=9)
    assert "+09:19" not in nxt.isoformat()
    assert nxt.isoformat().endswith("+09:00")


def test_previous_edition_from_07():
    bd, slot = es.previous_edition(date(2026, 9, 23), "07")
    assert bd == date(2026, 9, 22)
    assert slot == "01"


def test_previous_edition_from_13():
    bd, slot = es.previous_edition(date(2026, 9, 23), "13")
    assert bd == date(2026, 9, 23)
    assert slot == "07"


def test_build_highlights_new_and_rising():
    current = [
        {
            "slot": "07",
            "series_key": "google_jp",
            "items": [
                {"t": "Brand New Topic", "r": 1},
            ],
        },
        {
            "slot": "07",
            "series_key": "youtube_jp",
            "items": [{"t": "Climber", "r": 2}],
        },
        {
            "slot": "07",
            "series_key": "hatena_jp",
            "items": [{"t": "Quiet", "r": 1}],
        },
    ]
    previous = [
        {
            "slot": "01",
            "series_key": "google_jp",
            "items": [
                {"t": "Old Only", "r": 2},
            ],
        },
        {
            "slot": "01",
            "series_key": "youtube_jp",
            "items": [{"t": "Climber", "r": 9}],
        },
        {
            "slot": "01",
            "series_key": "hatena_jp",
            "items": [{"t": "Quiet", "r": 1}],
        },
    ]
    out = es.build_highlights(
        current,
        previous,
        current_slot="07",
        previous_slot="01",
        region="jp",
        locale="ja",
        limit=3,
    )
    kinds = {h["kind"] for h in out}
    labels = {h["label"] for h in out}
    assert "new" in kinds
    assert "Brand New Topic" in labels
    assert any(h["label"] == "Climber" and h["kind"] == "rising" for h in out)
    assert "Quiet" not in labels


def test_build_highlights_duplicate_labels_in_series():
    """同一 series 内で正規化キーが重複しても KeyError にならない（US 500 の原因だった）。"""
    current = [
        {
            "slot": "19",
            "series_key": "cnn_us",
            "items": [
                {"t": "Same Title", "r": 3},
                {"t": "Same  Title", "r": 1},  # 正規化で同一キー・より上位
                {"t": "Other", "r": 2},
            ],
        }
    ]
    previous = [
        {
            "slot": "13",
            "series_key": "cnn_us",
            "items": [{"t": "Quiet", "r": 1}],
        }
    ]
    out = es.build_highlights(
        current,
        previous,
        current_slot="19",
        previous_slot="13",
        region="us",
        locale="en",
        limit=3,
    )
    labels = {h["label"] for h in out}
    assert "Same Title" in labels or "Same  Title" in labels
    assert all(h["kind"] == "new" for h in out)


def test_series_matches_region_us():
    assert es.series_matches_region("cnn_us", "us")
    assert es.series_matches_region("wikipedia_en", "us")
    assert not es.series_matches_region("google_jp", "us")

    current = [
        {
            "slot": "13",
            "series_key": "qiita_jp",
            "items": [{"t": "Slight", "r": 3}],
        }
    ]
    previous = [
        {
            "slot": "07",
            "series_key": "qiita_jp",
            "items": [{"t": "Slight", "r": 5}],
        }
    ]
    out = es.build_highlights(
        current,
        previous,
        current_slot="13",
        previous_slot="07",
        region="jp",
    )
    assert out == []


def test_edition_label_locales():
    assert es.edition_label("07", "ja") == "7時版"
    assert es.edition_label("07", "en") == "07:00 edition"


def test_is_just_refreshed_window():
    start = JST.localize(datetime(2026, 9, 23, 7, 0))
    assert es.is_just_refreshed(start, JST.localize(datetime(2026, 9, 23, 7, 20)))
    assert not es.is_just_refreshed(start, JST.localize(datetime(2026, 9, 23, 9, 0)))


def test_build_edition_strip_payload_without_cache():
    now = JST.localize(datetime(2026, 9, 23, 7, 20))
    payload = es.build_edition_strip_payload(None, region="jp", locale="ja", now=now)
    assert payload["slot"] == "07"
    assert payload["edition_label"] == "7時版"
    assert payload["just_refreshed"] is True
    assert payload["highlights"] == []
    assert payload["has_snapshot"] is False
