"""スケジューラ slot_key 解決（OOM 回収・サーキットブレーカー）のテスト。"""

from datetime import datetime

import pytz

from utils.scheduler_slot_key import (
    incomplete_slot_within_grace,
    resolve_scheduler_slot_key,
    slot_key_for_datetime,
)


def test_slot_key_for_datetime_1pm_window():
    jst = pytz.timezone("Asia/Tokyo")
    dt = jst.localize(datetime(2026, 6, 20, 13, 30))
    assert slot_key_for_datetime(dt) == "1pm_2026-06-20"


def test_slot_key_for_datetime_outside_window():
    jst = pytz.timezone("Asia/Tokyo")
    dt = jst.localize(datetime(2026, 6, 20, 14, 11))
    assert slot_key_for_datetime(dt) is None


def test_incomplete_slot_within_grace_after_1pm_window():
    jst = pytz.timezone("Asia/Tokyo")
    dt = jst.localize(datetime(2026, 6, 20, 14, 11))
    slot = incomplete_slot_within_grace(dt, is_slot_completed=lambda _: False)
    assert slot == "1pm_2026-06-20"


def test_incomplete_slot_skips_completed():
    jst = pytz.timezone("Asia/Tokyo")
    dt = jst.localize(datetime(2026, 6, 20, 14, 11))

    def completed(key):
        return key == "1pm_2026-06-20"

    assert incomplete_slot_within_grace(dt, is_slot_completed=completed) is None


def test_resolve_from_stale_holder_timestamp():
    jst = pytz.timezone("Asia/Tokyo")
    # 14:11 JST だが holder は 13:47 取得 → 1pm スロット
    now = jst.localize(datetime(2026, 6, 20, 14, 11))
    holder_ts = int(jst.localize(datetime(2026, 6, 20, 13, 47)).timestamp())
    holder = f"e82d4d4a44e758-647-{holder_ts}"
    slot = resolve_scheduler_slot_key(now, holder, is_slot_completed=lambda _: False)
    assert slot == "1pm_2026-06-20"


def test_resolve_scheduler_slot_key_after_window_no_holder():
    jst = pytz.timezone("Asia/Tokyo")
    dt = jst.localize(datetime(2026, 6, 20, 14, 35))
    slot = resolve_scheduler_slot_key(dt, is_slot_completed=lambda _: False)
    assert slot == "1pm_2026-06-20"
