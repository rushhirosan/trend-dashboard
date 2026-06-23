"""snapshot_slot_health のユニットテスト。"""

from datetime import date, datetime
from unittest.mock import patch

import pytz

from services.snapshot_slot_health import (
    check_captured_at_in_slot_window,
    find_missing_prior_slots,
    format_prior_slot_gaps,
    format_snapshot_status_for_discord,
    iter_scheduled_slots_for_business_day,
    mark_slot_fully_done,
    prior_slot_codes,
    refresh_succeeded_for_snapshot,
    slot_has_snapshot,
    slot_is_fully_done,
    slot_key_for,
    slot_needs_recovery,
    snapshot_verified_slot_key,
    write_and_verify_snapshot,
)

JST = pytz.timezone("Asia/Tokyo")


class FakeDb:
    def __init__(
        self,
        counts: dict[tuple[date, str], int] | None = None,
        completed: set[str] | None = None,
    ):
        self.counts = counts or {}
        self.completed = completed or set()

    def count_trend_daily_snapshot_rows(self, business_day: date, slot: str) -> int:
        return self.counts.get((business_day, slot), 0)

    def has_slot_completed(self, slot_key: str) -> bool:
        return slot_key in self.completed

    def mark_slot_completed(self, slot_key: str) -> None:
        self.completed.add(slot_key)


def test_prior_slot_codes():
    assert prior_slot_codes("07") == []
    assert prior_slot_codes("13") == ["07"]
    assert prior_slot_codes("19") == ["07", "13"]
    assert prior_slot_codes("01") == ["07", "13", "19"]
    assert prior_slot_codes("99") == []


def test_find_missing_prior_slots():
    bd = date(2026, 6, 12)
    db = FakeDb(
        {
            (bd, "07"): 0,
            (bd, "13"): 70,
            (bd, "19"): 70,
        }
    )
    assert find_missing_prior_slots(db, bd, "13") == ["07"]
    assert find_missing_prior_slots(db, bd, "19") == ["07"]
    assert find_missing_prior_slots(db, bd, "01") == ["07"]


def test_format_prior_slot_gaps():
    bd = date(2026, 6, 12)
    assert format_prior_slot_gaps([], bd) == ""
    assert "07時" in format_prior_slot_gaps(["07"], bd)
    assert "2026-06-12" in format_prior_slot_gaps(["07", "13"], bd)


def test_format_snapshot_status_for_discord():
    assert format_snapshot_status_for_discord(None) == "（対象スロットなし）"
    assert format_snapshot_status_for_discord({}) == "（対象スロットなし）"
    ok = format_snapshot_status_for_discord(
        {
            "scheduler_slot_key": "7am_2026-06-12",
            "verified_ok": True,
            "business_day": "2026-06-12",
            "slot": "07",
            "row_count": 70,
        }
    )
    assert ok.startswith("OK ·")
    ng = format_snapshot_status_for_discord(
        {
            "scheduler_slot_key": "7am_2026-06-12",
            "verified_ok": False,
            "write_ok": False,
            "business_day": "2026-06-12",
            "slot": "07",
            "row_count": 0,
        }
    )
    assert ng.startswith("NG ·")
    assert "失敗" in ng


def test_slot_key_for_and_iter():
    bd = date(2026, 6, 20)
    assert slot_key_for(bd, "07") == "7am_2026-06-20"
    assert slot_key_for(bd, "01") == "1am_2026-06-21"
    keys = [k for _, k in iter_scheduled_slots_for_business_day(bd)]
    assert keys == [
        "7am_2026-06-20",
        "1pm_2026-06-20",
        "7pm_2026-06-20",
        "1am_2026-06-21",
    ]


def test_check_captured_at_in_slot_window():
    bd = date(2026, 6, 20)
    ok_time = JST.localize(datetime(2026, 6, 20, 13, 12))
    assert check_captured_at_in_slot_window(ok_time, bd, "13") == (True, "")
    bad_time = JST.localize(datetime(2026, 6, 20, 16, 2))
    ok, msg = check_captured_at_in_slot_window(bad_time, bd, "13")
    assert ok is False
    assert "期待帯" in msg


