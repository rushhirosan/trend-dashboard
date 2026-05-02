"""business_day / slot パースの単体テスト"""

from datetime import date

from services.trend_snapshot_service import parse_scheduler_slot_key


def test_parse_7am_same_calendar_day():
    bd, slot = parse_scheduler_slot_key("7am_2026-05-02")
    assert slot == "07"
    assert bd == date(2026, 5, 2)


def test_parse_1am_closes_previous_business_day():
    bd, slot = parse_scheduler_slot_key("1am_2026-05-03")
    assert slot == "01"
    assert bd == date(2026, 5, 2)


def test_parse_1pm():
    bd, slot = parse_scheduler_slot_key("1pm_2026-05-02")
    assert slot == "13"
    assert bd == date(2026, 5, 2)


def test_parse_7pm():
    bd, slot = parse_scheduler_slot_key("7pm_2026-05-02")
    assert slot == "19"
    assert bd == date(2026, 5, 2)


def test_parse_invalid():
    assert parse_scheduler_slot_key(None) is None
    assert parse_scheduler_slot_key("") is None
    assert parse_scheduler_slot_key("bad") is None
