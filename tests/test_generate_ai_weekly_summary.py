"""Tests for scripts/generate_ai_weekly_summary.py (week boundaries and loaders)."""

import importlib.util
import json
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
        ("medium_us", 7),
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
        ("openalex_ai_jp", 7),
        ("book_us_fiction", 3),
        ("appstore_jp", 0),
        ("appstore_us", 0),
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


def test_render_weekly_rising_markdown_compact_no_table(gaws):
    rising = {
        "jp": [
            {
                "label": "ライラック",
                "days": ["2026-06-08", "2026-06-09"],
                "day_count": 2,
                "jump_sum": 15.0,
                "best_rank": 6,
                "weekly_score": 145.0,
                "category": "エンタメ・ショッピング",
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
    assert "| 06-08 |" not in md
    assert "jump" not in md
    assert "各1件" not in md
    assert "**週内の動き**" in md
    assert "06-08 (8位)" in md
    assert "06-09 (6位)" in md
    assert "↑" not in md
    assert "↓" not in md
    assert "上ほど良い" not in md


def test_format_weekly_rising_movement_block_no_arrow(gaws):
    block = gaws.format_weekly_rising_movement_block(
        {
            "rank_evidence_by_day": {
                "2026-06-08": "7時10位 → 13時10位 → 19時10位",
                "2026-06-12": "7時4位 → 13時4位 → 19時4位",
            }
        }
    )
    assert "**週内の動き**" in block
    assert "06-08 (10位)" in block
    assert "06-12 (4位)" in block
    assert "↑" not in block
    assert "↓" not in block
    assert "上ほど良い" not in block


def test_format_weekly_rank_trend_block_shows_trend_line(gaws):
    block = gaws.format_weekly_rank_trend_block(
        "ライラック",
        {
            "2026-06-08": "7時10位 → 13時8位 → 19時8位",
            "2026-06-12": "7時4位 → 13時2位 → 19時2位",
        },
    )
    assert "**日別ベスト順位**" in block
    assert "06-08 (8位)" in block
    assert "06-12 (2位)" in block
    assert " ↑" in block


def test_format_weekly_rank_trend_block_us_is_english(gaws):
    gaws.configure_weekly_region("us")
    block = gaws.format_weekly_rank_trend_block(
        "The Whisper Man",
        {
            "2026-08-17": "7時7位 → 13時7位 → 19時7位",
            "2026-08-23": "7時9位 → 13時9位 → 19時9位",
        },
    )
    assert "**Best rank by day**" in block
    assert "順位の動き" not in block
    assert "上ほど良い" not in block
    gaws.configure_weekly_region("jp")


def test_format_weekly_rank_trend_block_skips_flat_ranks(gaws):
    assert gaws.format_weekly_rank_trend_block(
        "Flat",
        {
            "2026-06-08": "7時4位 → 13時4位 → 19時4位",
            "2026-06-09": "7時4位 → 13時4位 → 19時4位",
        },
    ) == ""


def test_pick_diverse_weekly_category_items_news_weather(gaws):
    pool = [
        {
            "label": "九州など非常に激しい雨のおそれ",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "nhk_jp",
            "rank_display_by_day": {"2026-07-01": "7時1位 → 13時1位 → 19時1位"},
        },
        {
            "label": "前線活動活発に 九州北部は激しい雨おそれ",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "nhk_jp",
            "rank_display_by_day": {"2026-07-03": "7時1位 → 13時1位 → 19時1位"},
        },
        {
            "label": "生食用の鶏肉 ガイドライン策定へ",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "nhk_jp",
            "rank_display_by_day": {"2026-07-02": "7時1位 → 13時1位 → 19時1位"},
        },
        {
            "label": "記録的水準の円安 今後は？",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "nhk_jp",
            "rank_display_by_day": {"2026-07-04": "7時1位 → 13時1位 → 19時1位"},
        },
    ]
    picked = gaws.pick_diverse_weekly_category_items(pool, "ニュース", 3)
    labels = [x["label"] for x in picked]
    assert len(picked) == 3
    assert sum("雨" in lab for lab in labels) == 1
    assert "生食用の鶏肉 ガイドライン策定へ" in labels
    assert "記録的水準の円安 今後は？" in labels
    rain = next(x for x in picked if "雨" in x["label"])
    assert "2026-07-01" in rain["rank_display_by_day"]
    assert "2026-07-03" in rain["rank_display_by_day"]


def test_pick_diverse_weekly_category_items_market_series(gaws):
    pool = [
        {
            "label": "Stock A",
            "weekly_score": 30,
            "day_count": 2,
            "best_rank": 1,
            "series_key": "stock_jp",
        },
        {
            "label": "Stock B",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "stock_jp",
        },
        {
            "label": "Crypto C",
            "weekly_score": 25,
            "day_count": 1,
            "best_rank": 1,
            "series_key": "crypto_jp",
        },
    ]
    picked = gaws.pick_diverse_weekly_category_items(pool, "マーケット", 3)
    labels = [x["label"] for x in picked]
    assert len(picked) == 3
    assert labels[0] == "Stock A"
    assert "Crypto C" in labels
    assert labels.count("Stock A") == 1
    assert "Stock B" in labels


def test_weekly_item_belongs_to_category_rejects_cross_category(gaws):
    assert gaws._weekly_item_belongs_to_category(
        "テック・開発",
        {"series_key": "zenn_jp", "label": "Zenn article"},
    )
    assert not gaws._weekly_item_belongs_to_category(
        "テック・開発",
        {"series_key": "rakuten_jp", "label": "楽天商品"},
    )
    assert not gaws._weekly_item_belongs_to_category(
        "マーケット",
        {"series_key": "nhk_jp", "label": "NHK headline"},
    )
    assert gaws._weekly_item_belongs_to_category(
        "検索・動画",
        {"series_key": "google_trends_jp", "label": "Trend"},
    )
    assert not gaws._weekly_item_belongs_to_category(
        "検索・動画",
        {"series_key": "hatena_jp", "label": "はてな"},
    )


def test_filter_weekly_category_pool_drops_foreign_series(gaws):
    pool = [
        {"label": "Tech", "series_key": "zenn_jp", "weekly_score": 25, "day_count": 1, "best_rank": 1},
        {"label": "Shop", "series_key": "rakuten_jp", "weekly_score": 30, "day_count": 1, "best_rank": 1},
    ]
    picked = gaws.pick_diverse_weekly_category_items(pool, "テック・開発", 3)
    assert [x["label"] for x in picked] == ["Tech"]


def test_filter_weekly_search_video_pool_allows_core_sources_only(gaws):
    pool = [
        {"label": "Trend A", "series_key": "google_trends_jp", "weekly_score": 25, "day_count": 1, "best_rank": 1},
        {"label": "Wiki B", "series_key": "wikipedia_ja", "weekly_score": 25, "day_count": 1, "best_rank": 1},
        {"label": "はてな記事", "series_key": "hatena_jp", "weekly_score": 25, "day_count": 1, "best_rank": 1},
        {"label": "LoL", "series_key": "twitch_jp", "weekly_score": 24, "day_count": 1, "best_rank": 1},
        {"label": "YouTube C", "series_key": "youtube_trends_jp", "weekly_score": 24, "day_count": 1, "best_rank": 1},
        {"label": "Trend D", "series_key": "google_trends_jp", "weekly_score": 23, "day_count": 1, "best_rank": 2},
    ]
    picked = gaws.pick_diverse_weekly_category_items(pool, "検索・動画", 3)
    labels = [x["label"] for x in picked]
    series = {x["series_key"] for x in picked}
    assert "はてな記事" not in labels
    assert "LoL" not in labels
    assert "Trend A" in labels
    assert "Wiki B" in labels
    assert "YouTube C" in labels
    assert series <= {"google_trends_jp", "wikipedia_ja", "youtube_trends_jp"}


def test_pick_regional_weekly_rising_picks_top_for_active_region(gaws):
    gaws.configure_weekly_region("jp")
    pools = {
        "jp": [
            {"label": "Counter-Strike", "weekly_score": 100, "jump_sum": 12.0},
            {"label": "League of Legends", "weekly_score": 90, "jump_sum": 8.0},
        ],
    }
    out = gaws.pick_regional_weekly_rising(pools)
    assert out["jp"][0]["label"] == "Counter-Strike"
    assert "us" not in out or out.get("us") == []


def test_aggregate_weekly_category_top3_prefers_multi_day(gaws):
    daily = {
        "2026-06-08": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "Topic A",
                        "series_key": "nhk_jp",
                        "rank_display": "7時3位 → 13時2位 → 19時2位",
                        "link_line": "[Topic A](https://example.com/a)",
                    }
                ],
            }
        ],
        "2026-06-09": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "Topic A",
                        "series_key": "nhk_jp",
                        "rank_display": "7時2位 → 13時1位 → 19時1位",
                        "link_line": "[Topic A](https://example.com/a)",
                    },
                    {
                        "label": "Topic B",
                        "series_key": "worldnews_jp",
                        "rank_display": "7時1位 → 13時1位 → 19時1位",
                        "link_line": "[Topic B](https://example.com/b)",
                    },
                ],
            }
        ],
    }
    blocks = gaws.aggregate_weekly_category_top3(daily, count=2)
    news = next(b for b in blocks if b["category"] == "ニュース")
    assert news["items"][0]["label"] == "Topic A"
    assert news["items"][0]["day_count"] == 2
    assert news["items"][0]["best_rank"] == 1


