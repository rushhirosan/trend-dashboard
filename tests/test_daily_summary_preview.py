"""daily_summary_preview のユニットテスト"""

from datetime import date
from pathlib import Path

from services.summary.daily_summary_preview import (
    DailySummaryPreview,
    clamp_teaser,
    extract_one_liner,
    first_sentence,
    load_latest_daily_preview,
    preview_for_fake_door,
    teaser_for_display,
)

SAMPLE = """---
status: draft
business_day: "2026-06-10"
generator: openai
snapshot_slots_included: ["07", "13", "19", "01"]
---

# 日次サマリー — 2026-06-10（JST）

## 昨日の一行結論

かつお節の話が一日を通して上位に。順位の動きが大きかったのは「AXIS CAMERAS」。

## 昨日の見どころ（3〜5）

### 1. 見出し
"""

# 旧見出し（今日の一行結論）でも拾えることを担保する後方互換用サンプル。
SAMPLE_LEGACY_HEADING = SAMPLE.replace(
    "## 昨日の一行結論", "## 今日の一行結論", 1
)

SAMPLE_WITH_TEASER = """---
status: draft
business_day: "2026-06-10"
generator: openai
teaser: "かつお節の話が一日を通して上位に。"
snapshot_slots_included: ["07", "13", "19", "01"]
---

# 日次サマリー — 2026-06-10（JST）

## 昨日の一行結論

かつお節の話が一日を通して上位に。順位の動きが大きかったのは「AXIS CAMERAS」。

## 昨日の見どころ（3〜5）

### 1. 見出し
"""

SAMPLE_APPROVED = SAMPLE.replace("status: draft", "status: approved", 1)


def test_extract_one_liner_new_heading():
    sample = SAMPLE.replace("## 昨日の一行結論", "## 昨日の注目", 1)
    assert extract_one_liner(sample) == (
        "かつお節の話が一日を通して上位に。順位の動きが大きかったのは「AXIS CAMERAS」。"
    )


def test_extract_one_liner():
    assert extract_one_liner(SAMPLE) == (
        "かつお節の話が一日を通して上位に。順位の動きが大きかったのは「AXIS CAMERAS」。"
    )


def test_extract_one_liner_legacy_heading():
    assert extract_one_liner(SAMPLE_LEGACY_HEADING) == (
        "かつお節の話が一日を通して上位に。順位の動きが大きかったのは「AXIS CAMERAS」。"
    )


def test_first_sentence():
    long = "一文目です。二文目です。"
    assert first_sentence(long) == "一文目です。"


def test_teaser_for_display_prefers_frontmatter_teaser():
    assert teaser_for_display("全文。", teaser="短いティーザー。") == "短いティーザー。"


def test_teaser_for_display_falls_back_to_first_sentence():
    assert teaser_for_display(
        "かつお節の話が一日を通して上位に。他の話題も続く。"
    ) == "かつお節の話が一日を通して上位に。"


def test_clamp_teaser():
    assert clamp_teaser("あ" * 100) == ("あ" * 89) + "…"


def test_load_latest_from_tmp_dir(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-09.md").write_text(
        SAMPLE.replace("2026-06-10", "2026-06-09").replace("かつお節", "古い話題"),
        encoding="utf-8",
    )
    (daily / "2026-06-10.md").write_text(SAMPLE, encoding="utf-8")
    preview = load_latest_daily_preview(
        daily_dir=daily, delivery_day=date(2026, 6, 11), allow_draft=True
    )
    assert preview is not None
    assert preview.business_day == date(2026, 6, 10)
    assert preview.delivery_day == date(2026, 6, 11)
    assert "かつお節" in preview.one_liner
    assert preview.display_teaser() == "かつお節の話が一日を通して上位に。"


def test_load_teaser_from_frontmatter(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-10.md").write_text(SAMPLE_WITH_TEASER, encoding="utf-8")
    preview = load_latest_daily_preview(
        daily_dir=daily, delivery_day=date(2026, 6, 11), allow_draft=True
    )
    assert preview is not None
    assert preview.teaser == "かつお節の話が一日を通して上位に。"
    assert preview.display_teaser() == "かつお節の話が一日を通して上位に。"


def test_headline_ja():
    p = DailySummaryPreview(
        business_day=date(2026, 6, 10),
        delivery_day=date(2026, 6, 11),
        one_liner="x",
        teaser="",
        snapshot_slots=("07", "13", "19", "01"),
        status="draft",
    )
    assert p.headline_ja() == "日次 6/11 — 昨日（6/10）のトレンド"
    assert p.subline_ja() == "日次 6/11 — 昨日（6/10）のトレンド（07/13/19/01 反映）"


def test_headline_ja_when_summary_is_stale():
    p = DailySummaryPreview(
        business_day=date(2026, 6, 10),
        delivery_day=date(2026, 6, 12),
        one_liner="x",
        teaser="",
        snapshot_slots=("07", "13", "19", "01"),
        status="draft",
    )
    assert p.headline_ja() == "日次 6/12 — 6/10のトレンド"


def test_load_latest_skips_draft_when_not_allowed(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-10.md").write_text(SAMPLE, encoding="utf-8")
    assert load_latest_daily_preview(daily_dir=daily, delivery_day=date(2026, 6, 11)) is None
    preview = load_latest_daily_preview(
        daily_dir=daily, delivery_day=date(2026, 6, 11), allow_draft=True
    )
    assert preview is not None


def test_load_latest_prefers_approved_over_newer_draft(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-09.md").write_text(
        SAMPLE_APPROVED.replace("2026-06-10", "2026-06-09").replace("かつお節", "承認済み"),
        encoding="utf-8",
    )
    (daily / "2026-06-10.md").write_text(SAMPLE, encoding="utf-8")
    preview = load_latest_daily_preview(daily_dir=daily, delivery_day=date(2026, 6, 11))
    assert preview is not None
    assert preview.business_day == date(2026, 6, 9)
    assert "承認済み" in preview.one_liner


def test_preview_for_fake_door_fallback():
    data = preview_for_fake_door("ja")
    if data["has_preview"]:
        assert data["headline"]
        assert data["subline"]
        assert data["teaser"]
        assert len(data["teaser"]) <= 90
    else:
        assert "準備中" in data["headline"]


SAMPLE_MECHANICAL = """---
status: draft
business_day: "2026-06-10"
generator: mechanical
teaser: "ニュース首位の短いリード。"
preview_lead: "ニュース首位の話題が一日を通して上位に。"
snapshot_slots_included: ["07", "13", "19", "01"]
---

# 日次サマリー — 2026-06-10（JST）

## 📈 昨日いちばん動いた3つ

1. [Topic](https://example.com)（Source）
"""


def test_load_mechanical_uses_preview_lead_when_no_body_one_liner(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-10.md").write_text(SAMPLE_MECHANICAL, encoding="utf-8")
    preview = load_latest_daily_preview(
        daily_dir=daily, delivery_day=date(2026, 6, 11), allow_draft=True
    )
    assert preview is not None
    assert "ニュース首位の話題" in preview.one_liner
    assert preview.display_teaser() == "ニュース首位の短いリード。"
