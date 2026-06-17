"""Tests for scripts/generate_ai_weekly_summary.py (week boundaries and loaders)."""

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_ai_weekly_summary.py"


@pytest.fixture(scope="module")
def gaws():
    spec = importlib.util.spec_from_file_location("generate_ai_weekly_summary", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_iso_week_stem(gaws):
    assert gaws.iso_week_stem(date(2026, 5, 12)) == "2026-W20"
    assert gaws.iso_week_stem(date(2026, 5, 17)) == "2026-W20"
    assert gaws.iso_week_stem(date(2026, 5, 18)) == "2026-W21"


def test_week_range_mon_sun(gaws):
    mon, sun = gaws.week_range_mon_sun(date(2026, 5, 14))
    assert mon == date(2026, 5, 11)
    assert sun == date(2026, 5, 17)


def test_week_dates(gaws):
    assert gaws.week_dates(date(2026, 5, 11)) == [
        date(2026, 5, 11 + i) for i in range(7)
    ]


def test_default_week_mon_jst_previous_completed_week(gaws):
    from zoneinfo import ZoneInfo

    jst = ZoneInfo("Asia/Tokyo")
    # 2026-05-18 is Monday JST → previous ISO week starts Monday 2026-05-11
    mon = datetime(2026, 5, 18, 12, 0, tzinfo=jst)
    assert gaws.default_week_mon_jst(mon) == date(2026, 5, 11)


def test_split_front_matter(gaws):
    raw = """---
a: b
---

# Hello

body
"""
    fm, body = gaws.split_front_matter(raw)
    assert "a: b" in fm
    assert body.startswith("# Hello")


def test_split_front_matter_no_fm(gaws):
    fm, body = gaws.split_front_matter("# Only\n")
    assert fm == ""
    assert "Only" in body


def test_build_daily_rollups_missing_and_found(tmp_path, gaws):
    ddir = tmp_path / "daily"
    ddir.mkdir(parents=True)
    (ddir / "2026-05-11.md").write_text(
        "---\nx: 1\n---\n\n## Body\n", encoding="utf-8"
    )
    mon, sun = date(2026, 5, 11), date(2026, 5, 17)
    text, meta = gaws.build_daily_rollups(mon, sun, ddir)
    assert meta["missing_dates"] == [
        d.isoformat() for d in gaws.week_dates(mon)[1:]
    ]
    assert "2026-05-11" in text
    assert "ファイルなし" in text
    assert meta["truncated"] is False


def test_aggregate_weekly_rising_prefers_multi_day(gaws):
    daily = {
        "2026-06-08": [
            {
                "label": "Alpha Topic",
                "jump": 10.0,
                "freq_slots": 2,
                "r_best": 1,
                "series_key": "google_trends_jp",
                "category": "ニュース",
                "url": "https://example.com/a",
            }
        ],
        "2026-06-09": [
            {
                "label": "Alpha Topic",
                "jump": 8.0,
                "freq_slots": 2,
                "r_best": 2,
                "series_key": "google_trends_jp",
                "category": "ニュース",
                "url": "https://example.com/a",
            }
        ],
        "2026-06-10": [
            {
                "label": "Beta One Day",
                "jump": 15.0,
                "freq_slots": 2,
                "r_best": 1,
                "series_key": "google_trends_jp",
                "category": "テック・開発",
            }
        ],
    }
    out = gaws.aggregate_weekly_rising(daily, count=2)
    assert len(out) >= 2
    assert out[0]["label"] == "Alpha Topic"
    assert out[0]["day_count"] == 2
    assert out[0]["jump_sum"] == 18.0
    assert out[0]["weekly_score"] > out[1]["weekly_score"]


def test_aggregate_weekly_rising_cross_and_series_weight(gaws):
    import snapshot_rising as sr

    daily = {
        "2026-06-08": [
            {
                "label": "Obscure Paper",
                "jump": 10.0,
                "freq_slots": 2,
                "r_best": 1,
                "series_key": "openalex_trending_us",
                "category": "テック・開発",
                "link_line": "Obscure",
            },
            {
                "label": "Search Spike",
                "jump": 10.0,
                "freq_slots": 2,
                "r_best": 1,
                "series_key": "google_trends_jp",
                "category": "検索・動画",
                "link_line": "Search",
            },
        ],
    }
    cross_keys = {sr.normalize_label_key("Search Spike")}
    out = gaws.aggregate_weekly_rising(daily, count=1, cross_label_keys=cross_keys)
    assert out[0]["label"] == "Search Spike"
    assert out[0]["cross_source"] is True


def test_compute_weekly_rising_score(gaws):
    low = gaws.compute_weekly_rising_score(
        1, 2, 10.0, cross_source=False, series_weight=3
    )
    high = gaws.compute_weekly_rising_score(
        3, 6, 25.0, cross_source=True, series_weight=15
    )
    assert high > low


@pytest.mark.parametrize(
    "series_key,expected",
    [
        ("google_trends_jp", 15),
        ("youtube_trends_us", 15),
        ("wikipedia_ja", 15),
        ("wikipedia_en", 15),
        ("nhk_jp", 15),
        ("cnn_us", 15),
        ("hatena_jp", 12),
        ("worldnews_us", 12),
        ("zenn_jp", 12),
        ("note_jp", 12),
        ("qiita_jp", 12),
        ("thehackernews_us", 12),
        ("medium_us", 12),
        ("devto_us", 12),
        ("hackernews_us", 12),
        ("producthunt_us", 12),
        ("music_trends_jp", 10),
        ("twitch_us", 10),
        ("rakuten_jp", 10),
        ("podcast_us", 10),
        ("movie_jp", 10),
        ("github_jp", 10),
        ("github_us", 10),
        ("openalex_ai_jp", 3),
        ("book_us_fiction", 3),
        ("bls_us", 7),
        ("usaspending_us", 7),
        ("prtimes_jp", 7),
        ("", 7),
    ],
)
def test_weekly_series_weight(gaws, series_key, expected):
    assert gaws.weekly_series_weight(series_key) == expected


def test_aggregate_weekly_rising_includes_sixth_daily_candidate(gaws):
    """日次 top5 切りで落ちる候補も、週次プール全件なら集計対象になる。"""
    daily = {
        "2026-06-08": [
            {
                "label": f"Topic {i}",
                "jump": 10.0,
                "freq_slots": 2,
                "r_best": 1,
                "series_key": "google_trends_jp",
            }
            for i in range(6)
        ],
    }
    out = gaws.aggregate_weekly_rising(daily, count=10)
    assert len(out) == 6
    labels = {x["label"] for x in out}
    assert "Topic 5" in labels


def test_aggregate_weekly_cross_source(gaws):
    daily = {
        "2026-06-08": [
            {
                "label": "Shared Cross",
                "providers": ["google_trends", "wikipedia"],
                "sources_display": "Google Trends, Wikipedia",
                "rank_evidence": "7時圏外 → 13時1位 → 19時圏外",
                "best_daytime_rank": 1,
                "jump": 5.0,
            }
        ],
        "2026-06-10": [
            {
                "label": "Shared Cross",
                "providers": ["google_trends", "wikipedia"],
                "sources_display": "Google Trends, Wikipedia",
                "rank_evidence": "7時5位 → 13時2位 → 19時3位",
                "best_daytime_rank": 2,
                "jump": 3.0,
            }
        ],
    }
    out = gaws.aggregate_weekly_cross_source(daily)
    assert len(out) == 1
    assert out[0]["day_count"] == 2
    assert "google_trends" in out[0]["providers"]


def test_format_rank_evidence_parsing(gaws):
    ranks = gaws.parse_rank_evidence("7時10位 → 13時8位 → 19時8位")
    assert ranks == {"07": 10, "13": 8, "19": 8}
    assert gaws.parse_rank_evidence("7時圏外 → 13時10位 → 19時9位") == {
        "07": None,
        "13": 10,
        "19": 9,
    }


def test_format_weekly_rank_table(gaws):
    table = gaws.format_weekly_rank_table(
        {
            "2026-06-08": "7時10位 → 13時8位 → 19時8位",
            "2026-06-09": "7時圏外 → 13時6位 → 19時6位",
        }
    )
    assert "| 日 | 07 | 13 | 19 |" in table
    assert "| 06-08 | 10 | 8 | 8 |" in table
    assert "| 06-09 | — | 6 | 6 |" in table


def test_render_weekly_rising_markdown_uses_table_not_prose_evidence(gaws):
    rising = {
        "jp": [
            {
                "label": "ライラック",
                "days": ["2026-06-08", "2026-06-09"],
                "day_count": 2,
                "jump_sum": 15.0,
                "weekly_score": 145.0,
                "category": "エンタメ",
                "link_line": "[ライラック](https://example.com)",
                "rank_evidence_by_day": {
                    "2026-06-08": "7時10位 → 13時8位 → 19時8位",
                    "2026-06-09": "7時8位 → 13時6位 → 19時6位",
                },
            }
        ],
        "us": [],
    }
    md = gaws.render_weekly_rising_markdown(rising)
    assert "| 06-08 | 10 | 8 | 8 |" in md
    assert "jump **+15.0**" in md
    assert "根拠:" not in md
    assert "jump合計" not in md
    assert "```mermaid" in md
    assert 'y-axis "順位" 1 --> 10' in md
    assert '("06-08 (8位)"' in md or '"06-08 (8位)"' in md


def test_format_weekly_best_rank_mermaid_y_axis_rank_one_at_top(gaws):
    chart = gaws.format_weekly_best_rank_mermaid(
        "ライラック",
        {
            "2026-06-08": "7時10位 → 13時8位 → 19時8位",
            "2026-06-12": "7時4位 → 13時2位 → 19時2位",
        },
    )
    assert 'y-axis "順位" 1 --> 10' in chart
    assert '"06-08 (8位)"' in chart
    assert '"06-12 (2位)"' in chart
    assert "line [3, 9]" in chart
    assert "上=1位" in chart


def test_assemble_weekly_markdown_includes_regional_sections(gaws):
    mon = date(2026, 6, 8)
    sun = date(2026, 6, 14)
    editorial = {
        "flow_jp": "今週は日本のテスト話題が動いた。",
        "flow_us": "今週は米国のテスト話題が動いた。",
        "carryover": ["論点A — 続く見込み"],
    }
    rising = {
        "jp": [
            {
                "label": "Rising JP",
                "days": ["2026-06-08"],
                "day_count": 1,
                "jump_sum": 10.0,
                "category": "ニュース",
                "link_line": "[Rising JP](https://example.com/jp)",
                "rank_evidence_by_day": {},
            }
        ],
        "us": [
            {
                "label": "Rising US",
                "days": ["2026-06-09"],
                "day_count": 1,
                "jump_sum": 9.0,
                "category": "テック・開発",
                "link_line": "[Rising US](https://example.com/us)",
                "rank_evidence_by_day": {},
            }
        ],
    }
    cross: dict = {"jp": [], "us": []}
    meta = {"missing_snapshot_dates": [], "partial_snapshot_dates": [], "missing_dates": []}
    md = gaws.assemble_weekly_markdown(
        "2026-W24", mon, sun, editorial, rising, cross, meta
    )
    assert "🇯🇵 日本" in md
    assert "🇺🇸 アメリカ" in md
    assert "今週いちばん動いた話題" in md
    assert "Rising JP" in md
    assert "Rising US" in md
    assert "ソース一覧" not in md
    assert "週のホットトピック" not in md


def test_openai_api_key_accepts_open_api_key_env(monkeypatch, gaws):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_API_KEY", "sk-test")
    assert gaws.openai_api_key() == "sk-test"


def test_openai_api_key_prefers_openai_api_key(monkeypatch, gaws):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-primary")
    monkeypatch.setenv("OPEN_API_KEY", "sk-fallback")
    assert gaws.openai_api_key() == "sk-primary"


def test_build_mechanical_llm_payload_splits_regions(gaws):
    rising = {
        "jp": [{"label": "JP Topic", "day_count": 1, "jump_sum": 5.0, "days": ["2026-06-08"]}],
        "us": [{"label": "US Topic", "day_count": 1, "jump_sum": 4.0, "days": ["2026-06-09"]}],
    }
    cross = {"jp": [], "us": []}
    payload = gaws.build_mechanical_llm_payload(rising, cross)
    assert "regions" in payload
    assert payload["regions"]["jp"]["weekly_rising"][0]["label"] == "JP Topic"
    assert payload["regions"]["us"]["weekly_rising"][0]["label"] == "US Topic"
