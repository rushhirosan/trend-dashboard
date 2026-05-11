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


def test_build_rollups_missing_and_found(tmp_path, gaws):
    ddir = tmp_path / "daily"
    ddir.mkdir(parents=True)
    (ddir / "2026-05-11.md").write_text(
        "---\nx: 1\n---\n\n## Body\n", encoding="utf-8"
    )
    mon, sun = date(2026, 5, 11), date(2026, 5, 17)
    text, meta = gaws.build_rollups(mon, sun, ddir)
    assert meta["missing_dates"] == [
        d.isoformat() for d in gaws.week_dates(mon)[1:]
    ]
    assert "2026-05-11" in text
    assert "ファイルなし" in text
    assert meta["truncated"] is False
