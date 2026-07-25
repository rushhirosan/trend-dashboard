"""Tests for scripts/generate_ai_daily_summary.py (date helper + API fetch)."""

import importlib.util
import json
import re
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_ai_daily_summary.py"
_SNAPSHOT_SERVICE = Path(__file__).resolve().parents[1] / "services" / "trend_snapshot_service.py"

_BOOK_JP_CATS = ("all", "fiction", "business", "humanities", "practical")
_BOOK_US_CATS = ("all", "fiction", "business", "biography", "science")
_OPENALEX_CATS = ("trending", "ai", "nlp", "climate", "biotech", "quantum", "medical")


@pytest.fixture(scope="module")
def gads():
    spec = importlib.util.spec_from_file_location("generate_ai_daily_summary", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _reset_daily_region(gads):
    gads.configure_daily_region("jp")
    yield
    gads.configure_daily_region("jp")


def test_default_business_day_jst_is_yesterday(gads):
    from zoneinfo import ZoneInfo

    jst = ZoneInfo("Asia/Tokyo")
    noon = datetime(2026, 5, 11, 12, 0, tzinfo=jst)
    assert gads.default_business_day_jst(noon) == date(2026, 5, 10)

    before_7 = datetime(2026, 5, 11, 6, 0, tzinfo=jst)
    assert gads.default_business_day_jst(before_7) == date(2026, 5, 10)


def test_fetch_snapshots_from_api_parses_success_payload(gads, monkeypatch):
    bd = date(2026, 5, 10)
    sample = [
        {
            "slot": "07",
            "series_key": "google_trends_jp",
            "items": [{"t": "alpha", "r": 1}],
            "captured_at": "2026-05-10T07:05:00+09:00",
        }
    ]

    def fake_get(url, **_kwargs):
        assert "business_day=2026-05-10" in url
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"success": True, "data": sample}
        return r

    monkeypatch.setattr(gads.requests, "get", fake_get)
    rows = gads.fetch_snapshots_from_api("https://example.com", bd, timeout=30)
    assert rows == sample


@pytest.mark.parametrize(
    "gha,db,cli,expected",
    [
        (False, "postgresql://x/trends-db.flycast:5432/db", False, False),
        ("true", "postgresql://x/trends-db.flycast:5432/db", False, True),
        ("true", "postgresql://h/db.internal:5432/db", False, True),
        ("true", "postgresql://localhost/db", False, False),
        ("true", "postgresql://x/trends-db.flycast/db", True, True),
        (False, "", True, True),
    ],
)
def test_use_http_snapshots_gha_fly_private_fallback(monkeypatch, gads, gha, db, cli, expected):
    if gha is False:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    else:
        monkeypatch.setenv("GITHUB_ACTIONS", gha)
    assert gads.use_http_snapshots(cli_from_api=cli, database_url=db) is expected


@pytest.mark.parametrize(
    "series_key,expected",
    [
        ("nhk_jp", "ニュース"),
        ("google_trends_jp", "検索・動画"),
        ("youtube_trends_us", "検索・動画"),
        ("wikipedia_ja", "検索・動画"),
        ("zenn_jp", "テック・開発"),
        ("jpcert_jp", "テック・開発"),
        ("hatena_jp", "テック・開発"),
        ("appstore_jp", "テック・開発"),
        ("stock_jp", "マーケット"),
        ("crypto_jp", "マーケット"),
        ("rakuten_jp", "エンタメ"),
        ("twitch_jp", "エンタメ"),
        ("bluesky_jp", "エンタメ"),
        ("ebay_us", "エンタメ"),
        ("book_jp_fiction", "エンタメ"),
        ("globenewswire_market_us", "ニュース"),
        ("estat_jp", "行政"),
        ("kkj_jp", "行政"),
    ],
)
def test_categorize_series_key(gads, series_key, expected):
    assert gads.categorize_series_key(series_key) == expected


def test_compact_rows_by_category_groups_series(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "google_trends_jp",
            "items": [{"t": "kw", "r": 1}],
            "captured_at": "2026-05-17T07:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-17T19:00:00+09:00",
        },
    ]
    payload = gads.compact_rows_by_category(rows)
    headings = [c["category"] for c in payload["categories"]]
    assert headings == list(gads.SUMMARY_CATEGORY_ORDER)
    news = next(c for c in payload["categories"] if c["category"] == "ニュース")
    search = next(c for c in payload["categories"] if c["category"] == "検索・動画")
    slot19 = next(s for s in news["slots"] if s["slot"] == "19")
    slot07 = next(s for s in search["slots"] if s["slot"] == "07")
    assert slot19["series"][0]["series_key"] == "nhk_jp"
    assert slot07["series"][0]["series_key"] == "google_trends_jp"


def test_build_rising_link_line_shows_day_evidence(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Climber", "r": 18}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Climber", "r": 2}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=1)
    assert "→" in rising[0]["rank_display"]
    assert "→" in rising[0]["link_line"]


