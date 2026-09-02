"""Tests for services.summary.morning_brief."""

from datetime import date
from unittest.mock import patch

from services.summary.morning_brief import (
    MorningBriefLines,
    _author_from_tounou_lines,
    _extract_tounou_article_lines,
    _format_en_on_this_day_line,
    _format_jp_history_line,
    _format_jp_proverb_line,
    _meaning_from_tounou_lines,
    _select_tounou_item_for_day,
    _split_jp_history_year,
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

    assert line.startswith("**8/22（土）**")
    assert "カレンダー" not in line
    assert "次の祝日は 9/21（月）敬老の日" in line


def test_build_calendar_line_jp_today_holiday():
    day = date(2026, 8, 11)
    holidays = {"2026-08-11": "山の日"}

    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(day, "jp")

    assert line.startswith("**8/11（火）**")
    assert "山の日（祝日）" in line
    assert "カレンダー" not in line


def test_build_calendar_line_us_next_holiday():
    day = date(2026, 8, 22)
    holidays = {"2026-09-07": "Labor Day"}

    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(day, "us")

    assert line.startswith("**8/22 (Sat)**")
    assert "Calendar" not in line
    assert "Next holiday: 9/7 (Mon) Labor Day" in line


def test_build_calendar_line_includes_observation_day():
    day = date(2026, 8, 25)
    holidays = {"2026-09-21": "敬老の日"}
    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(
            day, "jp", observation_day=date(2026, 8, 24)
        )
    assert line.startswith("**8/25（火）**")
    assert "サマリー生成対象日 8/24" in line
    assert "観測 " not in line
    assert "次の祝日は 9/21（月）敬老の日" in line


def test_build_calendar_line_includes_summary_date_us():
    day = date(2026, 8, 25)
    holidays = {"2026-09-07": "Labor Day"}
    with patch(
        "services.summary.morning_brief._holiday_map_for_day",
        return_value=holidays,
    ):
        line = build_calendar_line(
            day, "us", observation_day=date(2026, 8, 24)
        )
    assert line.startswith("**8/25 (Tue)**")
    assert "Summary date 8/24" in line
    assert "Observed " not in line
    assert "Next holiday: 9/7 (Mon) Labor Day" in line


def test_format_en_on_this_day_uses_api_year_and_calendar_day():
    line = _format_en_on_this_day_line(
        date(2026, 8, 23),
        "A 5.8 MW earthquake struck the Piedmont region of Virginia, "
        "and was felt by more people than any other quake in U.S. history.",
        year=2011,
    )
    assert line is not None
    assert line.startswith("**On this day** Aug 23, 2011 — ")
    assert "earthquake" in line
    assert "(Wikipedia)" in line


def test_format_en_on_this_day_does_not_clip_mid_word():
    line = _format_en_on_this_day_line(
        date(2026, 8, 25),
        "The NASA space probe Voyager 1 became the first man-made object "
        "to enter interstellar space.",
        year=2012,
    )
    assert line is not None
    assert "man-ma…" not in line
    assert "Voyager 1" in line
    assert "man-made" in line
    assert line.endswith("(Wikipedia)")


def test_format_en_on_this_day_without_year_still_shows_month_day():
    line = _format_en_on_this_day_line(
        date(2026, 8, 23),
        "A 5.8 MW earthquake struck the Piedmont region of Virginia.",
    )
    assert line is not None
    assert "Aug 23" in line
    assert "2011" not in line


def test_format_jp_history_line_includes_month_day_and_year():
    line = _format_jp_history_line(
        date(2026, 8, 23),
        "1059",
        "ローマ教皇がノルマン人を諸侯に任命",
    )
    assert line == (
        "**歴史** 8/23 · 1059年 — ローマ教皇がノルマン人を諸侯に任命（Wikipedia）"
    )


def test_split_jp_history_year_keeps_bce_prefix():
    year, rest = _split_jp_history_year(
        "紀元前44年 - キケロが初のピリッピカ"
    )
    assert year == "紀元前44"
    assert rest == "キケロが初のピリッピカ"
    line = _format_jp_history_line(date(2026, 9, 2), year, rest)
    assert line == (
        "**歴史** 9/2 · 紀元前44年 — キケロが初のピリッピカ（Wikipedia）"
    )


def test_split_jp_history_year_short_mae_prefix_is_bce():
    year, rest = _split_jp_history_year("前44年 - キケロが初のピリッピカ")
    assert year == "紀元前44"
    assert rest == "キケロが初のピリッピカ"


def test_split_jp_history_year_ce_has_no_era_prefix():
    year, rest = _split_jp_history_year("1059年 — ローマ教皇がノルマン人を諸侯に任命")
    assert year == "1059"
    assert rest == "ローマ教皇がノルマン人を諸侯に任命"


def test_extract_tounou_article_lines_and_meaning():
    lines = _extract_tounou_article_lines(SAMPLE_TOUNOU_HTML)
    assert lines[0].startswith("新井正明")
    meaning = _meaning_from_tounou_lines(lines)
    assert meaning is not None
    assert "右足" in meaning
    assert _author_from_tounou_lines(lines) == "新井正明"


def test_author_from_tounou_lines_without_bio_parens():
    assert _author_from_tounou_lines(["コピーライター吉田一馬"]) == "コピーライター吉田一馬"


def test_author_from_tounou_lines_rejects_commentary():
    assert (
        _author_from_tounou_lines(
            ["２０１６年に東京大学で行わた、マウスを迷路に入れた実験で、"]
        )
        is None
    )


def test_format_jp_proverb_line():
    line = _format_jp_proverb_line(
        "急がば回れ",
        author="新井正明",
    )
    assert line == "**格言** 「急がば回れ」 — 新井正明（10秒名言）"


def test_format_jp_proverb_line_prefers_author_over_meaning():
    quote = (
        "ぼくはキャリアを通じて9000回以上のシュートをはずした。"
        "300回近い試合に負けた。勝敗を決するシュートを託され、"
        "失敗したことは26回ある。人生で何度も失敗を重ねてきた。だから成功できた。"
    )
    line = _format_jp_proverb_line(
        quote,
        meaning="２０１６年に東京大学で行わた、マウスを迷路に入れた実験で、",
        author="マイケル・ジョーダン",
    )
    assert line == f"**格言** 「{quote}」 — マイケル・ジョーダン（10秒名言）"
    assert "…" not in line
    assert "マウス" not in line


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
        "services.summary.morning_brief._fetch_tounou_speaker",
        return_value="新井正明",
    ):
        line = build_jp_proverb_line(date(2026, 8, 22))

    assert line == "**格言** 「急がば回れ」 — 新井正明（10秒名言）"