def test_render_weekly_category_markdown_fallback_mechanical(gaws):
    category = {
        "jp": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "Topic A",
                        "day_count": 1,
                        "best_rank": 1,
                        "peak_day": "2026-07-01",
                        "peak_rank_display": "7時1位 → 13時1位 → 19時1位",
                        "rank_display_by_day": {
                            "2026-07-01": "7時1位 → 13時1位 → 19時1位",
                        },
                        "cross_source": True,
                        "link_line": "[Topic A](https://example.com/a)（Google Trends）",
                    }
                ],
                "pool": [],
            }
        ],
        "us": [],
    }
    editorial = {"category_themes": {"jp": {}, "us": {}}}
    md = gaws.render_weekly_category_markdown(category, editorial)
    assert "カテゴリ別 — 先週の top3" in md
    assert "[Topic A](https://example.com/a)" in md
    assert "07-01 1位" in md
    assert " — " not in md.split("#### ニュース")[1].split("###")[0]


def test_resolve_region_category_themes_returns_mechanical_top3(gaws):
    weekly_blocks = [
        {
            "category": "テック・開発",
            "items": [
                {"label": "AI Topic", "best_rank": 1, "day_count": 3, "link_line": "[AI Topic](https://example.com/ai)"},
                {"label": "GitHub Trend", "best_rank": 2, "day_count": 2, "link_line": "[GitHub Trend](https://example.com/gh)"},
                {"label": "Zenn Article", "best_rank": 1, "day_count": 1, "link_line": "[Zenn Article](https://example.com/z)"},
            ],
            "pool": [],
        }
    ]
    editorial = {"category_themes": {"jp": {}, "us": {}}}
    out = gaws.resolve_region_category_themes("jp", editorial, weekly_blocks)
    tech = next(b for b in out if b["category"] == "テック・開発")
    assert len(tech["themes"]) == 3
    assert tech["themes"][0]["items"][0]["label"] == "AI Topic"


