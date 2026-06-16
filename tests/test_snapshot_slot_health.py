"""snapshot_slot_health のユニットテスト。"""

from datetime import date
from unittest.mock import MagicMock, patch

from services.snapshot_slot_health import (
    find_missing_prior_slots,
    format_prior_slot_gaps,
    format_snapshot_status_for_discord,
    prior_slot_codes,
    slot_has_snapshot,
    slot_needs_recovery,
    write_and_verify_snapshot,
)


class FakeDb:
    def __init__(self, counts: dict[tuple[date, str], int] | None = None):
        self.counts = counts or {}

    def count_trend_daily_snapshot_rows(self, business_day: date, slot: str) -> int:
        return self.counts.get((business_day, slot), 0)


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


def test_slot_has_snapshot_and_needs_recovery():
    bd = date(2026, 6, 12)
    db = FakeDb({(bd, "07"): 0, (bd, "13"): 5})
    assert slot_has_snapshot(db, bd, "07") is False
    assert slot_has_snapshot(db, bd, "13") is True
    assert slot_needs_recovery(db, "7am_2026-06-12") is True
    assert slot_needs_recovery(db, "1pm_2026-06-12") is False
    assert slot_needs_recovery(db, "invalid") is False


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