def test_render_morning_brief_markdown_jp():
    lines = MorningBriefLines(
        calendar="**8/21（金）** · サマリー生成対象日 8/20 · 次の祝日は 9/21（月）敬老の日",
        fx="**為替** USD/JPY 154.2（前日終値比 +0.3）",
        stock="**株** 日経 38,420（前日終値 -0.4%）",
        history="**歴史** 8/21 · 697年 — 文武天皇が譲位（Wikipedia）",
        breath_second="**格言** 「急がば回れ」 — 新井正明（10秒名言）",
    )
    md = render_morning_brief_markdown(
        date(2026, 8, 21),
        "jp",
        lines=lines,
    )
    assert "## 🗓 今日のカレンダー" in md
    assert "## 💹 マーケット（前日まで）" in md
    assert "## ☕ ひと息（歴史 + 格言）" in md
    assert "（10秒名言）" in md
    assert md.rstrip().endswith("---")


def test_render_morning_brief_markdown_us():
    lines = MorningBriefLines(
        calendar="**8/21 (Fri)** · Summary date 8/20 · Next holiday: 9/1 (Mon) Labor Day",
        fx="**FX** USD/JPY 154.2 (+0.3 vs prior close)",
        stock="**Stocks** S&P 500 closed at 5,234.18 (-0.4%)",
        history="**On this day** Aug 21, 1962 — sample event (Wikipedia)",
        breath_second='**Quote** "Sample quote." — Author (ZenQuotes)',
    )
    md = render_morning_brief_markdown(
        date(2026, 8, 21),
        "us",
        lines=lines,
    )
    assert "## 🗓 Today's calendar" in md
    assert "## ☕ A breath (history + quote)" in md
    assert "**Quote**" in md


def test_build_morning_brief_lines_skips_market_when_disabled(monkeypatch):
    monkeypatch.setenv("MORNING_BRIEF_SKIP_MARKET", "true")
    with patch(
        "services.summary.morning_brief.build_calendar_line",
        return_value="**8/21（金）** · サマリー生成対象日 8/20",
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
        history="**歴史** 8/12 · 1868年 — 例",
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