def test_format_theme_display_line_uses_source_label(gaws):
    line = gaws.format_theme_display_line(
        {
            "items": [
                {
                    "label": "九州など非常に激しい雨のおそれ",
                    "best_rank": 1,
                    "link_line": "[九州など非常に激しい雨のおそれ](https://example.com/rain)（NHK）",
                }
            ],
        }
    )
    assert line == "[九州など非常に激しい雨のおそれ](https://example.com/rain)（NHK）"


def test_assemble_weekly_markdown_jp_only(gaws):
    gaws.configure_weekly_region("jp")
    mon = date(2026, 6, 8)
    sun = date(2026, 6, 14)
    editorial = {
        "flow_jp": "今週は日本のテスト話題が動いた。",
        "flow_us": "",
        "hot_topics": [
            {"title": "Cat JP", "why": "週を通じて議論が続いた。"},
        ],
        "next_week": ["関税関連が続くか。", "テックのAI記事が残るか。"],
        "category_themes": {"jp": {}, "us": {}},
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
    }
    meta = {"missing_snapshot_dates": [], "partial_snapshot_dates": [], "missing_dates": []}
    category = {
        "jp": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "Cat JP",
                        "day_count": 2,
                        "best_rank": 3,
                        "link_line": "[Cat JP](https://example.com/cat)",
                        "rank_display_by_day": {"2026-06-08": "7時3位 → 13時3位 → 19時3位"},
                    }
                ],
            }
        ],
    }
    md = gaws.assemble_weekly_markdown(
        "2026-W24", mon, sun, editorial, rising, category, meta
    )
    assert "🇯🇵 日本" not in md
    assert "🇺🇸" not in md
    assert "先週の流れ" not in md
    assert "先週いちばん動いた話題" in md
    assert "カテゴリ別 — 先週の top3" in md
    assert "Rising JP" in md
    assert "[Cat JP](https://example.com/cat)" in md
    assert "今週は日本のテスト話題が動いた。" not in md
    assert "週のホットトピック" not in md
    assert "来週に残る論点" not in md
    assert "複数ソースで週を通じて重なった話題" not in md

    md_llm = gaws.assemble_weekly_markdown(
        "2026-W24",
        mon,
        sun,
        editorial,
        rising,
        category,
        meta,
        include_flow=True,
        include_hot_topics=True,
        include_next_week=True,
    )
    assert "先週の流れ" in md_llm
    assert "今週は日本のテスト話題が動いた。" in md_llm
    assert "週のホットトピック" in md_llm
    assert "週を通じて議論が続いた。" in md_llm
    assert "来週に残る論点" in md_llm
    assert "関税関連が続くか。" in md_llm


