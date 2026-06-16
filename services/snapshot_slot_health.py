"""trend_daily_snapshots のスロット健全性チェック（欠損検知・保存後検証）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from services.trend_snapshot_service import parse_scheduler_slot_key

SLOT_ORDER = ("07", "13", "19", "01")


def prior_slot_codes(slot_code: str) -> List[str]:
    """同一 business_day 内で、slot_code より前のスロットコード。"""
    if slot_code not in SLOT_ORDER:
        return []
    idx = SLOT_ORDER.index(slot_code)
    return list(SLOT_ORDER[:idx])


def count_snapshot_rows(db: Any, business_day: date, slot_code: str) -> int:
    if db is None:
        return 0
    if hasattr(db, "count_trend_daily_snapshot_rows"):
        try:
            return int(db.count_trend_daily_snapshot_rows(business_day, slot_code))
        except Exception:
            pass
    if not hasattr(db, "get_trend_daily_snapshots_for_business_day"):
        return 0
    try:
        rows = db.get_trend_daily_snapshots_for_business_day(business_day) or []
    except Exception:
        return 0
    return sum(1 for r in rows if str(r.get("slot") or "") == slot_code)


def slot_has_snapshot(db: Any, business_day: date, slot_code: str) -> bool:
    return count_snapshot_rows(db, business_day, slot_code) > 0


def find_missing_prior_slots(
    db: Any,
    business_day: date,
    current_slot_code: str,
) -> List[str]:
    """current_slot より前のスロットで DB 行が 0 のもの。"""
    missing: List[str] = []
    for code in prior_slot_codes(current_slot_code):
        if not slot_has_snapshot(db, business_day, code):
            missing.append(code)
    return missing


def format_prior_slot_gaps(missing: List[str], business_day: date) -> str:
    if not missing:
        return ""
    labels = ", ".join(f"{c}時" for c in missing)
    return f"⚠️ {business_day.isoformat()} の未保存スロット: {labels}"


def parse_slot_key(slot_key: str) -> Optional[Tuple[date, str]]:
    parsed = parse_scheduler_slot_key(slot_key)
    if not parsed:
        return None
    return parsed


def slot_needs_recovery(
    db: Any,
    slot_key: str,
    *,
    require_completed: bool = False,
) -> bool:
    """スナップショット行が無い、または（任意で）スロット未完了なら復旧対象。"""
    parsed = parse_slot_key(slot_key)
    if not parsed:
        return False
    business_day, slot_code = parsed
    if slot_has_snapshot(db, business_day, slot_code):
        return False
    if require_completed and db and hasattr(db, "has_slot_completed"):
        if not db.has_slot_completed(slot_key):
            return False
    return True


def write_and_verify_snapshot(
    managers: Dict[str, Any],
    db: Any,
    scheduler_slot_key: Optional[str],
    trigger_source: str,
    captured_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """スナップショット保存 + DB 読み戻し検証。"""
    from services.trend_snapshot_service import write_snapshots_for_scheduler_run

    empty: Dict[str, Any] = {
        "write_ok": False,
        "verified_ok": False,
        "row_count": 0,
        "business_day": "",
        "slot": "",
        "scheduler_slot_key": scheduler_slot_key or "",
    }
    if not scheduler_slot_key:
        return empty
    parsed = parse_slot_key(scheduler_slot_key)
    if not parsed:
        return empty
    business_day, slot_code = parsed
    write_ok = write_snapshots_for_scheduler_run(
        managers=managers,
        scheduler_slot_key=scheduler_slot_key,
        trigger_source=trigger_source,
        captured_at=captured_at,
    )
    row_count = count_snapshot_rows(db, business_day, slot_code)
    verified_ok = bool(write_ok and row_count > 0)
    return {
        "write_ok": bool(write_ok),
        "verified_ok": verified_ok,
        "row_count": row_count,
        "business_day": business_day.isoformat(),
        "slot": slot_code,
        "scheduler_slot_key": scheduler_slot_key,
    }


def format_snapshot_status_for_discord(status: Optional[Dict[str, Any]]) -> str:
    if not status or not status.get("scheduler_slot_key"):
        return "（対象スロットなし）"
    if status.get("verified_ok"):
        return (
            f"OK · {status.get('business_day')} · slot {status.get('slot')} · "
            f"{status.get('row_count')} series"
        )
    row_count = status.get("row_count", 0)
    write_ok = status.get("write_ok")
    return (
        f"NG · {status.get('business_day')} · slot {status.get('slot')} · "
        f"DB {row_count}行 · write={'OK' if write_ok else '失敗'}"
    )