def test_format_snapshot_status_captured_at_warning():
    warn = format_snapshot_status_for_discord(
        {
            "scheduler_slot_key": "1pm_2026-06-20",
            "verified_ok": True,
            "captured_at_ok": False,
            "captured_at_warning": "時刻帯外",
            "business_day": "2026-06-20",
            "slot": "13",
            "row_count": 70,
        }
    )
    assert warn.startswith("⚠️ 時刻帯外")


def test_slot_has_snapshot_and_needs_recovery():
    bd = date(2026, 6, 12)
    db = FakeDb({(bd, "07"): 0, (bd, "13"): 5}, completed={"1pm_2026-06-12"})
    assert slot_has_snapshot(db, bd, "07") is False
    assert slot_has_snapshot(db, bd, "13") is True
    assert slot_needs_recovery(db, "7am_2026-06-12") is True
    # 旧仕様: 完了マークのみ（snap_verified なし）→ 未完了扱い
    assert slot_needs_recovery(db, "1pm_2026-06-12") is True
    assert slot_needs_recovery(db, "invalid") is False


def test_slot_is_fully_done():
    bd = date(2026, 6, 12)
    sk = "1pm_2026-06-12"
    db = FakeDb(
        {(bd, "13"): 70},
        completed={sk, snapshot_verified_slot_key(sk)},
    )
    assert slot_is_fully_done(db, sk) is True
    assert slot_needs_recovery(db, sk) is False


def test_mark_slot_fully_done():
    db = FakeDb()
    mark_slot_fully_done(db, "7am_2026-06-23")
    assert "7am_2026-06-23" in db.completed
    assert snapshot_verified_slot_key("7am_2026-06-23") in db.completed


def test_slot_needs_recovery_when_snapshot_exists_but_slot_incomplete():
    bd = date(2026, 6, 23)
    db = FakeDb({(bd, "07"): 70})
    assert slot_needs_recovery(db, "7am_2026-06-23") is True


def test_slot_needs_recovery_legacy_completed_without_snap_verified():
    """取得完了マークのみ（API 旧仕様）+ 古い snapshot 行 → gap_retry 対象。"""
    bd = date(2026, 6, 23)
    db = FakeDb({(bd, "07"): 70}, completed={"7am_2026-06-23"})
    assert slot_needs_recovery(db, "7am_2026-06-23") is True


def test_refresh_succeeded_for_snapshot():
    assert refresh_succeeded_for_snapshot({"success": True}) is True
    assert refresh_succeeded_for_snapshot({"success": False, "jp_phase_failed": True}) is False
    assert refresh_succeeded_for_snapshot({"success": False, "job_timed_out": True}) is False
    assert refresh_succeeded_for_snapshot({"success": True, "us_phase_failed": True}) is False


@patch("services.trend_snapshot_service.write_snapshots_for_scheduler_run")
def test_write_and_verify_snapshot(mock_write):
    bd = date(2026, 6, 12)
    db = FakeDb({(bd, "07"): 70})
    mock_write.return_value = True
    status = write_and_verify_snapshot(
        managers={},
        db=db,
        scheduler_slot_key="7am_2026-06-12",
        trigger_source="scheduler",
    )
    assert status["verified_ok"] is True
    assert status["row_count"] == 70
    assert status["slot"] == "07"
    assert "captured_at_ok" in status

    mock_write.return_value = False
    status2 = write_and_verify_snapshot(
        managers={},
        db=db,
        scheduler_slot_key="7am_2026-06-12",
        trigger_source="gap_retry",
    )
    assert status2["verified_ok"] is False
    assert status2["write_ok"] is False

    empty = write_and_verify_snapshot({}, db, None, "scheduler")
    assert empty["verified_ok"] is False
    mock_write.assert_called()


@patch("services.trend_snapshot_service.write_snapshots_for_scheduler_run")
def test_write_and_verify_snapshot_api_trigger(mock_write):
    bd = date(2026, 6, 12)
    db = FakeDb({(bd, "07"): 70})
    mock_write.return_value = True
    status = write_and_verify_snapshot(
        managers={},
        db=db,
        scheduler_slot_key="7am_2026-06-12",
        trigger_source="api",
    )
    assert status["verified_ok"] is True
    assert mock_write.call_args.kwargs["trigger_source"] == "api"
