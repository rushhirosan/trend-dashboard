"""Tests for weekly category theme rendering (scripts/generate_ai_weekly_summary.py)."""

import importlib.util
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


def test_merge_theme_rank_by_day_combines_labels(gaws):
    merged = gaws.merge_theme_rank_by_day(
        [
            {
                "rank_display_by_day": {
                    "2026-07-01": "7時1位 → 13時1位 → 19時1位",
                }
            },
            {
                "rank_display_by_day": {
                    "2026-07-03": "7時1位 → 13時2位 → 19時2位",
                }
            },
        ]
    )
    assert "2026-07-01" in merged
    assert "2026-07-03" in merged


def test_resolve_region_category_themes_uses_mechanical_labels(gaws):
    blocks = [
        {
            "category": "ニュース",
            "items": [
                {
                    "label": "Rain headline A",
                    "best_rank": 1,
                    "link_line": "[Rain headline A](https://example.com/a)（NHK）",
                    "rank_display_by_day": {"2026-07-01": "7時1位 → 13時1位 → 19時1位"},
                },
                {
                    "label": "Rain headline B",
                    "best_rank": 1,
                    "link_line": "[Rain headline B](https://example.com/b)（NHK）",
                    "rank_display_by_day": {"2026-07-03": "7時1位 → 13時1位 → 19時1位"},
                },
            ],
            "pool": [],
        }
    ]
    editorial = {
        "category_themes": {
            "jp": {
                "ニュース": [
                    {
                        "title": "九州北部の豪雨",
                        "labels": ["Rain headline A", "Rain headline B"],
                    }
                ]
            },
            "us": {},
        }
    }
    out = gaws.resolve_region_category_themes("jp", editorial, blocks)
    assert len(out) == 1
    assert len(out[0]["themes"]) == 2
    assert out[0]["themes"][0]["items"][0]["label"] == "Rain headline A"


def test_render_weekly_category_markdown_shows_concrete_link(gaws):
    category = {
        "jp": [
            {
                "category": "エンタメ・ショッピング",
                "items": [
                    {
                        "label": "最終絶叫計画 令和！",
                        "best_rank": 3,
                        "link_line": "[最終絶叫計画 令和！](https://example.com/movie)（映画）",
                        "rank_display_by_day": {
                            "2026-07-05": "7時3位 → 13時3位 → 19時3位",
                        },
                    }
                ],
                "pool": [],
            }
        ],
        "us": [],
    }
    editorial = {"category_themes": {"jp": {}, "us": {}}}
    md = gaws.render_weekly_category_markdown(category, editorial)
    assert "[最終絶叫計画 令和！](https://example.com/movie)" in md
    assert "映画と音楽のトレンド" not in md
    assert "07-05 3位" in md


def test_format_theme_display_line_never_uses_abstract_title(gaws):
    line = gaws.format_theme_display_line(
        {
            "title": "エンタメの話題",
            "items": [
                {
                    "label": "最終絶叫計画 令和！",
                    "best_rank": 3,
                    "link_line": "[最終絶叫計画 令和！](https://example.com/movie)（映画）",
                }
            ],
        }
    )
    assert line == "[最終絶叫計画 令和！](https://example.com/movie)（映画）"


def test_parse_editorial_json_category_themes_optional(gaws):
    gaws.configure_weekly_region("jp")
    raw = """{
      "flow_jp": "jp flow"
    }"""
    data = gaws.parse_editorial_json(raw)
    assert data["flow_jp"] == "jp flow"
    assert data["category_themes"]["jp"] == {}


def test_parse_editorial_json_us_flow(gaws):
    gaws.configure_weekly_region("us")
    raw = """{"flow_us": "us flow english"}"""
    data = gaws.parse_editorial_json(raw)
    assert data["flow_us"] == "us flow english"
    gaws.configure_weekly_region("jp")