def test_build_category_top3_prefers_intraday_jump_over_19_only_stale(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "nhk_jp",
            "items": [
                {"t": "Morning Typhoon Alert", "r": 12, "u": "https://www3.nhk.or.jp/news/a"}
            ],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
        {
            "slot": "13",
            "series_key": "nhk_jp",
            "items": [{"t": "Morning Typhoon Alert", "r": 4}],
            "captured_at": "2026-05-18T13:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "Morning Typhoon Alert", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "github_jp",
            "items": [{"t": "build-your-own-x", "r": 1, "u": "https://github.com/a/b"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    top3 = gads.build_category_top3(rows, count=3)
    news = next(b for b in top3 if b["category"] == "ニュース")
    assert news["items"][0]["label"] == "Morning Typhoon Alert"
    assert "7時" in news["items"][0]["rank_display"]
    assert "19時1位" in news["items"][0]["rank_display"]


def test_build_category_leader_prefers_day_jump(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "nhk_jp",
            "items": [{"t": "Day Story", "r": 10, "u": "https://www3.nhk.or.jp/news/a"}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "Day Story", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "github_jp",
            "items": [{"t": "build-your-own-x", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    leaders = gads.build_category_leaders_from_rows(rows)
    news = next(l for l in leaders if l["category"] == "ニュース")
    assert news["label"] == "Day Story"
    assert "7時" in news["rank_display"]


def test_build_rising_highlights_picks_rank_jump(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Climber", "r": 18}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
        {
            "slot": "13",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Climber", "r": 8}],
            "captured_at": "2026-05-18T13:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Climber", "r": 2}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "google_trends_jp",
            "items": [{"t": "Flat", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=2)
    assert len(rising) >= 1
    assert rising[0]["label"] == "Climber"
    assert rising[0]["jump"] == 16.0
    assert rising[0]["category"] == "検索・動画"
    assert "7時" in rising[0]["rank_evidence"]
    assert "YouTube" in rising[0]["link_line"]


def test_is_noisy_label_filters_procurement(gads):
    assert gads._is_noisy_label(
        "SIEMENS STAR CCM+ LICENSE RENEWAL (POP: 7/1/2026-6/30/2027)",
        "usaspending_us",
    )
    assert not gads._is_noisy_label("豊臣秀長", "wikipedia_jp")
    assert gads._is_noisy_label("に参加したレポマンガ！", "note_jp")


def test_pick_display_from_agg_prefers_longer_non_fragment(gads):
    agg = {
        "ranks": {"13": 1, "19": 1},
        "display_by_slot": {
            "13": "に参加したレポマンガ！",
            "19": "GitHubリポジトリに参加したレポマンガ！",
        },
    }
    assert gads._pick_display_from_agg(agg) == "GitHubリポジトリに参加したレポマンガ！"


def test_filter_rising_notes_drops_generic_boilerplate(gads):
    rising = [{"label": "Climber"}]
    notes = gads.filter_rising_notes(
        [{"match_label": "Climber", "note": "急上昇中のトピックです。"}],
        rising,
    )
    assert notes == []


def test_rising_note_misstates_when_already_top_at_13(gads):
    ranks = {"13": 1, "19": 1}
    assert gads._rising_note_misstates_movement("19時1位に上昇しました。", ranks)
    assert not gads._rising_note_misstates_movement(
        "13時3位から19時1位へ上昇。", {"13": 3, "19": 1}
    )


def test_describe_rank_movement_flat_after_oob(gads):
    assert gads.describe_rank_movement({"13": 1, "19": 1}) == (
        "7時圏外から13時1位へ上昇し、19時も1位を維持。"
    )
    assert gads.describe_rank_movement({"13": 3, "19": 1}) == (
        "13時3位から19時1位へ上昇。"
    )


def test_filter_rising_notes_replaces_misleading_with_mechanical(gads):
    rising = [
        {
            "label": "森鷗外「舞姫」",
            "ranks": {"13": 1, "19": 1},
        },
    ]
    notes = gads.filter_rising_notes(
        [{"match_label": "森鷗外「舞姫」", "note": "19時1位に上昇しました。"}],
        rising,
    )
    assert len(notes) == 1
    assert "13時1位" in notes[0]["note"]
    assert "19時1位に上昇" not in notes[0]["note"]


def test_teaser_rejects_misleading_late_slot_claim(gads):
    rising = [
        {
            "label": "森鷗外「舞姫」",
            "ranks": {"13": 1, "19": 1},
        },
    ]
    teaser = "「森鷗外「舞姫」」が19時1位に上昇。"
    assert not gads.teaser_is_acceptable(teaser, rising)


def test_slot_hour_label_strips_leading_zero(gads):
    assert gads._slot_hour_label("07") == "7"
    assert gads._slot_hour_label("13") == "13"
    assert gads.DAYTIME_SLOTS_ARROW == "7→13→19"


def test_format_rank_evidence_uses_compact_slot_wording(gads):
    assert gads._format_rank_evidence({"07": 8, "13": 3, "19": 1}) == (
        "7時8位 → 13時3位 → 19時1位"
    )


def test_format_rank_evidence_shows_oob_for_missing_slots(gads):
    assert gads._format_rank_evidence({"13": 1}) == (
        "7時圏外 → 13時1位 → 19時圏外"
    )


@pytest.mark.parametrize(
    "series_key,expected",
    [
        ("hatena_jp", "はてな"),
        ("wikipedia_ja", "Wikipedia"),
        ("wikipedia_jp", "Wikipedia"),
        ("jpcert_jp", "JPCERT/CC"),
        ("nhk_jp", "NHK"),
        ("ebay_us", "eBay (US)"),
        ("prtimes_hatena_jp", "PR TIMES × はてブ"),
    ],
)
def test_format_series_key_display(gads, series_key, expected):
    assert gads._format_series_key_display(series_key) == expected


def _all_snapshot_series_keys() -> frozenset[str]:
    """``trend_snapshot_service.collect_series_snapshots`` が返しうる series_key 集合。"""
    text = _SNAPSHOT_SERVICE.read_text(encoding="utf-8")
    keys = set(re.findall(r'add\(\s*"([a-z0-9_]+)"', text))
    keys.update(re.findall(r'out\.append\(\("([a-z0-9_]+)"', text))
    for cat in _BOOK_JP_CATS:
        keys.add(f"book_jp_{cat}")
    for cat in _BOOK_US_CATS:
        keys.add(f"book_us_{cat}")
    for cat in _OPENALEX_CATS:
        keys.add(f"openalex_{cat}_jp")
        keys.add(f"openalex_{cat}_us")
    return frozenset(keys)


def _provider_display_name(gads, series_key: str) -> str | None:
    """登録済みなら表示名、未登録なら None（prtimes_hatena_* は専用キー）。"""
    if series_key.startswith("prtimes_hatena"):
        return gads._PROVIDER_DISPLAY.get("prtimes_hatena")
    provider = gads._series_provider(series_key)
    return gads._PROVIDER_DISPLAY.get(provider)


def test_enumerated_keys_cover_static_add_calls_in_snapshot_service():
    text = _SNAPSHOT_SERVICE.read_text(encoding="utf-8")
    static = set(re.findall(r'add\(\s*"([a-z0-9_]+)"', text))
    static |= set(re.findall(r'out\.append\(\("([a-z0-9_]+)"', text))
    enumerated = _all_snapshot_series_keys()
    missing = static - enumerated
    assert not missing, (
        "Update _all_snapshot_series_keys() for new snapshot series_key patterns: "
        + ", ".join(sorted(missing))
    )


def test_all_snapshot_series_keys_have_provider_display_names(gads):
    unmapped: list[str] = []
    for key in sorted(_all_snapshot_series_keys()):
        if _provider_display_name(gads, key) is None:
            unmapped.append(f"{key} → provider={gads._series_provider(key)!r}")
    assert not unmapped, (
        "Add _PROVIDER_DISPLAY entries in generate_ai_daily_summary.py for:\n  "
        + "\n  ".join(unmapped)
    )


def test_all_snapshot_series_keys_avoid_raw_key_in_display(gads):
    """link_line に series_key 生文字列（hatena_jp 等）が残らない。"""
    bad: list[str] = []
    for key in sorted(_all_snapshot_series_keys()):
        display = gads._format_series_key_display(key)
        base = display.removesuffix(" (US)").removesuffix(" (EN)")
        if key in display or base == key:
            bad.append(f"{key!r} → {display!r}")
    assert not bad, "Display names should not echo raw series_key:\n  " + "\n  ".join(bad)


def test_rank_jump_score_penalizes_decline(gads):
    assert gads._rank_jump_score({"13": 1, "19": 5}) == 6.0
    assert gads._rank_jump_score({"13": 5, "19": 1}) == 10.0


def test_rising_qualifies_excludes_peak_then_fade(gads):
    assert not gads._rising_qualifies({"13": 1, "19": 5}, 6.0)
    assert gads._rising_qualifies({"13": 5, "19": 1}, 10.0)


def test_build_rising_excludes_single_slot_and_fade(gads):
    rows = [
        {
            "slot": "13",
            "series_key": "podcast_us",
            "items": [{"t": "Only Afternoon", "r": 1}],
            "captured_at": "2026-06-01T13:00:00+09:00",
        },
        {
            "slot": "13",
            "series_key": "zenn_jp",
            "items": [{"t": "Fade Article", "r": 1}],
            "captured_at": "2026-06-01T13:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "zenn_jp",
            "items": [{"t": "Fade Article", "r": 5}],
            "captured_at": "2026-06-01T19:00:00+09:00",
        },
        {
            "slot": "13",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Real Rise", "r": 8}],
            "captured_at": "2026-06-01T13:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Real Rise", "r": 2}],
            "captured_at": "2026-06-01T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    labels = [r["label"] for r in rising]
    assert "Only Afternoon" not in labels
    assert "Fade Article" not in labels
    assert "Real Rise" in labels
    assert "7時圏外" in rising[0]["rank_evidence"]


def test_build_cross_source_excludes_same_provider_openalex(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "openalex_ai_us",
            "items": [{"t": "Paper A", "r": 1}],
            "captured_at": "2026-05-22T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "openalex_nlp_us",
            "items": [{"t": "Paper A", "r": 1}],
            "captured_at": "2026-05-22T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_excludes_same_provider_prtimes(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "prtimes_jp",
            "items": [{"t": "同じプレスリリース", "r": 6}],
            "captured_at": "2026-05-23T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "prtimes_hatena_jp",
            "items": [{"t": "同じプレスリリース", "r": 8}],
            "captured_at": "2026-05-23T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_excludes_same_provider_book_us(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "book_us_all",
            "items": [{"t": "The Odyssey of Homer", "r": 1}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "book_us_fiction",
            "items": [{"t": "The Odyssey of Homer", "r": 1}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_excludes_same_provider_wikipedia(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "wikipedia_ja",
            "items": [{"t": "Topic", "r": 1}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "wikipedia_en",
            "items": [{"t": "Topic", "r": 1}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_excludes_same_provider_google_trends_regions(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "google_trends_jp",
            "items": [{"t": "同じキーワード", "r": 1}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "google_trends_us",
            "items": [{"t": "同じキーワード", "r": 3}],
            "captured_at": "2026-05-24T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_excludes_generic_sports_label(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "google_trends_us",
            "items": [{"t": "Sports", "r": 10}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "twitch_jp",
            "items": [{"t": "Sports", "r": 5}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "twitch_us",
            "items": [{"t": "Sports", "r": 6}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_dedupes_twitch_provider_keys(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "hatena_jp",
            "items": [{"t": "具体的な技術記事タイトル", "r": 2}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "twitch_jp",
            "items": [{"t": "具体的な技術記事タイトル", "r": 4}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "twitch_us",
            "items": [{"t": "具体的な技術記事タイトル", "r": 5}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
    ]
    cross = gads.build_cross_source_highlights(rows, count=3)
    assert len(cross) == 1
    assert cross[0]["series_keys"] == ["hatena_jp", "twitch_jp"]
    assert "Twitch" in cross[0]["sources_display"]
    assert "twitch_us" not in cross[0]["series_keys"]


@pytest.mark.parametrize(
    "series_key,expected",
    [
        ("book_us_all", "book_us"),
        ("book_jp_fiction", "book_jp"),
        ("wikipedia_ja", "wikipedia"),
        ("wikipedia_en", "wikipedia"),
        ("google_trends_jp", "google_trends"),
        ("openalex_ai_jp", "openalex"),
        ("prtimes_hatena_jp", "prtimes"),
        ("globenewswire_market_us", "globenewswire"),
        ("nhk_jp", "nhk"),
        ("hatena_jp", "hatena"),
        ("zenn_jp", "zenn"),
    ],
)
def test_series_provider_groups_same_upstream(gads, series_key, expected):
    assert gads._series_provider(series_key) == expected


def test_build_cross_source_highlights_finds_overlap(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "wikipedia_jp",
            "items": [{"t": "豊臣秀長", "r": 1}],
            "captured_at": "2026-05-20T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "google_trends_jp",
            "items": [{"t": "豊臣秀長", "r": 3}],
            "captured_at": "2026-05-20T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "devto_us",
            "items": [{"t": "Only Dev", "r": 1}],
            "captured_at": "2026-05-20T19:00:00+09:00",
        },
    ]
    cross = gads.build_cross_source_highlights(rows, count=3)
    assert len(cross) == 1
    assert cross[0]["label"] == "豊臣秀長"
    assert "wikipedia_jp" in cross[0]["series_keys"]
    assert "google_trends_jp" in cross[0]["series_keys"]


def test_build_cross_source_excludes_same_article_hatena_zenn(gads):
    article_url = "https://zenn.dev/user/articles/claude-code-tips"
    rows = [
        {
            "slot": "13",
            "series_key": "hatena_jp",
            "items": [{"t": "Claude Code の使い方", "r": 3, "u": article_url}],
            "captured_at": "2026-05-29T13:00:00+09:00",
        },
        {
            "slot": "13",
            "series_key": "zenn_jp",
            "items": [{"t": "Claude Code の使い方", "r": 4, "u": article_url}],
            "captured_at": "2026-05-29T13:00:00+09:00",
        },
    ]
    assert gads.build_cross_source_highlights(rows, count=3) == []


def test_build_cross_source_keeps_different_urls_same_title(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [
                {
                    "t": "台風接近",
                    "r": 1,
                    "u": "https://www3.nhk.or.jp/news/html/20260529/k100.html",
                }
            ],
            "captured_at": "2026-05-29T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "google_trends_jp",
            "items": [{"t": "台風接近", "r": 2}],
            "captured_at": "2026-05-29T19:00:00+09:00",
        },
    ]
    cross = gads.build_cross_source_highlights(rows, count=3)
    assert len(cross) == 1
    assert cross[0]["label"] == "台風接近"


def test_normalize_article_url_ignores_google_search(gads):
    assert gads._normalize_article_url("https://www.google.com/search?q=foo") is None
    assert (
        gads._normalize_article_url("https://zenn.dev/a/articles/abc")
        == "zenn.dev/a/articles/abc"
    )


def test_build_category_top3_includes_links(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [
                {"t": "Head A", "r": 1, "u": "https://www3.nhk.or.jp/news/a"},
                {"t": "Head B", "r": 2},
            ],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "zenn_jp",
            "items": [{"t": "Zenn post", "r": 1, "u": "https://zenn.dev/a/b"}],
            "captured_at": "2026-05-25T19:00:00+09:00",
        },
    ]
    top3 = gads.build_category_top3(rows, count=3)
    news = next(b for b in top3 if b["category"] == "ニュース")
    assert len(news["items"]) == 2
    assert "https://www3.nhk.or.jp/news/a" in news["items"][0]["link_line"]
    tech = next(b for b in top3 if b["category"] == "テック・開発")
    assert "https://zenn.dev/a/b" in tech["items"][0]["link_line"]


def test_render_rising_highlights_markdown_empty(gads):
    md = gads.render_rising_highlights_markdown([])
    assert "## 📈 昨日いちばん動いた3つ" in md
    assert "順位が大きく上がった" in md


def test_render_rising_highlights_markdown_lists_items(gads):
    items = [
        {
            "link_line": "[Climber](https://example.com)（YouTube · 7時18位 → 19時2位）",
            "label": "Climber",
            "rank_evidence": "7時18位 → 13時圏外 → 19時2位",
            "ranks": {"07": 18, "19": 2},
            "jump": 16.0,
            "category": "検索・動画",
        },
    ]
    md = gads.render_rising_highlights_markdown(
        items,
        [{"match_label": "Climber", "note": "7時18位から19時2位へ上昇。"}],
    )
    assert "1. [Climber]" in md
    assert "**補足**: 7時18位から19時2位へ上昇。" in md
    assert "jump" not in md
    assert "| 07 | 13 | 19 |" not in md
    assert "**順位の動き**" not in md


def test_format_daily_slot_rank_trend_shows_labels_and_direction(gads):
    trend = gads.format_daily_slot_rank_trend(
        "Climber",
        {"07": 18, "13": 3, "19": 1},
    )
    assert trend.startswith("> **順位の動き**")
    assert '"7時 (18位)"' not in trend
    assert "7時 (18位)" in trend
    assert "19時 (1位)" in trend
    assert trend.endswith("↑")


def test_format_daily_slot_rank_trend_small_ranks(gads):
    trend = gads.format_daily_slot_rank_trend("Moved", {"13": 4, "19": 2})
    assert "13時 (4位)" in trend
    assert "19時 (2位)" in trend
    assert "↑" in trend


def test_format_daily_slot_rank_trend_skips_single_slot(gads):
    assert gads.format_daily_slot_rank_trend("Only", {"19": 1}) == ""


def test_format_daily_slot_rank_trend_skips_flat_ranks(gads):
    assert gads.format_daily_slot_rank_trend("Flat", {"13": 1, "19": 1}) == ""
    assert gads.format_daily_slot_rank_trend("Moved", {"13": 4, "19": 2}) != ""


def test_render_cross_source_highlights_markdown_empty(gads):
    md = gads.render_cross_source_highlights_markdown([], date(2026, 5, 27))
    assert "## 複数ソースで重なった話題 — 2026-05-27" in md
    assert gads._CROSS_NONE_LINE in md
    assert "### 1." not in md


def test_render_cross_source_highlights_markdown_lists_items(gads):
    highlights = [
        {
            "label": "豊臣秀長",
            "sources_display": "Wikipedia (JA), Google Trends (JP)",
            "rank_evidence": "7時8位 → 13時圏外 → 19時2位",
            "ranks": {"07": 8, "19": 2},
        },
    ]
    md = gads.render_cross_source_highlights_markdown(highlights, date(2026, 5, 20))
    assert "### 1. 豊臣秀長" in md
    assert "Wikipedia (JA), Google Trends (JP)" in md
    assert "| 07 | 13 | 19 |" in md
    assert "**順位の動き**" in md
    assert "```mermaid" not in md
    assert "**根拠**" not in md
    assert gads._CROSS_NONE_LINE not in md


def test_inject_cross_source_strips_llm_none_when_items_present(gads):
    llm = (
        "# 日次\n\n- **対象（観測日）**: 2026-05-27\n"
        "- **生成・送信完了**: 自動\n\n"
        "## 複数ソースで重なった話題 — 2026-05-27\n\n"
        "### 1. 例\n\n本文\n\n"
        f"{gads._CROSS_NONE_LINE}\n\n"
        "## 📊 カテゴリ別トップ3\n\n### ニュース\n"
    )
    cross = gads.render_cross_source_highlights_markdown(
        [
            {
                "label": "豊臣秀長",
                "sources_display": "Wikipedia (JA), Google Trends (JP)",
                "rank_evidence": "19時1位",
            },
        ],
        date(2026, 5, 27),
    )
    out = gads.inject_cross_source_highlights(llm, cross)
    assert out.count(gads._CROSS_NONE_LINE) == 0
    assert "### 1. 豊臣秀長" in out
    assert "### 1. 例" not in out


def test_inject_cross_source_after_rising_section(gads):
    md = (
        "# 日次\n\n- **対象（観測日）**: 2026-05-26\n"
        "- **生成・送信完了**: 自動\n\n"
        "## 📈 昨日いちばん動いた3つ\n\n1. [例](https://example.com)\n"
    )
    cross = "## 複数ソースで重なった話題 — 2026-05-26\n\n" + gads._CROSS_NONE_LINE + "\n"
    out = gads.inject_cross_source_highlights(md, cross)
    assert out.index("昨日いちばん動いた3つ") < out.index("複数ソースで重なった話題")


def test_inject_rising_highlights_before_cross_section(gads):
    md = (
        "# 日次\n\n- **対象（観測日）**: 2026-05-26\n"
        "- **生成・送信完了**: 自動\n\n"
        "## 複数ソースで重なった話題 — 2026-05-26\n\n### 1. 例\n"
    )
    rising = "## 📈 昨日いちばん動いた3つ\n\n1. [例](https://example.com)（NHK · 19時1位）\n"
    out = gads.inject_rising_highlights(md, rising)
    assert out.index("昨日いちばん動いた3つ") < out.index("複数ソースで重なった話題")
    assert out.count("昨日いちばん動いた3つ") == 1


def test_inject_category_top3_replaces_notable_and_appends(gads):
    md = (
        "# 日次\n\n## 📊 カテゴリ別トップ1\n\n- item\n\n"
        "## 💡 昨日特異だったこと\n\n"
        "繰り返しだけの文。\n"
    )
    top3 = "### ニュース\n1. [例](https://example.com)（NHK · 19時1位）\n"
    out = gads.inject_category_top3(md, f"## 📊 カテゴリ別トップ3\n\n{top3}")
    assert out.count("## 📊 カテゴリ別トップ3") == 1
    assert "## 📊 カテゴリ別トップ1" not in out
    assert "## 💡 昨日特異だったこと" not in out
    assert "繰り返しだけの文" not in out
    assert "https://example.com" in out


def test_build_llm_payload_includes_editorial_fields(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    payload = gads.build_llm_payload(
        rows, date(2026, 5, 18), rising_items=rising, cross_items=cross, top3_blocks=top3
    )
    assert "editorial_candidates" in payload
    assert "quiet_editorial_categories" in payload
    assert "rising_highlights" in payload
    assert "cross_source_highlights" in payload
    assert "spotlight_max" not in payload
    assert "急上昇" not in payload["reader_context"] or "editorial_candidates" in payload["reader_context"]


def test_build_llm_payload_marks_quiet_tech_when_all_stale(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "github_jp",
            "items": [{"t": "build-your-own-x", "r": 1, "u": "https://github.com/a/b"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "ipa_jp",
            "items": [
                {
                    "t": "更新：Windows 10のサポート終了に伴う注意喚起",
                    "r": 1,
                    "u": "https://www.ipa.go.jp/x",
                }
            ],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "jpcert_jp",
            "items": [
                {
                    "t": "Weekly Report: Twigに複数の脆弱性",
                    "r": 1,
                    "u": "https://www.jpcert.or.jp/x",
                }
            ],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    payload = gads.build_llm_payload(
        rows, date(2026, 5, 18), rising_items=rising, cross_items=cross, top3_blocks=top3
    )
    assert "テック・開発" in payload["quiet_editorial_categories"]
    assert payload["editorial_candidates"] == []


def test_is_stale_label(gads):
    assert gads._is_stale_label("build-your-own-x")
    assert gads._is_stale_label("更新：Windows 10のサポート終了に伴う注意喚起")
    assert not gads._is_stale_label("沖縄・奄美にあすから接近")


def test_build_category_top3_deprioritizes_stale(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "github_jp",
            "items": [{"t": "build-your-own-x", "r": 1, "u": "https://github.com/a/b"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "zenn_jp",
            "items": [{"t": "Fresh Zenn Article", "r": 2, "u": "https://zenn.dev/a/b"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    top3 = gads.build_category_top3(rows, count=3)
    tech = next(b for b in top3 if b["category"] == "テック・開発")
    assert tech["items"][0]["label"] == "Fresh Zenn Article"


def test_build_editorial_candidates_includes_category_leader(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "台風接近ニュース", "r": 1, "u": "https://www3.nhk.or.jp/news/a"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "07",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Rising Video", "r": 5}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "youtube_trends_jp",
            "items": [{"t": "Rising Video", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    cands = gads.build_editorial_candidates(rising, cross, top3, rows)
    labels = [c["label"] for c in cands]
    assert "台風接近ニュース" in labels
    assert any(c["reason"] == "category_leader" for c in cands)


def test_build_editorial_candidates_excludes_stale(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "台風接近", "r": 1, "u": "https://www3.nhk.or.jp/news/a"}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "github_jp",
            "items": [{"t": "build-your-own-x", "r": 1}],
            "captured_at": "2026-05-18T19:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    cands = gads.build_editorial_candidates(rising, cross, top3, rows)
    labels = [c["label"] for c in cands]
    assert "台風接近" in labels
    assert "build-your-own-x" not in labels


def test_one_liner_is_acceptable_requires_rising_labels(gads):
    rising = [
        {"label": "Ariana Grande MV", "category": "検索・動画"},
        {"label": "Splatoon 3", "category": "検索・動画"},
        {"label": "Victor Wembanyama", "category": "検索・動画"},
    ]
    news = [
        {
            "label": "老舗ホテルのカピピン",
            "category": "ニュース",
            "reason": "category_leader",
        }
    ]
    weak = (
        "「老舗ホテルのカピピン」が注目を集めており、"
        "特に検索・動画カテゴリでは「Victor Wembanyama」が人気です。"
    )
    assert not gads.one_liner_is_acceptable(weak, news, rising)
    mech = gads.build_mechanical_one_liner(news, rising, [])
    assert "Ariana Grande MV" in mech or "Ariana" in mech
    assert "Splatoon 3" in mech
    assert "Victor Wembanyama" in mech
    assert "カピピン" in mech
    assert gads.one_liner_is_acceptable(mech, news, rising)


def test_finalize_editorial_replaces_one_liner_and_filters_generic_notes(gads):
    rising = [
        {
            "label": "Climber",
            "category": "検索・動画",
            "rank_evidence": "7時圏外 → 13時3位 → 19時1位",
            "link_line": "[Climber](https://example.com)（YouTube · 19時1位）",
        },
    ]
    editorial_candidates = [
        {
            "label": "Climber",
            "category": "検索・動画",
            "reason": "rising",
            "rank_evidence": "7時圏外 → 13時3位 → 19時1位",
        },
    ]
    index = {
        gads._normalize_label_key("Climber"): {
            "label": "Climber",
            "link_line": "[Climber](https://example.com)（YouTube · 19時1位）",
        }
    }
    editorial = {
        "one_liner": "動きは限定的でした。",
        "spotlights": [],
        "rising_notes": [
            {"match_label": "Climber", "note": "若い世代の間で話題です。"},
        ],
    }
    out, trace = gads.finalize_editorial(
        editorial,
        editorial_candidates=editorial_candidates,
        rising_items=rising,
        cross_items=[],
        label_index=index,
    )
    assert trace["one_liner_source"] == "mechanical"
    assert "Climber" in out["one_liner"]
    assert out["teaser"]
    assert "Climber" in out["teaser"]
    assert trace.get("teaser_source") in ("llm", "derived")
    assert len(out["teaser"]) <= gads._TEASER_MAX_CHARS
    assert out["spotlights"] == []
    assert trace["spotlights_renderable"] == 0
    assert not any("若い世代" in str(n.get("note") or "") for n in out["rising_notes"])


def test_parse_editorial_json(gads):
    raw = json.dumps(
        {
            "teaser": "「Climber」が順位上昇。",
            "one_liner": "台風と dazn が目立った。",
            "spotlights": [
                {
                    "title": "台風",
                    "body": "接近が報じられた。",
                    "source_labels": ["台風接近"],
                }
            ],
            "rising_notes": [{"match_label": "Climber", "note": "順位上昇。"}],
            "cross_intro": None,
            "category_intros": {"ニュース": "気象系。"},
        },
        ensure_ascii=False,
    )
    data = gads.parse_editorial_json(raw)
    assert data["teaser"].startswith("「Climber」")
    assert data["one_liner"].startswith("台風")
    assert len(data["spotlights"]) == 1
    assert data["cross_intro"] is None


def test_render_editorial_markdown_one_liner_only(gads):
    editorial = {
        "one_liner": "テスト一行。",
        "spotlights": [
            {
                "title": "台風",
                "body": "接近。",
                "source_labels": ["台風接近"],
            }
        ],
    }
    index = {
        gads._normalize_label_key("台風接近"): {
            "label": "台風接近",
            "link_line": "[台風接近](https://example.com)（NHK · 19時1位）",
        }
    }
    md = gads.render_editorial_markdown(editorial, index)
    assert gads._ONE_LINER_HEADING in md
    assert "テスト一行。" in md
    assert gads._SPOTLIGHTS_HEADING not in md
    assert "### 1. 台風" not in md


def test_render_rising_highlights_includes_notes(gads):
    items = [
        {
            "link_line": "[Climber](https://example.com)（YouTube · 19時2位）",
            "rank_evidence": "7時18位 → 19時2位",
            "category": "検索・動画",
            "label": "Climber",
        },
    ]
    md = gads.render_rising_highlights_markdown(
        items, [{"match_label": "Climber", "note": "日中に順位が大きく上昇。"}]
    )
    assert "**補足**" in md
    assert "順位が大きく上昇" in md


def test_render_cross_source_includes_intro(gads):
    md = gads.render_cross_source_highlights_markdown(
        [{"label": "豊臣秀長", "sources_display": "Wiki", "rank_evidence": "19時1位"}],
        date(2026, 5, 20),
        cross_intro="複数ソースで同名が観測された。",
    )
    assert "複数ソースで同名が観測された。" in md


def test_render_category_top3_omits_trend_blurbs(gads):
    blocks = [
        {
            "category": "ニュース",
            "items": [
                {
                    "label": "Head A",
                    "link_line": "[Head A](https://example.com)（NHK · 19時1位）",
                }
            ],
        }
    ]
    md = gads.render_category_top3_markdown(blocks, {"ニュース": "気象関連が中心。"})
    assert "**昨日の傾向**" not in md
    assert "気象関連が中心。" not in md
    assert "### ニュース" in md
    assert "Head A" in md


def test_assemble_daily_markdown_structure(gads):
    bd = date(2026, 5, 31)
    editorial = {"one_liner": "一行。", "spotlights": [], "rising_notes": [], "category_intros": {}}
    md = gads.assemble_daily_markdown(bd, editorial, {}, [], [], [])
    assert "# 日次サマリー — 2026-05-31" in md
    assert gads._ONE_LINER_HEADING in md
    assert gads._RISING_HEADING in md
    assert "複数ソースで重なった話題" in md
    assert gads._TOP3_HEADING in md


def test_build_llm_payload_no_legacy_category_list(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    payload = gads.build_llm_payload(
        rows, date(2026, 5, 18), rising_items=rising, cross_items=cross, top3_blocks=top3
    )
    assert "categories" not in payload
    assert "category_top1" not in payload
    assert "category_top3" not in payload
    assert "notable_summary" not in payload
    assert "editorial_candidates" in payload


def test_build_llm_payload_news_candidate_when_only_nhk(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
    ]
    rising = gads.build_rising_highlights(rows, count=3)
    cross = gads.build_cross_source_highlights(rows, count=3)
    top3 = gads.build_category_top3(rows, count=3)
    payload = gads.build_llm_payload(
        rows, date(2026, 5, 18), rising_items=rising, cross_items=cross, top3_blocks=top3
    )
    assert payload["business_day"] == "2026-05-18"
    assert any(c["label"] == "headline" for c in payload["editorial_candidates"])
    assert "テック・開発" in payload["quiet_editorial_categories"]


def test_write_generation_status_json(tmp_path, gads):
    bd = date(2026, 6, 1)
    daily_dir = tmp_path / "daily"
    p = gads.write_generation_status(
        bd,
        ok=True,
        daily_dir=daily_dir,
        markdown="docs/summaries/daily/2026-06-01.md",
        model="gpt-4o-mini",
        snapshot_row_count=42,
    )
    assert p.name == "2026-06-01.generation.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["business_day"] == "2026-06-01"
    assert data["ok"] is True
    assert data["snapshot_row_count"] == 42
    assert "logged_at" in data


def test_filter_rows_by_region_keeps_matching_series(gads):
    rows = [
        {"series_key": "nhk_jp", "label": "JP"},
        {"series_key": "hackernews_us", "label": "US"},
        {"series_key": "crypto_global", "label": "BTC"},
        {"series_key": "unknown_key", "label": "??"},
    ]
    jp = gads.filter_rows_by_region(rows, "jp")
    us = gads.filter_rows_by_region(rows, "us")
    assert [r["series_key"] for r in jp] == ["nhk_jp", "crypto_global"]
    assert [r["series_key"] for r in us] == ["hackernews_us", "crypto_global"]


def test_series_region_stock_and_crypto(gads):
    assert gads.series_region("stock_jp") == "jp"
    assert gads.series_region("stock_us") == "us"
    assert gads.series_region("crypto_global") == "global"


def test_configure_daily_region_us_paths_and_headings(gads):
    gads.configure_daily_region("us")
    assert gads._ACTIVE_REGION == "us"
    assert gads.daily_output_dir().name == "us"
    assert "takeaway" in gads._ONE_LINER_HEADING.lower()
    assert "Biggest movers" in gads._RISING_HEADING
    hdr = gads.render_header_markdown(date(2026, 7, 13))
    assert "Daily summary" in hdr
    assert "Observation day" not in hdr
    assert "Generated" not in hdr
    gads.configure_daily_region("jp")
    assert gads.daily_output_dir() == gads.DAILY_DIR
    assert "一行結論" in gads._ONE_LINER_HEADING
    jp_hdr = gads.render_header_markdown(date(2026, 7, 13))
    assert "対象（観測日）" not in jp_hdr
    assert "生成・送信完了" not in jp_hdr


def test_us_render_uses_english_labels_not_japanese(gads):
    gads.configure_daily_region("us")
    assert gads.category_display_name("ニュース") == "News"
    assert gads.category_display_name("検索・動画") == "Search & Video"
    assert gads._format_rank_evidence({"13": 1}) == "out@7 → #1@13 → out@19"
    assert gads.describe_rank_movement({"13": 1, "19": 1}).startswith("Surged")

    rising_md = gads.render_rising_highlights_markdown(
        [
            {
                "label": "Lindsey Graham",
                "link_line": "[Lindsey Graham](https://example.com)（Wikipedia (EN)）",
            }
        ],
        [{"match_label": "Lindsey Graham", "note": "Held the top of Search & Video."}],
    )
    assert "**Note**:" in rising_md
    assert "補足" not in rising_md

    top3_md = gads.render_category_top3_markdown(
        [
            {"category": "News", "items": [], "quiet": True},
            {
                "category": "Search & Video",
                "items": [
                    {
                        "label": "Lindsey Graham",
                        "link_line": "[Lindsey Graham](https://example.com)"
                        "（Wikipedia (EN) · out@7 → #1@13 → #1@19）",
                    }
                ],
            },
        ],
        {"Search & Video": "Search interest clustered on politics."},
    )
    assert "- **News**: (no data)" in top3_md
    assert "### Search & Video" in top3_md
    assert "Yesterday's trend" not in top3_md
    assert "Search interest clustered on politics." not in top3_md
    assert "データなし" not in top3_md
    assert "昨日の傾向" not in top3_md
    assert "ニュース" not in top3_md
    assert "検索・動画" not in top3_md


def test_exclude_market_default_is_false():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "services" / "trend_snapshot_service.py"
    spec = importlib.util.spec_from_file_location("trend_snapshot_service", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid importing heavy deps; just eval the function body via reading source
    text = path.read_text(encoding="utf-8")
    assert 'TREND_SNAPSHOT_EXCLUDE_MARKET", "false"' in text
    assert 'TREND_SNAPSHOT_EXCLUDE_MARKET", "true"' not in text