def test_enrich_hot_topics_with_links_from_rising_and_category(gaws):
    editorial = {
        "hot_topics": [
            {"title": "Rising JP", "why": "jump"},
            {"title": "News A", "why": "hot"},
            {"title": "Unknown", "why": "no link"},
        ]
    }
    rising = {
        "jp": [
            {
                "label": "Rising JP",
                "link_line": "[Rising JP](https://example.com/rise)（App Store · 6位）",
                "url": "https://example.com/rise",
            }
        ]
    }
    category = {
        "jp": [
            {
                "category": "ニュース",
                "pool": [
                    {
                        "label": "News A",
                        "link_line": "[News A](https://example.com/news)（NHK · 1位）",
                        "url": "https://example.com/news",
                    }
                ],
                "items": [],
            }
        ]
    }
    out = gaws.enrich_hot_topics_with_links(editorial, rising, category)
    topics = out["hot_topics"]
    assert topics[0]["link_line"] == "[Rising JP](https://example.com/rise)（App Store）"
    assert topics[1]["link_line"] == "[News A](https://example.com/news)（NHK）"
    assert topics[2]["link_line"] == "Unknown"


def test_assemble_weekly_markdown_us_hot_topic_links(gaws):
    gaws.configure_weekly_region("us")
    mon = date(2026, 6, 8)
    sun = date(2026, 6, 14)
    editorial = {
        "flow_jp": "",
        "flow_us": "Last week U.S. topics moved.",
        "hot_topics": [{"title": "Hot US", "why": "Cross-source all week."}],
        "next_week": ["Watch Fed news."],
        "category_themes": {"jp": {}, "us": {}},
    }
    rising = {"us": []}
    category = {
        "us": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "Hot US",
                        "link_line": "[Hot US](https://example.com/us-hot)（World News (US)）",
                        "url": "https://example.com/us-hot",
                    }
                ],
                "pool": [
                    {
                        "label": "Hot US",
                        "link_line": "[Hot US](https://example.com/us-hot)（World News (US)）",
                        "url": "https://example.com/us-hot",
                    }
                ],
            }
        ]
    }
    meta = {"missing_snapshot_dates": [], "partial_snapshot_dates": [], "missing_dates": []}
    md = gaws.assemble_weekly_markdown(
        "2026-W24", mon, sun, editorial, rising, category, meta
    )
    assert "[Hot US](https://example.com/us-hot)" in md
    assert "Why hot" not in md
    assert "Hot topics last week" not in md
    gaws.configure_weekly_region("jp")


def test_weekly_rising_filters_flat_jump(gaws):
    pools = {
        "jp": [
            {"label": "Flat", "jump_sum": 1.0},
            {"label": "Real Move", "jump_sum": 12.0},
        ],
    }
    out = gaws.pick_regional_weekly_rising(pools)
    assert len(out["jp"]) == 1
    assert out["jp"][0]["label"] == "Real Move"


def test_parse_editorial_json_hot_and_next(gaws):
    raw = json.dumps(
        {
            "flow_jp": "流れ。",
            "hot_topics": [{"title": "A", "why": "理由"}],
            "next_week": ["論点1", "論点2"],
        },
        ensure_ascii=False,
    )
    gaws.configure_weekly_region("jp")
    data = gaws.parse_editorial_json(raw)
    assert data["flow_jp"] == "流れ。"
    assert data["hot_topics"][0]["title"] == "A"
    assert data["next_week"] == ["論点1", "論点2"]


