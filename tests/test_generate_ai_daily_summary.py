"""Tests for scripts/generate_ai_daily_summary.py (date helper + API fetch)."""

import importlib.util
import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_ai_daily_summary.py"


@pytest.fixture(scope="module")
def gads():
    spec = importlib.util.spec_from_file_location("generate_ai_daily_summary", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        ("zenn_jp", "テック・開発"),
        ("jpcert_jp", "テック・開発"),
        ("stock_jp", "マーケット"),
        ("book_jp_fiction", "エンタメ"),
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


def test_is_noisy_label_filters_procurement(gads):
    assert gads._is_noisy_label(
        "SIEMENS STAR CCM+ LICENSE RENEWAL (POP: 7/1/2026-6/30/2027)",
        "usaspending_us",
    )
    assert not gads._is_noisy_label("豊臣秀長", "wikipedia_jp")


def test_format_rank_evidence_uses_snapshot_wording(gads):
    assert gads._format_rank_evidence({"07": 8, "13": 3, "19": 1}) == (
        "07時スナップショット8位 → 13時スナップショット3位 → 19時スナップショット1位"
    )


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


def test_build_category_top1_picks_per_category(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "NHK headline", "r": 1}],
            "captured_at": "2026-05-20T19:00:00+09:00",
        },
        {
            "slot": "19",
            "series_key": "zenn_jp",
            "items": [{"t": "Zenn article", "r": 1}],
            "captured_at": "2026-05-20T19:00:00+09:00",
        },
    ]
    top1 = gads.build_category_top1(rows)
    by_cat = {c["category"]: c for c in top1}
    assert by_cat["ニュース"]["label"] == "NHK headline"
    assert by_cat["ニュース"]["rank_display"] == "19時スナップショット1位"
    assert by_cat["テック・開発"]["label"] == "Zenn article"
    assert by_cat["エンタメ"].get("quiet") is True


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


def test_inject_category_top3_replaces_notable_and_appends(gads):
    md = (
        "# 日次\n\n## 📊 カテゴリ別トップ1\n\n- item\n\n"
        "## 💡 昨日特異だったこと\n\n"
        "繰り返しだけの文。\n"
    )
    top3 = "### ニュース\n1. [例](https://example.com)（nhk_jp · 19時スナップショット1位）\n"
    out = gads.inject_category_top3(md, f"## 📊 カテゴリ別トップ3\n\n{top3}")
    assert out.count("## 📊 カテゴリ別トップ3") == 1
    assert "## 💡 昨日特異だったこと" not in out
    assert "繰り返しだけの文" not in out
    assert "https://example.com" in out


def test_build_llm_payload_includes_cross_and_top1(gads):
    rows = [
        {
            "slot": "19",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
    ]
    payload = gads.build_llm_payload(rows, date(2026, 5, 18))
    assert "cross_source_highlights" in payload
    assert "category_top1" in payload
    assert "category_top3" in payload
    assert "notable_summary" not in payload
    assert "rising_highlights_fallback" in payload
    assert "reader_context" in payload
    assert "今日の見方" not in payload["reader_context"]


def test_build_llm_payload_omits_empty_categories(gads):
    rows = [
        {
            "slot": "07",
            "series_key": "nhk_jp",
            "items": [{"t": "headline", "r": 1}],
            "captured_at": "2026-05-18T07:00:00+09:00",
        },
    ]
    payload = gads.build_llm_payload(rows, date(2026, 5, 18))
    assert payload["business_day"] == "2026-05-18"
    assert "reader_context" in payload
    cats = [c["category"] for c in payload["categories"]]
    assert cats == ["ニュース"]
    assert "テック・開発" in payload["quiet_categories"]


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
