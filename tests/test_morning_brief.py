"""Tests for services.summary.morning_brief."""

from datetime import date
from unittest.mock import patch

from services.summary.morning_brief import (
    MorningBriefLines,
    _extract_tounou_article_lines,
    _format_jp_proverb_line,
    _meaning_from_tounou_lines,
    _select_tounou_item_for_day,
    build_calendar_line,
    build_jp_proverb_line,
    build_morning_brief_lines,
    delivery_day_for_business_day,
    render_morning_brief_markdown,
    WeeklyBriefLines,
    build_week_calendar_line,
    delivery_week_for_observation_week,
    render_weekly_brief_markdown,
)

SAMPLE_TOUNOU_HTML = """
<div class="entry-content">
<p>新井正明（日本の実業家・1912-2003・住友生命保険元会長）</p>
<p>２７歳の時に戦場で負った傷が原因で、右足を切断されています。</p>
<p>嫌な事、辛い事を経験することが自分を研ぎ澄まし、</p>
<p>メルマガ「10秒で読める名言集」より</p>
<!-- .entry-content -->
</div>
"""


def test_delivery_day_is_business_day_plus_one():
    assert delivery_day_for_business_day(date(2026, 8, 21)) == date(2026, 8, 22)


def test_build_calendar_line_jp_next_holiday():
    day = date(2026, 8, 22)  # Saturday
    holidays = {
        "2026-09-21": "敬老の日",
        "2026-09-23": "秋分の日",
    }

    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(day, "jp")

    assert line.startswith("**カレンダー** 土曜")
    assert "次の祝日は 9/21（月）敬老の日" in line


def test_build_calendar_line_jp_today_holiday():
    day = date(2026, 8, 11)
    holidays = {"2026-08-11": "山の日"}

    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(day, "jp")

    assert "今日は 8/11（火）山の日（祝日）" in line


def test_build_calendar_line_us_next_holiday():
    day = date(2026, 8, 22)
    holidays = {"2026-09-07": "Labor Day"}

    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(day, "us")

    assert "**Calendar** Saturday" in line
    assert "Next holiday: 9/7 (Mon) Labor Day" in line


def test_extract_tounou_article_lines_and_meaning():
    lines = _extract_tounou_article_lines(SAMPLE_TOUNOU_HTML)
    assert lines[0].startswith("新井正明")
    meaning = _meaning_from_tounou_lines(lines)
    assert meaning is not None
    assert "右足" in meaning


def test_format_jp_proverb_line():
    line = _format_jp_proverb_line(
        "急がば回れ",
        "慌てず確実な道を選ぶ方が、結果的に早い",
    )
    assert line == (
        "**格言** 「急がば回れ」 — 慌てず確実な道を選ぶ方が、"
        "結果的に早い（10秒名言）"
    )


def test_select_tounou_item_for_day_is_stable():
    items = [{"title": "A", "link": "1"}, {"title": "B", "link": "2"}]
    d = date(2026, 8, 22)
    assert _select_tounou_item_for_day(items, d) == _select_tounou_item_for_day(items, d)


def test_build_jp_proverb_line_from_tounou():
    items = [
        {
            "title": "急がば回れ",
            "link": "https://meigen.tounou.net/?p=1",
        }
    ]

    with patch(
        "services.summary.morning_brief._fetch_tounou_rss_items",
        return_value=items,
    ), patch(
        "services.summary.morning_brief._fetch_tounou_meaning",
        return_value="慌てず確実な道を選ぶ方が、結果的に早い",
    ):
        line = build_jp_proverb_line(date(2026, 8, 22))

    assert line is not None
    assert "（10秒名言）" in line
    assert "急がば回れ" in line
    assert "慌てず" in line


def test_render_morning_brief_markdown_jp():
    lines = MorningBriefLines(
        calendar="**カレンダー** 金曜 · 次の祝日は 9/21（月）敬老の日",
        fx="**為替** USD/JPY 154.2（前日終値比 +0.3）",
        stock="**株** 日経 38,420（前日終値 -0.4%）",
        history="**歴史** 697年 — 文武天皇が譲位（Wikipedia）",
        breath_second=(
            "**格言** 「急がば回れ」— 慌てず確実な道を選ぶ方が、"
            "結果的に早い（10秒名言）"
        ),
    )
    md = render_morning_brief_markdown(
        date(2026, 8, 21),
        "jp",
        lines=lines,
    )
    assert "## 🗓 今日どう動くか" in md
    assert "## 💹 マーケット（前日まで）" in md
    assert "## ☕ ひと息（歴史 + 格言）" in md
    assert "（10秒名言）" in md
    assert md.rstrip().endswith("---")


def test_render_morning_brief_markdown_us():
    lines = MorningBriefLines(
        calendar="**Calendar** Friday · Next holiday: 9/1 (Mon) Labor Day",
        fx="**FX** USD/JPY 154.2 (+0.3 vs prior close)",
        stock="**Stocks** S&P 500 closed at 5,234.18 (-0.4%)",
        history="**On this day** 1962 — sample event (Wikipedia)",
        breath_second='**Quote** "Sample quote." — Author (ZenQuotes)',
    )
    md = render_morning_brief_markdown(
        date(2026, 8, 21),
        "us",
        lines=lines,
    )
    assert "## 🗓 Today at a glance" in md
    assert "## ☕ A breath (history + quote)" in md
    assert "**Quote**" in md


def test_build_morning_brief_lines_skips_market_when_disabled(monkeypatch):
    monkeypatch.setenv("MORNING_BRIEF_SKIP_MARKET", "true")
    with patch(
        "services.summary.morning_brief.build_calendar_line",
        return_value="**カレンダー** 金曜",
    ), patch(
        "services.summary.morning_brief.build_history_line",
        return_value=None,
    ), patch(
        "services.summary.morning_brief.build_breath_second_line",
        return_value=None,
    ), patch(
        "services.summary.morning_brief.build_market_lines",
    ) as market_mock:
        lines = build_morning_brief_lines(date(2026, 8, 21), "jp")
    market_mock.assert_not_called()
    assert lines.fx is None
    assert lines.stock is None


def test_delivery_week_follows_observation_sunday():
    mon, sun = delivery_week_for_observation_week(date(2026, 8, 16))
    assert mon == date(2026, 8, 17)
    assert sun == date(2026, 8, 23)


def test_build_week_calendar_line_lists_holidays_in_delivery_week():
    week_mon = date(2026, 9, 21)
    week_sun = date(2026, 9, 27)
    holidays = {
        "2026-09-21": "敬老の日",
        "2026-09-23": "秋分の日",
        "2026-10-12": "スポーツの日",
    }
    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_week_calendar_line(week_mon, week_sun, "jp")
    assert "**今週**" in line
    assert "敬老の日" in line
    assert "秋分の日" in line
    assert "スポーツの日" not in line


def test_render_weekly_brief_markdown_sections():
    lines = WeeklyBriefLines(
        calendar="**今週** 8/17（月）〜8/23（日） · 祝日なし",
        fx="**為替** USD/JPY 150.0（週次 +0.5%）",
        stock="**株** 日経 40000（週次 -1.2%）",
        history="**歴史** 1868年 — 例",
        breath_second="**格言** 「例」（10秒名言）",
    )
    md = render_weekly_brief_markdown(
        date(2026, 8, 10),
        date(2026, 8, 16),
        "jp",
        lines=lines,
    )
    assert "## 🗓 今週のカレンダー" in md
    assert "## 💹 マーケット（先週）" in md
    assert "## ☕ ひと息（歴史 + 格言）" in md