def test_assemble_weekly_markdown_us_english(gaws):
    gaws.configure_weekly_region("us")
    mon = date(2026, 6, 8)
    sun = date(2026, 6, 14)
    editorial = {
        "flow_jp": "",
        "flow_us": "U.S. tech topics moved this week.",
        "hot_topics": [{"title": "Hot US", "why": "Cross-source all week."}],
        "next_week": ["Watch Fed news."],
        "category_themes": {"jp": {}, "us": {}},
    }
    rising = {
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
    category = {"us": []}
    meta = {"missing_snapshot_dates": [], "partial_snapshot_dates": [], "missing_dates": []}
    md = gaws.assemble_weekly_markdown(
        "2026-W24", mon, sun, editorial, rising, category, meta
    )
    assert "Weekly summary" in md
    assert "Last week in review" not in md
    assert "Biggest movers last week" in md
    assert "Hot topics last week" not in md
    assert "What to watch next week" not in md
    assert "来週に残る論点" not in md
    assert "ソース一覧" not in md

    md_llm = gaws.assemble_weekly_markdown(
        "2026-W24",
        mon,
        sun,
        editorial,
        rising,
        category,
        meta,
        include_flow=True,
        include_hot_topics=True,
        include_next_week=True,
    )
    assert "Last week in review" in md_llm
    assert "U.S. tech topics moved this week." in md_llm
    assert "Hot topics last week" in md_llm
    assert "What to watch next week" in md_llm
    assert "週のホットトピック" not in md
    gaws.configure_weekly_region("jp")  # restore for other tests


def test_openai_api_key_accepts_open_api_key_env(monkeypatch, gaws):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_API_KEY", "sk-test")
    assert gaws.openai_api_key() == "sk-test"


def test_openai_api_key_prefers_openai_api_key(monkeypatch, gaws):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-primary")
    monkeypatch.setenv("OPEN_API_KEY", "sk-fallback")
    assert gaws.openai_api_key() == "sk-primary"


def test_build_mechanical_llm_payload_active_region_only(gaws):
    gaws.configure_weekly_region("jp")
    rising = {
        "jp": [{"label": "JP Topic", "day_count": 1, "jump_sum": 5.0, "days": ["2026-06-08"]}],
    }
    cross = {"jp": []}
    category = {
        "jp": [{"category": "ニュース", "items": [{"label": "JP Cat"}], "pool": [], "quiet": False}],
    }
    payload = gaws.build_mechanical_llm_payload(rising, cross, category)
    assert "regions" in payload
    assert payload["regions"]["jp"]["weekly_rising"][0]["label"] == "JP Topic"
    assert "us" not in payload["regions"]
    assert payload["regions"]["jp"]["weekly_category_pool"][0]["category"] == "ニュース"


def test_build_mechanical_weekly_preview_lead_prefers_rising(gaws):
    gaws.configure_weekly_region("jp")
    lead = gaws.build_mechanical_weekly_preview_lead(
        {"jp": [{"label": "Topic A", "day_count": 3, "days": ["a", "b", "c"]}]},
        {"jp": []},
    )
    assert "Topic A" in lead
    assert "3日" in lead


def test_run_generate_mechanical_includes_flow_and_hot(gaws, monkeypatch):
    gaws.configure_weekly_region("jp")
    week_mon = date(2026, 6, 8)
    meta_base = {
        "snapshot_days_found": 7,
        "missing_snapshot_dates": [],
        "partial_snapshot_dates": [],
        "missing_dates": [],
        "daily_files": [{"found": True}] * 7,
    }
    rising = {
        "jp": [
            {
                "label": "Rising JP",
                "link_line": "[Rising JP](https://example.com/jp)",
                "day_count": 3,
                "days": ["2026-06-08", "2026-06-09", "2026-06-10"],
                "series_key": "google_trends_jp",
                "rank_evidence_by_day": {},
            }
        ]
    }
    category = {
        "jp": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "News Hot",
                        "day_count": 4,
                        "days": ["a", "b", "c", "d"],
                        "series_key": "nhk_jp",
                        "cross_source": True,
                        "best_rank": 1,
                        "link_line": "[News Hot](https://example.com/news)",
                    }
                ],
                "quiet": False,
            }
        ]
    }
    monkeypatch.setattr(
        gaws,
        "build_week_snapshot_rollups",
        lambda *a, **k: (meta_base, rising, {"jp": []}, category),
    )
    monkeypatch.setattr(
        gaws,
        "build_daily_rollups",
        lambda *a, **k: ("", {"missing_dates": []}),
    )
    monkeypatch.setattr(
        "services.summary.morning_brief.render_weekly_brief_markdown",
        lambda *a, **k: "## 🗓 今週のカレンダー\n\n**今週** test\n\n---\n",
    )
    text, meta = gaws.run_generate_mechanical(
        week_mon,
        gaws.DAILY_DIR,
        via_http=True,
        database_url="",
        base_url="https://example.com",
        connect_timeout=5,
        request_timeout=5,
    )
    assert meta["generator"] == "mechanical"
    assert "generator: mechanical" in text
    assert "preview_lead:" in text
    assert "生成・送信完了" not in text
    assert "time not filled" not in text
    body = text.split("---", 2)[-1]
    assert "先週の流れ" in body
    assert "Rising JP" in body
    assert "週のホットトピック" in body
    assert "News Hot" in body
    assert "先週いちばん動いた話題" in body
    assert "今週のカレンダー" in text
    # オープナー → 流れ の順
    assert text.index("今週のカレンダー") < text.index("先週の流れ")


