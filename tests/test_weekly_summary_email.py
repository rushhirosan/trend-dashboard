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
