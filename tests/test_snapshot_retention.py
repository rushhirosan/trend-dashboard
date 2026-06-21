"""snapshot_retention のユニットテスト"""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from services.snapshot_retention import (
    DEFAULT_RETENTION_DAYS,
    collect_expired_summary_files,
    daily_summary_cutoff_business_day,
    purge_expired_snapshots,
    purge_expired_summary_files,
    retention_days,
    retention_enabled,
    snapshot_cutoff_business_day,
    scheduler_slot_cutoff,
    weekly_summary_cutoff,
    weekly_summary_retention_days,
)

JST = ZoneInfo("Asia/Tokyo")


def test_snapshot_cutoff_business_day():
    cutoff = snapshot_cutoff_business_day(
        today=date(2026, 6, 22),
        days=10,
    )
    assert cutoff == date(2026, 6, 12)


def test_daily_summary_cutoff_matches_snapshot_default():
    cutoff = daily_summary_cutoff_business_day(
        today=date(2026, 6, 22),
        days=10,
    )
    assert cutoff == date(2026, 6, 12)


def test_weekly_summary_cutoff():
    cutoff = weekly_summary_cutoff(today=date(2026, 6, 22), days=30)
    assert cutoff == date(2026, 5, 23)


@patch.dict("os.environ", {"SUMMARY_WEEKLY_RETENTION_DAYS": "30"}, clear=False)
def test_weekly_summary_retention_days():
    assert weekly_summary_retention_days() == 30


def test_scheduler_slot_cutoff():
    now = datetime(2026, 6, 22, 15, 0, tzinfo=JST)
    cutoff = scheduler_slot_cutoff(now=now, days=10)
    assert cutoff.date() == date(2026, 6, 12)


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_DAYS": "10"}, clear=False)
def test_retention_days_default_env():
    assert retention_days() == 10


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_DAYS": "3"}, clear=False)
def test_retention_days_clamped_to_min():
    assert retention_days() == 7


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_DAYS": "999"}, clear=False)
def test_retention_days_clamped_to_max():
    assert retention_days() == 90


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_ENABLED": "false"}, clear=False)
def test_purge_skipped_when_disabled():
    db = MagicMock()
    result = purge_expired_snapshots(db=db)
    assert result["enabled"] is False
    assert result["snapshots_deleted"] == 0
    db.purge_trend_daily_snapshots_older_than.assert_not_called()


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_ENABLED": "true"}, clear=False)
def test_purge_dry_run_counts_only():
    db = MagicMock()
    db.count_trend_daily_snapshots_older_than.return_value = 100
    db.count_scheduler_slot_run_older_than.return_value = 5
    result = purge_expired_snapshots(
        db=db,
        days=DEFAULT_RETENTION_DAYS,
        dry_run=True,
        purge_summary_files=False,
    )
    assert result["dry_run"] is True
    assert result["snapshots_deleted"] == 100
    assert result["scheduler_rows_deleted"] == 5
    db.purge_trend_daily_snapshots_older_than.assert_not_called()


@patch.dict("os.environ", {"TREND_SNAPSHOT_RETENTION_ENABLED": "true"}, clear=False)
def test_purge_deletes_when_enabled():
    db = MagicMock()
    db.purge_trend_daily_snapshots_older_than.return_value = 42
    db.purge_scheduler_slot_run_older_than.return_value = 3
    result = purge_expired_snapshots(
        db=db, days=10, dry_run=False, purge_summary_files=False
    )
    assert result["ok"] is True
    assert result["snapshots_deleted"] == 42
    assert result["scheduler_rows_deleted"] == 3
    db.purge_trend_daily_snapshots_older_than.assert_called_once()
    db.purge_scheduler_slot_run_older_than.assert_called_once()


@patch.dict("os.environ", {}, clear=True)
def test_retention_enabled_defaults_true():
    assert retention_enabled() is True


def test_collect_expired_summary_files(tmp_path: Path):
    daily = tmp_path / "daily"
    weekly = tmp_path / "weekly"
    daily.mkdir()
    weekly.mkdir()

    (daily / "2026-06-01.md").write_text("old", encoding="utf-8")
    (daily / "2026-06-01.generation.json").write_text("{}", encoding="utf-8")
    (daily / "2026-06-20.md").write_text("keep", encoding="utf-8")
    (daily / "README.md").write_text("docs", encoding="utf-8")
    (weekly / "2026-W10.md").write_text("old week", encoding="utf-8")
    (weekly / "2026-W24.md").write_text("keep week", encoding="utf-8")

    expired_daily, expired_weekly = collect_expired_summary_files(
        tmp_path,
        today=date(2026, 6, 22),
        daily_days=10,
        weekly_days=30,
    )

    assert {p.name for p in expired_daily} == {
        "2026-06-01.md",
        "2026-06-01.generation.json",
    }
    assert {p.name for p in expired_weekly} == {"2026-W10.md"}


def test_purge_expired_summary_files_deletes(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-06-01.md").write_text("old", encoding="utf-8")
    (daily / "2026-06-20.md").write_text("keep", encoding="utf-8")

    result = purge_expired_summary_files(
        tmp_path,
        today=date(2026, 6, 22),
        daily_days=10,
        weekly_days=30,
        dry_run=False,
    )

    assert result["daily_summary_files_deleted"] == 1
    assert not (daily / "2026-06-01.md").exists()
    assert (daily / "2026-06-20.md").exists()
