"""daily_summary_preview のユニットテスト"""

from datetime import date
from pathlib import Path

from services.summary.daily_summary_preview import (
    DailySummaryPreview,
    extract_one_liner,
    load_latest_daily_preview,
    preview_for_fake_door,
)

SAMPLE = """---
status: draft
business_day: "2026-06-10"
generator: openai
snapshot_slots_included: ["07", "13", "19", "01"]
---

# 日次サマリー — 2026-06-10（JST）

## 今日の一行結論

かつお節の話が一日を通して上位に。

## 昨日の見どころ（3〜5）

### 1. 見出し
"""


def test_extract_one_liner():
    assert extract_one_liner(SAMPLE) == "かつお節の話が一日を通して上位に。"


def test_load_latest_from_tmp_dir(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-09.md").write_text(
        SAMPLE.replace("2026-06-10", "2026-06-09").replace("かつお節", "古い話題"),
        encoding="utf-8",
    )
    (daily / "2026-06-10.md").write_text(SAMPLE, encoding="utf-8")
    preview = load_latest_daily_preview(daily_dir=daily, delivery_day=date(2026, 6, 11))
    assert preview is not None
    assert preview.business_day == date(2026, 6, 10)
    assert preview.delivery_day == date(2026, 6, 11)
    assert "かつお節" in preview.one_liner


def test_headline_ja():
    p = DailySummaryPreview(
        business_day=date(2026, 6, 10),
        delivery_day=date(2026, 6, 11),
        one_liner="x",
        snapshot_slots=("07", "13", "19", "01"),
        status="draft",
    )
    assert p.headline_ja() == "6/11 朝刊 — 昨日（6/10）のトレンド"


def test_headline_ja_when_summary_is_stale():
    p = DailySummaryPreview(
        business_day=date(2026, 6, 10),
        delivery_day=date(2026, 6, 12),
        one_liner="x",
        snapshot_slots=("07", "13", "19", "01"),
        status="draft",
    )
    assert p.headline_ja() == "6/12 朝刊 — 6/10のトレンド"


def test_preview_for_fake_door_fallback():
    data = preview_for_fake_door("ja")
    if data["has_preview"]:
        assert data["headline"]
        assert data["one_liner"]
    else:
        assert "準備中" in data["headline"]
