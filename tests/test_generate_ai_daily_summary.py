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


def test_build_notable_summary_includes_cross_and_top1(gads):
    cross = [
        {
            "label": "豊臣秀長",
            "series_keys": ["wikipedia_jp", "google_trends_jp"],
            "rank_evidence": "07時スナップショット8位 → 19時スナップショット2位",
        }
    ]
    top1 = [
        {
            "category": "ニュース",
            "label": "NHK headline",
            "series_key": "nhk_jp",
            "rank_display": "19時スナップショット1位",
        },
        {"category": "エンタメ", "label": None, "quiet": True},
    ]
    summary = gads.build_notable_summary(cross, top1, ["エンタメ"])
    assert "豊臣秀長" in summary["recommended_sentence"]
    assert "wikipedia_jp" in summary["recommended_sentence"]
    assert "ニュース" in summary["recommended_sentence"]
    assert "NHK headline" in summary["recommended_sentence"]
    assert len(summary["cross_source_items"]) == 1
    assert len(summary["category_top1_items"]) == 1


def test_build_notable_summary_without_cross(gads):
    top1 = [
        {
            "category": "ニュース",
            "label": "事件ヘッド",
            "series_key": "nhk_jp",
            "rank_display": "19時スナップショット1位",
        },
    ]
    summary = gads.build_notable_summary([], top1, ["エンタメ"])
    assert "重複はなかった" in summary["recommended_sentence"]
    assert "事件ヘッド" in summary["recommended_sentence"]


def test_inject_notable_sentence_replaces_section(gads):
    md = "# 日次\n\n## 💡 昨日特異だったこと\n\n古い抽象文。\n\n## 他\n"
    out = gads.inject_notable_sentence(md, "新しい具体文。")
    assert "新しい具体文。" in out
    assert "古い抽象文" not in out


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
    assert "notable_summary" in payload
    assert "recommended_sentence" in payload["notable_summary"]
    assert "notable_hints" in payload
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