def test_merge_front_matter_mechanical_weekly(gaws):
    meta = {
        "input_mode": "snapshots",
        "snapshot_days_found": 7,
        "missing_snapshot_dates": [],
        "partial_snapshot_dates": [],
        "missing_dates": [],
        "daily_files": [],
    }
    full = gaws.merge_front_matter(
        "2026-W24",
        date(2026, 6, 8),
        date(2026, 6, 14),
        "",
        "# 週次サマリー\n",
        meta,
        teaser="短い週次",
        preview_lead="先週の機械リード全文。",
        generator="mechanical",
    )
    assert "generator: mechanical" in full
    assert 'preview_lead: "先週の機械リード全文。"' in full
    assert "model:" not in full.split("---")[1]


def test_aggregate_weekly_rising_skips_appstore(gaws):
    daily = {
        "2026-06-08": [
            {
                "label": "Some App",
                "series_key": "appstore_jp",
                "jump": 20.0,
                "freq_slots": 3,
                "ranks": {"07": 10, "13": 1},
            },
            {
                "label": "News Topic",
                "series_key": "nhk_jp",
                "jump": 8.0,
                "freq_slots": 2,
                "ranks": {"07": 5, "13": 2},
            },
        ]
    }
    out = gaws.aggregate_weekly_rising(daily, count=5)
    labels = [x["label"] for x in out]
    assert "Some App" not in labels
    assert "News Topic" in labels


def test_build_mechanical_weekly_flow_and_hot_topics(gaws):
    gaws.configure_weekly_region("jp")
    rising = {
        "jp": [
            {
                "label": "Rising JP",
                "day_count": 3,
                "days": ["a", "b", "c"],
                "series_key": "google_trends_jp",
            }
        ]
    }
    category = {
        "jp": [
            {
                "category": "ニュース",
                "items": [
                    {
                        "label": "News Hot",
                        "day_count": 4,
                        "series_key": "nhk_jp",
                        "cross_source": True,
                        "best_rank": 1,
                    },
                    {
                        "label": "Skip App",
                        "day_count": 5,
                        "series_key": "appstore_jp",
                        "cross_source": False,
                        "best_rank": 1,
                    },
                ],
            }
        ]
    }
    flow = gaws.build_mechanical_weekly_flow(rising, category)
    assert "Rising JP" in flow
    assert "News Hot" in flow
    assert "Skip App" not in flow
    hot = gaws.build_mechanical_weekly_hot_topics(rising, category)
    titles = [h["title"] for h in hot]
    assert "News Hot" in titles
    assert "Skip App" not in titles
    assert all("why" in h for h in hot)


def test_script_imports_when_run_as_python_scripts_path():
    """GHA は `python scripts/generate_ai_weekly_summary.py`。sys.path[0] は scripts/。"""
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        cwd=_SCRIPT.resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--from-api" in result.stdout

