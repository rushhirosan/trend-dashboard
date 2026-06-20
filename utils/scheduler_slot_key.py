"""スケジューラ slot_key の解決（OOM 回収・サーキットブレーカー用）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

from utils.scheduler_lock import scheduler_lock_holder_unix_ts

# (cron hour JST, slot name)
SCHEDULED_SLOTS = (
    (1, "1am"),
    (7, "7am"),
    (13, "1pm"),
    (19, "7pm"),
)

DEFAULT_MISFIRE_GRACE_SECONDS = 3600


def slot_key_for_datetime(now_jst: datetime) -> Optional[str]:
    """現在時刻が属するスロットのキー（例: 1pm_2026-06-20）。該当しなければ None。"""
    date_str = now_jst.date().isoformat()
    h = now_jst.hour
    if 0 <= h < 2:
        return f"1am_{date_str}"
    if 6 <= h < 8:
        return f"7am_{date_str}"
    if 12 <= h < 14:
        return f"1pm_{date_str}"
    if 18 <= h < 20:
        return f"7pm_{date_str}"
    return None


def incomplete_slot_within_grace(
    now_jst: datetime,
    *,
    misfire_grace_seconds: int = DEFAULT_MISFIRE_GRACE_SECONDS,
    job_timeout_seconds: int = 5100,
    is_slot_completed: Callable[[str], bool] | None = None,
) -> Optional[str]:
    """misfire + ジョブ上限内で未完了のスロットがあればその slot_key を返す。"""
    today = now_jst.date()
    for hour, name in SCHEDULED_SLOTS:
        slot_key = f"{name}_{today.isoformat()}"
        scheduled = now_jst.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now_jst < scheduled:
            continue
        grace_end = scheduled + timedelta(seconds=misfire_grace_seconds + job_timeout_seconds)
        if now_jst > grace_end:
            continue
        if is_slot_completed and is_slot_completed(slot_key):
            continue
        return slot_key
    return None


def resolve_scheduler_slot_key(
    now_jst: datetime,
    stale_holder_id: Optional[str] = None,
    *,
    misfire_grace_seconds: int = DEFAULT_MISFIRE_GRACE_SECONDS,
    job_timeout_seconds: int = 5100,
    is_slot_completed: Callable[[str], bool] | None = None,
) -> Optional[str]:
    """OOM 回収・サーキット判定用。時刻ウィンドウ外でも進行中スロットを特定する。"""
    slot = slot_key_for_datetime(now_jst)
    if slot:
        return slot
    if stale_holder_id:
        ts = scheduler_lock_holder_unix_ts(stale_holder_id)
        if ts is not None:
            holder_dt = datetime.fromtimestamp(ts, tz=now_jst.tzinfo)
            slot = slot_key_for_datetime(holder_dt)
            if slot:
                return slot
    return incomplete_slot_within_grace(
        now_jst,
        misfire_grace_seconds=misfire_grace_seconds,
        job_timeout_seconds=job_timeout_seconds,
        is_slot_completed=is_slot_completed,
    )
