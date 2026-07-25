"""Tests for services/summary/weekly_summary_email.py."""

from services.summary.weekly_summary_email import (
    strip_legacy_weekly_charts,
    weekly_markdown_to_email_html,
    weekly_markdown_to_email_text,
)

_SAMPLE = """---
status: approved
iso_week: "2026-W26"
---

# 週次サマリー

![chart](_charts/2026-W26/jp-01.svg)

| 日 | 07 | 13 | 19 |
|:--:|:-:|:-:|:-:|
| 06-24 | 8 | — | 2 |

> **日別ベスト順位**（上ほど良い）: 06-24 (2位) → 06-26 (1位) ↑
"""


def test_strip_legacy_weekly_charts_removes_images():
    out = strip_legacy_weekly_charts(_SAMPLE)
    assert "![chart]" not in out
    assert "**日別ベスト順位**" in out
    assert "| 06-24 |" in out


def test_weekly_markdown_to_email_text_has_no_attachments_markers():
    text = weekly_markdown_to_email_text(_SAMPLE)
    assert "![chart]" not in text
    assert "06-24 (2位)" in text
    assert "status: approved" not in text


def test_weekly_markdown_to_email_html_is_inline_only():
    html = weekly_markdown_to_email_html(_SAMPLE)
    assert "<img" not in html
    assert "06-24 (2位)" in html
    assert "<table>" in html
    assert "<strong>" in html  # **日別ベスト順位**


def test_weekly_markdown_to_email_html_has_anchor_links():
    md = """---
status: draft
---

1. [PAYDAY 3](https://www.google.com/search?q=PAYDAY+3)（Twitch）
"""
    html = weekly_markdown_to_email_html(md)
    assert '<a href="https://www.google.com/search?q=PAYDAY+3">PAYDAY 3</a>' in html
    assert "PAYDAY 3 (https://" not in html


def test_weekly_flow_inserts_breaks_after_japanese_periods():
    md = """---
status: draft
---

## 今週の流れ（短文）

今週はAが注目を集めました。また、Bが話題となりました。検索ではCが急上昇し、1位を記録。エンタメではDが注目を集めました。
"""
    html = weekly_markdown_to_email_html(md)
    assert "集めました。<br>" in html
    assert "なりました。<br>" in html
    # 「記録。」のあとも改行（句点）
    assert "記録。<br>" in html
    text = weekly_markdown_to_email_text(md)
    assert "集めました。\nまた、" in text


def test_list_item_period_not_broken():
    md = "1. タイトルです\n"
    html = weekly_markdown_to_email_html(md)
    assert "1.<br>" not in html
    assert "1. タイトルです" in html


def test_email_html_skips_duplicate_leading_h1():
    md = """---
status: draft
---

# 日次サマリー — 2026-07-22（JST）

## 昨日の一行結論

本文です。
"""
    html = weekly_markdown_to_email_html(md, title="日次サマリー — 2026-07-22 (JP)")
    assert html.count("<h1>") == 1
    assert "日次サマリー — 2026-07-22 (JP)" in html
    assert "（JST）" not in html
    assert "昨日の一行結論" in html


def test_email_strips_category_trend_blurbs():
    md = """### テック・開発
**昨日の傾向**: WordPressが話題です。

1. [A](https://ex.com)
"""
    html = weekly_markdown_to_email_html(md)
    assert "昨日の傾向" not in html
    assert "WordPressが話題" not in html
    assert "テック・開発" in html


def test_email_strips_redundant_header_meta():
    md = """# 日次サマリー — 2026-07-24（JST）
- **対象（観測日）**: 2026年7月24日
- **生成・送信完了**: 自動生成（時刻未入力）

## 昨日の一行結論

本文。
"""
    html = weekly_markdown_to_email_html(md, title="日次サマリー — 2026-07-24 (JP)")
    assert "対象（観測日）" not in html
    assert "生成・送信完了" not in html
    assert "昨日の一行結論" in html
